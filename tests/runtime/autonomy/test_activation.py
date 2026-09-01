"""Tests for activation state evaluation derived from correlated evidence (Gate F Task 1)."""

from __future__ import annotations

from kernel.cas import CAS, InMemoryCasStore
from kernel.ledger import Event, LedgerRow


def _evidence_cas(*names: str) -> CAS:
    cas = CAS(InMemoryCasStore())
    for name in names:
        cas.put(name.encode())
    return cas


def _row(seq: int, kind: str, payload: dict[str, object]) -> LedgerRow:
    return LedgerRow(
        seq=seq,
        timestamp=f"2026-08-31T00:{seq:02d}:00Z",
        event=Event(schema_ver=1, kind=kind, payload=payload),
        prev_hash="0" * 64,
        row_hash=f"{seq:064x}"[-64:],
    )


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
    from runtime.autonomy.activation import (
        ActivationStage,
        evaluate_activation,
    )

    cas = _evidence_cas("probe-1", "probe-2", "probe-3")
    refs = [cas.put(name.encode()) for name in ("probe-1", "probe-2", "probe-3")]

    # Mock rows with probe events
    rows = [
        LedgerRow(
            seq=1,
            timestamp="2026-08-31T00:00:00Z",
            event=Event(
                schema_ver=1,
                kind="ROUTE_PROBE_ADMITTED",
                payload={
                    "route": "google/gemini",
                    "transaction_id": "tx-1",
                    "evidence_hash": refs[0],
                },
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
                payload={
                    "route": "google/gemini",
                    "transaction_id": "tx-2",
                    "evidence_hash": refs[1],
                },
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
                payload={
                    "route": "google/gemini",
                    "transaction_id": "tx-3",
                    "evidence_hash": refs[2],
                },
            ),
            prev_hash="2" * 64,
            row_hash="3" * 64,
        ),
    ]

    decision = evaluate_activation(rows, cas)
    assert decision.counts.admitted_route_probes == 3
    assert decision.stage == ActivationStage.ISOLATED_CANARY


def test_activation_deduplicates_transaction_and_rejects_uncorrelated_claims() -> None:
    from runtime.autonomy.activation import ActivationStage, evaluate_activation

    cas = _evidence_cas("probe")
    evidence = cas.put(b"probe")
    rows = [
        _row(
            1,
            "ROUTE_PROBE_ADMITTED",
            {"route": "google/gemini", "transaction_id": "same", "evidence_hash": evidence},
        ),
        _row(
            2,
            "ROUTE_PROBE_ADMITTED",
            {"route": "google/gemini", "transaction_id": "same", "evidence_hash": evidence},
        ),
        _row(3, "ROUTE_PROBE_ADMITTED", {"route": "worker-prose"}),
    ]

    decision = evaluate_activation(rows, cas)

    assert decision.counts.admitted_route_probes == 1
    assert decision.stage == ActivationStage.SUPERVISED_RECOVERY_ONLY
    assert "MINIMUM_PROBES_OUTSTANDING" in decision.blocking_reason_codes


def test_activation_fails_closed_on_conflicting_transaction_provenance() -> None:
    from runtime.autonomy.activation import ActivationStage, evaluate_activation

    cas = _evidence_cas("a", "b")
    first = cas.put(b"a")
    second = cas.put(b"b")
    rows = [
        _row(
            1,
            "ROUTE_PROBE_ADMITTED",
            {"route": "google/gemini", "transaction_id": "conflict", "evidence_hash": first},
        ),
        _row(
            2,
            "ROUTE_PROBE_ADMITTED",
            {"route": "cline/glm", "transaction_id": "conflict", "evidence_hash": second},
        ),
    ]

    decision = evaluate_activation(rows, cas)

    assert decision.stage == ActivationStage.SUPERVISED_RECOVERY_ONLY
    assert "PROVENANCE_CONFLICT" in decision.blocking_reason_codes


def test_activation_critical_failure_forces_supervised_recovery() -> None:
    from runtime.autonomy.activation import ActivationStage, evaluate_activation

    decision = evaluate_activation(
        [_row(1, "CRITICAL_FAILURE", {"transaction_id": "escape", "reason": "scope escape"})],
        _evidence_cas(),
    )

    assert decision.counts.critical_failures == 1
    assert decision.stage == ActivationStage.SUPERVISED_RECOVERY_ONLY
    assert "CRITICAL_FAILURE_PRESENT" in decision.blocking_reason_codes


def test_activation_does_not_progress_after_critical_escape_even_with_minimums() -> None:
    from runtime.autonomy.activation import ActivationStage, evaluate_activation

    cas = CAS(InMemoryCasStore())
    rows: list[LedgerRow] = []
    seq = 0
    def add(kind: str, tx: str, **payload: object) -> None:
        nonlocal seq
        seq += 1
        ref = cas.put(tx.encode())
        rows.append(_row(seq, kind, {**payload, "transaction_id": tx, "evidence_hash": ref}))

    for index in range(3):
        add("ROUTE_PROBE_ADMITTED", f"probe-{index}", route="cline/glm")
    for index in range(3):
        add("TRACE_A_CANARY_PASSED", f"trace-{index}")
    add("SUPERVISOR_ROTATED", "rotation")
    add("QUOTA_STOP_RECOVERED", "quota")
    add("CRITICAL_FAILURE", "escape", reason="scope escape")

    decision = evaluate_activation(rows, cas)

    assert decision.stage == ActivationStage.SUPERVISED_RECOVERY_ONLY
    assert "CRITICAL_FAILURE_PRESENT" in decision.blocking_reason_codes


def test_activation_requires_founder_authority_for_bootstrap_transition() -> None:
    from runtime.autonomy.activation import ActivationStage, evaluate_activation

    cas = CAS(InMemoryCasStore())
    rows: list[LedgerRow] = []
    for index in range(3):
        ref = cas.put(f"probe-{index}".encode())
        rows.append(
            _row(
                index + 1,
                "ROUTE_PROBE_ADMITTED",
                {"route": "cline/glm", "transaction_id": f"probe-{index}", "evidence_hash": ref},
            )
        )
    for index in range(3):
        ref = cas.put(f"trace-{index}".encode())
        rows.append(
            _row(
                index + 4,
                "TRACE_A_CANARY_PASSED",
                {"transaction_id": f"trace-{index}", "evidence_hash": ref},
            )
        )
    for seq, kind, tx in (
        (7, "SUPERVISOR_ROTATED", "rotation"),
        (8, "QUOTA_STOP_RECOVERED", "quota"),
    ):
        ref = cas.put(tx.encode())
        rows.append(_row(seq, kind, {"transaction_id": tx, "evidence_hash": ref}))
    bootstrap_ref = cas.put(b"bootstrap")
    rows.append(
        _row(
            9,
            "FOUNDER_BOOTSTRAP_SEALED",
            {"transaction_id": "bootstrap", "evidence_hash": bootstrap_ref, "authority": "worker"},
        )
    )

    decision = evaluate_activation(rows, cas)

    assert decision.stage == ActivationStage.AWAITING_FOUNDER_BOOTSTRAP
