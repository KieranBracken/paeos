"""Tests for lifecycle L01-L19 audit evidence derivation (Gate G Task 1)."""

from __future__ import annotations

from pathlib import Path

from kernel.ledger import Event, LedgerRow


def test_audit_run_unproven_when_empty() -> None:
    from runtime.lifecycle_audit import (
        LayerDisposition,
        LifecycleAuditReport,
        audit_run,
    )

    report = audit_run("R-EMPTY", rows=[], cas=None, repository=Path("."))
    assert isinstance(report, LifecycleAuditReport)
    assert report.run_id == "R-EMPTY"
    assert len(report.layers) == 19
    assert all(layer_ev.disposition == LayerDisposition.UNPROVEN for layer_ev in report.layers)
    assert "UNPROVEN_LAYERS_PRESENT" in report.blocking_reason_codes



def test_audit_run_with_executed_layer() -> None:
    from runtime.lifecycle_audit import (
        LayerDisposition,
        audit_run,
    )

    rows = [
        LedgerRow(
            seq=1,
            timestamp="2026-08-31T00:00:00Z",
            event=Event(
                schema_ver=1,
                kind="STAGE_COMPLETED",
                payload={"run_id": "R-001", "layer": 1, "artifact_hash": "a" * 64},
            ),
            prev_hash="0" * 64,
            row_hash="1" * 64,
        )
    ]
    report = audit_run("R-001", rows=rows, cas=None, repository=Path("."))
    l01 = report.layers[0]
    assert l01.disposition == LayerDisposition.EXECUTED
    assert l01.ledger_sequences == (1,)
