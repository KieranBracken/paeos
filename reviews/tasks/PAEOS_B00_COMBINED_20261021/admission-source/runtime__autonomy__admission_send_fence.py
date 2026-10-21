"""Linearizable admission-currentness and one-shot send claims on the canonical PAEOS ledger.

This module consumes admission and signed-policy facts already committed by their trusted
owners. It does not enroll a key, create an admission, or enable a provider route. A claim is
append-only and remains consumed after a crash, timeout, restart, or UNKNOWN outcome.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from kernel.ledger import GENESIS_HASH, Event, ForkRejected, Ledger, LedgerRow

__all__ = [
    "AdmissionAuthorityVerifier",
    "AdmissionNotCurrent",
    "AdmissionSendFence",
    "DuplicateSendOperation",
    "SendLease",
    "SendOperation",
    "SendOutcome",
    "SendSettlementError",
]

_ADMISSION_CURRENT = "ADMISSION_CURRENT"
_ADMISSION_REVOKED = "ADMISSION_REVOKED"
_POLICY_CURRENT = "DISCLOSURE_POLICY_CURRENT"
_POLICY_REVOKED = "DISCLOSURE_POLICY_REVOKED"
_SEND_CLAIMED = "ADMISSION_SEND_CLAIMED"
_SEND_SETTLED = "ADMISSION_SEND_SETTLED"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MAX_FRAME_BYTES = 2 * 1024 * 1024
_MAX_CAS_ATTEMPTS = 16


class AdmissionSendFenceError(RuntimeError):
    """A local fail-closed fence result; never a provider or task result."""


class AdmissionNotCurrent(AdmissionSendFenceError):
    """Admission or policy state is absent, stale, revoked, malformed, or mismatched."""


class DuplicateSendOperation(AdmissionSendFenceError):
    """The canonical logical job already has a send claim, including an unresolved one."""


class SendSettlementError(AdmissionSendFenceError):
    """A send lease is missing, already settled, or has an invalid settlement."""


class SendOutcome(StrEnum):
    RETURNED = "RETURNED"
    UNKNOWN = "UNKNOWN"


class AdmissionAuthorityVerifier(Protocol):
    """Trusted verifier supplied by the existing admission and policy owners."""

    def verify_admission(self, payload: Mapping[str, object]) -> bool: ...

    def verify_policy(self, payload: Mapping[str, object]) -> bool: ...

    def authorize_frame(
        self,
        admission: Mapping[str, object],
        policy: Mapping[str, object],
        *,
        frame_digest: str,
        route_digest: str,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class SendOperation:
    """One trusted transport's exact request bytes and immutable task/route identity."""

    admission_ref: str
    expected_epoch: int
    task_id: str
    goal_id: str
    run_id: str
    stage: str
    role: str
    workspace_id: str
    route_id: str
    route_digest: str
    request_id: str
    frame: bytes
    operation_kind: str | None = None
    session_id: str | None = None
    contract_digest: str | None = None
    scope_digest: str | None = None
    root_allocation_id: str | None = None
    frame_ordinal: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "admission_ref",
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "role",
            "workspace_id",
            "route_id",
            "request_id",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value or len(value) > 512 or "\x00" in value:
                raise ValueError(f"invalid {name}")
        if type(self.expected_epoch) is not int or self.expected_epoch < 1:
            raise ValueError("expected_epoch must be a positive integer")
        if not isinstance(self.frame, bytes) or not 0 < len(self.frame) <= _MAX_FRAME_BYTES:
            raise ValueError("outbound frame is empty or outside its size bound")
        if type(self.route_digest) is not str or not _HASH.fullmatch(self.route_digest):
            raise ValueError("route_digest must be a lowercase SHA-256 digest")
        if self.operation_kind is not None:
            if type(self.operation_kind) is not str or self.operation_kind not in {
                "WORKER_LAUNCH",
                "PROVIDER_FRAME",
            }:
                raise ValueError("invalid operation_kind")
            if type(self.frame_ordinal) is not int or self.frame_ordinal < 0:
                raise ValueError("invalid parent frame ordinal")
            for name in ("session_id", "root_allocation_id"):
                value = getattr(self, name)
                if type(value) is not str or not value or len(value) > 512 or "\x00" in value:
                    raise ValueError(f"invalid {name}")
            for name in ("contract_digest", "scope_digest"):
                value = getattr(self, name)
                if type(value) is not str or not _HASH.fullmatch(value):
                    raise ValueError(f"invalid {name}")

    @property
    def frame_digest(self) -> str:
        return hashlib.sha256(self.frame).hexdigest()


@dataclass(frozen=True, slots=True)
class SendLease:
    lease_id: str
    logical_job_id: str
    frame_digest: str
    route_digest: str
    ledger_seq: int


class AdmissionSendFence:
    """Validate current canonical state and append unique claims on the one PAEOS ledger.

    ``authority`` must come from the trusted composition root. There is no default verifier,
    enrollment, key lookup, policy seed, or environment-based activation path.
    """

    def __init__(
        self,
        ledger: Ledger,
        *,
        authority: AdmissionAuthorityVerifier,
        domain_tag: str = "PRODUCTION",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(ledger, Ledger):
            raise TypeError("canonical PAEOS Ledger is required")
        if authority is None:
            raise TypeError("an explicit trusted admission/policy verifier is required")
        if type(domain_tag) is not str or not domain_tag.strip():
            raise ValueError("domain_tag is required")
        self._ledger = ledger
        self._authority = authority
        self._domain_tag = domain_tag.strip().upper()
        context_validator = getattr(authority, "validate_context", None)
        if context_validator is not None:
            context_validator(ledger, self._domain_tag)
        self._now = now or (lambda: datetime.now(UTC))
        self._settlement_lock = threading.Lock()
        self._issued_leases: dict[str, SendLease] = {}

    def preflight(self, admission_ref: str, expected_epoch: int) -> None:
        """Read-only check before a transport inspects or signs its session payload.

        The actual claim rechecks the same state and compares the ledger head transactionally.
        This method alone never authorizes a send.
        """
        if type(admission_ref) is not str or not admission_ref:
            raise AdmissionNotCurrent("admission reference is unavailable")
        if type(expected_epoch) is not int or expected_epoch < 1:
            raise AdmissionNotCurrent("admission epoch is unavailable")
        rows, head_hash = self._snapshot()
        admission, _policy = self._resolve_current(rows, admission_ref, expected_epoch)
        logical_job_id = self._required_text(admission, "logical_job_id")
        if getattr(self._authority, "requires_authenticated_settlement", False):
            logical_job_id = self._parent_job_id(
                self._required_text(admission, "root_allocation_id"), "WORKER_LAUNCH", 0
            )
        if any(
            row.event.kind == _SEND_CLAIMED
            and row.domain_tag == self._domain_tag
            and row.event.payload.get("logical_job_id") == logical_job_id
            for row in rows
        ):
            raise DuplicateSendOperation("logical operation already has a durable send claim")
        if self._ledger.head_hash() != head_hash:
            raise AdmissionNotCurrent("canonical admission state changed during preflight")

    def acquire_send_lease(self, operation: SendOperation) -> SendLease:
        """Atomically reserve the current logical operation before any sink/socket write."""
        if not isinstance(operation, SendOperation):
            raise TypeError("SendOperation is required")
        lease_id = uuid.uuid4().hex
        for _ in range(_MAX_CAS_ATTEMPTS):
            rows, head_hash = self._snapshot()
            admission, policy = self._resolve_current(
                rows, operation.admission_ref, operation.expected_epoch
            )
            self._validate_operation(operation, admission)
            logical_job_id = self._required_text(admission, "logical_job_id")
            if operation.operation_kind is not None:
                if (
                    operation.operation_kind not in {"WORKER_LAUNCH", "PROVIDER_FRAME"}
                    or type(operation.frame_ordinal) is not int
                    or operation.frame_ordinal < 0
                    or not operation.root_allocation_id
                ):
                    raise AdmissionNotCurrent("explicit parent operation binding required")
                logical_job_id = self._parent_job_id(
                    operation.root_allocation_id, operation.operation_kind, operation.frame_ordinal
                )
            if any(
                row.event.kind == _SEND_CLAIMED
                and row.domain_tag == self._domain_tag
                and row.event.payload.get("logical_job_id") == logical_job_id
                for row in rows
            ):
                raise DuplicateSendOperation("logical operation already has a durable send claim")
            validator = getattr(self._authority, "validate_operation", None)
            if operation.operation_kind is not None and validator is None:
                raise AdmissionNotCurrent("provider frames require concrete parent authorization")
            if validator is not None and validator(operation, admission, rows) is not True:
                raise AdmissionNotCurrent("parent scope or root allocation refused operation")
            try:
                allowed = self._authority.authorize_frame(
                    admission,
                    policy,
                    frame_digest=operation.frame_digest,
                    route_digest=operation.route_digest,
                )
            except Exception as exc:
                raise AdmissionNotCurrent(
                    "trusted disclosure policy refused the outbound frame"
                ) from exc
            if allowed is not True:
                raise AdmissionNotCurrent("trusted disclosure policy refused the outbound frame")

            payload = {
                "lease_id": lease_id,
                "admission_ref": operation.admission_ref,
                "admission_epoch": operation.expected_epoch,
                "logical_job_id": logical_job_id,
                "task_id": operation.task_id,
                "goal_id": operation.goal_id,
                "run_id": operation.run_id,
                "stage": operation.stage,
                "role": operation.role,
                "workspace_id": operation.workspace_id,
                "policy_id": self._required_text(admission, "policy_id"),
                "policy_revision": self._required_int(admission, "policy_revision"),
                "policy_digest": self._required_hash(admission, "policy_digest"),
                "route_id": operation.route_id,
                "route_digest": operation.route_digest,
                "request_id": operation.request_id,
                "frame_digest": operation.frame_digest,
                "state": "CLAIMED",
                **(
                    {
                        k: getattr(operation, k)
                        for k in (
                            "operation_kind",
                            "session_id",
                            "contract_digest",
                            "scope_digest",
                            "root_allocation_id",
                            "frame_ordinal",
                        )
                    }
                    if operation.operation_kind is not None
                    else {}
                ),
                **({"grant_id": admission["grant_id"]} if "grant_id" in admission else {}),
                **(
                    {"root_grant_digest": admission["root_grant_digest"]}
                    if "root_grant_digest" in admission
                    else {}
                ),
            }
            try:
                seq = self._ledger.append_if_head(
                    Event(1, _SEND_CLAIMED, payload),
                    expected_head_hash=head_hash,
                    domain_tag=self._domain_tag,
                )
            except ForkRejected:
                continue
            lease = SendLease(
                lease_id=lease_id,
                logical_job_id=logical_job_id,
                frame_digest=operation.frame_digest,
                route_digest=operation.route_digest,
                ledger_seq=seq,
            )
            with self._settlement_lock:
                self._issued_leases[lease_id] = lease
            return lease
        raise AdmissionNotCurrent("canonical ledger remained contended; no send was claimed")

    def finish_send_lease(
        self,
        lease: SendLease,
        outcome: SendOutcome,
        *,
        outcome_ref: str | None = None,
    ) -> int:
        """Append one immutable result or UNKNOWN settlement; never releases the claim."""
        if not isinstance(lease, SendLease) or not re.fullmatch(r"[0-9a-f]{32}", lease.lease_id):
            raise SendSettlementError("send lease capability is invalid")
        if not isinstance(outcome, SendOutcome):
            raise SendSettlementError("send outcome is invalid")
        if outcome is SendOutcome.RETURNED:
            if getattr(self._authority, "requires_authenticated_settlement", False):
                raise SendSettlementError("returned evidence requires authenticated reconciliation")
            if type(outcome_ref) is not str or not _HASH.fullmatch(outcome_ref):
                raise SendSettlementError("returned outcome requires a digest reference")
        elif outcome_ref is not None:
            raise SendSettlementError("UNKNOWN outcome cannot claim a result reference")

        with self._settlement_lock:
            if self._issued_leases.get(lease.lease_id) is not lease:
                raise SendSettlementError("send lease was not issued by this live transport fence")
            for _ in range(_MAX_CAS_ATTEMPTS):
                rows, head_hash = self._snapshot()
                claims = [
                    row
                    for row in rows
                    if row.event.kind == _SEND_CLAIMED
                    and row.domain_tag == self._domain_tag
                    and row.event.payload.get("lease_id") == lease.lease_id
                ]
                if len(claims) != 1:
                    raise SendSettlementError("send lease is absent or ambiguous")
                if any(
                    row.event.kind == _SEND_SETTLED
                    and row.domain_tag == self._domain_tag
                    and row.event.payload.get("lease_id") == lease.lease_id
                    for row in rows
                ):
                    raise SendSettlementError("send lease already has an immutable settlement")
                claim = claims[0].event.payload
                payload = {
                    "lease_id": lease.lease_id,
                    "logical_job_id": claim.get("logical_job_id"),
                    "outcome": outcome.value,
                    "outcome_ref": outcome_ref,
                }
                try:
                    seq = self._ledger.append_if_head(
                        Event(1, _SEND_SETTLED, payload),
                        expected_head_hash=head_hash,
                        domain_tag=self._domain_tag,
                    )
                    del self._issued_leases[lease.lease_id]
                    return seq
                except ForkRejected:
                    continue
        raise SendSettlementError(
            "canonical ledger remained contended; settlement was not recorded"
        )

    def query_send_claim(self, lease_id: str) -> dict[str, object]:
        """Read durable claim/outcome after restart; never grants a new send."""
        rows, head = self._snapshot()
        claims = [
            r
            for r in rows
            if r.domain_tag == self._domain_tag
            and r.event.kind == _SEND_CLAIMED
            and r.event.payload.get("lease_id") == lease_id
        ]
        if len(claims) != 1:
            raise SendSettlementError("claim absent or ambiguous")
        result = dict(claims[0].event.payload)
        settlements = [
            r
            for r in rows
            if r.domain_tag == self._domain_tag
            and r.event.kind == _SEND_SETTLED
            and r.event.payload.get("lease_id") == lease_id
        ]
        if len(settlements) > 1:
            raise SendSettlementError("ambiguous settlement")
        if settlements:
            settlement = settlements[0].event.payload
            if settlement.get("outcome") == "RETURNED" and getattr(
                self._authority, "requires_authenticated_settlement", False
            ):
                evidence = settlement.get("evidence")
                verifier = getattr(self._authority, "verify_settlement_record", None)
                if (
                    not isinstance(evidence, Mapping)
                    or verifier is None
                    or verifier(evidence, result) is not True
                    or evidence.get("outcome") != settlement.get("outcome")
                    or evidence.get("outcome_ref") != settlement.get("outcome_ref")
                ):
                    raise SendSettlementError("stored return evidence is unauthenticated")
            result.update(settlement)
            result["state"] = "SETTLED"
        if self._ledger.head_hash() != head:
            raise SendSettlementError("claim changed during query")
        return json.loads(json.dumps(result))

    def reconcile_send_claim(
        self, lease_id: str, evidence: Mapping[str, object], *, outcome_bytes: bytes | None = None
    ) -> int:
        """Authenticate a receiver receipt against the durable exact claim and bytes.

        UNKNOWN is terminal and consumes the allocation; reconciliation never retries
        a send and cannot replace any existing settlement.
        """
        evidence = json.loads(json.dumps(dict(evidence), allow_nan=False))
        verifier = getattr(self._authority, "verify_settlement", None)
        if verifier is None:
            raise SendSettlementError("authenticated reconciliation unavailable")
        for _ in range(_MAX_CAS_ATTEMPTS):
            rows, head = self._snapshot()
            claims = [
                r
                for r in rows
                if r.domain_tag == self._domain_tag
                and r.event.kind == _SEND_CLAIMED
                and r.event.payload.get("lease_id") == lease_id
            ]
            if len(claims) != 1 or any(
                r.domain_tag == self._domain_tag
                and r.event.kind == _SEND_SETTLED
                and r.event.payload.get("lease_id") == lease_id
                for r in rows
            ):
                raise SendSettlementError("claim absent, ambiguous or already settled")
            claim = claims[0].event.payload
            if verifier(evidence, claim, outcome_bytes) is not True:
                raise SendSettlementError("invalid authenticated return evidence")
            payload = {
                "lease_id": lease_id,
                "logical_job_id": claim["logical_job_id"],
                "outcome": evidence["outcome"],
                "outcome_ref": evidence.get("outcome_ref"),
                "evidence": evidence,
            }
            try:
                seq = self._ledger.append_if_head(
                    Event(1, _SEND_SETTLED, payload),
                    expected_head_hash=head,
                    domain_tag=self._domain_tag,
                )
                with self._settlement_lock:
                    self._issued_leases.pop(lease_id, None)
                return seq
            except ForkRejected:
                continue
        raise SendSettlementError("canonical ledger remained contended")

    def send_once(
        self,
        operation: SendOperation,
        sink: Callable[[bytes], object],
    ) -> object:
        """Testable actual sink seam: a claim precedes the one sink call and is never replayed."""
        lease = self.acquire_send_lease(operation)
        try:
            result = sink(operation.frame)
        except BaseException:
            with suppress(SendSettlementError):
                self.finish_send_lease(lease, SendOutcome.UNKNOWN)
            raise
        if getattr(self._authority, "requires_authenticated_settlement", False):
            # Local sink return is not an authenticated receiver receipt. Keep the
            # durable claim consumed and unresolved until explicit reconciliation.
            with self._settlement_lock:
                self._issued_leases.pop(lease.lease_id, None)
            return result
        if isinstance(result, bytes):
            outcome_bytes = result
        elif isinstance(result, str):
            outcome_bytes = result.encode("utf-8")
        else:
            outcome_bytes = b""
        self.finish_send_lease(
            lease,
            SendOutcome.RETURNED,
            outcome_ref=hashlib.sha256(outcome_bytes).hexdigest(),
        )
        return result

    def _snapshot(self) -> tuple[list[LedgerRow], str]:
        rows = self._ledger.read()
        observed_head = rows[-1].row_hash if rows else GENESIS_HASH
        verified_head = self._ledger.verify_chain()
        if verified_head != observed_head:
            raise AdmissionNotCurrent("canonical ledger changed while resolving authority state")
        return rows, observed_head

    @staticmethod
    def _parent_job_id(allocation_id: str, operation_kind: str, ordinal: int) -> str:
        return hashlib.sha256(repr((allocation_id, operation_kind, ordinal)).encode()).hexdigest()

    def _resolve_current(
        self,
        rows: Sequence[LedgerRow],
        admission_ref: str,
        expected_epoch: int,
    ) -> tuple[Mapping[str, object], Mapping[str, object]]:
        admission_rows = [
            row
            for row in rows
            if row.domain_tag == self._domain_tag
            and row.event.kind in {_ADMISSION_CURRENT, _ADMISSION_REVOKED}
            and row.event.payload.get("admission_ref") == admission_ref
        ]
        if not admission_rows or admission_rows[-1].event.kind != _ADMISSION_CURRENT:
            raise AdmissionNotCurrent("canonical admission is absent or revoked")
        admission = admission_rows[-1].event.payload
        if self._required_int(admission, "epoch") != expected_epoch:
            raise AdmissionNotCurrent("canonical admission epoch is stale")
        if not self._verify(self._authority.verify_admission, admission):
            raise AdmissionNotCurrent("canonical admission proof is invalid")
        if not self._not_expired(admission):
            raise AdmissionNotCurrent("canonical admission is expired")

        policy_id = self._required_text(admission, "policy_id")
        policy_rows = [
            row
            for row in rows
            if row.domain_tag == self._domain_tag
            and row.event.kind in {_POLICY_CURRENT, _POLICY_REVOKED}
            and row.event.payload.get("policy_id") == policy_id
        ]
        if not policy_rows or policy_rows[-1].event.kind != _POLICY_CURRENT:
            raise AdmissionNotCurrent("canonical disclosure policy is absent or revoked")
        policy = policy_rows[-1].event.payload
        if self._required_int(policy, "revision") != self._required_int(
            admission, "policy_revision"
        ) or self._required_hash(policy, "digest") != self._required_hash(
            admission, "policy_digest"
        ):
            raise AdmissionNotCurrent("canonical disclosure policy revision is stale")
        if not self._verify(self._authority.verify_policy, policy):
            raise AdmissionNotCurrent("canonical disclosure policy proof is invalid")
        if not self._not_expired(policy):
            raise AdmissionNotCurrent("canonical disclosure policy is expired")
        validator = getattr(self._authority, "validate_current", None)
        if validator is not None and validator(rows, admission, policy) is not True:
            raise AdmissionNotCurrent("canonical root authority is revoked")
        return admission, policy

    @staticmethod
    def _verify(
        verifier: Callable[[Mapping[str, object]], bool], payload: Mapping[str, object]
    ) -> bool:
        try:
            return verifier(payload) is True
        except Exception:
            return False

    def _validate_operation(
        self,
        operation: SendOperation,
        admission: Mapping[str, object],
    ) -> None:
        for field in (
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "role",
            "workspace_id",
            "route_id",
            "route_digest",
        ):
            if admission.get(field) != getattr(operation, field):
                raise AdmissionNotCurrent(f"send operation does not match admitted {field}")

    def _not_expired(self, payload: Mapping[str, object]) -> bool:
        expires = payload.get("expires_at")
        now = self._now()
        if not isinstance(expires, str) or not isinstance(now, datetime):
            return False
        try:
            expires_at = datetime.fromisoformat(expires)
        except ValueError:
            return False
        if expires_at.tzinfo is None or now.tzinfo is None or now.utcoffset() is None:
            return False
        return now.astimezone(UTC) < expires_at.astimezone(UTC)

    @staticmethod
    def _required_text(payload: Mapping[str, object], field: str) -> str:
        value = payload.get(field)
        if type(value) is not str or not value or "\x00" in value:
            raise AdmissionNotCurrent(f"canonical authority field {field} is invalid")
        return value

    @staticmethod
    def _required_int(payload: Mapping[str, object], field: str) -> int:
        value = payload.get(field)
        if type(value) is not int or value < 1:
            raise AdmissionNotCurrent(f"canonical authority field {field} is invalid")
        return value

    @staticmethod
    def _required_hash(payload: Mapping[str, object], field: str) -> str:
        value = payload.get(field)
        if type(value) is not str or not _HASH.fullmatch(value):
            raise AdmissionNotCurrent(f"canonical authority field {field} is invalid")
        return value
