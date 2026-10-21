"""Stage-19 RESTART continuous scheduler + Economic Governor (Phase 3 / K11, §9.4).

The `SoftLoop` runs *one* goal; the **`ContinuousScheduler`** is stage-19 RESTART — it pulls goals
from a source and runs each through the loop **continuously**, under an **`EconomicGovernor`**. The
governor is **K11 (budget conservation) at the global level**: the sum of per-run allocations may
never exceed the global budget, per dimension (tokens · wallclock · runs). When the governor cannot
admit the next run, the scheduler **HALTS — it does not spin** (halt-not-spiral, §9.4), and under
budget pressure it recommends a cheaper model **tier** (backpressure, 7.5 A-7).

The scheduler's readiness port supplies negative diagnostics only. No verified canonical C2
admission adapter is composed here, so production dispatch remains unavailable even when a caller
claims readiness. Test-only substitutions exercise queue and budget behavior; they supply no
runtime authority, atomic admission or qualification evidence.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from enum import Enum

from kernel.types import WeightClass

from runtime.orchestrator import Intake, RunOutcome
from runtime.task_package import Budget
from runtime.triage import triage

__all__ = [
    "ConcurrentScheduler",
    "ContinuousScheduler",
    "EconomicGovernor",
    "GlobalBudget",
    "HeldIntake",
    "ReadinessHold",
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
        # The governor is the K11 *parent* shared by concurrently-admitted children (M2). Every
        # mutation of the running totals is taken under this lock, so `try_admit` is atomic and
        # Σ children.reserved ≤ parent holds no matter how many schedulers admit in parallel.
        self._lock = threading.Lock()

    def _can_admit_locked(self, allocation: Budget) -> bool:
        return (
            self._tokens + allocation.tokens <= self._budget.tokens
            and self._wallclock + allocation.wallclock_s <= self._budget.wallclock_s
            and self._runs + 1 <= self._budget.runs
        )

    def can_admit(self, allocation: Budget) -> bool:
        with self._lock:
            return self._can_admit_locked(allocation)

    def try_admit(self, allocation: Budget) -> bool:
        """Atomically admit **and** charge an allocation, or refuse — the concurrency-safe gate.

        Under concurrency the check-then-charge of `can_admit`+`charge` would race (two children
        could both pass the check against the same free budget, then both charge, breaching K11).
        `try_admit` fuses them under the lock: it reserves the allocation iff it fits, so the K11
        parent invariant Σ children.reserved ≤ parent holds across any number of concurrent admits.
        Returns True if reserved (the caller must later `settle`), False if refused (halt-not-spin).
        """
        with self._lock:
            if not self._can_admit_locked(allocation):
                return False
            self._tokens += allocation.tokens
            self._wallclock += allocation.wallclock_s
            self._runs += 1
            return True

    def charge(self, allocation: Budget) -> None:
        """Debit an admitted allocation. Enforces K11: raises if it would exceed the global."""
        with self._lock:
            if not self._can_admit_locked(allocation):
                raise BudgetConservationError("charge would breach the global budget (K11)")
            self._tokens += allocation.tokens
            self._wallclock += allocation.wallclock_s
            self._runs += 1

    def settle(self, reserved: Budget, spent_tokens: int, spent_wallclock_s: float) -> None:
        """Refund unspent portion of reserved budget (M2 actual-spend metering)."""
        spent_t = max(0, min(spent_tokens, reserved.tokens))
        spent_w = max(0.0, min(spent_wallclock_s, float(reserved.wallclock_s)))
        with self._lock:
            self._tokens -= reserved.tokens - spent_t
            self._wallclock -= int(reserved.wallclock_s - spent_w)

    def remaining(self) -> GlobalBudget:
        with self._lock:
            return GlobalBudget(
                self._budget.tokens - self._tokens,
                self._budget.wallclock_s - self._wallclock,
                self._budget.runs - self._runs,
            )

    def tier(self) -> str:
        """Model-tier hint (backpressure): 'economy' when token budget runs low, else 'full'."""
        if self._budget.tokens <= 0:
            return "economy"
        with self._lock:
            remaining_fraction = (self._budget.tokens - self._tokens) / self._budget.tokens
        return "economy" if remaining_fraction < self._economy_below else "full"


class BudgetConservationError(Exception):
    """A charge would make Σ allocations exceed the global budget — the K11 conservation guard."""


class StopReason(Enum):
    SOURCE_EXHAUSTED = "source-exhausted"  # nothing left
    BUDGET_EXHAUSTED = "budget-exhausted"  # governor cannot admit the next run (halt-not-spiral)
    READINESS_HELD = "readiness-held"  # unfinished work, not source completion


class ReadinessHold(Enum):
    """Negative diagnostics only; no member grants execution authority."""

    MISSING = "missing-readiness"
    ERROR = "readiness-error"
    INVALID = "invalid-readiness"
    BLOCKED = "prerequisite-blocked"
    UNQUALIFIED = "prerequisite-unqualified"
    STALE = "stale-readiness"
    CONTRADICTORY = "contradictory-readiness"
    UNKNOWN = "acceptance-unknown"
    ADMISSION_UNAVAILABLE = "canonical-admission-unavailable"


@dataclass(frozen=True, slots=True)
class HeldIntake:
    intake: Intake
    reason: ReadinessHold


def _admission_hold(
    intake: Intake, readiness_probe: Callable[[Intake], object] | None
) -> ReadinessHold:
    """Deny before budget effects; caller readiness can only explain the hold.

    A boolean, metadata shape or caller-supplied Ready is not authenticated admission.
    The missing production adapter must eventually bind current canonical identity,
    authority, prerequisites, attempt, scope, snapshot and fencing atomically with
    the applicable budget reservation. This local port cannot establish that proof.
    """
    if readiness_probe is None:
        return ReadinessHold.MISSING
    try:
        verdict = readiness_probe(intake)
    except Exception:
        return ReadinessHold.ERROR
    if verdict is None:
        return ReadinessHold.MISSING
    if isinstance(verdict, ReadinessHold):
        return verdict
    return ReadinessHold.INVALID


@dataclass(frozen=True, slots=True)
class SchedulerReport:
    """The result of a continuous scheduling pass."""

    outcomes: tuple[RunOutcome, ...]
    remaining: GlobalBudget
    stop_reason: StopReason
    held: tuple[HeldIntake, ...] = ()


def _allocation(intake: Intake, budget_by_class: Mapping[WeightClass, Budget]) -> Budget:
    """The weight-class ceiling this intake reserves — the triage budget it is admitted against."""
    return triage(
        changed_paths=intake.changed_paths,
        verifiable=intake.verifiable,
        reversible=intake.reversible,
        budget_by_class=budget_by_class,
    ).budget


class ContinuousScheduler:
    """Stage-19 RESTART: pull goals and run each through the soft loop, governed by K11."""

    def __init__(
        self,
        run_one: Callable[[Intake], RunOutcome],
        *,
        governor: EconomicGovernor,
        budget_by_class: Mapping[WeightClass, Budget],
        readiness_probe: Callable[[Intake], object] | None = None,
    ) -> None:
        self._run_one = run_one
        self._governor = governor
        self._budget_by_class = budget_by_class
        self._readiness_probe = readiness_probe

    def _allocation(self, intake: Intake) -> Budget:
        return _allocation(intake, self._budget_by_class)

    def run(self, source: Iterable[Intake]) -> SchedulerReport:
        """Run goals until the source is exhausted OR the governor halts the loop."""
        outcomes: list[RunOutcome] = []
        held: list[HeldIntake] = []
        stop = StopReason.SOURCE_EXHAUSTED
        queue = deque(source)
        while queue:
            intake = queue.popleft()
            reason = _admission_hold(intake, self._readiness_probe)
            if reason is not None:
                held.append(HeldIntake(intake, reason))
                continue  # retain the hold; never requeue/retry it in this pass
            allocation = self._allocation(intake)
            if not self._governor.can_admit(allocation):
                stop = StopReason.BUDGET_EXHAUSTED  # halt, do NOT spin (§9.4)
                break
            self._governor.charge(allocation)  # K11: reserve the ceiling before running
            outcome = self._run_one(intake)
            self._governor.settle(allocation, outcome.spent_tokens, outcome.spent_wallclock_s)
            outcomes.append(outcome)
            # RB-0008 §3: Queue high-leverage (>5x) friction repair intakes ahead of goals
            if outcome.high_leverage_intake is not None:
                queue.appendleft(outcome.high_leverage_intake)
        if held and stop is StopReason.SOURCE_EXHAUSTED:
            stop = StopReason.READINESS_HELD
        return SchedulerReport(tuple(outcomes), self._governor.remaining(), stop, tuple(held))


class ConcurrentScheduler:
    """Multi-goal concurrency under the global K11 parent (M2)."""

    def __init__(
        self,
        run_one: Callable[[Intake], RunOutcome],
        *,
        governor: EconomicGovernor,
        budget_by_class: Mapping[WeightClass, Budget],
        max_concurrency: int = 4,
        readiness_probe: Callable[[Intake], object] | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self._run_one = run_one
        self._governor = governor
        self._budget_by_class = budget_by_class
        self._max_concurrency = max_concurrency
        self._readiness_probe = readiness_probe

    def run(self, source: Iterable[Intake]) -> SchedulerReport:
        """Admit and run goals concurrently under the K11 parent until the source is exhausted or
        the governor halts the loop. Outcomes are returned in completion order."""
        it = iter(source)
        pending: deque[Intake] = deque()
        outcomes: list[RunOutcome] = []
        held: list[HeldIntake] = []
        stop = StopReason.SOURCE_EXHAUSTED
        inflight: dict[Future[RunOutcome], Budget] = {}
        holdover: Intake | None = None  # an intake refused under pressure, awaiting freed budget
        source_done = False

        with ThreadPoolExecutor(max_workers=self._max_concurrency) as pool:
            while True:
                # 1) Fill the pool: admit while concurrency slots AND budget allow.
                while not source_done and len(inflight) < self._max_concurrency:
                    if holdover is not None:
                        intake = holdover
                    elif pending:
                        intake = pending.popleft()
                    else:
                        intake = next(it, None)

                    holdover = None
                    if intake is None:
                        source_done = True
                        break
                    reason = _admission_hold(intake, self._readiness_probe)
                    if reason is not None:
                        held.append(HeldIntake(intake, reason))
                        continue
                    allocation = self._allocation(intake)
                    if self._governor.try_admit(allocation):  # atomic reserve (K11 child)
                        inflight[pool.submit(self._run_one, intake)] = allocation
                    elif not inflight:
                        stop = StopReason.BUDGET_EXHAUSTED  # nothing will free budget → HALT
                        source_done = True
                        break
                    else:
                        holdover = intake  # backpressure: wait for a settle, then retry this one
                        break

                # 2) Nothing running ⇒ source exhausted or halted.
                if not inflight:
                    break

                # 3) Wait for ≥1 goal to finish; settle it (frees budget for the next admit).
                done, _ = wait(inflight, return_when=FIRST_COMPLETED)
                for fut in done:
                    allocation = inflight.pop(fut)
                    outcome = fut.result()
                    self._governor.settle(
                        allocation, outcome.spent_tokens, outcome.spent_wallclock_s
                    )
                    outcomes.append(outcome)
                    # RB-0008 §3: Immediate queueing for high-leverage (>5x) friction repair intakes
                    if outcome.high_leverage_intake is not None:
                        pending.appendleft(outcome.high_leverage_intake)
                        source_done = False

        if held and stop is StopReason.SOURCE_EXHAUSTED:
            stop = StopReason.READINESS_HELD
        return SchedulerReport(tuple(outcomes), self._governor.remaining(), stop, tuple(held))

    def _allocation(self, intake: Intake) -> Budget:
        return _allocation(intake, self._budget_by_class)
