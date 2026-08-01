"""Stage-19 RESTART continuous scheduler + Economic Governor (Phase 3 / K11, §9.4).

The `SoftLoop` runs *one* goal; the **`ContinuousScheduler`** is stage-19 RESTART — it pulls goals
from a source and runs each through the loop **continuously**, under an **`EconomicGovernor`**. The
governor is **K11 (budget conservation) at the global level**: the sum of per-run allocations may
never exceed the global budget, per dimension (tokens · wallclock · runs). When the governor cannot
admit the next run, the scheduler **HALTS — it does not spin** (halt-not-spiral, §9.4), and under
budget pressure it recommends a cheaper model **tier** (backpressure, 7.5 A-7).

The scheduler depends only on an injected `run_one: Intake -> RunOutcome` (the soft-loop driver) and
the governor — no vendor, no live coupling. Tests inject a scripted `run_one`; deployment injects a
self-host driver.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

from kernel.types import WeightClass

from runtime.orchestrator import Intake, RunOutcome
from runtime.task_package import Budget
from runtime.triage import triage

__all__ = [
    "ContinuousScheduler",
    "EconomicGovernor",
    "GlobalBudget",
    "SchedulerReport",
    "StopReason",
]


@dataclass(frozen=True, slots=True)
class GlobalBudget:
    """The scheduler's total budget across all runs — the K11 *parent* allocation, per dimension."""

    tokens: int
    wallclock_s: int
    runs: int


class EconomicGovernor:
    """K11 budget conservation at the global level: Σ admitted allocations ≤ the global budget, per
    dimension. `can_admit` refuses a run whose allocation would breach a dimension; `charge` debits
    an admitted allocation (never letting the sum exceed the global). `tier` is the backpressure
    hint: a cheaper model when the budget runs low (below `economy_below` tokens remaining)."""

    def __init__(self, budget: GlobalBudget, *, economy_below: float = 0.25) -> None:
        self._budget = budget
        self._economy_below = economy_below
        self._tokens = 0
        self._wallclock = 0
        self._runs = 0

    def can_admit(self, allocation: Budget) -> bool:
        return (
            self._tokens + allocation.tokens <= self._budget.tokens
            and self._wallclock + allocation.wallclock_s <= self._budget.wallclock_s
            and self._runs + 1 <= self._budget.runs
        )

    def charge(self, allocation: Budget) -> None:
        """Debit an admitted allocation. Enforces K11: raises if it would exceed the global."""
        if not self.can_admit(allocation):
            raise BudgetConservationError("charge would breach the global budget (K11)")
        self._tokens += allocation.tokens
        self._wallclock += allocation.wallclock_s
        self._runs += 1

    def remaining(self) -> GlobalBudget:
        return GlobalBudget(
            self._budget.tokens - self._tokens,
            self._budget.wallclock_s - self._wallclock,
            self._budget.runs - self._runs,
        )

    def tier(self) -> str:
        """Model-tier hint (backpressure): 'economy' when the token budget runs low, else 'full'."""
        if self._budget.tokens <= 0:
            return "economy"
        remaining_fraction = (self._budget.tokens - self._tokens) / self._budget.tokens
        return "economy" if remaining_fraction < self._economy_below else "full"


class BudgetConservationError(Exception):
    """A charge would make Σ allocations exceed the global budget — the K11 conservation guard."""


class StopReason(Enum):
    SOURCE_EXHAUSTED = "source-exhausted"  # nothing left
    BUDGET_EXHAUSTED = "budget-exhausted"  # governor cannot admit the next run (halt-not-spiral)


@dataclass(frozen=True, slots=True)
class SchedulerReport:
    """The result of a continuous scheduling pass."""

    outcomes: tuple[RunOutcome, ...]
    remaining: GlobalBudget
    stop_reason: StopReason


class ContinuousScheduler:
    """Stage-19 RESTART: pull goals and run each through the soft loop, governed by K11."""

    def __init__(
        self,
        run_one: Callable[[Intake], RunOutcome],
        *,
        governor: EconomicGovernor,
        budget_by_class: Mapping[WeightClass, Budget],
    ) -> None:
        self._run_one = run_one
        self._governor = governor
        self._budget_by_class = budget_by_class

    def _allocation(self, intake: Intake) -> Budget:
        decision = triage(
            changed_paths=intake.changed_paths,
            verifiable=intake.verifiable,
            reversible=intake.reversible,
            budget_by_class=self._budget_by_class,
        )
        return decision.budget

    def run(self, source: Iterable[Intake]) -> SchedulerReport:
        """Run goals until the source is exhausted OR the governor halts the loop."""
        outcomes: list[RunOutcome] = []
        stop = StopReason.SOURCE_EXHAUSTED
        for intake in source:
            allocation = self._allocation(intake)
            if not self._governor.can_admit(allocation):
                stop = StopReason.BUDGET_EXHAUSTED  # halt, do NOT spin (§9.4)
                break
            self._governor.charge(allocation)  # K11: reserve before running
            outcomes.append(self._run_one(intake))
        return SchedulerReport(tuple(outcomes), self._governor.remaining(), stop)
