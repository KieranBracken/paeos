from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from kernel.ledger import GENESIS_HASH, Event, LedgerRow, compute_row_hash
from runtime.control_plane.events import (
    CONTROL_PLANE_TRANSACTION,
    INITIAL_TRANSACTION_DIGEST,
    TransactionCommand,
    transaction_event,
)
from runtime.control_plane.projection import (
    ProjectionError,
    project_row,
    rebuild_projection,
)
from runtime.integrations.bridge_protocol import (
    TransactionEvent,
    TransactionState,
)


def command(**changes: object) -> TransactionCommand:
    values: dict[str, Any] = {
        "request_id": "req-001",
        "transaction_key": "a" * 64,
        "run_id": "run-001",
        "stage_id": "L14",
        "payload_hash": "b" * 64,
        "event": TransactionEvent.PREPARE,
        "actor": "architect",
        "at": "2026-08-30T10:00:00+00:00",
        "expected_prior_digest": INITIAL_TRANSACTION_DIGEST,
        "fencing_token": 1,
    }
    values.update(changes)
    return TransactionCommand(**values)


def row_for(cmd: TransactionCommand, *, seq: int = 1, prev_hash: str = GENESIS_HASH) -> LedgerRow:
    event = transaction_event(cmd)
    timestamp = f"2026-08-30T10:00:{seq:02d}+00:00"
    return LedgerRow(
        seq=seq,
        timestamp=timestamp,
        event=event,
        prev_hash=prev_hash,
        row_hash=compute_row_hash(prev_hash, seq, timestamp, event),
    )


def test_transaction_event_is_canonical_and_complete() -> None:
    encoded = transaction_event(command())
    assert encoded.schema_ver == 1
    assert encoded.kind == CONTROL_PLANE_TRANSACTION
    assert encoded.payload["event"] == "PREPARE"
    assert encoded.payload["request_id"] == "req-001"
    assert set(encoded.payload) == {
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
    }


def test_projector_folds_exact_happy_path() -> None:
    first = row_for(command())
    projected = project_row(None, first)
    assert projected.record.state is TransactionState.PREPARED
    assert projected.ledger_seq == 1
    assert projected.ledger_head == first.row_hash
    assert projected.fencing_token == 1

    second_command = command(
        event=TransactionEvent.CLAIM,
        actor="worker",
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=projected.digest,
        fencing_token=2,
        lease_owner="worker-1",
        lease_expires_at="2026-08-30T10:05:00+00:00",
    )
    second = row_for(second_command, seq=2, prev_hash=first.row_hash)
    result = project_row(projected, second)
    assert result.record.state is TransactionState.CLAIMED
    assert result.record.lease_owner == "worker-1"
    assert result.fencing_token == 2
    assert result.ledger_seq == 2
    assert rebuild_projection([first, second]) == {"req-001": result}


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"expected_prior_digest": "c" * 64}, "expected_prior_digest"),
        ({"fencing_token": 0}, "fencing_token"),
        ({"fencing_token": 1}, "fencing_token"),
    ],
)
def test_projector_rejects_stale_digest_or_fence(changes: dict[str, object], message: str) -> None:
    first = project_row(None, row_for(command()))
    next_command = command(
        event=TransactionEvent.CLAIM,
        actor="worker",
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=first.digest,
        fencing_token=2,
        lease_owner="worker-1",
        lease_expires_at="2026-08-30T10:05:00+00:00",
    )
    next_command = replace(next_command, **changes)
    with pytest.raises(ProjectionError, match=message):
        project_row(first, row_for(next_command, seq=2, prev_hash=first.ledger_head))


def test_projector_rejects_duplicate_transaction_key() -> None:
    first = row_for(command())
    second = row_for(
        command(request_id="req-002", event=TransactionEvent.PREPARE, fencing_token=1),
        seq=2,
        prev_hash=first.row_hash,
    )
    with pytest.raises(ProjectionError, match="transaction_key"):
        rebuild_projection([first, second])


@pytest.mark.parametrize(
    "bad_event",
    [
        Event(99, CONTROL_PLANE_TRANSACTION, {}),
        Event(1, CONTROL_PLANE_TRANSACTION, {"request_id": "req-001"}),
        Event(1, "UNKNOWN_EVENT", {}),
    ],
)
def test_projector_rejects_malformed_or_unknown_event(bad_event: Event) -> None:
    timestamp = "2026-08-30T10:00:01+00:00"
    row = LedgerRow(
        seq=1,
        timestamp=timestamp,
        event=bad_event,
        prev_hash=GENESIS_HASH,
        row_hash=compute_row_hash(GENESIS_HASH, 1, timestamp, bad_event),
    )
    with pytest.raises(ProjectionError):
        project_row(None, row)


def test_projector_preserves_terminal_states_and_rejects_follow_up() -> None:
    prepared = project_row(None, row_for(command()))
    claimed_command = command(
        event=TransactionEvent.CLAIM,
        actor="worker",
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=prepared.digest,
        fencing_token=2,
        lease_owner="worker-1",
        lease_expires_at="2026-08-30T10:05:00+00:00",
    )
    claimed = project_row(
        prepared,
        row_for(claimed_command, seq=2, prev_hash=prepared.ledger_head),
    )
    uncertain_command = command(
        event=TransactionEvent.SIDE_EFFECT_UNCERTAIN,
        actor="execution-layer",
        at="2026-08-30T10:02:00+00:00",
        expected_prior_digest=claimed.digest,
        fencing_token=3,
        last_side_effect="dispatch:worker-1",
    )
    uncertain = project_row(
        claimed,
        row_for(uncertain_command, seq=3, prev_hash=claimed.ledger_head),
    )
    assert uncertain.record.state is TransactionState.RECONCILIATION_REQUIRED
    quarantine = command(
        event=TransactionEvent.QUARANTINE,
        actor="overseer-recovery",
        at="2026-08-30T10:03:00+00:00",
        expected_prior_digest=uncertain.digest,
        fencing_token=4,
    )
    quarantined = project_row(
        uncertain,
        row_for(quarantine, seq=4, prev_hash=uncertain.ledger_head),
    )
    assert quarantined.record.state is TransactionState.QUARANTINED
    with pytest.raises(ProjectionError, match="terminal"):
        project_row(
            quarantined,
            row_for(
                command(
                    event=TransactionEvent.PREPARE,
                    expected_prior_digest=quarantined.digest,
                    fencing_token=5,
                ),
                seq=5,
                prev_hash=quarantined.ledger_head,
            ),
        )
