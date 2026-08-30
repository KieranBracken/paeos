"""Canonical ledger event codec for control-plane transactions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import cast

from kernel.ledger import Event, JsonValue

from runtime.integrations.bridge_protocol import TransactionEvent

CONTROL_PLANE_EVENT_SCHEMA = 1
CONTROL_PLANE_TRANSACTION = "CONTROL_PLANE_TRANSACTION"
INITIAL_TRANSACTION_DIGEST = hashlib.sha256(
    b"PAEOS-CONTROL-PLANE-EMPTY/v1"
).hexdigest()


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


def transaction_event(command: TransactionCommand) -> Event:
    """Encode a command as a complete, model-independent ledger event."""

    if not isinstance(command.event, TransactionEvent):
        raise TypeError("command.event must be a TransactionEvent")
    if isinstance(command.fencing_token, bool) or not isinstance(
        command.fencing_token, int
    ):
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
    }
    return Event(
        schema_ver=CONTROL_PLANE_EVENT_SCHEMA,
        kind=CONTROL_PLANE_TRANSACTION,
        payload=cast(dict[str, JsonValue], payload),
    )
