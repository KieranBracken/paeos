"""B1.G acceptance tests for triage + per-goal budget (PAEOS-8 §10 / K11).

Routine goal → fast path; kernel-touching → full path; budget breach halts. Adversary T6:
triage-inflation (claiming reversible+verifiable for a kernel change, or requesting more budget)
cannot escape the full path or gain compute.
"""

from __future__ import annotations

import pytest
from kernel.types import WeightClass
from runtime.task_package import Budget, Cost
from runtime.triage import BudgetExceeded, GoalBudget, Trace, triage

_BUDGETS = {
    WeightClass.ROUTINE: Budget(50_000, 300, 1),
    WeightClass.SUBSTANTIAL: Budget(200_000, 900, 2),
    WeightClass.KERNEL_TOUCHING: Budget(400_000, 1800, 3),
}


def _triage(changed_paths: tuple[str, ...], *, verifiable: bool, reversible: bool):
    return triage(
        changed_paths=changed_paths,
        verifiable=verifiable,
        reversible=reversible,
        budget_by_class=_BUDGETS,
    )


# ---- fast / full routing --------------------------------------------------


def test_routine_goal_takes_fast_path() -> None:
    d = _triage(("docs/notes.md",), verifiable=True, reversible=True)
    assert d.weight_class is WeightClass.ROUTINE
    assert d.trace is Trace.A  # fast
    assert d.budget == _BUDGETS[WeightClass.ROUTINE]


def test_soft_but_risky_goal_takes_full_path() -> None:
    d = _triage(("runtime/x.py",), verifiable=False, reversible=True)
    assert d.weight_class is WeightClass.SUBSTANTIAL
    assert d.trace is Trace.B  # full


def test_kernel_touching_goal_takes_full_path() -> None:
    d = _triage(("kernel/ledger.py",), verifiable=True, reversible=True)
    assert d.weight_class is WeightClass.KERNEL_TOUCHING
    assert d.trace is Trace.B  # full


# ---- Adversary T6: triage-inflation -------------------------------------


def test_kernel_change_cannot_be_inflated_onto_the_fast_path() -> None:
    # even claiming reversible + verifiable, a kernel touch is forced to full (classifier wins)
    d = _triage(("kernel/gates.py",), verifiable=True, reversible=True)
    assert d.weight_class is WeightClass.KERNEL_TOUCHING
    assert d.trace is Trace.B


def test_traversal_kernel_touch_still_full_path() -> None:
    d = _triage(("runtime/../kernel/x.py",), verifiable=True, reversible=True)
    assert d.weight_class is WeightClass.KERNEL_TOUCHING


def test_budget_comes_from_policy_not_the_caller() -> None:
    # the caller cannot request a budget; it is fixed by weight class
    d = _triage(("docs/x.md",), verifiable=True, reversible=True)
    assert d.budget is _BUDGETS[WeightClass.ROUTINE]  # the policy budget, not agent-chosen


# ---- per-goal budget: breach halts (K11) ----------------------------------


def test_budget_charges_and_reports_remaining() -> None:
    gb = GoalBudget(Budget(1000, 60, 2))
    gb.charge(Cost(tokens=400, wallclock_s=10.0, model_ver="m"))
    assert gb.spent_tokens == 400
    assert gb.remaining_tokens == 600


def test_token_breach_halts() -> None:
    gb = GoalBudget(Budget(1000, 60, 2))
    with pytest.raises(BudgetExceeded):
        gb.charge(Cost(tokens=1001, wallclock_s=1.0, model_ver="m"))
    assert gb.spent_tokens == 0  # rejected before mutating


def test_wallclock_breach_halts() -> None:
    gb = GoalBudget(Budget(1000, 60, 2))
    with pytest.raises(BudgetExceeded):
        gb.charge(Cost(tokens=1, wallclock_s=61.0, model_ver="m"))


def test_cumulative_breach_halts() -> None:
    gb = GoalBudget(Budget(1000, 60, 2))
    gb.charge(Cost(tokens=700, wallclock_s=10.0, model_ver="m"))
    with pytest.raises(BudgetExceeded):
        gb.charge(Cost(tokens=400, wallclock_s=10.0, model_ver="m"))  # 700+400 > 1000


def test_retry_budget_halts() -> None:
    gb = GoalBudget(Budget(1000, 60, 1))
    gb.charge_retry()  # first retry ok (budget = 1)
    with pytest.raises(BudgetExceeded):
        gb.charge_retry()  # second retry exceeds
