from __future__ import annotations

import json
import subprocess
import sys
import time
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
from runtime.control_plane.projection import ProjectionError
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


def test_competing_processes_commit_exactly_one_claim(tmp_path: Path) -> None:
    """Two real adapter processes cannot append a second claim after a race."""

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
    start = tmp_path / "start"
    child = r"""
import json
import sys
import time
from pathlib import Path

from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from runtime.control_plane.coordinator import TransactionCoordinator
from runtime.control_plane.events import TransactionCommand
from runtime.control_plane.sqlite_projection import SqliteControlPlaneProjection
from runtime.integrations.bridge_protocol import TransactionEvent

state = Path(sys.argv[1])
prior_digest = sys.argv[2]
prior_head = sys.argv[3]
actor = sys.argv[4]
ready = Path(sys.argv[5])
start = Path(sys.argv[6])
result = Path(sys.argv[7])
ready.write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 5.0
while not start.exists() and time.monotonic() < deadline:
    time.sleep(0.001)
try:
    ledger = Ledger(SqliteLedgerStore(state / "ledger.db"), writer_id="control-plane")
    coordinator = TransactionCoordinator(
        ledger,
        SqliteControlPlaneProjection(state / "projection.db"),
    )

    original_append = ledger.append

    def coordinated_append(event):
        if actor == "adapter-two":
            (state / "second-append-entered").write_text("ready", encoding="utf-8")
            deadline = time.monotonic() + 2.0
            while not (state / "first-committed").exists() and time.monotonic() < deadline:
                time.sleep(0.001)
        else:
            deadline = time.monotonic() + 2.0
            while not (state / "second-append-entered").exists() and time.monotonic() < deadline:
                time.sleep(0.001)
        committed_seq = original_append(event)
        if actor == "adapter-one":
            (state / "first-committed").write_text("committed", encoding="utf-8")
        return committed_seq

    ledger.append = coordinated_append
    command = TransactionCommand(
        request_id="req-001",
        transaction_key="a" * 64,
        run_id="run-001",
        stage_id="L14",
        payload_hash="b" * 64,
        event=TransactionEvent.CLAIM,
        actor=actor,
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=prior_digest,
        fencing_token=2,
        lease_owner=actor,
        lease_expires_at="2026-08-30T10:05:00+00:00",
    )
    receipt = coordinator.apply(command, expected_ledger_head=prior_head)
    payload = {"status": "committed", "owner": actor, "seq": receipt.ledger_seq}
except Exception as exc:
    payload = {"status": "rejected", "type": type(exc).__name__, "message": str(exc)}
result.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
"""
    processes: list[subprocess.Popen[str]] = []
    result_paths: list[Path] = []
    try:
        for index, actor in enumerate(("adapter-one", "adapter-two")):
            ready_path = tmp_path / f"ready-{index}"
            result_path = tmp_path / f"result-{index}.json"
            result_paths.append(result_path)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        child,
                        str(tmp_path),
                        prepared.projected_digest,
                        prepared.ledger_head,
                        actor,
                        str(ready_path),
                        str(start),
                        str(result_path),
                    ],
                    text=True,
                )
            )

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not all(
            (tmp_path / f"ready-{index}").exists() for index in range(2)
        ):
            time.sleep(0.005)
        assert all((tmp_path / f"ready-{index}").exists() for index in range(2))
        start.write_text("go", encoding="utf-8")
        assert all(process.wait(timeout=5) == 0 for process in processes)
        outcomes = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    assert sum(item["status"] == "committed" for item in outcomes) == 1
    assert sum(item["status"] == "rejected" for item in outcomes) == 1
    assert len(ledger.read()) == 2
    winner = projection.get(
        "req-001",
        verified_ledger_head=ledger.head_hash(),
    )
    assert winner.record.state is TransactionState.CLAIMED
    assert winner.record.lease_owner in {"adapter-one", "adapter-two"}


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


def test_projection_failure_after_append_rebuilds_without_second_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, ledger, projection = coordinator_case(tmp_path)

    def fail_after_append(*_args: object, **_kwargs: object) -> None:
        raise ProjectionError("injected projection crash")

    monkeypatch.setattr(projection, "apply_committed", fail_after_append)
    receipt = coordinator.prepare(
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

    assert len(ledger.read()) == 1
    assert (
        projection.get("req-001", verified_ledger_head=receipt.ledger_head).record.state
        is TransactionState.PREPARED
    )
