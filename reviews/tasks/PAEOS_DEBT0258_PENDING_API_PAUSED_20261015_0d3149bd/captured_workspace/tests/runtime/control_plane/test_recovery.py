from __future__ import annotations

from pathlib import Path

import pytest
from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from runtime.control_plane.coordinator import StaleComparison, TransactionCoordinator
from runtime.control_plane.events import SideEffectCertainty
from runtime.control_plane.recovery import RecoveryController
from runtime.control_plane.sqlite_projection import SqliteControlPlaneProjection
from runtime.control_plane.watchdog import RecoveryAction, WatchdogDecision
from runtime.integrations.bridge_protocol import (
    TransactionEvent,
    TransactionRecord,
    TransactionState,
)
from tests.runtime.control_plane.test_projection import command


def case(tmp_path: Path) -> tuple[TransactionCoordinator, Ledger, SqliteControlPlaneProjection]:
    ledger = Ledger(SqliteLedgerStore(tmp_path / "ledger.db"), writer_id="control-plane")
    projection = SqliteControlPlaneProjection(tmp_path / "projection.db")
    return TransactionCoordinator(ledger, projection), ledger, projection


def claimed_case(tmp_path: Path):
    coordinator, ledger, projection = case(tmp_path)
    prepared = coordinator.prepare(
        TransactionRecord(
            schema_version="paeos-bridge-v2",
            request_id="req-001",
            transaction_key="a" * 64,
            run_id="run-001",
            stage_id="L14",
            payload_hash="b" * 64,
        ),
        expected_ledger_head=ledger.head_hash(),
    )
    claimed = coordinator.apply(
        command(
            event=TransactionEvent.CLAIM,
            actor="worker-1",
            at="2026-08-30T10:01:00+00:00",
            expected_prior_digest=prepared.projected_digest,
            fencing_token=2,
            lease_owner="worker-1",
            lease_expires_at="2026-08-30T10:05:00+00:00",
        ),
        expected_ledger_head=prepared.ledger_head,
    )
    return coordinator, ledger, projection, claimed


def expire_decision(head: str) -> WatchdogDecision:
    return WatchdogDecision(
        request_id="req-001",
        transaction_key="a" * 64,
        fencing_token=2,
        action=RecoveryAction.EXPIRE_PRE_SIDE_EFFECT_LEASE,
        reason_code="PRE_SIDE_EFFECT_HARD_STALL",
        observed_ledger_head=head,
        evidence_hashes=(),
        side_effect_certainty=SideEffectCertainty.NOT_ATTEMPTED,
    )


def test_safe_expiry_is_fenced_and_returns_to_prepared(tmp_path: Path) -> None:
    coordinator, ledger, projection, claimed = claimed_case(tmp_path)
    controller = RecoveryController(coordinator, ledger, projection)

    receipt = controller.apply(expire_decision(claimed.ledger_head))

    assert receipt.action is RecoveryAction.EXPIRE_PRE_SIDE_EFFECT_LEASE
    assert receipt.resulting_state is TransactionState.PREPARED
    assert receipt.new_fencing_token == 3
    assert receipt.ledger_seq == 3
    projected = projection.get("req-001", verified_ledger_head=receipt.ledger_head)
    assert projected.record.lease_owner is None


def test_stale_decision_does_not_append_or_replay(tmp_path: Path) -> None:
    coordinator, ledger, projection, claimed = claimed_case(tmp_path)
    controller = RecoveryController(coordinator, ledger, projection)
    first = controller.apply(expire_decision(claimed.ledger_head))
    count = len(ledger.read())

    with pytest.raises(StaleComparison, match="head"):
        controller.apply(expire_decision(claimed.ledger_head))

    assert len(ledger.read()) == count
    assert (
        projection.get("req-001", verified_ledger_head=first.ledger_head).record.state
        is TransactionState.PREPARED
    )


def test_possible_side_effect_never_expires_lease(tmp_path: Path) -> None:
    coordinator, ledger, projection, claimed = claimed_case(tmp_path)
    controller = RecoveryController(coordinator, ledger, projection)
    decision = WatchdogDecision(
        request_id="req-001",
        transaction_key="a" * 64,
        fencing_token=2,
        action=RecoveryAction.REQUIRE_RECONCILIATION,
        reason_code="HARD_STALL_AFTER_POSSIBLE_SIDE_EFFECT",
        observed_ledger_head=claimed.ledger_head,
        evidence_hashes=(),
        side_effect_certainty=SideEffectCertainty.ACCEPTED,
    )

    with pytest.raises(ValueError, match="idempotency"):
        controller.apply(decision)
    assert len(ledger.read()) == 2
    assert (
        projection.get("req-001", verified_ledger_head=claimed.ledger_head).record.state
        is TransactionState.CLAIMED
    )
