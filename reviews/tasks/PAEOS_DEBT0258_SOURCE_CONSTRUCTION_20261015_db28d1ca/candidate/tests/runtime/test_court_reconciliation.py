"""Tests for Court count reconciliation and model provenance verification (Gate G Task 2)."""

from __future__ import annotations

import pytest
from kernel.ledger import Event, LedgerRow


def test_reconcile_court_counts_from_ledger_rows() -> None:
    from runtime.court_reconciliation import CourtCounts, reconcile_court_counts

    rows = [
        LedgerRow(
            seq=1,
            timestamp="2026-08-31T00:00:00Z",
            event=Event(schema_ver=1, kind="COURT_SEALED", payload={"claim_id": "C-001"}),
            prev_hash="0" * 64,
            row_hash="1" * 64,
        ),
        LedgerRow(
            seq=2,
            timestamp="2026-08-31T00:01:00Z",
            event=Event(schema_ver=1, kind="COURT_REMANDED", payload={"claim_id": "C-002"}),
            prev_hash="1" * 64,
            row_hash="2" * 64,
        ),
        LedgerRow(
            seq=3,
            timestamp="2026-08-31T00:02:00Z",
            event=Event(schema_ver=1, kind="COURT_REMEDIATED", payload={"claim_id": "C-002"}),
            prev_hash="2" * 64,
            row_hash="3" * 64,
        ),
    ]
    counts = reconcile_court_counts(rows)
    assert isinstance(counts, CourtCounts)
    assert counts.sealed == 1
    assert counts.remanded == 1
    assert counts.remediated == 1


def test_verify_builder_auditor_receipts_detects_mismatch() -> None:
    from runtime.court_reconciliation import (
        DecorrelationError,
        verify_builder_auditor_receipts,
    )

    rows = [
        LedgerRow(
            seq=1,
            timestamp="2026-08-31T00:00:00Z",
            event=Event(
                schema_ver=1,
                kind="WORKER_DISPATCHED",
                payload={"run_id": "R-001", "builder_family": "glm"},
            ),
            prev_hash="0" * 64,
            row_hash="1" * 64,
        ),
        LedgerRow(
            seq=2,
            timestamp="2026-08-31T00:01:00Z",
            event=Event(
                schema_ver=1,
                kind="AUDITOR_RECEIPT_CAPTURED",
                payload={"run_id": "R-001", "auditor_family": "glm"},  # Homogeneous!
            ),
            prev_hash="1" * 64,
            row_hash="2" * 64,
        ),
    ]
    with pytest.raises(DecorrelationError, match="same family"):
        verify_builder_auditor_receipts("R-001", rows)


def test_reconcile_court_counts_deduplicates_and_correlates_dispositions() -> None:
    from runtime.court_reconciliation import CourtCounts, reconcile_court_counts

    rows = [
        LedgerRow(
            seq=1,
            timestamp="2026-08-31T00:00:00Z",
            event=Event(schema_ver=1, kind="COURT_SEALED", payload={"claim_id": "C-1"}),
            prev_hash="0" * 64,
            row_hash="1" * 64,
        ),
        LedgerRow(
            seq=2,
            timestamp="2026-08-31T00:00:01Z",
            event=Event(schema_ver=1, kind="COURT_SEALED", payload={"claim_id": "C-1"}),
            prev_hash="1" * 64,
            row_hash="2" * 64,
        ),
        LedgerRow(
            seq=3,
            timestamp="2026-08-31T00:00:02Z",
            event=Event(schema_ver=1, kind="COURT_REMEDIATED", payload={"claim_id": "ORPHAN"}),
            prev_hash="2" * 64,
            row_hash="3" * 64,
        ),
        LedgerRow(
            seq=4,
            timestamp="2026-08-31T00:00:03Z",
            event=Event(schema_ver=1, kind="COURT_REMANDED", payload={"claim_id": "C-2"}),
            prev_hash="3" * 64,
            row_hash="4" * 64,
        ),
        LedgerRow(
            seq=5,
            timestamp="2026-08-31T00:00:04Z",
            event=Event(schema_ver=1, kind="COURT_REMEDIATED", payload={"claim_id": "C-2"}),
            prev_hash="4" * 64,
            row_hash="5" * 64,
        ),
    ]

    assert reconcile_court_counts(rows) == CourtCounts(sealed=1, remanded=1, remediated=1)


def test_verify_builder_auditor_receipts_rejects_unknown_identity() -> None:
    from runtime.court_reconciliation import DecorrelationError, verify_builder_auditor_receipts

    rows = [
        LedgerRow(
            seq=1,
            timestamp="2026-08-31T00:00:00Z",
            event=Event(schema_ver=1, kind="WORKER_DISPATCHED", payload={"run_id": "R-UNKNOWN"}),
            prev_hash="0" * 64,
            row_hash="1" * 64,
        )
    ]

    with pytest.raises(DecorrelationError, match="missing"):
        verify_builder_auditor_receipts("R-UNKNOWN", rows)
