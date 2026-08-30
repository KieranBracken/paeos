"""Immutable protocol envelopes and write-once storage for the PAEOS bridge.

``TransactionStore`` remains a compatibility/materialization seam for legacy bridge files. The
ledger-derived control-plane projection is canonical for new coordination code; mutable JSON
materializations must never be used as transaction authority.
"""

from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import cast

from runtime.worker_admission import WorkerBinding

SCHEMA_VERSION = "paeos-bridge-v2"

_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]+")
_HEX_HASH = re.compile(r"[0-9a-f]{64}")
_UNKNOWN_MODEL_VALUES = frozenset({"unknown", "none", "null", "unavailable"})


class Disposition(StrEnum):
    CONTINUE = "CONTINUE"
    REMAND = "REMAND"
    HALT = "HALT"
    NEEDS_FOUNDER = "NEEDS_FOUNDER"


class CircuitBreaker(StrEnum):
    NONEXISTENT_OR_UNAUTHORIZED_SUBAGENT_INVOCATION = (
        "NONEXISTENT_OR_UNAUTHORIZED_SUBAGENT_INVOCATION"
    )
    UNREQUESTED_REVIEW_OR_SKILL_ROUTING = "UNREQUESTED_REVIEW_OR_SKILL_ROUTING"
    PASTED_GOVERNANCE_TEXT_INTERPRETED_AS_TOOL_ARGUMENTS = (
        "PASTED_GOVERNANCE_TEXT_INTERPRETED_AS_TOOL_ARGUMENTS"
    )
    COMMAND_EXPANSION_BEYOND_THE_AUTHORIZED_COMMAND = (
        "COMMAND_EXPANSION_BEYOND_THE_AUTHORIZED_COMMAND"
    )
    SHELL_COMMAND_MUTATED_MATERIALLY_FROM_DIRECTIVE = (
        "SHELL_COMMAND_MUTATED_MATERIALLY_FROM_DIRECTIVE"
    )
    REPEATED_IDENTICAL_FAILED_TOOL_CALL_WITHOUT_NEW_RATIONALE = (
        "REPEATED_IDENTICAL_FAILED_TOOL_CALL_WITHOUT_NEW_RATIONALE"
    )
    REPEATED_IDENTICAL_COMMAND_AFTER_SAME_RESULT_WITHOUT_EXPLICIT_RERUN_AUTHORITY = (
        "REPEATED_IDENTICAL_COMMAND_AFTER_SAME_RESULT_WITHOUT_EXPLICIT_RERUN_AUTHORITY"
    )
    WRITE_ATTEMPT_OUTSIDE_CURRENT_ALLOWLIST = "WRITE_ATTEMPT_OUTSIDE_CURRENT_ALLOWLIST"
    TRUNK_OR_MAIN_PROMOTION_ATTEMPT = "TRUNK_OR_MAIN_PROMOTION_ATTEMPT"
    UNAUTHORIZED_LIFECYCLE_ADVANCEMENT = "UNAUTHORIZED_LIFECYCLE_ADVANCEMENT"
    SELF_RATIFICATION_ATTEMPT = "SELF_RATIFICATION_ATTEMPT"


class ProtocolViolation(RuntimeError):
    """A fail-closed rejection carrying its exact circuit-breaker class."""

    def __init__(
        self,
        breaker: CircuitBreaker | str,
        message: str | None = None,
    ) -> None:
        if isinstance(breaker, CircuitBreaker):
            resolved_breaker = breaker
            resolved_message = breaker.value if message is None else message
        else:
            if message is not None:
                raise TypeError("string-only compatibility form accepts one argument")
            resolved_breaker = CircuitBreaker.UNAUTHORIZED_LIFECYCLE_ADVANCEMENT
            resolved_message = breaker
        super().__init__(resolved_message)
        self.breaker = resolved_breaker


class TransactionState(StrEnum):
    NEW = "NEW"
    PREPARED = "PREPARED"
    CLAIMED = "CLAIMED"
    RESPONDED = "RESPONDED"
    CONSUMED = "CONSUMED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    QUARANTINED = "QUARANTINED"


class TransactionEvent(StrEnum):
    PREPARE = "PREPARE"
    CLAIM = "CLAIM"
    EXPIRE_LEASE = "EXPIRE_LEASE"
    RESPOND = "RESPOND"
    CONSUME = "CONSUME"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True, slots=True)
class BridgePaths:
    state_root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_root", self.state_root.resolve())

    @property
    def bridge_root(self) -> Path:
        return self.state_root / "bridge"

    @property
    def requests(self) -> Path:
        return self.bridge_root / "requests"

    @property
    def responses(self) -> Path:
        return self.bridge_root / "responses"

    @property
    def quarantine(self) -> Path:
        return self.bridge_root / "quarantine"

    @property
    def transactions(self) -> Path:
        return self.bridge_root / "transactions"

    def ensure(self) -> None:
        for path in (
            self.requests,
            self.responses,
            self.quarantine,
            self.transactions,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class RequestEnvelope:
    schema_version: str
    request_id: str
    transaction_key: str
    created_at: str
    expires_at: str
    goal_id: str
    run_id: str
    stage_id: str
    role: str
    workspace_root: str
    worker_transport_id: str
    worker_session_id: str
    worker_pid: int
    worker_tty: str | None
    worker_model_provider: str
    worker_model_id: str
    worker_model_family: str
    semantic_hash: str
    evidence_manifest_hash: str
    payload_hash: str
    allowed_dispositions: tuple[Disposition, ...]


@dataclass(frozen=True, slots=True)
class ResponseEnvelope:
    schema_version: str
    request_id: str
    transaction_key: str
    run_id: str
    stage_id: str
    payload_hash: str
    lease_owner: str
    overseer_model_provider: str
    overseer_model_id: str
    overseer_model_family: str
    disposition: Disposition
    response_text: str
    response_hash: str
    source_task_id: str
    completed_at: str


@dataclass(frozen=True, slots=True)
class TransitionEntry:
    at: str
    actor: str
    event: TransactionEvent
    from_state: TransactionState
    to_state: TransactionState


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    schema_version: str
    request_id: str
    transaction_key: str
    run_id: str
    stage_id: str
    payload_hash: str
    state: TransactionState = TransactionState.NEW
    lease_owner: str | None = None
    lease_expires_at: str | None = None
    last_side_effect: str | None = None
    transitions: tuple[TransitionEntry, ...] = ()
    legacy_state: str | None = None
    legacy_dispatch_seq: int | None = None
    legacy_raw_hash: str | None = None


@dataclass(frozen=True, slots=True)
class CircuitBreakerIncident:
    schema_version: str
    breaker: CircuitBreaker
    occurred_at: str
    request_id: str
    transaction_key: str
    state: TransactionState
    raw_exception: str
    request_envelope_hash: str
    last_confirmed_side_effect: str | None


def _normalize(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _normalize(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _normalize(item) for key, item in mapping.items()}
    if isinstance(value, tuple):
        sequence = cast(tuple[object, ...], value)
        return [_normalize(item) for item in sequence]
    if isinstance(value, list):
        sequence = cast(list[object], value)
        return [_normalize(item) for item in sequence]
    return value


def canonical_json(value: object) -> str:
    try:
        return json.dumps(
            _normalize(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolViolation(f"value is not canonically serializable: {exc}") from exc


def content_hash(value: str | bytes | Mapping[str, object]) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    elif isinstance(value, Mapping):
        payload = canonical_json(value).encode("utf-8")
    else:
        raise ProtocolViolation("content_hash accepts only text, bytes, or a mapping")
    return hashlib.sha256(payload).hexdigest()


def transaction_key(
    *,
    request_id: str,
    run_id: str,
    stage_id: str,
    semantic_hash: str,
    evidence_manifest_hash: str,
    payload_hash: str,
) -> str:
    identity = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "run_id": run_id,
        "stage_id": stage_id,
        "semantic_hash": semantic_hash,
        "evidence_manifest_hash": evidence_manifest_hash,
        "payload_hash": payload_hash,
    }
    return hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()


def _validate_identifier(value: object, field_name: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ProtocolViolation(f"{field_name} must be a slash-free protocol identifier")


def _validate_hash(value: object, field_name: str) -> None:
    if not isinstance(value, str) or _HEX_HASH.fullmatch(value) is None:
        raise ProtocolViolation(f"{field_name} must be a lowercase 64-character hex digest")


def _validate_model_identity(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolViolation(f"{field_name} must be a non-empty string")
    if value.strip().lower() in _UNKNOWN_MODEL_VALUES:
        raise ProtocolViolation(f"{field_name} must be attributable, not a placeholder")


def _parse_aware_timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ProtocolViolation(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProtocolViolation(f"{field_name} must be valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProtocolViolation(f"{field_name} must be timezone-aware")
    return parsed


def validate_request(request: RequestEnvelope) -> None:
    if request.schema_version != SCHEMA_VERSION:
        raise ProtocolViolation("unsupported request schema_version")

    for field_name, value in (
        ("request_id", request.request_id),
        ("goal_id", request.goal_id),
        ("run_id", request.run_id),
        ("stage_id", request.stage_id),
        ("role", request.role),
        ("worker_transport_id", request.worker_transport_id),
        ("worker_session_id", request.worker_session_id),
    ):
        _validate_identifier(value, field_name)

    for field_name, value in (
        ("transaction_key", request.transaction_key),
        ("semantic_hash", request.semantic_hash),
        ("evidence_manifest_hash", request.evidence_manifest_hash),
        ("payload_hash", request.payload_hash),
    ):
        _validate_hash(value, field_name)

    created_at = _parse_aware_timestamp(request.created_at, "created_at")
    expires_at = _parse_aware_timestamp(request.expires_at, "expires_at")
    if expires_at <= created_at:
        raise ProtocolViolation("expires_at must be later than created_at")

    if not isinstance(request.workspace_root, str):
        raise ProtocolViolation("workspace_root must be a string")
    if not Path(request.workspace_root).is_absolute():
        raise ProtocolViolation("workspace_root must be absolute")

    if (
        isinstance(request.worker_pid, bool)
        or not isinstance(request.worker_pid, int)
        or request.worker_pid <= 0
    ):
        raise ProtocolViolation("worker_pid must be a positive integer")

    for field_name, value in (
        ("worker_model_provider", request.worker_model_provider),
        ("worker_model_id", request.worker_model_id),
        ("worker_model_family", request.worker_model_family),
    ):
        _validate_model_identity(value, field_name)

    if request.worker_tty is None:
        if not request.worker_transport_id.startswith("headless:"):
            raise ProtocolViolation("worker_tty may be null only for a headless transport")
    elif not isinstance(request.worker_tty, str) or not request.worker_tty.strip():
        raise ProtocolViolation("worker_tty must be non-empty when present")

    allowed = request.allowed_dispositions
    if not isinstance(allowed, tuple) or not allowed:
        raise ProtocolViolation("allowed_dispositions must be a non-empty tuple")
    if any(not isinstance(item, Disposition) for item in allowed):
        raise ProtocolViolation("allowed_dispositions must contain only Disposition values")
    if len(set(allowed)) != len(allowed):
        raise ProtocolViolation("allowed_dispositions must not contain duplicates")


def validate_response(response: ResponseEnvelope) -> None:
    if response.schema_version != SCHEMA_VERSION:
        raise ProtocolViolation("unsupported response schema_version")

    for field_name, value in (
        ("request_id", response.request_id),
        ("run_id", response.run_id),
        ("stage_id", response.stage_id),
        ("lease_owner", response.lease_owner),
        ("source_task_id", response.source_task_id),
    ):
        _validate_identifier(value, field_name)

    for field_name, value in (
        ("transaction_key", response.transaction_key),
        ("payload_hash", response.payload_hash),
        ("response_hash", response.response_hash),
    ):
        _validate_hash(value, field_name)

    for field_name, value in (
        ("overseer_model_provider", response.overseer_model_provider),
        ("overseer_model_id", response.overseer_model_id),
        ("overseer_model_family", response.overseer_model_family),
    ):
        _validate_model_identity(value, field_name)

    if not isinstance(response.disposition, Disposition):
        raise ProtocolViolation("disposition must be a Disposition value")
    if response.response_hash != content_hash(response.response_text):
        raise ProtocolViolation("response_hash does not match response_text")
    _parse_aware_timestamp(response.completed_at, "completed_at")


@dataclass(frozen=True, slots=True)
class AdmittedWorkerRequest:
    """A request bound to an admitted worker, with its manifest evidence bytes.

    evidence_manifest_bytes are the exact canonical UTF-8 bytes whose SHA-256
    equals request.evidence_manifest_hash. They contain the admitted worker
    receipt hash, so a later verifier can recover and persist the exact
    manifest without recomputing policy.
    """

    request: RequestEnvelope
    evidence_manifest_bytes: bytes


def worker_evidence_manifest(
    request: RequestEnvelope,
    worker_receipt_hash: str | None = None,
) -> dict[str, object]:
    """Canonical evidence-manifest snapshot for a request.

    This mapping is the canonical object whose hash is assigned to
    `RequestEnvelope.evidence_manifest_hash`. Before admission binding the
    worker receipt hash is null; `bind_request_to_admitted_worker` inserts the
    admitted worker receipt hash and recomputes the hash. No new
    RequestEnvelope field is introduced: the receipt travels only through this
    hash-addressed manifest.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request.request_id,
        "run_id": request.run_id,
        "stage_id": request.stage_id,
        "worker_transport_id": request.worker_transport_id,
        "worker_session_id": request.worker_session_id,
        "worker_pid": request.worker_pid,
        "worker_tty": request.worker_tty,
        "worker_model_provider": request.worker_model_provider,
        "worker_model_id": request.worker_model_id,
        "worker_model_family": request.worker_model_family,
        "semantic_hash": request.semantic_hash,
        "payload_hash": request.payload_hash,
        "worker_receipt_hash": worker_receipt_hash,
    }


def bind_request_to_admitted_worker(
    request: RequestEnvelope,
    binding: WorkerBinding,
) -> AdmittedWorkerRequest:
    """Bind an admitted worker receipt into a request's evidence manifest.

    Returns an AdmittedWorkerRequest carrying the bound envelope and the exact
    canonical manifest bytes whose SHA-256 is the bound evidence_manifest_hash.

    Fails closed unless the request's existing worker identity matches the
    admitted binding, the existing transaction_key binds the request's current
    canonical fields, and the existing evidence_manifest_hash is the canonical
    unbound manifest hash (or the already-bound hash, making binding
    idempotent). The admitted receipt hash is inserted into the canonical
    evidence-manifest snapshot, which is serialized, parsed, and reserialized
    before the bytes are returned (no trailing newline); evidence_manifest_hash
    is recomputed and the transaction_key is recomputed from the resulting
    canonical request.
    """
    _validate_hash(binding.receipt_hash, "worker receipt hash")
    validate_request(request)

    identity_matches = (
        request.worker_transport_id == binding.transport
        and request.worker_session_id == binding.session
        and request.worker_pid == binding.pid
        and request.worker_tty == binding.tty
        and request.worker_model_provider == binding.provider
        and request.worker_model_id == binding.model
        and request.worker_model_family == binding.family.value
    )
    if not identity_matches:
        raise ProtocolViolation(
            "request worker identity conflicts with the admitted receipt binding"
        )

    def _recomputed_key(evidence_manifest_hash: str) -> str:
        return transaction_key(
            request_id=request.request_id,
            run_id=request.run_id,
            stage_id=request.stage_id,
            semantic_hash=request.semantic_hash,
            evidence_manifest_hash=evidence_manifest_hash,
            payload_hash=request.payload_hash,
        )

    unbound_hash = content_hash(worker_evidence_manifest(request))
    bound_manifest = worker_evidence_manifest(
        request, worker_receipt_hash=binding.receipt_hash
    )
    # Serialize, parse, and reserialize the canonical snapshot so the returned
    # bytes are exactly the canonical evidence. No trailing newline is added.
    snapshot = canonical_json(bound_manifest)
    reparsed: dict[str, object] = json.loads(snapshot)
    reserialized = canonical_json(reparsed)
    if reserialized != snapshot:
        raise ProtocolViolation("evidence-manifest snapshot is not canonically stable")
    manifest_bytes = reserialized.encode("utf-8")
    bound_hash = content_hash(manifest_bytes)

    if request.evidence_manifest_hash == bound_hash:
        if request.transaction_key != _recomputed_key(bound_hash):
            raise ProtocolViolation(
                "bound evidence manifest conflicts with the existing transaction binding"
            )
        return AdmittedWorkerRequest(
            request=request, evidence_manifest_bytes=manifest_bytes
        )
    if request.evidence_manifest_hash != unbound_hash:
        raise ProtocolViolation(
            "existing evidence_manifest_hash conflicts with the canonical manifest"
        )
    if request.transaction_key != _recomputed_key(unbound_hash):
        raise ProtocolViolation(
            "existing transaction binding does not bind the request's canonical fields"
        )
    return AdmittedWorkerRequest(
        request=dataclasses.replace(
            request,
            evidence_manifest_hash=bound_hash,
            transaction_key=_recomputed_key(bound_hash),
        ),
        evidence_manifest_bytes=manifest_bytes,
    )


def write_once_bytes(path: Path, payload: bytes) -> None:
    target = Path(path)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temp_path, target)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temp_path)


def persist_immutable_bytes(path: Path, payload: bytes) -> str:
    """Durably persist content once and return its content hash.

    A repeated write is accepted only when the existing bytes are identical.  A
    different payload at the same path is a protocol violation, which prevents a
    crashed or retried dispatch from silently replacing the request evidence.
    """

    target = Path(path)
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if not target.parent.is_dir():
        raise ProtocolViolation(
            CircuitBreaker.WRITE_ATTEMPT_OUTSIDE_CURRENT_ALLOWLIST,
            f"immutable evidence parent does not exist: {target.parent}",
        )
    try:
        write_once_bytes(target, payload)
    except FileExistsError:
        try:
            existing = target.read_bytes()
        except OSError as exc:
            raise ProtocolViolation("immutable evidence cannot be read") from exc
        if existing != payload:
            raise ProtocolViolation(
                CircuitBreaker.WRITE_ATTEMPT_OUTSIDE_CURRENT_ALLOWLIST,
                "immutable evidence already exists with different bytes",
            ) from None
        return content_hash(existing)
    return content_hash(payload)


def write_once_json(path: Path, value: object) -> None:
    payload = (canonical_json(value) + "\n").encode("utf-8")
    write_once_bytes(path, payload)


def load_json(path: Path) -> dict[str, object]:
    source = Path(path)
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolViolation(f"{source} is not valid UTF-8") from exc
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolViolation(f"{source} contains malformed JSON") from exc
    if not isinstance(parsed, dict):
        raise ProtocolViolation(f"{source} must contain a JSON object")
    return cast(dict[str, object], parsed)


_TRANSITIONS: dict[
    tuple[TransactionState, TransactionEvent],
    TransactionState,
] = {
    (TransactionState.NEW, TransactionEvent.PREPARE): TransactionState.PREPARED,
    (TransactionState.PREPARED, TransactionEvent.CLAIM): TransactionState.CLAIMED,
    (TransactionState.CLAIMED, TransactionEvent.EXPIRE_LEASE): TransactionState.PREPARED,
    (TransactionState.CLAIMED, TransactionEvent.RESPOND): TransactionState.RESPONDED,
    (TransactionState.RESPONDED, TransactionEvent.CONSUME): TransactionState.CONSUMED,
}

_TERMINAL_STATES = frozenset(
    {
        TransactionState.CONSUMED,
        TransactionState.RECONCILIATION_REQUIRED,
        TransactionState.QUARANTINED,
    }
)


def _protocol_error(
    message: str,
    *,
    breaker: CircuitBreaker = CircuitBreaker.UNAUTHORIZED_LIFECYCLE_ADVANCEMENT,
) -> ProtocolViolation:
    return ProtocolViolation(breaker, message)


def _validate_record(record: TransactionRecord) -> None:
    if record.schema_version != SCHEMA_VERSION:
        raise _protocol_error("unsupported transaction schema_version")
    for field_name, value in (
        ("request_id", record.request_id),
        ("run_id", record.run_id),
        ("stage_id", record.stage_id),
    ):
        _validate_identifier(value, field_name)
    for field_name, value in (
        ("transaction_key", record.transaction_key),
        ("payload_hash", record.payload_hash),
    ):
        _validate_hash(value, field_name)
    if not isinstance(record.state, TransactionState):
        raise _protocol_error("state must be a TransactionState")

    if record.state in {
        TransactionState.CLAIMED,
        TransactionState.RESPONDED,
        TransactionState.CONSUMED,
    } and (
        record.lease_owner is None or record.lease_expires_at is None
    ):
        raise _protocol_error(
            f"{record.state.value} requires an active lease"
        )

    if record.lease_owner is None:
        if record.lease_expires_at is not None:
            raise _protocol_error("lease expiry requires a lease owner")
    else:
        _validate_identifier(record.lease_owner, "lease_owner")
        if record.lease_expires_at is None:
            raise _protocol_error("lease owner requires an expiry")
        _parse_aware_timestamp(record.lease_expires_at, "lease_expires_at")

    if not isinstance(record.transitions, tuple):
        raise _protocol_error("transitions must be an immutable tuple")
    for entry in record.transitions:
        if not isinstance(entry, TransitionEntry):
            raise _protocol_error("transitions must contain TransitionEntry values")
        _parse_aware_timestamp(entry.at, "transition.at")
        _validate_identifier(entry.actor, "transition.actor")
        if not isinstance(entry.event, TransactionEvent):
            raise _protocol_error("transition event is invalid")
        if not isinstance(entry.from_state, TransactionState):
            raise _protocol_error("transition from_state is invalid")
        if not isinstance(entry.to_state, TransactionState):
            raise _protocol_error("transition to_state is invalid")

    if record.legacy_state is not None and not record.legacy_state.strip():
        raise _protocol_error("legacy_state must be non-empty when present")
    if record.legacy_dispatch_seq is not None and (
        isinstance(record.legacy_dispatch_seq, bool)
        or not isinstance(record.legacy_dispatch_seq, int)
    ):
        raise _protocol_error("legacy_dispatch_seq must be an integer")
    if record.legacy_raw_hash is not None:
        _validate_hash(record.legacy_raw_hash, "legacy_raw_hash")


def incident_from_violation(
    violation: ProtocolViolation,
    *,
    record: TransactionRecord,
    occurred_at: str,
    request_envelope_hash: str,
) -> CircuitBreakerIncident:
    _validate_record(record)
    _parse_aware_timestamp(occurred_at, "occurred_at")
    _validate_hash(request_envelope_hash, "request_envelope_hash")
    return CircuitBreakerIncident(
        schema_version=SCHEMA_VERSION,
        breaker=violation.breaker,
        occurred_at=occurred_at,
        request_id=record.request_id,
        transaction_key=record.transaction_key,
        state=record.state,
        raw_exception=str(violation),
        request_envelope_hash=request_envelope_hash,
        last_confirmed_side_effect=record.last_side_effect,
    )


def reduce_transaction(
    record: TransactionRecord,
    event: TransactionEvent,
    *,
    actor: str,
    at: str,
    lease_owner: str | None = None,
    lease_expires_at: str | None = None,
    last_side_effect: str | None = None,
) -> TransactionRecord:
    _validate_record(record)
    _validate_identifier(actor, "actor")
    at_value = _parse_aware_timestamp(at, "at")
    if not isinstance(event, TransactionEvent):
        raise _protocol_error("event must be a TransactionEvent")

    if record.state is TransactionState.RECONCILIATION_REQUIRED:
        if event is not TransactionEvent.QUARANTINE or actor not in {
            "founder",
            "overseer-recovery",
        }:
            raise _protocol_error("reconciliation is terminal for automation")
        to_state = TransactionState.QUARANTINED
    elif record.state in {
        TransactionState.CONSUMED,
        TransactionState.QUARANTINED,
    }:
        raise _protocol_error(f"{record.state.value} is terminal")
    elif event is TransactionEvent.SIDE_EFFECT_UNCERTAIN:
        if record.state not in {
            TransactionState.NEW,
            TransactionState.PREPARED,
            TransactionState.CLAIMED,
            TransactionState.RESPONDED,
        }:
            raise _protocol_error("uncertain side effect is invalid from current state")
        to_state = TransactionState.RECONCILIATION_REQUIRED
    elif event is TransactionEvent.QUARANTINE:
        to_state = TransactionState.QUARANTINED
    else:
        try:
            to_state = _TRANSITIONS[(record.state, event)]
        except KeyError as exc:
            raise _protocol_error(
                f"invalid transition {record.state.value} -> {event.value}"
            ) from exc

    next_lease_owner = record.lease_owner
    next_lease_expires_at = record.lease_expires_at
    if event is TransactionEvent.CLAIM:
        if lease_owner is None or not lease_owner.strip():
            raise _protocol_error("CLAIM requires a non-empty lease_owner")
        _validate_identifier(lease_owner, "lease_owner")
        if lease_expires_at is None:
            raise _protocol_error("CLAIM requires lease_expires_at")
        lease_expiry = _parse_aware_timestamp(
            lease_expires_at,
            "lease_expires_at",
        )
        if lease_expiry <= at_value:
            raise _protocol_error("CLAIM lease must expire after transition time")
        next_lease_owner = lease_owner
        next_lease_expires_at = lease_expires_at
    elif event in {TransactionEvent.RESPOND, TransactionEvent.CONSUME}:
        if record.lease_owner is None or record.lease_expires_at is None:
            raise _protocol_error(f"{event.value} requires an active lease")
        lease_expiry = _parse_aware_timestamp(
            record.lease_expires_at,
            "lease_expires_at",
        )
        if lease_expiry <= at_value:
            raise _protocol_error(f"{event.value} lease is stale")
    elif event is TransactionEvent.EXPIRE_LEASE:
        if record.state is not TransactionState.CLAIMED:
            raise _protocol_error("EXPIRE_LEASE requires a CLAIMED transaction")
        if record.lease_owner is None or record.lease_expires_at is None:
            raise _protocol_error("EXPIRE_LEASE requires an active lease")
        next_lease_owner = None
        next_lease_expires_at = None

    entry = TransitionEntry(
        at=at,
        actor=actor,
        event=event,
        from_state=record.state,
        to_state=to_state,
    )
    updated = dataclasses.replace(
        record,
        state=to_state,
        lease_owner=next_lease_owner,
        lease_expires_at=next_lease_expires_at,
        last_side_effect=(
            record.last_side_effect if last_side_effect is None else last_side_effect
        ),
        transitions=(*record.transitions, entry),
    )
    _validate_record(updated)
    return updated


def correlate_response(
    request: RequestEnvelope,
    response: ResponseEnvelope,
    *,
    record: TransactionRecord,
    now: str,
) -> None:
    validate_request(request)
    validate_response(response)
    _validate_record(record)
    now_value = _parse_aware_timestamp(now, "now")
    if now_value >= _parse_aware_timestamp(request.expires_at, "expires_at"):
        raise _protocol_error("request is expired")
    if record.state is not TransactionState.CLAIMED:
        raise _protocol_error("response requires a CLAIMED transaction")
    if record.lease_owner is None or record.lease_expires_at is None:
        raise _protocol_error("CLAIMED transaction has no active lease")
    if now_value >= _parse_aware_timestamp(
        record.lease_expires_at,
        "lease_expires_at",
    ):
        raise _protocol_error("transaction lease is stale")

    for field_name, expected, actual in (
        ("request_id", request.request_id, response.request_id),
        ("transaction_key", request.transaction_key, response.transaction_key),
        ("run_id", request.run_id, response.run_id),
        ("stage_id", request.stage_id, response.stage_id),
        ("payload_hash", request.payload_hash, response.payload_hash),
        ("lease_owner", record.lease_owner, response.lease_owner),
    ):
        if actual != expected:
            raise _protocol_error(f"response {field_name} does not correlate")

    for field_name, expected, actual in (
        ("record.request_id", request.request_id, record.request_id),
        ("record.transaction_key", request.transaction_key, record.transaction_key),
        ("record.run_id", request.run_id, record.run_id),
        ("record.stage_id", request.stage_id, record.stage_id),
        ("record.payload_hash", request.payload_hash, record.payload_hash),
    ):
        if actual != expected:
            raise _protocol_error(f"{field_name} does not correlate")

    if response.disposition not in request.allowed_dispositions:
        raise _protocol_error("response disposition is not allowed")
    if (
        request.worker_model_family.strip().lower()
        == response.overseer_model_family.strip().lower()
    ):
        raise _protocol_error("Builder and Auditor model families must differ")


def _mapping_string(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise _protocol_error(f"{key} must be a string")
    return value


def migrate_legacy_transaction(
    raw: Mapping[str, object],
    *,
    at: str,
) -> TransactionRecord:
    _parse_aware_timestamp(at, "at")
    legacy_state = _mapping_string(raw, "state")
    if legacy_state not in {"DISPATCHING", "SUBMITTED"}:
        raise _protocol_error(f"unknown legacy outbound state {legacy_state!r}")
    dispatch_seq = raw.get("dispatch_seq")
    if isinstance(dispatch_seq, bool) or not isinstance(dispatch_seq, int):
        raise _protocol_error("legacy dispatch_seq must be an integer")

    request_id = _mapping_string(raw, "request_id")
    transaction_id = _mapping_string(raw, "transaction_key")
    run_id = _mapping_string(raw, "run_id")
    stage_id = _mapping_string(raw, "stage_id")
    payload_hash = _mapping_string(raw, "payload_hash")
    _validate_identifier(request_id, "request_id")
    _validate_identifier(run_id, "run_id")
    _validate_identifier(stage_id, "stage_id")
    _validate_hash(transaction_id, "transaction_key")
    _validate_hash(payload_hash, "payload_hash")

    entry = TransitionEntry(
        at=at,
        actor="legacy-migration",
        event=TransactionEvent.SIDE_EFFECT_UNCERTAIN,
        from_state=TransactionState.NEW,
        to_state=TransactionState.RECONCILIATION_REQUIRED,
    )
    record = TransactionRecord(
        schema_version=SCHEMA_VERSION,
        request_id=request_id,
        transaction_key=transaction_id,
        run_id=run_id,
        stage_id=stage_id,
        payload_hash=payload_hash,
        state=TransactionState.RECONCILIATION_REQUIRED,
        transitions=(entry,),
        legacy_state=legacy_state,
        legacy_dispatch_seq=dispatch_seq,
        legacy_raw_hash=content_hash(canonical_json(raw)),
    )
    _validate_record(record)
    return record


def _json_object_from_bytes(raw: bytes, *, source: str) -> dict[str, object]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _protocol_error(f"{source} is not valid UTF-8") from exc
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _protocol_error(f"{source} contains malformed JSON") from exc
    if not isinstance(parsed, dict):
        raise _protocol_error(f"{source} must contain a JSON object")
    return cast(dict[str, object], parsed)


def _optional_mapping_string(
    raw: Mapping[str, object],
    key: str,
) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise _protocol_error(f"{key} must be a string or null")
    return value


def _transition_from_mapping(raw: Mapping[str, object]) -> TransitionEntry:
    try:
        event = TransactionEvent(_mapping_string(raw, "event"))
        from_state = TransactionState(_mapping_string(raw, "from_state"))
        to_state = TransactionState(_mapping_string(raw, "to_state"))
    except ValueError as exc:
        raise _protocol_error("stored transition contains an invalid enum") from exc
    entry = TransitionEntry(
        at=_mapping_string(raw, "at"),
        actor=_mapping_string(raw, "actor"),
        event=event,
        from_state=from_state,
        to_state=to_state,
    )
    _parse_aware_timestamp(entry.at, "transition.at")
    _validate_identifier(entry.actor, "transition.actor")
    return entry


def _record_from_mapping(raw: Mapping[str, object]) -> TransactionRecord:
    try:
        state = TransactionState(_mapping_string(raw, "state"))
    except ValueError as exc:
        raise _protocol_error("stored transaction state is invalid") from exc

    raw_transitions = raw.get("transitions")
    if not isinstance(raw_transitions, list):
        raise _protocol_error("stored transitions must be a list")
    transitions: list[TransitionEntry] = []
    for item in raw_transitions:
        if not isinstance(item, Mapping):
            raise _protocol_error("stored transition must be an object")
        transitions.append(_transition_from_mapping(cast(Mapping[str, object], item)))

    legacy_dispatch_seq = raw.get("legacy_dispatch_seq")
    if legacy_dispatch_seq is not None and (
        isinstance(legacy_dispatch_seq, bool) or not isinstance(legacy_dispatch_seq, int)
    ):
        raise _protocol_error("legacy_dispatch_seq must be an integer or null")

    record = TransactionRecord(
        schema_version=_mapping_string(raw, "schema_version"),
        request_id=_mapping_string(raw, "request_id"),
        transaction_key=_mapping_string(raw, "transaction_key"),
        run_id=_mapping_string(raw, "run_id"),
        stage_id=_mapping_string(raw, "stage_id"),
        payload_hash=_mapping_string(raw, "payload_hash"),
        state=state,
        lease_owner=_optional_mapping_string(raw, "lease_owner"),
        lease_expires_at=_optional_mapping_string(raw, "lease_expires_at"),
        last_side_effect=_optional_mapping_string(raw, "last_side_effect"),
        transitions=tuple(transitions),
        legacy_state=_optional_mapping_string(raw, "legacy_state"),
        legacy_dispatch_seq=legacy_dispatch_seq,
        legacy_raw_hash=_optional_mapping_string(raw, "legacy_raw_hash"),
    )
    _validate_record(record)
    return record


def _response_from_mapping(raw: Mapping[str, object]) -> ResponseEnvelope:
    try:
        disposition = Disposition(_mapping_string(raw, "disposition"))
    except ValueError as exc:
        raise _protocol_error("stored response disposition is invalid") from exc
    response = ResponseEnvelope(
        schema_version=_mapping_string(raw, "schema_version"),
        request_id=_mapping_string(raw, "request_id"),
        transaction_key=_mapping_string(raw, "transaction_key"),
        run_id=_mapping_string(raw, "run_id"),
        stage_id=_mapping_string(raw, "stage_id"),
        payload_hash=_mapping_string(raw, "payload_hash"),
        lease_owner=_mapping_string(raw, "lease_owner"),
        overseer_model_provider=_mapping_string(
            raw,
            "overseer_model_provider",
        ),
        overseer_model_id=_mapping_string(raw, "overseer_model_id"),
        overseer_model_family=_mapping_string(
            raw,
            "overseer_model_family",
        ),
        disposition=disposition,
        response_text=_mapping_string(raw, "response_text"),
        response_hash=_mapping_string(raw, "response_hash"),
        source_task_id=_mapping_string(raw, "source_task_id"),
        completed_at=_mapping_string(raw, "completed_at"),
    )
    validate_response(response)
    return response


def _safe_request_id(request_id: str) -> str:
    try:
        _validate_identifier(request_id, "request_id")
    except ProtocolViolation as exc:
        raise ProtocolViolation(
            CircuitBreaker.WRITE_ATTEMPT_OUTSIDE_CURRENT_ALLOWLIST,
            str(exc),
        ) from exc
    return request_id


def _quarantine_bytes(
    paths: BridgePaths,
    *,
    request_id: str,
    raw: bytes,
    violation: ProtocolViolation,
    source: str,
) -> None:
    safe_id = _safe_request_id(request_id)
    raw_hash = hashlib.sha256(raw).hexdigest()
    stem = f"{safe_id}--{raw_hash}"
    raw_path = paths.quarantine / f"{stem}.raw"
    reason_path = paths.quarantine / f"{stem}.reason.json"
    reason = {
        "schema_version": SCHEMA_VERSION,
        "breaker": violation.breaker.value,
        "message": str(violation),
        "request_id": safe_id,
        "raw_hash": raw_hash,
        "source": source,
    }
    with suppress(FileExistsError):
        write_once_bytes(raw_path, raw)
    with suppress(FileExistsError):
        write_once_json(reason_path, reason)


class TransactionStore:
    def __init__(self, paths: BridgePaths) -> None:
        self._paths = paths
        self._paths.ensure()

    def _transaction_path(self, request_id: str) -> Path:
        return self._paths.transactions / f"{_safe_request_id(request_id)}.json"

    def create(self, record: TransactionRecord) -> Path:
        _validate_record(record)
        target = self._transaction_path(record.request_id)
        for candidate in sorted(self._paths.transactions.glob("*.json")):
            existing = self.load_or_quarantine(candidate.stem)
            if (
                existing.transaction_key == record.transaction_key
                and existing.state not in _TERMINAL_STATES
            ):
                raise ProtocolViolation(
                    CircuitBreaker.REPEATED_IDENTICAL_COMMAND_AFTER_SAME_RESULT_WITHOUT_EXPLICIT_RERUN_AUTHORITY,
                    "a nonterminal transaction already has this transaction_key",
                )
        write_once_json(target, record)
        return target

    def load(self, request_id: str) -> TransactionRecord:
        path = self._transaction_path(request_id)
        raw = path.read_bytes()
        data = _json_object_from_bytes(raw, source=str(path))
        return _record_from_mapping(data)

    def load_or_quarantine(self, request_id: str) -> TransactionRecord:
        path = self._transaction_path(request_id)
        raw = path.read_bytes()
        try:
            data = _json_object_from_bytes(raw, source=str(path))
            return _record_from_mapping(data)
        except ProtocolViolation as exc:
            _quarantine_bytes(
                self._paths,
                request_id=request_id,
                raw=raw,
                violation=exc,
                source=str(path),
            )
            raise

    def digest(self, request_id: str) -> str:
        """Return the exact current transaction-file digest for a compare-and-swap save."""

        raw = self._transaction_path(request_id).read_bytes()
        return hashlib.sha256(raw).hexdigest()

    @contextmanager
    def _transaction_lock(self):
        lock_path = self._paths.bridge_root / ".transactions.lock"
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def save(
        self,
        record: TransactionRecord,
        *,
        expected_prior_digest: str | None = None,
    ) -> None:
        if expected_prior_digest is None:
            raise _protocol_error("save requires expected_prior_digest")
        _validate_hash(expected_prior_digest, "expected_prior_digest")
        _validate_record(record)
        target = self._transaction_path(record.request_id)
        with self._transaction_lock():
            if not target.exists():
                raise _protocol_error("save requires an existing transaction record")
            raw = target.read_bytes()
            actual_prior_digest = hashlib.sha256(raw).hexdigest()
            if actual_prior_digest != expected_prior_digest:
                raise _protocol_error(
                    "transaction changed concurrently; reconciliation required"
                )
            existing = _record_from_mapping(
                _json_object_from_bytes(raw, source=str(target))
            )
            if (
                len(record.transitions) != len(existing.transitions) + 1
                or record.transitions[:-1] != existing.transitions
            ):
                raise _protocol_error("save requires exactly one appended reducer transition")

            transition = record.transitions[-1]
            claim_lease_owner = (
                record.lease_owner
                if transition.event is TransactionEvent.CLAIM
                else None
            )
            claim_lease_expires_at = (
                record.lease_expires_at
                if transition.event is TransactionEvent.CLAIM
                else None
            )
            changed_side_effect = (
                record.last_side_effect
                if record.last_side_effect != existing.last_side_effect
                else None
            )
            expected = reduce_transaction(
                existing,
                transition.event,
                actor=transition.actor,
                at=transition.at,
                lease_owner=claim_lease_owner,
                lease_expires_at=claim_lease_expires_at,
                last_side_effect=changed_side_effect,
            )
            if expected != record:
                raise _protocol_error(
                    "save record does not match the pure reducer result"
                )

            payload = (canonical_json(record) + "\n").encode("utf-8")
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=self._paths.transactions,
            )
            temp_path = Path(temp_name)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, target)
            finally:
                with suppress(FileNotFoundError):
                    os.unlink(temp_path)

    def persist_request(self, request: RequestEnvelope) -> Path:
        validate_request(request)
        target = self._paths.requests / (f"{_safe_request_id(request.request_id)}.json")
        write_once_json(target, request)
        return target

    def persist_response(self, response: ResponseEnvelope) -> Path:
        validate_response(response)
        target = self._paths.responses / (f"{_safe_request_id(response.request_id)}.json")
        write_once_json(target, response)
        return target

    def accept_response(
        self,
        request: RequestEnvelope,
        *,
        record: TransactionRecord,
        now: str,
    ) -> ResponseEnvelope:
        validate_request(request)
        response_path = self._paths.responses / (f"{_safe_request_id(request.request_id)}.json")
        if not response_path.exists():
            raise _protocol_error("correlated response does not exist")
        raw = response_path.read_bytes()
        try:
            data = _json_object_from_bytes(raw, source=str(response_path))
            response = _response_from_mapping(data)
            correlate_response(
                request,
                response,
                record=record,
                now=now,
            )
        except ProtocolViolation as exc:
            _quarantine_bytes(
                self._paths,
                request_id=request.request_id,
                raw=raw,
                violation=exc,
                source=str(response_path),
            )
            raise
        return response
