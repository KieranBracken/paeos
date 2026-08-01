"""Phase-3 tests — Stage-19 continuous scheduler + Economic Governor (K11, §9.4)."""

from __future__ import annotations

import pytest
from kernel.types import WeightClass
from runtime.orchestrator import Intake, RunOutcome, RunStatus
from runtime.scheduler import (
    BudgetConservationError,
    ContinuousScheduler,
    EconomicGovernor,
    GlobalBudget,
    StopReason,
)
from runtime.task_package import Budget

_BUDGETS = {
    WeightClass.ROUTINE: Budget(100, 60, 2),
    WeightClass.SUBSTANTIAL: Budget(300, 120, 3),
    WeightClass.KERNEL_TOUCHING: Budget(600, 240, 3),
}


def _intake(objective: str = "g") -> Intake:
    return Intake(
        objective=objective, changed_paths=("runtime/x.py",),  # SOFT + verifiable ⇒ ROUTINE
        plan_write_scopes=("runtime/x.py",), builder_evidence=(),
        goal_signature="domain:runtime", verifiable=True, reversible=True,
    )


def _sealed(intake: Intake) -> RunOutcome:
    return RunOutcome(RunStatus.SEALED, "g-" + intake.objective, "sealed")


# ---- Economic Governor: K11 conservation ----------------------------------


def test_governor_conserves_the_global_budget() -> None:
    gov = EconomicGovernor(GlobalBudget(tokens=250, wallclock_s=1000, runs=5))
    alloc = _BUDGETS[WeightClass.ROUTINE]  # 100 tokens
    assert gov.can_admit(alloc)
    gov.charge(alloc)
    gov.charge(alloc)  # 200 <= 250
    assert not gov.can_admit(alloc)  # 300 would breach — refused
    assert gov.remaining().tokens == 50
    with pytest.raises(BudgetConservationError):
        gov.charge(alloc)  # K11: never let Σ allocations exceed the global budget


def test_governor_tier_is_backpressure_under_low_budget() -> None:
    gov = EconomicGovernor(GlobalBudget(tokens=1000, wallclock_s=10_000, runs=100))
    assert gov.tier() == "full"
    for _ in range(8):
        gov.charge(Budget(100, 1, 1))  # spend 800/1000 ⇒ 20% remaining < 25%
    assert gov.tier() == "economy"  # recommend the cheaper model tier


# ---- Continuous scheduler: RESTART loop, halt-not-spiral -------------------


def test_scheduler_runs_until_source_exhausted() -> None:
    gov = EconomicGovernor(GlobalBudget(tokens=10_000, wallclock_s=10_000, runs=100))
    sched = ContinuousScheduler(_sealed, governor=gov, budget_by_class=_BUDGETS)
    report = sched.run([_intake("a"), _intake("b"), _intake("c")])
    assert len(report.outcomes) == 3
    assert report.stop_reason is StopReason.SOURCE_EXHAUSTED


def test_scheduler_halts_not_spins_on_budget_exhaustion() -> None:
    # global 250 tokens; each ROUTINE run allocates 100 ⇒ 2 admitted, the rest refused (halt)
    gov = EconomicGovernor(GlobalBudget(tokens=250, wallclock_s=10_000, runs=100))
    ran: list[str] = []

    def _record(intake: Intake) -> RunOutcome:
        ran.append(intake.objective)
        return _sealed(intake)

    sched = ContinuousScheduler(_record, governor=gov, budget_by_class=_BUDGETS)
    report = sched.run(_intake(str(i)) for i in range(10))  # a long source
    assert len(report.outcomes) == 2  # only what the budget allowed
    assert ran == ["0", "1"]  # the loop HALTED — it did not keep pulling goals
    assert report.stop_reason is StopReason.BUDGET_EXHAUSTED
    assert report.remaining.tokens == 50
