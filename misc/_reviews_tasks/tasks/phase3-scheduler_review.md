# Constitutional Implementation Review: [Phase 3 — Stage-19 Scheduler + Economic Governor (K11)]

**Date**: 2026-08-01
**Task**: Stage-19 RESTART continuous scheduler + Economic Governor enforcing K11 budget conservation
(Phase 3 / PAEOS-7 §8 comp 1, §9.4, 7.5 A-7). **Reviewer Role**: Auditor / Builder Self-Adversarial

## Summary of Findings

- **BLOCKER**: 0 · **MAJOR**: 0 · **MINOR**: 0 · **OBSERVATION**: 1

Deliverables (`runtime/scheduler.py`):
- **`EconomicGovernor`** — **K11 at the global level**: Σ admitted per-run allocations ≤ the global
  budget, *per dimension* (tokens · wallclock · runs). `can_admit` refuses a breaching run; `charge`
  raises `BudgetConservationError` if it would exceed the global; `tier()` recommends the cheaper
  model under budget pressure (backpressure).
- **`ContinuousScheduler`** — **stage-19 RESTART**: pulls goals from a source and runs each through the
  soft loop (an injected `run_one`), continuously, governed by K11. On exhaustion it **HALTS — it does
  not spin** (halt-not-spiral, §9.4), reporting `SOURCE_EXHAUSTED` vs `BUDGET_EXHAUSTED`.

Evidence: **334 passed** (+4); ruff clean (clean-cache); pyright 0 errors (strict on `kernel/`);
F1 **2644/20000** (unchanged — F2-SOFT, kernel untouched). Scheduler imports no vendor/adapter
(**AI-010 Port Independence** holds).

## What this delivers

The Phase-3 continuous loop, bounded. The per-goal `GoalBudget` already enforced K11 *within* a run;
the `EconomicGovernor` extends K11 to the **whole schedule** — the parent budget of which each run is
a child, conserved per dimension. The scheduler is the stage-19 RESTART cycle (`RESTART → RE_DERIVE`)
made continuous, with the governor as the economic control that keeps it from spiralling: when the
budget cannot cover the next run, it stops pulling goals rather than looping.

## Evaluation Checklist

### 1. Constitutional Compliance
**PASS.** K11 is enforced by construction: `can_admit` gates admission and `charge` refuses to breach
the global budget, per dimension — the exact "Σ children.allocated ≤ parent.allocated − spent" law.
Halt-not-spiral (§9.4) is the deny-by-default posture applied to scheduling.

### 2. Architectural Drift
**PASS.** The scheduler depends only on an injected `run_one: Intake → RunOutcome` + the governor +
`triage` (for the allocation) — **no vendor, no live coupling** (Port Independence). It composes the
existing soft loop; it adds no authority.

### 3–7. Duplication / Simplicity / Derivation / Debt
**PASS.** Reuses `triage`/`Budget`; the governor is one conservation check per dimension. The three
verbs (`can_admit`/`charge`/`tier`) + the RESTART loop are minimal. No hidden debt.

### 8. Security Implications
**PASS.** Economic safety: an unbounded self-hosting loop is a §7.5 resource-exhaustion vector; the
governor bounds it (halt-not-spiral) and K11 makes over-allocation impossible.

### 9–10. Runtime / Extensibility
**PASS.** `run_one` is the seam a live self-host driver plugs into; a real goal *source* (a queue,
`spec/` backlog) drops in behind `Iterable[Intake]`; `tier()` is the hook a model-tiering runtime
reads.

## Adversary / property pass

1. **K11 conserved** — the governor admits runs only while the sum of allocations fits the global
   budget; a charge past it raises `BudgetConservationError` (tested, per dimension).
2. **Halt-not-spiral** — given a long source and a small budget, the scheduler runs exactly what the
   budget allows and **stops pulling goals** (tested: `ran == ["0","1"]`, `BUDGET_EXHAUSTED`).
3. **Source exhaustion** — with ample budget it runs the whole source and stops `SOURCE_EXHAUSTED`.
4. **Backpressure** — `tier()` flips to `economy` under low budget (tested).

## OBSERVATION

1. **The governor allocates the weight-class *ceiling*, not metered actual spend.** K11 is about
   *allocation* conservation (Σ allocated ≤ global), which this enforces exactly and conservatively.
   Reconciling to *actual* spend (refunding the unspent difference after a run, via a `cost` on
   `RunOutcome`) is a refinement that would let the schedule fit more real work under the same budget —
   a clean follow-on that needs the soft loop to report its total charged cost.

## Action Items
- [ ] **Founder**: ratify the scheduler + governor (F2-SOFT) → merge ff-only, remote CI green, tag.
- [ ] **Follow-on**: meter actual spend (`RunOutcome.cost`) and reconcile the governor to it (refund
      unspent allocation) — tighter economics.
- [ ] **Deployment**: wire `run_one` to the live self-host driver + a real goal source for a live
      continuous run (under the governor).
