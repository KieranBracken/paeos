"""Phase-3 tests — Stage-19 continuous scheduler + Economic Governor (K11, §9.4)."""

from __future__ import annotations

import threading
from dataclasses import replace

import pytest
import runtime.scheduler as scheduler_module
from kernel.types import WeightClass
from runtime.orchestrator import Intake, RunOutcome, RunStatus
from runtime.scheduler import (
    BudgetConservationError,
    ConcurrentScheduler,
    ContinuousScheduler,
    EconomicGovernor,
    GlobalBudget,
    ReadinessHold,
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
        objective=objective,
        changed_paths=("runtime/x.py",),  # SOFT + verifiable ⇒ ROUTINE
        plan_write_scopes=("runtime/x.py",),
        builder_evidence=(),
        goal_signature="domain:runtime",
        verifiable=True,
        reversible=True,
    )


def _outcome(
    intake: Intake, *, spent_tokens: int = 100, spent_wallclock: float = 0.0
) -> RunOutcome:
    # spent_tokens defaults to the ROUTINE ceiling (100) — a run that spends its whole allocation,
    # so `settle` refunds nothing and the governor behaves like the old ceiling-charge.
    return RunOutcome(
        RunStatus.SEALED,
        "g-" + intake.objective,
        "sealed",
        spent_tokens=spent_tokens,
        spent_wallclock_s=spent_wallclock,
    )


def _sealed(intake: Intake) -> RunOutcome:
    return _outcome(intake)


def _synthetic_admissions(monkeypatch, intakes: list[Intake]) -> None:
    """Test-only substitution of the unavailable canonical admission boundary.

    Exact object allowlist, with no production constructor, flag or public positive
    callback. This preserves local budget/queue tests; it proves no runtime authority.
    Every permitted run_one in this file is a side-effect-free scripted callback.
    """
    deny = scheduler_module._admission_hold

    def synthetic(item, probe):
        if any(item is permitted for permitted in intakes):
            return None
        return deny(item, probe)

    monkeypatch.setattr(scheduler_module, "_admission_hold", synthetic)


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


def test_scheduler_runs_until_source_exhausted(monkeypatch) -> None:
    gov = EconomicGovernor(GlobalBudget(tokens=10_000, wallclock_s=10_000, runs=100))
    sched = ContinuousScheduler(_sealed, governor=gov, budget_by_class=_BUDGETS)
    intakes = [_intake("a"), _intake("b"), _intake("c")]
    _synthetic_admissions(monkeypatch, intakes)
    report = sched.run(intakes)
    assert len(report.outcomes) == 3
    assert report.stop_reason is StopReason.SOURCE_EXHAUSTED


def test_scheduler_halts_not_spins_on_budget_exhaustion(monkeypatch) -> None:
    # global 250 tokens; each ROUTINE run allocates 100 ⇒ 2 admitted, the rest refused (halt)
    gov = EconomicGovernor(GlobalBudget(tokens=250, wallclock_s=10_000, runs=100))
    ran: list[str] = []

    def _record(intake: Intake) -> RunOutcome:
        ran.append(intake.objective)
        return _sealed(intake)

    sched = ContinuousScheduler(_record, governor=gov, budget_by_class=_BUDGETS)
    intakes = [_intake(str(i)) for i in range(10)]
    _synthetic_admissions(monkeypatch, intakes)
    report = sched.run(iter(intakes))  # a long source
    assert len(report.outcomes) == 2  # only what the budget allowed
    assert ran == ["0", "1"]  # the loop HALTED — it did not keep pulling goals
    assert report.stop_reason is StopReason.BUDGET_EXHAUSTED
    assert report.remaining.tokens == 50


def test_governor_settles_actual_spend_so_more_runs_fit_exactly(monkeypatch) -> None:
    # M2 exact metering: global 250 tokens, ROUTINE ceiling 100, but each run only SPENDS 50.
    # `charge` reserves 100 (admission stays conservative), `settle` refunds the unspent 50, so the
    # running total grows by the ACTUAL 50/run — 4 runs fit (Σ actual 200 ≤ 250) where pure
    # ceiling-charge would admit only 2. Admission still needs full-ceiling headroom, so it halts
    # (never spins) once a 5th reservation would breach.
    gov = EconomicGovernor(GlobalBudget(tokens=250, wallclock_s=10_000, runs=100))
    sched = ContinuousScheduler(
        lambda i: _outcome(i, spent_tokens=50), governor=gov, budget_by_class=_BUDGETS
    )
    intakes = [_intake(str(i)) for i in range(10)]
    _synthetic_admissions(monkeypatch, intakes)
    report = sched.run(iter(intakes))
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


def test_concurrent_scheduler_caps_concurrency_at_the_k11_parent_and_halts(monkeypatch) -> None:
    # global 300 tokens, ROUTINE ceiling 100 ⇒ the K11 parent admits at most 3 concurrent children,
    # regardless of the larger pool (max_concurrency=10). A Barrier(3) proves all three run AT ONCE
    # (a governor that wrongly serialized would break the barrier ⇒ error). Each spends its whole
    # ceiling ⇒ settle refunds nothing ⇒ the 4th/5th can never be admitted ⇒ HALT (not spin).
    gov = EconomicGovernor(GlobalBudget(tokens=300, wallclock_s=100_000, runs=100))
    barrier = threading.Barrier(3, timeout=5)

    def run_one(intake: Intake) -> RunOutcome:
        barrier.wait()  # only returns if 3 children are concurrent; else BrokenBarrierError
        return _outcome(intake, spent_tokens=100)  # spends the full ceiling ⇒ no refund

    sched = ConcurrentScheduler(run_one, governor=gov, budget_by_class=_BUDGETS, max_concurrency=10)
    intakes = [_intake(str(i)) for i in range(5)]
    _synthetic_admissions(monkeypatch, intakes)
    report = sched.run(iter(intakes))
    assert len(report.outcomes) == 3  # only three children fit the parent budget
    assert report.stop_reason is StopReason.BUDGET_EXHAUSTED
    assert report.remaining.tokens == 0  # Σ children.reserved == parent (never exceeded)


def test_concurrent_scheduler_runs_all_isolated_under_exact_metering(monkeypatch) -> None:
    # Ample parent (1000 tokens); 9 isolated children run concurrently (max 3 at a time), each
    # spending only 30 of its 100 ceiling. All complete; the governor tracks EXACT actual spend.
    gov = EconomicGovernor(GlobalBudget(tokens=1000, wallclock_s=100_000, runs=100))
    seen = set()
    lock = threading.Lock()

    def run_one(intake: Intake) -> RunOutcome:
        with lock:
            seen.add(intake.objective)  # isolation: each child processed once, independently
        return _outcome(intake, spent_tokens=30)

    sched = ConcurrentScheduler(run_one, governor=gov, budget_by_class=_BUDGETS, max_concurrency=3)
    intakes = [_intake(str(i)) for i in range(9)]
    _synthetic_admissions(monkeypatch, intakes)
    report = sched.run(iter(intakes))
    assert len(report.outcomes) == 9
    assert seen == {str(i) for i in range(9)}  # every goal ran, exactly once, isolated
    assert report.stop_reason is StopReason.SOURCE_EXHAUSTED
    assert report.remaining.tokens == 1000 - 9 * 30  # exact: Σ actual spend, not Σ ceiling


@pytest.mark.parametrize("scheduler_type", [ContinuousScheduler, ConcurrentScheduler])
def test_default_scheduler_holds_before_budget_and_invocation(scheduler_type) -> None:
    # R1: removing the denial boundary would invoke work and consume a run slot.
    budget = GlobalBudget(tokens=1000, wallclock_s=1000, runs=10)
    gov = EconomicGovernor(budget)
    invoked: list[Intake] = []
    intake = _intake("unadmitted")

    def record(item: Intake) -> RunOutcome:
        invoked.append(item)
        return _sealed(item)

    report = scheduler_type(record, governor=gov, budget_by_class=_BUDGETS).run([intake])

    assert invoked == []
    assert report.outcomes == ()
    assert report.remaining == budget
    assert report.stop_reason.value == "readiness-held"
    assert report.held[0].intake is intake
    assert report.held[0].reason.value == "missing-readiness"


# R1/R2/R7: callbacks supply negative diagnostics only. Even plausible positive
# shapes must not cause a reserve or dispatch without a real admission adapter.
@pytest.mark.parametrize("scheduler_type", [ContinuousScheduler, ConcurrentScheduler])
@pytest.mark.parametrize(
    ("verdict", "reason"),
    [
        (None, ReadinessHold.MISSING),
        (False, ReadinessHold.INVALID),
        (True, ReadinessHold.INVALID),
        ("Ready", ReadinessHold.INVALID),
        ({"ready": True, "goal_signature": "domain:runtime"}, ReadinessHold.INVALID),
        (
            {"root": "root", "task": "task", "parent": "parent", "attempt": "a", "fence": 1},
            ReadinessHold.INVALID,
        ),
        (ReadinessHold.BLOCKED, ReadinessHold.BLOCKED),
        (ReadinessHold.UNQUALIFIED, ReadinessHold.UNQUALIFIED),
        (ReadinessHold.STALE, ReadinessHold.STALE),
        (ReadinessHold.CONTRADICTORY, ReadinessHold.CONTRADICTORY),
        (ReadinessHold.UNKNOWN, ReadinessHold.UNKNOWN),
        (ReadinessHold.ADMISSION_UNAVAILABLE, ReadinessHold.ADMISSION_UNAVAILABLE),
    ],
)
def test_readiness_diagnostics_never_reserve_or_submit(
    monkeypatch, scheduler_type, verdict, reason
) -> None:
    budget = GlobalBudget(tokens=1000, wallclock_s=1000, runs=10)
    gov = EconomicGovernor(budget)
    intake = _intake("diagnostic-only")
    probed = []

    def forbidden(*args, **kwargs):
        pytest.fail("held intake reached reservation, charge, submission or invocation")

    for name in ("can_admit", "charge", "try_admit"):
        monkeypatch.setattr(gov, name, forbidden)
    monkeypatch.setattr(scheduler_module.ThreadPoolExecutor, "submit", forbidden)

    def probe(item):
        probed.append(item)
        return verdict

    report = scheduler_type(
        forbidden, governor=gov, budget_by_class=_BUDGETS, readiness_probe=probe
    ).run([intake])
    assert probed == [intake]
    assert report.outcomes == ()
    assert report.remaining == budget
    assert report.stop_reason is StopReason.READINESS_HELD
    assert [(hold.intake, hold.reason) for hold in report.held] == [(intake, reason)]


@pytest.mark.parametrize("scheduler_type", [ContinuousScheduler, ConcurrentScheduler])
def test_probe_exception_holds_once_without_exposing_error(scheduler_type) -> None:
    probed = []
    intake = _intake()
    gov = EconomicGovernor(GlobalBudget(1000, 1000, 10))

    def probe(item):
        probed.append(item)
        raise RuntimeError("sensitive error detail")

    report = scheduler_type(
        _sealed, governor=gov, budget_by_class=_BUDGETS, readiness_probe=probe
    ).run([intake])
    assert probed == [intake]
    assert report.outcomes == ()
    assert report.remaining == GlobalBudget(1000, 1000, 10)
    assert report.held[0].reason is ReadinessHold.ERROR
    assert "sensitive" not in repr(report)


@pytest.mark.parametrize("scheduler_type", [ContinuousScheduler, ConcurrentScheduler])
def test_all_held_inputs_are_reported_once_without_retry(scheduler_type) -> None:
    intakes = [_intake("a"), _intake("b")]
    probed = []

    def probe(item):
        probed.append(item)
        return ReadinessHold.BLOCKED

    report = scheduler_type(
        _sealed,
        governor=EconomicGovernor(GlobalBudget(1000, 1000, 10)),
        budget_by_class=_BUDGETS,
        readiness_probe=probe,
    ).run(iter(intakes))
    assert probed == intakes
    assert [hold.intake for hold in report.held] == intakes
    assert report.stop_reason is StopReason.READINESS_HELD
    assert report.outcomes == ()


@pytest.mark.parametrize("scheduler_type", [ContinuousScheduler, ConcurrentScheduler])
def test_empty_source_is_exhausted_without_querying_readiness(scheduler_type) -> None:
    def forbidden(item):
        pytest.fail("empty source queried readiness")

    report = scheduler_type(
        _sealed,
        governor=EconomicGovernor(GlobalBudget(1000, 1000, 10)),
        budget_by_class=_BUDGETS,
        readiness_probe=forbidden,
    ).run([])
    assert report.stop_reason is StopReason.SOURCE_EXHAUSTED
    assert report.held == ()
    assert report.outcomes == ()


@pytest.mark.parametrize("scheduler_type", [ContinuousScheduler, ConcurrentScheduler])
@pytest.mark.parametrize("reason", [ReadinessHold.STALE, ReadinessHold.UNQUALIFIED])
def test_synthetic_parent_cannot_bypass_denial_for_generated_repair(
    monkeypatch, scheduler_type, reason
) -> None:
    # R1/R2/R5: only the parent is synthetically admitted. Its repair returns
    # through the real denial boundary after the parent's completion invalidates it.
    parent, repair = _intake("parent"), _intake("repair")
    _synthetic_admissions(monkeypatch, [parent])
    ran, probed = [], []

    def run_one(item):
        ran.append(item)
        assert item is parent
        return replace(_sealed(item), high_leverage_intake=repair)

    def probe(item):
        assert ran == [parent]
        probed.append(item)
        return reason

    report = scheduler_type(
        run_one,
        governor=EconomicGovernor(GlobalBudget(1000, 1000, 10)),
        budget_by_class=_BUDGETS,
        readiness_probe=probe,
    ).run([parent])
    assert ran == [parent]
    assert probed == [repair]
    assert len(report.outcomes) == 1
    assert report.remaining == GlobalBudget(900, 1000, 9)
    assert report.stop_reason is StopReason.READINESS_HELD
    assert [(hold.intake, hold.reason) for hold in report.held] == [(repair, reason)]


@pytest.mark.parametrize("scheduler_type", [ContinuousScheduler, ConcurrentScheduler])
def test_synthetic_valid_intake_can_progress_after_a_held_one(monkeypatch, scheduler_type) -> None:
    blocked, independent = _intake("blocked"), _intake("independent")
    _synthetic_admissions(monkeypatch, [independent])
    ran = []

    def run_one(item):
        ran.append(item)
        return _sealed(item)

    report = scheduler_type(
        run_one,
        governor=EconomicGovernor(GlobalBudget(1000, 1000, 10)),
        budget_by_class=_BUDGETS,
    ).run([blocked, independent])
    assert ran == [independent]
    assert [hold.intake for hold in report.held] == [blocked]
    assert report.remaining.runs == 9
    assert report.stop_reason is StopReason.READINESS_HELD


@pytest.mark.parametrize("scheduler_type", [ContinuousScheduler, ConcurrentScheduler])
@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("snapshot-changed", ReadinessHold.STALE),
        ("authority-revoked", ReadinessHold.STALE),
        ("scope-incompatible", ReadinessHold.BLOCKED),
        ("attempt-missing", ReadinessHold.INVALID),
        ("duplicate-attempt", ReadinessHold.CONTRADICTORY),
        ("fence-stale", ReadinessHold.STALE),
        ("registry-quarantined", ReadinessHold.BLOCKED),
        ("lineage-contradictory", ReadinessHold.CONTRADICTORY),
        ("acceptance-unknown", ReadinessHold.UNKNOWN),
    ],
)
def test_synthetic_admission_refusal_precedes_second_reservation(
    monkeypatch, scheduler_type, case, reason
) -> None:
    # R5/R6/R7 exercise scheduler consumption of a synthetic canonical refusal,
    # not authentication or atomicity of the nonexistent production adapter.
    intake = _intake(case)
    checked, ran = [], []

    def synthetic(item, probe):
        assert item is intake
        checked.append(item)
        return None if len(checked) == 1 else reason

    monkeypatch.setattr(scheduler_module, "_admission_hold", synthetic)

    def run_one(item):
        ran.append(item)
        return _sealed(item)

    report = scheduler_type(
        run_one,
        governor=EconomicGovernor(GlobalBudget(1000, 1000, 10)),
        budget_by_class=_BUDGETS,
    ).run([intake, intake])
    assert checked == [intake, intake]
    assert ran == [intake]
    assert len(report.outcomes) == 1
    assert report.remaining == GlobalBudget(900, 1000, 9)
    assert report.stop_reason is StopReason.READINESS_HELD
    assert [(hold.intake, hold.reason) for hold in report.held] == [(intake, reason)]


@pytest.mark.parametrize("scheduler_type", [ContinuousScheduler, ConcurrentScheduler])
def test_budget_halt_does_not_erase_prior_holds(monkeypatch, scheduler_type) -> None:
    blocked, candidate = _intake("blocked"), _intake("candidate")
    _synthetic_admissions(monkeypatch, [candidate])
    report = scheduler_type(
        _sealed,
        governor=EconomicGovernor(GlobalBudget(0, 1000, 10)),
        budget_by_class=_BUDGETS,
    ).run([blocked, candidate])
    assert report.outcomes == ()
    assert report.stop_reason is StopReason.BUDGET_EXHAUSTED
    assert [hold.intake for hold in report.held] == [blocked]
    assert report.remaining == GlobalBudget(0, 1000, 10)
