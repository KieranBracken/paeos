"""Durability and auditability tests for L17-L19 evolution events."""

from __future__ import annotations

from kernel.ledger import InMemoryLedgerStore, Ledger
from runtime.court import Verdict, VerdictOutcome
from runtime.evolution import EvolutionLayer
from runtime.memory import ScarStore
from runtime.orchestrator import RunOutcome, RunStatus


def _sealed() -> RunOutcome:
    return RunOutcome(RunStatus.SEALED, "goal-sealed", "sealed")


def _remanded() -> RunOutcome:
    verdict = Verdict(
        outcome=VerdictOutcome.REMAND,
        artifact_hash="a" * 64,
        unmet_claims=("builds",),
        detail="not reproduced",
    )
    return RunOutcome(RunStatus.REMANDED, "goal-remanded", "court remanded", verdict=verdict)


def _evolution(ledger: Ledger) -> EvolutionLayer:
    ticks = iter(("t1", "t2", "t3", "t4"))
    return EvolutionLayer(scar_store=ScarStore(), ledger=ledger, clock=lambda: next(ticks))


def test_completed_run_appends_four_ordered_events() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _evolution(ledger).run(
        _sealed(),
        goal_signature="domain:runtime,task:evolution",
        changed_paths=("runtime/evolution.py",),
        run_id="run-sealed",
    )

    events = [row.event for row in ledger.read() if row.event.kind == "EVOLUTION_EVENT"]
    assert [event.payload["layer"] for event in events] == [
        "RETROSPECT",
        "EVOLVE",
        "MEMORY_UPDATE",
        "IMPROVE_RUNTIME",
    ]
    assert all(event.payload["run_id"] == "run-sealed" for event in events)
    assert all(event.payload["goal_id"] == "goal-sealed" for event in events)
    assert all(event.payload["status"] == "SEALED" for event in events)
    assert all("recorded_at=" in str(event.payload["summary"]) for event in events)


def test_failed_run_records_retrospect_failure_status() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _evolution(ledger).run(
        _remanded(),
        goal_signature="domain:runtime,task:evolution",
        changed_paths=("runtime/evolution.py",),
        run_id="run-remanded",
    )

    events = [row.event for row in ledger.read() if row.event.kind == "EVOLUTION_EVENT"]
    assert events
    assert events[0].payload["layer"] == "RETROSPECT"
    assert events[0].payload["run_id"] == "run-remanded"
    assert events[0].payload["goal_id"] == "goal-remanded"
    assert events[0].payload["status"] == "REMANDED"


def test_evolution_events_preserve_ledger_chain() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _evolution(ledger).run(
        _sealed(),
        goal_signature="domain:runtime,task:evolution",
        changed_paths=(),
        run_id="run-chain",
    )
    assert ledger.verify_chain() == ledger.head_hash()
