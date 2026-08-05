# PAEOS-IP-0012 — Dynamic Budget Ceiling Elevation Protocol (K11 Mid-Run Elevation)

Status: **RATIFIED BY FOUNDER** (2026-08-05) · Filed: 2026-08-05 · Channel: CER-2
Level: **runtime-governance** (upgrades `runtime/scheduler.py` & `EconomicGovernor` K11 accounting; zero core kernel changes needed).

Source: Founder architectural intent (2026-08-05).

## 1. Observation

In complex or high-depth tasks (e.g. `Heavy` weight-class goals), worker sessions (`PLANNER`, `DESIGNER`, `BUILDER`) may hit their pre-assigned triage budget ceiling mid-run. Currently, when a goal hits its allocated token or wallclock ceiling:
1. The scheduler remands or halts the goal (`BUDGET_EXHAUSTED`), or
2. The agent is forced to take low-quality shortcuts to finish under budget, introducing architectural compromises that get recorded as **Debt Entries**.

This creates a false tradeoff between **completion quality** and **fixed triage estimates**.

## 2. Principle & Tradeoff Analysis

The founder's core insight (2026-08-05):
- **Cost is conserved**: Raising a goal's ceiling does **not** increase total monetary cost or bypass global budget limits. Under K11 reserve-then-settle accounting (Phase 3 Milestone 2), elevating a goal's allocation simply draws additional tokens from the global parent budget pool (`remaining_tokens`).
- **Time is the buffer**: Consuming more allocation runway means global token exhaustion occurs sooner, requiring the operator to wait for the session limit / quota reset. The operator trades **time (waiting longer for reset)** for **higher software quality and zero hasty debt**.

## 3. Proposed Protocol (K11 Mid-Run Budget Elevation)

1. **Mid-Run Elevation Request (`request_budget_elevation`)**:
   When an in-flight worker detects that thorough design, deep planning, or comprehensive test coverage requires more allocation than the initial triage granted, it submits a `request_budget_elevation` event with an additional token delta ($\Delta_{\text{tokens}}$) and rationale.

2. **EconomicGovernor Atomic Re-Admission**:
   The `EconomicGovernor` evaluates whether the parent budget holds $\Delta_{\text{tokens}}$.
   - If affirmative: `governor.charge(\Delta)` reserves the additional ceiling for the goal in-flight, updating its active allocation.
   - If negative: the governor applies backpressure (waiting for another concurrent goal to `settle` and free budget) or halts cleanly (`BUDGET_EXHAUSTED`).

3. **Exact Settlement (`settle`)**:
   On goal completion, `governor.settle(reserved_total, actual_tokens, actual_wallclock)` refunds any unspent portion of the elevated ceiling back to the global pool, maintaining exact K11 conservation.

## 4. Architectural Invariants Preserved

- **K11 Budget Conservation**: $\sum \text{reserved}_{\text{in-flight}} + \sum \text{actual}_{\text{settled}} \le \text{GlobalBudget}$.
- **Zero Kernel Pollution**: Handled entirely in `runtime/scheduler.py` and `EconomicGovernor`; core `kernel/` remains 100% vendor-independent (AI-010).
- **Quality Over Haste (A2)**: Prevents low-quality agent shortcuts by replacing premature remands with explicit budget elevations.

## 5. Status
Drafted for Founder Ratification (2026-08-05).
