"""Durable bookkeeping for native supervisor messages, not PAEOS runtime state."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

_SCHEMA = "paeos.native-coordination-cache/1"
_IDENTIFIER = re.compile(r"\S{1,160}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SendOutcome = Literal["SENT", "UNKNOWN"]
AssignmentDisposition = Literal["HELD", "COMPLETED"]
LegacyDisposition = Literal["NOT_SENT_CONFIRMED", "HELD", "COMPLETED"]
_ACTIVE_STATES = {"PENDING_SEND", "UNKNOWN", "SENT", "TURN_STARTED", "ACTIVE"}


class CoordinationError(RuntimeError):
    """Base error for invalid local coordination-cache operations."""


class DuplicateIdentityError(CoordinationError):
    """An assignment or event ID was already used for a different effect."""


class InvalidTransitionError(CoordinationError):
    """A send, reconciliation, or callback transition is not eligible."""


class NonAuthoritativeStateError(CoordinationError):
    """The helper refuses to read or modify a state marked runtime-canonical."""


class CoordinationCache:
    """Atomically update a native coordination cache with stable identities.

    The cache is deliberately non-authoritative. It may record send intent,
    delivery uncertainty, and callbacks, but never represents PAEOS admission,
    worker execution, Court disposition, or qualification.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    @contextmanager
    def _file_lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": _SCHEMA,
                "canonical_authority": False,
                "processed_events": {},
                "assignments": {},
            }

        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CoordinationError(f"cannot read coordination cache: {self.path}") from exc
        if not isinstance(state, dict):
            raise CoordinationError("coordination cache must contain a JSON object")
        if state.get("canonical_authority") is True:
            raise NonAuthoritativeStateError(
                "native coordination helper cannot modify runtime-canonical state"
            )
        if state.get("canonical_authority") is not False:
            raise NonAuthoritativeStateError(
                "cache authority is implicit; explicit migration is required"
            )
        if state.get("schema") != _SCHEMA:
            raise NonAuthoritativeStateError(
                "cache schema is not recognized; explicit migration is required"
            )
        if "processed_events" not in state or "assignments" not in state:
            raise CoordinationError("cache requires explicit processed_events and assignments maps")
        if not isinstance(state["processed_events"], dict):
            raise CoordinationError("processed_events must be a JSON object")
        if not isinstance(state["assignments"], dict):
            raise CoordinationError("assignments must be a JSON object")
        return state

    def _write_unlocked(self, state: dict[str, Any]) -> None:
        if state.get("canonical_authority") is True:
            raise NonAuthoritativeStateError(
                "native coordination helper cannot write runtime-canonical state"
            )
        if state.get("canonical_authority") is not False or state.get("schema") != _SCHEMA:
            raise NonAuthoritativeStateError(
                "cache authority/schema changed; explicit migration is required"
            )
        encoded = (json.dumps(state, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as temporary:
                temporary.write(encoded)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)

    def snapshot(self) -> dict[str, Any]:
        """Return an isolated copy of the cache under the shared file lock."""

        with self._file_lock():
            return deepcopy(self._read_unlocked())

    def record_assignment_intent(
        self,
        *,
        assignment_id: str,
        owner_thread_id: str,
        event_id: str,
        intent_sha256: str,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        """Persist a send intent before the native messaging tool is called."""

        assignment_id = _identifier(assignment_id, "assignment_id")
        owner_thread_id = _identifier(owner_thread_id, "owner_thread_id")
        event_id = _identifier(event_id, "event_id")
        intent_sha256 = _sha256(intent_sha256, "intent_sha256")
        timestamp = _timestamp(created_at)

        with self._file_lock():
            state = self._read_unlocked()
            if assignment_id in state["assignments"] or _event_exists(state, event_id):
                raise DuplicateIdentityError("assignment_id and event_id must be stable and unique")
            if _owner_has_open_assignment(state, owner_thread_id):
                raise InvalidTransitionError(
                    "owner already has an active, pending, or uncertain assignment"
                )
            attempt_id = f"{assignment_id}:send:1"
            assignment = {
                "assignment_id": assignment_id,
                "owner_thread_id": owner_thread_id,
                "state": "PENDING_SEND",
                "callback_state": "EXPECTED",
                "actual_turn_starts": [],
                "created_at": timestamp,
                "attempts": [
                    {
                        "attempt_id": attempt_id,
                        "event_id": event_id,
                        "state": "PENDING_SEND",
                        "intent_sha256": intent_sha256,
                        "created_at": timestamp,
                    }
                ],
            }
            state["assignments"][assignment_id] = assignment
            self._write_unlocked(state)
            return deepcopy(assignment)

    def record_send_outcome(
        self,
        *,
        assignment_id: str,
        outcome: SendOutcome,
        result_sha256: str,
        recorded_at: str | None = None,
    ) -> dict[str, Any]:
        """Record the actual tool result after a previously persisted intent."""

        if outcome not in {"SENT", "UNKNOWN"}:
            raise InvalidTransitionError("send outcome must be SENT or UNKNOWN")
        result_sha256 = _sha256(result_sha256, "result_sha256")
        timestamp = _timestamp(recorded_at)

        with self._file_lock():
            state = self._read_unlocked()
            assignment = _assignment(state, assignment_id)
            attempt = assignment["attempts"][-1]
            prior_evidence_proves_send = (
                assignment["callback_state"] == "RECEIVED"
                or bool(assignment.get("actual_turn_starts"))
                or (attempt["state"] == "SENT" and "result_sha256" not in attempt)
            )
            if prior_evidence_proves_send:
                if outcome != "SENT":
                    raise InvalidTransitionError(
                        "callback or actual turn start already proves the send was delivered"
                    )
                if attempt["state"] != "SENT" or "result_sha256" in attempt:
                    raise InvalidTransitionError("the send attempt already has a tool outcome")
                attempt.update({"result_sha256": result_sha256, "result_at": timestamp})
                assignment["state"] = "ACTIVE"
                assignment["send_result_at"] = timestamp
                self._write_unlocked(state)
                return deepcopy(assignment)
            if assignment["state"] != "PENDING_SEND" or attempt["state"] != "PENDING_SEND":
                raise InvalidTransitionError("only a pending send may receive a tool outcome")
            attempt.update(
                {"state": outcome, "result_sha256": result_sha256, "result_at": timestamp}
            )
            assignment.update({"state": outcome, "send_result_at": timestamp})
            if outcome == "UNKNOWN":
                assignment["requires_reconciliation"] = True
            self._write_unlocked(state)
            return deepcopy(assignment)

    def reconcile_unknown_send(
        self,
        *,
        assignment_id: str,
        delivered: bool,
        evidence: Mapping[str, Any],
        reconciled_at: str | None = None,
    ) -> dict[str, Any]:
        """Resolve an UNKNOWN only with explicit, nonempty inspection evidence."""

        if not isinstance(delivered, bool) or not isinstance(evidence, Mapping) or not evidence:
            raise InvalidTransitionError(
                "UNKNOWN reconciliation requires an observed result and evidence"
            )
        timestamp = _timestamp(reconciled_at)
        evidence_digest = _json_sha256(dict(evidence))

        with self._file_lock():
            state = self._read_unlocked()
            assignment = _assignment(state, assignment_id)
            attempt = assignment["attempts"][-1]
            if assignment["state"] != "UNKNOWN" or attempt["state"] != "UNKNOWN":
                raise InvalidTransitionError("only an UNKNOWN send can be reconciled")
            if not delivered and (
                assignment.get("callback_state") == "RECEIVED"
                or assignment.get("actual_turn_starts")
            ):
                raise InvalidTransitionError(
                    "callback or actual turn start contradicts a non-delivery finding"
                )
            outcome = "SENT" if delivered else "NOT_SENT_CONFIRMED"
            attempt.update(
                {
                    "state": outcome,
                    "reconciled_at": timestamp,
                    "reconciliation_evidence_sha256": evidence_digest,
                }
            )
            assignment.update(
                {
                    "state": outcome,
                    "reconciled_at": timestamp,
                    "reconciliation_evidence_sha256": evidence_digest,
                    "requires_reconciliation": False,
                }
            )
            self._write_unlocked(state)
            return deepcopy(assignment)

    def begin_retry(
        self,
        *,
        assignment_id: str,
        event_id: str,
        intent_sha256: str,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        """Create a new send attempt only after non-delivery was confirmed."""

        event_id = _identifier(event_id, "event_id")
        intent_sha256 = _sha256(intent_sha256, "intent_sha256")
        timestamp = _timestamp(created_at)

        with self._file_lock():
            state = self._read_unlocked()
            assignment = _assignment(state, assignment_id)
            if assignment["state"] != "NOT_SENT_CONFIRMED":
                raise InvalidTransitionError(
                    "retry requires a reconciled NOT_SENT_CONFIRMED result"
                )
            if _event_exists(state, event_id):
                raise DuplicateIdentityError("retry event_id has already been used")
            attempt_number = len(assignment["attempts"]) + 1
            attempt = {
                "attempt_id": f"{assignment_id}:send:{attempt_number}",
                "event_id": event_id,
                "state": "PENDING_SEND",
                "intent_sha256": intent_sha256,
                "created_at": timestamp,
            }
            assignment["attempts"].append(attempt)
            assignment.update({"state": "PENDING_SEND", "created_at": timestamp})
            assignment.pop("requires_reconciliation", None)
            self._write_unlocked(state)
            return deepcopy(assignment)

    def record_callback(
        self,
        *,
        event_id: str,
        assignment_id: str,
        origin_thread: str,
        source_turn_id: str,
        payload_sha256: str,
        received_at: str | None = None,
    ) -> bool:
        """Record one owner callback and its actual native source turn."""

        event_id = _identifier(event_id, "event_id")
        assignment_id = _identifier(assignment_id, "assignment_id")
        origin_thread = _identifier(origin_thread, "origin_thread")
        source_turn_id = _identifier(source_turn_id, "source_turn_id")
        payload_sha256 = _sha256(payload_sha256, "payload_sha256")
        timestamp = _timestamp(received_at)

        with self._file_lock():
            state = self._read_unlocked()
            existing = state["processed_events"].get(event_id)
            if existing is not None:
                if (
                    existing.get("assignment_id") == assignment_id
                    and existing.get("origin_thread") == origin_thread
                    and existing.get("source_turn_id") == source_turn_id
                    and existing.get("payload_sha256") == payload_sha256
                ):
                    return False
                raise DuplicateIdentityError("event_id collision has conflicting callback evidence")
            assignment = _assignment(state, assignment_id)
            if assignment["owner_thread_id"] != origin_thread:
                raise InvalidTransitionError("callback origin does not match the assigned owner")
            if assignment["state"] not in _ACTIVE_STATES:
                raise InvalidTransitionError("callback is incompatible with the send state")
            if _turn_id_exists(state, source_turn_id, excluding_assignment=assignment_id):
                raise DuplicateIdentityError("source_turn_id already belongs to another assignment")
            if not any(
                start.get("recipient_turn_id") == source_turn_id
                for start in assignment.get("actual_turn_starts", [])
            ):
                assignment.setdefault("actual_turn_starts", []).append(
                    {
                        "recipient_turn_id": source_turn_id,
                        "recipient_status": "completed",
                        "evidence_sha256": payload_sha256,
                        "observed_at": timestamp,
                        "source": "owner_callback",
                    }
                )
                assignment["turn_started_at"] = timestamp
            attempt = assignment["attempts"][-1]
            if attempt["state"] in {"PENDING_SEND", "UNKNOWN"}:
                attempt.update(
                    {
                        "state": "SENT",
                        "delivery_evidence_sha256": payload_sha256,
                        "delivery_evidence_source": "owner_callback",
                    }
                )
                assignment.pop("requires_reconciliation", None)
            assignment["state"] = "ACTIVE"
            state["processed_events"][event_id] = {
                "event_id": event_id,
                "assignment_id": assignment_id,
                "origin_thread": origin_thread,
                "source_turn_id": source_turn_id,
                "payload_sha256": payload_sha256,
                "state": "RECEIVED",
                "received_at": timestamp,
            }
            assignment.update(
                {
                    "callback_state": "RECEIVED",
                    "callback_event_id": event_id,
                    "callback_received_at": timestamp,
                }
            )
            self._write_unlocked(state)
            return True

    def record_turn_start(
        self,
        *,
        assignment_id: str,
        event_id: str,
        recipient_turn_id: str,
        recipient_status: Literal["inProgress", "completed"],
        evidence_sha256: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Record a verified native recipient turn; queued tool receipts are not starts."""

        assignment_id = _identifier(assignment_id, "assignment_id")
        event_id = _identifier(event_id, "event_id")
        recipient_turn_id = _identifier(recipient_turn_id, "recipient_turn_id")
        if recipient_status not in {"inProgress", "completed"}:
            raise InvalidTransitionError(
                "only an observed inProgress or completed turn is execution evidence"
            )
        evidence_sha256 = _sha256(evidence_sha256, "evidence_sha256")
        timestamp = _timestamp(observed_at)

        with self._file_lock():
            state = self._read_unlocked()
            if _event_exists(state, event_id):
                raise DuplicateIdentityError("turn-start event_id has already been used")
            assignment = _assignment(state, assignment_id)
            if assignment["state"] not in _ACTIVE_STATES:
                raise InvalidTransitionError("turn start is incompatible with a closed assignment")
            if _turn_id_exists(state, recipient_turn_id, excluding_assignment=assignment_id):
                raise DuplicateIdentityError(
                    "recipient_turn_id already belongs to another assignment"
                )
            existing_start = next(
                (
                    start
                    for start in assignment.get("actual_turn_starts", [])
                    if start.get("recipient_turn_id") == recipient_turn_id
                ),
                None,
            )
            if existing_start is not None:
                raise DuplicateIdentityError(
                    "recipient_turn_id was already recorded for this assignment"
                )

            assignment.setdefault("actual_turn_starts", []).append(
                {
                    "event_id": event_id,
                    "recipient_turn_id": recipient_turn_id,
                    "recipient_status": recipient_status,
                    "evidence_sha256": evidence_sha256,
                    "observed_at": timestamp,
                    "source": "thread_status_readback",
                }
            )
            attempt = assignment["attempts"][-1]
            if attempt["state"] in {"PENDING_SEND", "UNKNOWN"}:
                attempt.update(
                    {
                        "state": "SENT",
                        "delivery_evidence_sha256": evidence_sha256,
                        "delivery_evidence_source": "recipient_turn_readback",
                    }
                )
                assignment.pop("requires_reconciliation", None)
            assignment.update({"state": "ACTIVE", "turn_started_at": timestamp})
            state["processed_events"][event_id] = {
                "event_id": event_id,
                "assignment_id": assignment_id,
                "recipient_turn_id": recipient_turn_id,
                "recipient_status": recipient_status,
                "evidence_sha256": evidence_sha256,
                "state": "TURN_STARTED",
                "observed_at": timestamp,
            }
            self._write_unlocked(state)
            return deepcopy(assignment)

    def record_assignment_disposition(
        self,
        *,
        assignment_id: str,
        disposition: AssignmentDisposition,
        evidence_sha256: str,
        wake_condition: str | None = None,
        closed_at: str | None = None,
    ) -> dict[str, Any]:
        """Close an owner slot only after an evidence-backed completion or hold."""

        if disposition not in {"HELD", "COMPLETED"}:
            raise InvalidTransitionError("unsupported assignment disposition")
        evidence_sha256 = _sha256(evidence_sha256, "evidence_sha256")
        if disposition == "HELD" and not wake_condition:
            raise InvalidTransitionError("HELD disposition requires an exact wake condition")
        timestamp = _timestamp(closed_at)

        with self._file_lock():
            state = self._read_unlocked()
            assignment = _assignment(state, assignment_id)
            if assignment["state"] not in _ACTIVE_STATES:
                raise InvalidTransitionError("only an open assignment may be closed")
            if assignment.get("callback_state") != "RECEIVED":
                raise InvalidTransitionError(
                    "assignment disposition requires the owner's material callback or handoff acknowledgement"
                )
            assignment.update(
                {
                    "state": disposition,
                    "closed_at": timestamp,
                    "disposition_evidence_sha256": evidence_sha256,
                }
            )
            if wake_condition is not None:
                assignment["wake_condition"] = wake_condition
            self._write_unlocked(state)
            return deepcopy(assignment)

    def reconcile_legacy_assignment(
        self,
        *,
        assignment_id: str,
        owner_thread_id: str,
        event_id: str,
        disposition: LegacyDisposition,
        evidence_sha256: str,
        wake_condition: str | None = None,
        reconciled_at: str | None = None,
    ) -> dict[str, Any]:
        """Append an explicit closeout for a legacy entry without rewriting its history."""

        assignment_id = _identifier(assignment_id, "assignment_id")
        owner_thread_id = _identifier(owner_thread_id, "owner_thread_id")
        event_id = _identifier(event_id, "event_id")
        if disposition not in {"NOT_SENT_CONFIRMED", "HELD", "COMPLETED"}:
            raise InvalidTransitionError("unsupported legacy reconciliation disposition")
        evidence_sha256 = _sha256(evidence_sha256, "evidence_sha256")
        if disposition == "HELD" and not wake_condition:
            raise InvalidTransitionError(
                "HELD legacy reconciliation requires an exact wake condition"
            )
        timestamp = _timestamp(reconciled_at)

        with self._file_lock():
            state = self._read_unlocked()
            if _event_exists(state, event_id):
                raise DuplicateIdentityError("legacy reconciliation event_id has already been used")
            assignment = _assignment(state, assignment_id)
            recorded_owner = assignment.get(
                "owner_thread_id", assignment.get("owner_thread", assignment.get("target_thread"))
            )
            if recorded_owner != owner_thread_id:
                raise InvalidTransitionError(
                    "legacy reconciliation owner does not match the saved entry"
                )
            if disposition == "NOT_SENT_CONFIRMED" and assignment.get("state") not in {
                "UNKNOWN",
                "PENDING_SEND",
            }:
                raise InvalidTransitionError(
                    "NOT_SENT_CONFIRMED conflicts with the saved legacy send outcome"
                )
            if "coordinator_reconciliation" in assignment:
                raise InvalidTransitionError(
                    "legacy assignment already has an explicit reconciliation"
                )
            reconciliation = {
                "event_id": event_id,
                "owner_thread_id": owner_thread_id,
                "disposition": disposition,
                "evidence_sha256": evidence_sha256,
                "reconciled_at": timestamp,
            }
            if wake_condition is not None:
                reconciliation["wake_condition"] = wake_condition
            assignment["coordinator_reconciliation"] = reconciliation
            state["processed_events"][event_id] = {
                "event_id": event_id,
                "assignment_id": assignment_id,
                "origin_thread": owner_thread_id,
                "evidence_sha256": evidence_sha256,
                "state": "LEGACY_ASSIGNMENT_RECONCILED",
                "disposition": disposition,
                "received_at": timestamp,
            }
            self._write_unlocked(state)
            return deepcopy(assignment)

    def record_handoff_ack(
        self,
        *,
        assignment_id: str,
        event_id: str,
        origin_thread: str,
        source_turn_id: str,
        payload_sha256: str,
        handoff_summary_sha256: str,
        acknowledged_at: str | None = None,
    ) -> dict[str, Any]:
        """Record the existing owner's explicit stop/handoff acknowledgement."""

        event_id = _identifier(event_id, "event_id")
        assignment_id = _identifier(assignment_id, "assignment_id")
        origin_thread = _identifier(origin_thread, "origin_thread")
        source_turn_id = _identifier(source_turn_id, "source_turn_id")
        payload_sha256 = _sha256(payload_sha256, "payload_sha256")
        handoff_summary_sha256 = _sha256(handoff_summary_sha256, "handoff_summary_sha256")
        timestamp = _timestamp(acknowledged_at)

        with self._file_lock():
            state = self._read_unlocked()
            if _event_exists(state, event_id):
                raise DuplicateIdentityError(
                    "handoff acknowledgement event_id has already been used"
                )
            assignment = _assignment(state, assignment_id)
            if assignment["owner_thread_id"] != origin_thread:
                raise InvalidTransitionError(
                    "handoff acknowledgement origin is not the assigned owner"
                )
            if assignment["state"] not in _ACTIVE_STATES:
                raise InvalidTransitionError(
                    "handoff acknowledgement is incompatible with a closed assignment"
                )
            if _turn_id_exists(state, source_turn_id, excluding_assignment=assignment_id):
                raise DuplicateIdentityError(
                    "handoff source_turn_id already belongs to another assignment"
                )
            if any(
                start.get("recipient_turn_id") == source_turn_id
                for start in assignment.get("actual_turn_starts", [])
            ):
                raise DuplicateIdentityError(
                    "handoff source_turn_id was already recorded for this assignment"
                )
            attempt = assignment["attempts"][-1]
            if attempt["state"] in {"PENDING_SEND", "UNKNOWN"}:
                attempt.update(
                    {
                        "state": "SENT",
                        "delivery_evidence_sha256": payload_sha256,
                        "delivery_evidence_source": "owner_handoff_ack",
                    }
                )
                assignment.pop("requires_reconciliation", None)
            assignment.setdefault("actual_turn_starts", []).append(
                {
                    "recipient_turn_id": source_turn_id,
                    "recipient_status": "completed",
                    "evidence_sha256": payload_sha256,
                    "observed_at": timestamp,
                    "source": "owner_handoff_ack",
                }
            )
            assignment.update(
                {
                    "state": "HANDED_OFF",
                    "callback_state": "RECEIVED",
                    "handoff_ack": {
                        "event_id": event_id,
                        "origin_thread": origin_thread,
                        "source_turn_id": source_turn_id,
                        "payload_sha256": payload_sha256,
                        "handoff_summary_sha256": handoff_summary_sha256,
                        "acknowledged_at": timestamp,
                    },
                    "closed_at": timestamp,
                }
            )
            state["processed_events"][event_id] = {
                "event_id": event_id,
                "assignment_id": assignment_id,
                "origin_thread": origin_thread,
                "source_turn_id": source_turn_id,
                "payload_sha256": payload_sha256,
                "handoff_summary_sha256": handoff_summary_sha256,
                "state": "HANDOFF_ACKNOWLEDGED",
                "received_at": timestamp,
            }
            self._write_unlocked(state)
            return deepcopy(assignment)

    def recovery_candidates(
        self,
        *,
        now: str,
        callback_grace_seconds: float,
    ) -> dict[str, list[str]]:
        """List pending/uncertain effects and overdue callbacks without dispatching."""

        current = _parse_timestamp(now)
        if callback_grace_seconds < 0:
            raise ValueError("callback_grace_seconds must not be negative")
        pending_sends: list[str] = []
        unknown_sends: list[str] = []
        awaiting_turn_start: list[str] = []
        missed_callbacks: list[str] = []

        with self._file_lock():
            state = self._read_unlocked()
            for assignment_id, assignment in state["assignments"].items():
                status = assignment.get("state")
                if status == "PENDING_SEND":
                    pending_sends.append(assignment_id)
                elif status == "UNKNOWN":
                    unknown_sends.append(assignment_id)
                elif status == "SENT" and assignment.get("callback_state") != "RECEIVED":
                    attempt_time = _parse_timestamp(assignment["send_result_at"])
                    if (current - attempt_time).total_seconds() >= callback_grace_seconds:
                        awaiting_turn_start.append(assignment_id)
                elif status == "ACTIVE" and assignment.get("callback_state") != "RECEIVED":
                    turn_time = _parse_timestamp(assignment["turn_started_at"])
                    if (current - turn_time).total_seconds() >= callback_grace_seconds:
                        missed_callbacks.append(assignment_id)

        return {
            "pending_sends": sorted(pending_sends),
            "unknown_sends": sorted(unknown_sends),
            "awaiting_turn_start": sorted(awaiting_turn_start),
            "missed_callback_candidates": sorted(missed_callbacks),
            "redispatch": [],
        }


def _assignment(state: dict[str, Any], assignment_id: str) -> dict[str, Any]:
    assignment_id = _identifier(assignment_id, "assignment_id")
    assignment = state["assignments"].get(assignment_id)
    if assignment is None:
        raise InvalidTransitionError(f"unknown assignment_id: {assignment_id}")
    return assignment


def _event_exists(state: dict[str, Any], event_id: str) -> bool:
    if event_id in state["processed_events"]:
        return True
    return any(
        attempt.get("event_id") == event_id
        for assignment in state["assignments"].values()
        for attempt in assignment.get("attempts", [])
    )


def _owner_has_open_assignment(state: dict[str, Any], owner_thread_id: str) -> bool:
    for assignment in state["assignments"].values():
        assigned_owner = assignment.get(
            "owner_thread_id", assignment.get("owner_thread", assignment.get("target_thread"))
        )
        reconciliation = assignment.get("coordinator_reconciliation", {})
        reconciled_state = reconciliation.get("disposition")
        if assigned_owner == owner_thread_id and (
            assignment.get("state") in _ACTIVE_STATES
            and reconciled_state not in {"NOT_SENT_CONFIRMED", "HELD", "COMPLETED", "HANDED_OFF"}
        ):
            return True
    return False


def _turn_id_exists(
    state: dict[str, Any], recipient_turn_id: str, *, excluding_assignment: str
) -> bool:
    for assignment_id, assignment in state["assignments"].items():
        if assignment_id == excluding_assignment:
            continue
        if any(
            start.get("recipient_turn_id") == recipient_turn_id
            for start in assignment.get("actual_turn_starts", [])
        ):
            return True
        if assignment.get("handoff_ack", {}).get("source_turn_id") == recipient_turn_id:
            return True
    return any(
        event.get("assignment_id") != excluding_assignment
        and (
            event.get("source_turn_id") == recipient_turn_id
            or event.get("recipient_turn_id") == recipient_turn_id
        )
        for event in state["processed_events"].values()
        if isinstance(event, dict)
    )


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be a nonempty stable identifier without whitespace")
    return value


def _sha256(value: str, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(UTC).isoformat()
    return _parse_timestamp(value).isoformat()


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamps must be ISO-8601 strings")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamps must be ISO-8601 strings") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return parsed


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()
