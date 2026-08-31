"""Tests for activation state evaluation derived from correlated evidence (Gate F Task 1)."""

from __future__ import annotations

from kernel.ledger import LedgerRow


def test_evaluate_activation_defaults_to_supervised_recovery_only() -> None:
    from runtime.autonomy.activation import (
        ActivationDecision,
        ActivationStage,
        evaluate_activation,
    )

    decision = evaluate_activation([])
    assert isinstance(decision, ActivationDecision)
    assert decision.stage == ActivationStage.SUPERVISED_RECOVERY_ONLY
    assert decision.counts.admitted_route_probes == 0
    assert "MINIMUM_PROBES_OUTSTANDING" in decision.blocking_reason_codes


def test_evaluate_activation_progresses_with_probes() -> None:
    from kernel.ledger import Event
    from runtime.autonomy.activation import (
        ActivationStage,
        evaluate_activation,
    )

    # Mock rows with probe events
    rows = [
        LedgerRow(
            seq=1,
            timestamp="2026-08-31T00:00:00Z",
            event=Event(
                schema_ver=1,
                kind="ROUTE_PROBE_ADMITTED",
                payload={"route": "google/gemini"},
            ),
            prev_hash="0" * 64,
            row_hash="1" * 64,
        ),
        LedgerRow(
            seq=2,
            timestamp="2026-08-31T00:01:00Z",
            event=Event(
                schema_ver=1,
                kind="ROUTE_PROBE_ADMITTED",
                payload={"route": "cline/glm"},
            ),
            prev_hash="1" * 64,
            row_hash="2" * 64,
        ),
        LedgerRow(
            seq=3,
            timestamp="2026-08-31T00:02:00Z",
            event=Event(
                schema_ver=1,
                kind="ROUTE_PROBE_ADMITTED",
                payload={"route": "openrouter/free"},
            ),
            prev_hash="2" * 64,
            row_hash="3" * 64,
        ),
    ]

    decision = evaluate_activation(rows)
    assert decision.counts.admitted_route_probes == 3
    assert decision.stage == ActivationStage.ISOLATED_CANARY

