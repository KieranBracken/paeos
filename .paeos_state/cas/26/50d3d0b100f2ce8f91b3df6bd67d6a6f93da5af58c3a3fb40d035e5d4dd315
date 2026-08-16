"""Triage cost gate + per-goal budget (PAEOS-8 §10 B1.G / K11 / §2.3 ceremony depth).

Triage assigns two things at the start of a run:

  1. **Weight class → ceremony depth (fast/full path).** A change touching the TCB (`kernel/` or
     `constitution/`, via the B0.11 classifier) is **always `KERNEL_TOUCHING` → full path** — an
     agent cannot triage-inflate its way onto the fast path (T6). Otherwise the kernel router's
     `verifiability x reversibility` decides: reversible **and** cheaply verified ⇒ `ROUTINE` →
     **fast path** (Trace-A); else `SUBSTANTIAL` → **full path** (Trace-B). The fast-path *edges*
     themselves are the ratified `ROUTINE` compression edges in `is_legal` (B0.5).

  2. **Budget.** The per-goal budget is assigned **by weight class from policy** — not requested by
     the agent — so a bloated request cannot buy more compute (T6). `GoalBudget` then debits actual
     cost and **halts on breach** (K11 budget conservation): a charge that would exceed tokens,
     wallclock, or retries raises `BudgetExceeded`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from kernel.classifier import classify_paths
from kernel.types import WeightClass

from runtime.task_package import Budget, Cost

__all__ = [
    "BudgetExceeded",
    "GoalBudget",
    "Trace",
    "TriageDecision",
    "triage",
]


class Trace(Enum):
    """Ceremony depth (§2.3): A = fast (Trace-A), B = full (Trace-B)."""

    A = "trace_a"
    B = "trace_b"


@dataclass(frozen=True, slots=True)
class TriageDecision:
    weight_class: WeightClass
    trace: Trace  # A = fast path, B = full path
    budget: Budget


def triage(
    *,
    changed_paths: tuple[str, ...],
    verifiable: bool,
    reversible: bool,
    budget_by_class: Mapping[WeightClass, Budget],
) -> TriageDecision:
    """Assign weight class, ceremony depth, and the policy budget for a run.

    A TCB-touching change is forced to `KERNEL_TOUCHING`/full regardless of the `verifiable`/
    `reversible` claims (T6). The budget comes from `budget_by_class`, not the caller.
    """
    if classify_paths(changed_paths) == "HARD":
        weight_class = WeightClass.KERNEL_TOUCHING  # TCB touch ⇒ full path, no inflation possible
    elif verifiable and reversible:
        weight_class = WeightClass.ROUTINE
    else:
        weight_class = WeightClass.SUBSTANTIAL
    trace = Trace.A if weight_class is WeightClass.ROUTINE else Trace.B
    return TriageDecision(
        weight_class=weight_class, trace=trace, budget=budget_by_class[weight_class]
    )


class BudgetExceeded(Exception):
    """A charge would exceed the per-goal budget — the run halts (K11)."""


class GoalBudget:
    """Tracks spend against a per-goal budget and halts on breach (K11 budget conservation)."""

    def __init__(self, budget: Budget) -> None:
        self._budget = budget
        self._spent_tokens = 0
        self._spent_wallclock = 0.0
        self._retries = 0

    def charge(self, cost: Cost) -> None:
        """Debit `cost`. Raise BudgetExceeded (before mutating) if it would breach the budget."""
        new_tokens = self._spent_tokens + cost.tokens
        new_wallclock = self._spent_wallclock + cost.wallclock_s
        if new_tokens > self._budget.tokens:
            raise BudgetExceeded(
                f"tokens {new_tokens} > budget {self._budget.tokens}"
            )
        if new_wallclock > self._budget.wallclock_s:
            raise BudgetExceeded(
                f"wallclock {new_wallclock}s > budget {self._budget.wallclock_s}s"
            )
        self._spent_tokens = new_tokens
        self._spent_wallclock = new_wallclock

    def charge_retry(self) -> None:
        """Record a retry. Raise BudgetExceeded past the retry budget."""
        if self._retries + 1 > self._budget.retries:
            raise BudgetExceeded(f"retries {self._retries + 1} > budget {self._budget.retries}")
        self._retries += 1

    @property
    def spent_tokens(self) -> int:
        return self._spent_tokens

    @property
    def spent_wallclock(self) -> float:
        return self._spent_wallclock

    @property
    def remaining_tokens(self) -> int:
        return self._budget.tokens - self._spent_tokens
