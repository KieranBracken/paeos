"""Canonical ledger event codec for control-plane transactions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from kernel.ledger import Event, JsonValue

from runtime.integrations.bridge_protocol import TransactionEvent

CONTROL_PLANE_EVENT_SCHEMA = 1
CONTROL_PLANE_TRANSACTION = "CONTROL_PLANE_TRANSACTION"
INITIAL_TRANSACTION_DIGEST = hashlib.sha256(b"PAEOS-CONTROL-PLANE-EMPTY/v1").hexdigest()


class SideEffectCertainty(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    REJECTED_BEFORE_ACCEPTANCE = "REJECTED_BEFORE_ACCEPTANCE"
    ACCEPTED = "ACCEPTED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True, slots=True)
class DispatchEvidence:
    """Immutable facts captured at the external-dispatch crash boundaries.

    Hashes refer to bytes durably written through the bridge's write-once helper.  The
    evidence is journaled with a transaction event; it is diagnostic fact, not a new
    reducer state.
    """

    request_bytes_persisted: bool = False
    request_bytes_hash: str | None = None
    attempted: bool = False
    accepted: bool = False
    response_bytes_persisted: bool = False
    response_bytes_hash: str | None = None
    response_verified: bool = False

    def __post_init__(self) -> None:
        booleans = (
            self.request_bytes_persisted,
            self.attempted,
            self.accepted,
            self.response_bytes_persisted,
            self.response_verified,
        )
        if any(not isinstance(value, bool) for value in booleans):
            raise TypeError("dispatch evidence flags must be booleans")
        for field_name, value in (
            ("request_bytes_hash", self.request_bytes_hash),
            ("response_bytes_hash", self.response_bytes_hash),
        ):
            if value is not None and (
                len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError(f"{field_name} must be a lowercase 64-character hex digest")
        if self.request_bytes_persisted != (self.request_bytes_hash is not None):
            raise ValueError("request byte persistence must have exactly one content hash")
        if self.response_bytes_persisted != (self.response_bytes_hash is not None):
            raise ValueError("response byte persistence must have exactly one content hash")
        if self.attempted and not self.request_bytes_persisted:
            raise ValueError("dispatch attempt requires durably persisted request bytes")
        if self.accepted and not self.attempted:
            raise ValueError("transport acceptance requires a dispatch attempt")
        if self.response_bytes_persisted and not self.accepted:
            raise ValueError("persisted response bytes require transport acceptance")
        if self.response_verified and not self.response_bytes_persisted:
            raise ValueError("response verification requires persisted response bytes")


@dataclass(frozen=True, slots=True)
class TransactionCommand:
    """One reducer input, fully bound to its expected predecessor and fence."""

    request_id: str
    transaction_key: str
    run_id: str
    stage_id: str
    payload_hash: str
    event: TransactionEvent
    actor: str
    at: str
    expected_prior_digest: str
    fencing_token: int
    lease_owner: str | None = None
    lease_expires_at: str | None = None
    last_side_effect: str | None = None
    side_effect_certainty: SideEffectCertainty = SideEffectCertainty.NOT_ATTEMPTED
    idempotency_key: str | None = None
    dispatch_evidence: DispatchEvidence | None = None


def idempotency_key(
    *,
    transaction_key: str,
    operation: str,
    payload_hash: str,
) -> str:
    """Derive a stable key for one externally visible operation."""

    encoded = "|".join((transaction_key, operation, payload_hash)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def side_effect_retry_eligible(certainty: SideEffectCertainty) -> bool:
    """Return whether a failure is proven safe to retry automatically."""

    return certainty in {
        SideEffectCertainty.NOT_ATTEMPTED,
        SideEffectCertainty.REJECTED_BEFORE_ACCEPTANCE,
    }


def transaction_event(command: TransactionCommand) -> Event:
    """Encode a command as a complete, model-independent ledger event."""

    if not isinstance(command.event, TransactionEvent):
        raise TypeError("command.event must be a TransactionEvent")
    if not isinstance(command.side_effect_certainty, SideEffectCertainty):
        raise TypeError("command.side_effect_certainty must be a SideEffectCertainty")
    if command.dispatch_evidence is not None and not isinstance(
        command.dispatch_evidence, DispatchEvidence
    ):
        raise TypeError("command.dispatch_evidence must be DispatchEvidence or None")
    if command.idempotency_key is not None and (
        len(command.idempotency_key) != 64
        or any(character not in "0123456789abcdef" for character in command.idempotency_key)
    ):
        raise ValueError("idempotency_key must be a lowercase 64-character hex digest")
    if isinstance(command.fencing_token, bool) or not isinstance(command.fencing_token, int):
        raise TypeError("command.fencing_token must be an integer")
    payload: dict[str, JsonValue] = {
        "request_id": command.request_id,
        "transaction_key": command.transaction_key,
        "run_id": command.run_id,
        "stage_id": command.stage_id,
        "payload_hash": command.payload_hash,
        "event": command.event.value,
        "actor": command.actor,
        "at": command.at,
        "expected_prior_digest": command.expected_prior_digest,
        "fencing_token": command.fencing_token,
        "lease_owner": command.lease_owner,
        "lease_expires_at": command.lease_expires_at,
        "last_side_effect": command.last_side_effect,
        "side_effect_certainty": command.side_effect_certainty.value,
        "idempotency_key": command.idempotency_key,
        "dispatch_evidence": (
            None
            if command.dispatch_evidence is None
            else {
                "request_bytes_persisted": command.dispatch_evidence.request_bytes_persisted,
                "request_bytes_hash": command.dispatch_evidence.request_bytes_hash,
                "attempted": command.dispatch_evidence.attempted,
                "accepted": command.dispatch_evidence.accepted,
                "response_bytes_persisted": command.dispatch_evidence.response_bytes_persisted,
                "response_bytes_hash": command.dispatch_evidence.response_bytes_hash,
                "response_verified": command.dispatch_evidence.response_verified,
            }
        ),
    }
    return Event(
        schema_ver=CONTROL_PLANE_EVENT_SCHEMA,
        kind=CONTROL_PLANE_TRANSACTION,
        payload=cast(dict[str, JsonValue], payload),
    )
