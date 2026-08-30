from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from runtime.control_plane.coordinator import (
    StaleComparison,
    StaleFence,
    TransactionCoordinator,
)
from runtime.control_plane.sqlite_projection import SqliteControlPlaneProjection
from runtime.integrations.bridge_protocol import (
    TransactionEvent,
    TransactionRecord,
    TransactionState,
)
from tests.runtime.control_plane.test_projection import command


def coordinator_case(
    tmp_path: Path,
) -> tuple[TransactionCoordinator, Ledger, SqliteControlPlaneProjection]:
    ledger = Ledger(SqliteLedgerStore(tmp_path / "ledger.db"), writer_id="control-plane")
    projection = SqliteControlPlaneProjection(tmp_path / "projection.db")
    return TransactionCoordinator(ledger, projection), ledger, projection


def test_prepare_appends_one_canonical_event_and_projects_it(tmp_path: Path) -> None:
    coordinator, ledger, projection = coordinator_case(tmp_path)
    record = TransactionRecord(
        schema_version="paeos-bridge-v2",
        request_id="req-001",
        transaction_key="a" * 64,
        run_id="run-001",
        stage_id="L14",
        payload_hash="b" * 64,
    )

    receipt = coordinator.prepare(record, expected_ledger_head=ledger.head_hash())

    assert receipt.ledger_seq == 1
    assert len(ledger.read()) == 1
    projected = projection.get("req-001", verified_ledger_head=receipt.ledger_head)
    assert projected.record.state is TransactionState.PREPARED
    assert projected.digest == receipt.projected_digest


def test_stale_comparison_does_not_append_a_second_claim(tmp_path: Path) -> None:
    coordinator, ledger, projection = coordinator_case(tmp_path)
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
    claim = command(
        event=TransactionEvent.CLAIM,
        actor="worker",
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=prepared.projected_digest,
        fencing_token=2,
        lease_owner="worker-1",
        lease_expires_at="2026-08-30T10:05:00+00:00",
    )
    committed = coordinator.apply(claim, expected_ledger_head=prepared.ledger_head)
    assert committed.fencing_token == 2
    count_after_first = len(ledger.read())
    with pytest.raises((StaleComparison, StaleFence)):
        coordinator.apply(claim, expected_ledger_head=prepared.ledger_head)
    assert len(ledger.read()) == count_after_first
    assert (
        projection.get("req-001", verified_ledger_head=committed.ledger_head).record.state
        is TransactionState.CLAIMED
    )


def test_old_process_with_newer_fence_is_rejected(tmp_path: Path) -> None:
    coordinator, ledger, _ = coordinator_case(tmp_path)
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
    newer = command(
        event=TransactionEvent.CLAIM,
        actor="worker-new",
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=prepared.projected_digest,
        fencing_token=3,
        lease_owner="worker-new",
        lease_expires_at="2026-08-30T10:05:00+00:00",
    )
    committed = coordinator.apply(newer, expected_ledger_head=prepared.ledger_head)
    stale = replace(newer, fencing_token=2, expected_prior_digest=prepared.projected_digest)
    with pytest.raises(StaleFence):
        coordinator.apply(stale, expected_ledger_head=committed.ledger_head)
    assert len(ledger.read()) == 2


def test_independent_sqlite_connections_share_one_fenced_commit_stream(tmp_path: Path) -> None:
    store_one = SqliteLedgerStore(tmp_path / "ledger.db")
    store_two = SqliteLedgerStore(tmp_path / "ledger.db")
    ledger_one = Ledger(store_one, writer_id="control-plane")
    ledger_two = Ledger(store_two, writer_id="control-plane")
    coordinator_one = TransactionCoordinator(
        ledger_one,
        SqliteControlPlaneProjection(tmp_path / "projection.db"),
    )
    coordinator_two = TransactionCoordinator(
        ledger_two,
        SqliteControlPlaneProjection(tmp_path / "projection.db"),
    )
    prepared = coordinator_one.prepare(
        TransactionRecord(
            schema_version="paeos-bridge-v2",
            request_id="req-001",
            transaction_key="a" * 64,
            run_id="run-001",
            stage_id="L14",
            payload_hash="b" * 64,
        ),
        expected_ledger_head=ledger_one.head_hash(),
    )
    claim = command(
        event=TransactionEvent.CLAIM,
        actor="worker",
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=prepared.projected_digest,
        fencing_token=2,
        lease_owner="worker-1",
        lease_expires_at="2026-08-30T10:05:00+00:00",
    )
    committed = coordinator_one.apply(claim, expected_ledger_head=prepared.ledger_head)
    with pytest.raises((StaleComparison, StaleFence)):
        coordinator_two.apply(claim, expected_ledger_head=prepared.ledger_head)
    assert committed.ledger_seq == 2
    assert [row.seq for row in ledger_two.read()] == [1, 2]


def test_recover_projection_replays_committed_ledger(tmp_path: Path) -> None:
    coordinator, ledger, projection = coordinator_case(tmp_path)
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
    assert coordinator.recover_projection() == prepared.ledger_head
    assert (
        projection.get("req-001", verified_ledger_head=prepared.ledger_head).record.state
        is TransactionState.PREPARED
    )
