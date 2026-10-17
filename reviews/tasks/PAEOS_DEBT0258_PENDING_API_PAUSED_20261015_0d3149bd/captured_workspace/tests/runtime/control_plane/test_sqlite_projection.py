from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from runtime.control_plane.projection import rebuild_projection
from runtime.control_plane.sqlite_projection import (
    ProjectionCorruption,
    ProjectionHeadMismatch,
    SqliteControlPlaneProjection,
)
from runtime.integrations.bridge_protocol import TransactionEvent, TransactionState
from tests.runtime.control_plane.test_projection import command, row_for


def test_replace_restart_and_claimable_are_ledger_head_bound(tmp_path: Path) -> None:
    first = row_for(command())
    projection_path = tmp_path / "projection.sqlite3"
    projection = SqliteControlPlaneProjection(projection_path)
    projection.replace_from_verified_ledger([first], first.row_hash)

    assert projection.recorded_head() == (1, first.row_hash)
    assert (
        projection.claimable(verified_ledger_head=first.row_hash)[0].record.state
        is TransactionState.PREPARED
    )
    loaded = SqliteControlPlaneProjection(projection_path)
    assert loaded.get("req-001", verified_ledger_head=first.row_hash) == projection.get(
        "req-001", verified_ledger_head=first.row_hash
    )
    with pytest.raises(ProjectionHeadMismatch):
        loaded.claimable(verified_ledger_head="f" * 64)


def test_sqlite_uses_wal_and_full_synchronous_mode(tmp_path: Path) -> None:
    path = tmp_path / "projection.sqlite3"
    SqliteControlPlaneProjection(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2


def test_apply_committed_requires_verified_prior_head_and_supports_crash_gap(
    tmp_path: Path,
) -> None:
    first = row_for(command())
    second_command = command(
        event=TransactionEvent.CLAIM,
        actor="worker",
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=rebuild_projection([first])["req-001"].digest,
        fencing_token=2,
        lease_owner="worker-1",
        lease_expires_at="2026-08-30T10:05:00+00:00",
    )
    second = row_for(second_command, seq=2, prev_hash=first.row_hash)
    projection = SqliteControlPlaneProjection(tmp_path / "projection.sqlite3")
    projection.replace_from_verified_ledger([first], first.row_hash)
    with pytest.raises(ProjectionHeadMismatch):
        projection.apply_committed(second, verified_prior_head="f" * 64)
    assert (
        projection.get("req-001", verified_ledger_head=first.row_hash).record.state
        is TransactionState.PREPARED
    )

    # A ledger append that was not projected leaves the old projection usable only at its old head.
    with pytest.raises(ProjectionHeadMismatch):
        projection.get("req-001", verified_ledger_head=second.row_hash)
    projection.apply_committed(second, verified_prior_head=first.row_hash)
    assert (
        projection.get("req-001", verified_ledger_head=second.row_hash).record.state
        is TransactionState.CLAIMED
    )


def test_replace_rejects_forged_head_or_row(tmp_path: Path) -> None:
    first = row_for(command())
    projection = SqliteControlPlaneProjection(tmp_path / "projection.sqlite3")
    with pytest.raises(ProjectionHeadMismatch):
        projection.replace_from_verified_ledger([first], "f" * 64)

    projection.replace_from_verified_ledger([first], first.row_hash)
    with sqlite3.connect(tmp_path / "projection.sqlite3") as connection:
        connection.execute("UPDATE control_plane_projection_meta SET ledger_head = ?", ("f" * 64,))
        connection.commit()
    with pytest.raises(ProjectionCorruption):
        projection.recorded_head()

    with sqlite3.connect(tmp_path / "projection.sqlite3") as connection:
        connection.execute(
            "UPDATE control_plane_projection_meta SET ledger_head = ?",
            (first.row_hash,),
        )
        connection.execute("UPDATE control_plane_projection SET digest = ?", ("f" * 64,))
        connection.commit()
    with pytest.raises(ProjectionCorruption):
        projection.claimable(verified_ledger_head=first.row_hash)


def test_missing_or_extra_projection_rows_fail_closed(tmp_path: Path) -> None:
    first = row_for(command())
    path = tmp_path / "projection.sqlite3"
    projection = SqliteControlPlaneProjection(path)
    projection.replace_from_verified_ledger([first], first.row_hash)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "DELETE FROM control_plane_projection WHERE request_id = ?",
            ("req-001",),
        )
        connection.commit()
    with pytest.raises(ProjectionCorruption):
        projection.claimable(verified_ledger_head=first.row_hash)

    projection.replace_from_verified_ledger([first], first.row_hash)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO control_plane_projection "
            "(request_id, transaction_key, ledger_seq, ledger_head, row_hash, row_timestamp, "
            "row_prev_hash, event_json, record_json, digest, fencing_token) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "req-extra",
                "c" * 64,
                1,
                first.row_hash,
                first.row_hash,
                first.timestamp,
                first.prev_hash,
                "{}",
                "{}",
                "d" * 64,
                1,
            ),
        )
        connection.commit()
    with pytest.raises(ProjectionCorruption):
        projection.claimable(verified_ledger_head=first.row_hash)
