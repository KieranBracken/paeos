"""Pure replay of canonical control-plane transaction ledger events."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from kernel.ledger import GENESIS_HASH, Event, JsonValue, LedgerRow, compute_row_hash

from runtime.control_plane.events import (
    CONTROL_PLANE_EVENT_SCHEMA,
    CONTROL_PLANE_TRANSACTION,
    INITIAL_TRANSACTION_DIGEST,
    DispatchEvidence,
    SideEffectCertainty,
    TransactionCommand,
)
from runtime.integrations.bridge_protocol import (
    SCHEMA_VERSION,
    ProtocolViolation,
    TransactionEvent,
    TransactionRecord,
    reduce_transaction,
)

_COMMAND_KEYS = frozenset(
    {
        "request_id",
        "transaction_key",
        "run_id",
        "stage_id",
        "payload_hash",
        "event",
        "actor",
        "at",
        "expected_prior_digest",
        "fencing_token",
        "lease_owner",
        "lease_expires_at",
        "last_side_effect",
        "side_effect_certainty",
        "idempotency_key",
        "dispatch_evidence",
    }
)


class ProjectionError(RuntimeError):
    """A malformed, stale, conflicting, or unreplayable ledger projection."""


@dataclass(frozen=True, slots=True)
class ProjectedTransaction:
    record: TransactionRecord
    digest: str
    fencing_token: int
    ledger_seq: int
    ledger_head: str


def _fail(message: str) -> ProjectionError:
    return ProjectionError(message)


def _as_string(payload: Mapping[str, JsonValue], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise _fail(f"{key} must be a string")
    return value


def _as_optional_string(payload: Mapping[str, JsonValue], key: str) -> str | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, str):
        raise _fail(f"{key} must be a string or null")
    return value


def _dispatch_evidence(payload: Mapping[str, JsonValue]) -> DispatchEvidence | None:
    raw = payload.get("dispatch_evidence")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise _fail("dispatch_evidence must be an object or null")
    expected_keys = {
        "request_bytes_persisted",
        "request_bytes_hash",
        "attempted",
        "accepted",
        "response_bytes_persisted",
        "response_bytes_hash",
        "response_verified",
    }
    if set(raw) != expected_keys:
        raise _fail("dispatch_evidence is incomplete or contains unknown fields")
    flags: dict[str, bool] = {}
    for key in (
        "request_bytes_persisted",
        "attempted",
        "accepted",
        "response_bytes_persisted",
        "response_verified",
    ):
        value = raw.get(key)
        if not isinstance(value, bool):
            raise _fail(f"dispatch_evidence.{key} must be a boolean")
        flags[key] = value
    request_bytes_hash: str | None = None
    response_bytes_hash: str | None = None
    for key in ("request_bytes_hash", "response_bytes_hash"):
        value = raw.get(key)
        if value is not None and not isinstance(value, str):
            raise _fail(f"dispatch_evidence.{key} must be a string or null")
        if key == "request_bytes_hash":
            request_bytes_hash = value
        else:
            response_bytes_hash = value
    try:
        return DispatchEvidence(
            request_bytes_persisted=flags["request_bytes_persisted"],
            request_bytes_hash=request_bytes_hash,
            attempted=flags["attempted"],
            accepted=flags["accepted"],
            response_bytes_persisted=flags["response_bytes_persisted"],
            response_bytes_hash=response_bytes_hash,
            response_verified=flags["response_verified"],
        )
    except (TypeError, ValueError) as exc:
        raise _fail(str(exc)) from exc


def _as_fence(payload: Mapping[str, JsonValue]) -> int:
    value = payload.get("fencing_token")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _fail("fencing_token must be a positive integer")
    return value


def _command_from_event(event: Event) -> TransactionCommand:
    if event.schema_ver != CONTROL_PLANE_EVENT_SCHEMA:
        raise _fail("unsupported control-plane event schema")
    if event.kind != CONTROL_PLANE_TRANSACTION:
        raise _fail("unknown control-plane event kind")
    payload = event.payload
    if frozenset(payload) != _COMMAND_KEYS:
        raise _fail("control-plane event payload is incomplete or contains unknown fields")
    try:
        event_kind = TransactionEvent(_as_string(payload, "event"))
    except ValueError as exc:
        raise _fail("control-plane event contains an invalid transaction event") from exc
    try:
        certainty = SideEffectCertainty(_as_string(payload, "side_effect_certainty"))
    except ValueError as exc:
        raise _fail("control-plane event contains an invalid side-effect certainty") from exc
    return TransactionCommand(
        request_id=_as_string(payload, "request_id"),
        transaction_key=_as_string(payload, "transaction_key"),
        run_id=_as_string(payload, "run_id"),
        stage_id=_as_string(payload, "stage_id"),
        payload_hash=_as_string(payload, "payload_hash"),
        event=event_kind,
        actor=_as_string(payload, "actor"),
        at=_as_string(payload, "at"),
        expected_prior_digest=_as_string(payload, "expected_prior_digest"),
        fencing_token=_as_fence(payload),
        lease_owner=_as_optional_string(payload, "lease_owner"),
        lease_expires_at=_as_optional_string(payload, "lease_expires_at"),
        last_side_effect=_as_optional_string(payload, "last_side_effect"),
        side_effect_certainty=certainty,
        idempotency_key=_as_optional_string(payload, "idempotency_key"),
        dispatch_evidence=_dispatch_evidence(payload),
    )


def _verify_row(row: LedgerRow) -> None:
    if row.seq < 1:
        raise _fail("ledger sequence must be positive")
    expected = compute_row_hash(row.prev_hash, row.seq, row.timestamp, row.event)
    if expected != row.row_hash:
        raise _fail("ledger row hash does not verify")


def _digest(record: TransactionRecord, fencing_token: int, ledger_seq: int) -> str:
    from runtime.integrations.bridge_protocol import canonical_json

    body = canonical_json(
        {
            "record": record,
            "fencing_token": fencing_token,
            "ledger_seq": ledger_seq,
        }
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _initial_record(command: TransactionCommand) -> TransactionRecord:
    return TransactionRecord(
        schema_version=SCHEMA_VERSION,
        request_id=command.request_id,
        transaction_key=command.transaction_key,
        run_id=command.run_id,
        stage_id=command.stage_id,
        payload_hash=command.payload_hash,
    )


def project_row(
    current: ProjectedTransaction | None,
    row: LedgerRow,
) -> ProjectedTransaction:
    """Apply one verified transaction row through the reviewed reducer."""

    _verify_row(row)
    command = _command_from_event(row.event)
    if current is None:
        if command.expected_prior_digest != INITIAL_TRANSACTION_DIGEST:
            raise _fail("expected_prior_digest does not identify an empty transaction")
        if command.event is not TransactionEvent.PREPARE:
            raise _fail("a new transaction must begin with PREPARE")
        if command.fencing_token != 1:
            raise _fail("first transaction fence must be 1")
        record = _initial_record(command)
        prior_fence = 0
    else:
        if row.seq <= current.ledger_seq:
            raise _fail("ledger sequence is not increasing")
        if command.expected_prior_digest != current.digest:
            raise _fail("expected_prior_digest is stale or does not match projection")
        if command.fencing_token <= current.fencing_token:
            raise _fail("fencing_token is reused or decreasing")
        existing = current.record
        if (
            command.request_id != existing.request_id
            or command.transaction_key != existing.transaction_key
            or command.run_id != existing.run_id
            or command.stage_id != existing.stage_id
            or command.payload_hash != existing.payload_hash
        ):
            raise _fail("transaction identity conflicts with the existing projection")
        record = existing
        prior_fence = current.fencing_token

    if command.fencing_token <= prior_fence:
        raise _fail("fencing_token is reused or decreasing")
    if command.event is TransactionEvent.SIDE_EFFECT_UNCERTAIN:
        if command.side_effect_certainty not in {
            SideEffectCertainty.ACCEPTED,
            SideEffectCertainty.UNCERTAIN,
        }:
            raise _fail("uncertain side effect requires accepted or uncertain certainty")
        if command.idempotency_key is None:
            raise _fail("uncertain side effect requires an idempotency_key")
        if command.dispatch_evidence is None or not command.dispatch_evidence.attempted:
            raise _fail("uncertain side effect requires dispatch attempt evidence")
        if (
            command.side_effect_certainty is SideEffectCertainty.ACCEPTED
            and not command.dispatch_evidence.accepted
        ):
            raise _fail("accepted side effect requires transport acceptance evidence")
    elif command.side_effect_certainty in {
        SideEffectCertainty.ACCEPTED,
        SideEffectCertainty.UNCERTAIN,
    }:
        raise _fail("accepted or uncertain side effect must enter reconciliation")
    if command.idempotency_key is not None:
        if command.last_side_effect != command.idempotency_key:
            raise _fail("idempotency_key must match last_side_effect")
        if current is not None and current.record.last_side_effect == command.idempotency_key:
            raise _fail("idempotency_key was already committed for this transaction")
    try:
        next_record = reduce_transaction(
            record,
            command.event,
            actor=command.actor,
            at=command.at,
            lease_owner=command.lease_owner,
            lease_expires_at=command.lease_expires_at,
            last_side_effect=command.last_side_effect,
        )
    except ProtocolViolation as exc:
        raise _fail(str(exc)) from exc
    return ProjectedTransaction(
        record=next_record,
        digest=_digest(next_record, command.fencing_token, row.seq),
        fencing_token=command.fencing_token,
        ledger_seq=row.seq,
        ledger_head=row.row_hash,
    )


def rebuild_projection(rows: Iterable[LedgerRow]) -> dict[str, ProjectedTransaction]:
    """Verify the complete ledger chain and replay all control-plane rows."""

    projections: dict[str, ProjectedTransaction] = {}
    transaction_keys: dict[str, str] = {}
    side_effect_keys: dict[str, str] = {}
    previous_hash = GENESIS_HASH
    expected_seq = 1
    last_hash = GENESIS_HASH
    for row in rows:
        if row.seq != expected_seq:
            raise _fail("ledger sequence is not dense")
        if row.prev_hash != previous_hash:
            raise _fail("ledger chain predecessor does not match")
        _verify_row(row)
        previous_hash = row.row_hash
        last_hash = row.row_hash
        expected_seq += 1
        if row.event.kind != CONTROL_PLANE_TRANSACTION:
            continue
        command = _command_from_event(row.event)
        if command.idempotency_key is not None:
            prior_request = side_effect_keys.get(command.idempotency_key)
            if prior_request is not None:
                raise _fail("idempotency_key was already committed")
        prior = projections.get(command.request_id)
        if prior is None and command.transaction_key in transaction_keys:
            raise _fail("duplicate transaction_key")
        projected = project_row(prior, row)
        existing_request = transaction_keys.get(projected.record.transaction_key)
        if existing_request is not None and existing_request != command.request_id:
            raise _fail("duplicate transaction_key")
        projections[command.request_id] = projected
        transaction_keys[projected.record.transaction_key] = command.request_id
        if command.idempotency_key is not None:
            side_effect_keys[command.idempotency_key] = command.request_id

    if projections and last_hash != GENESIS_HASH:
        projections = {
            request_id: replace(projected, ledger_head=last_hash)
            for request_id, projected in projections.items()
        }
    return projections
