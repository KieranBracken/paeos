"""Phase-3 tests — Stage-19 continuous scheduler + Economic Governor (K11, §9.4)."""

from __future__ import annotations

import threading

import pytest
from kernel.types import WeightClass
from runtime.orchestrator import Intake, RunOutcome, RunStatus
from runtime.scheduler import (
    BudgetConservationError,
    ConcurrentScheduler,
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


def _outcome(
    intake: Intake, *, spent_tokens: int = 100, spent_wallclock: float = 0.0
) -> RunOutcome:
    # spent_tokens defaults to the ROUTINE ceiling (100) — a run that spends its whole allocation,
    # so `settle` refunds nothing and the governor behaves like the old ceiling-charge.
    return RunOutcome(
        RunStatus.SEALED, "g-" + intake.objective, "sealed",
        spent_tokens=spent_tokens, spent_wallclock_s=spent_wallclock,
    )


def _sealed(intake: Intake) -> RunOutcome:
    return _outcome(intake)


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


def test_governor_settles_actual_spend_so_more_runs_fit_exactly() -> None:
    # M2 exact metering: global 250 tokens, ROUTINE ceiling 100, but each run only SPENDS 50.
    # `charge` reserves 100 (admission stays conservative), `settle` refunds the unspent 50, so the
    # running total grows by the ACTUAL 50/run — 4 runs fit (Σ actual 200 ≤ 250) where pure
    # ceiling-charge would admit only 2. Admission still needs full-ceiling headroom, so it halts
    # (never spins) once a 5th reservation would breach.
    gov = EconomicGovernor(GlobalBudget(tokens=250, wallclock_s=10_000, runs=100))
    sched = ContinuousScheduler(
        lambda i: _outcome(i, spent_tokens=50), governor=gov, budget_by_class=_BUDGETS
    )
    report = sched.run(_intake(str(i)) for i in range(10))
    assert len(report.outcomes) == 4  # exact metering fit 4; ceiling-charge would fit only 2
    assert report.stop_reason is StopReason.BUDGET_EXHAUSTED
    assert report.remaining.tokens == 50  # Sum of actual spend = 4 * 50 = 200 charged of 250


def test_governor_settle_never_refunds_the_run_slot_or_overspend() -> None:
    # A run that OVERSPENDS its ceiling (defensive: GoalBudget forbids it, but settle must be safe)
    # refunds nothing, and the run slot is consumed regardless of spend.
    gov = EconomicGovernor(GlobalBudget(tokens=1000, wallclock_s=1000, runs=5))
    alloc = Budget(100, 60, 2)
    gov.charge(alloc)
    gov.settle(alloc, spent_tokens=999, spent_wallclock_s=999.0)  # clamp: refund 0, not negative
    assert gov.remaining().tokens == 900  # full ceiling stays charged
    assert gov.remaining().runs == 4  # the run slot is NOT refunded


# ---- Concurrent scheduler: parallel children under one K11 parent (M2) -----


def test_concurrent_scheduler_caps_concurrency_at_the_k11_parent_and_halts() -> None:
    # global 300 tokens, ROUTINE ceiling 100 ⇒ the K11 parent admits at most 3 concurrent children,
    # regardless of the larger pool (max_concurrency=10). A Barrier(3) proves all three run AT ONCE
    # (a governor that wrongly serialized would break the barrier ⇒ error). Each spends its whole
    # ceiling ⇒ settle refunds nothing ⇒ the 4th/5th can never be admitted ⇒ HALT (not spin).
    gov = EconomicGovernor(GlobalBudget(tokens=300, wallclock_s=100_000, runs=100))
    barrier = threading.Barrier(3, timeout=5)

    def run_one(intake: Intake) -> RunOutcome:
        barrier.wait()  # only returns if 3 children are concurrent; else BrokenBarrierError
        return _outcome(intake, spent_tokens=100)  # spends the full ceiling ⇒ no refund

    sched = ConcurrentScheduler(
        run_one, governor=gov, budget_by_class=_BUDGETS, max_concurrency=10
    )
    report = sched.run(_intake(str(i)) for i in range(5))
    assert len(report.outcomes) == 3  # only three children fit the parent budget
    assert report.stop_reason is StopReason.BUDGET_EXHAUSTED
    assert report.remaining.tokens == 0  # Σ children.reserved == parent (never exceeded)


def test_concurrent_scheduler_runs_all_isolated_under_exact_metering() -> None:
    # Ample parent (1000 tokens); 9 isolated children run concurrently (max 3 at a time), each
    # spending only 30 of its 100 ceiling. All complete; the governor tracks EXACT actual spend.
    gov = EconomicGovernor(GlobalBudget(tokens=1000, wallclock_s=100_000, runs=100))
    seen = set()
    lock = threading.Lock()

    def run_one(intake: Intake) -> RunOutcome:
        with lock:
            seen.add(intake.objective)  # isolation: each child processed once, independently
        return _outcome(intake, spent_tokens=30)

    sched = ConcurrentScheduler(
        run_one, governor=gov, budget_by_class=_BUDGETS, max_concurrency=3
    )
    report = sched.run(_intake(str(i)) for i in range(9))
    assert len(report.outcomes) == 9
    assert seen == {str(i) for i in range(9)}  # every goal ran, exactly once, isolated
    assert report.stop_reason is StopReason.SOURCE_EXHAUSTED
    assert report.remaining.tokens == 1000 - 9 * 30  # exact: Σ actual spend, not Σ ceiling
