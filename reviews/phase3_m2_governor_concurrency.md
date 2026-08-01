# L17 Constitutional Review — Phase 3 Milestone 2: Exact Metering + Multi-Goal Concurrency

**Date**: 2026-08-01 · **Author role**: Auditor (recommends; the founder ratifies — CER-5).
**Status**: presented for founder ratification. **Not merged.** No kernel/constitution change.

## 1. What was directed

> "Phase 3 Milestone 2: (1) Governor actual-spend metering (charge `RunOutcome.cost` + refund
> unspent allocation to tighten K11 from conservative to exact) and (2) Multi-goal concurrency &
> isolation (parallel goals under the global K11 parent)."

## 2. Part 1 — Exact-spend metering (reserve-then-settle)

**Before:** the `EconomicGovernor` charged the weight-class *ceiling* per run and never gave it
back. Σ *ceilings* ≤ global — safe, but pessimistic: a run that used a third of its ceiling still
consumed the whole ceiling of the global budget, so far fewer runs fit than the budget truly allowed.

**Now:** *reserve-then-settle.* `charge`/`try_admit` still reserve the ceiling **before** the run
(admission stays conservative — nothing can start that can't be afforded). When the run finishes it
reports its **actual** spend on `RunOutcome` (new `spent_tokens` / `spent_wallclock_s`), and the
governor **`settle`s**: it refunds `reserved − actual` per dimension. The running total then tracks
*actual* spend, so **exact** K11 accounting — more real work fits under the same global budget.

Conservation-safety of `settle` (all tested): the refund is **clamped to `[0, reserved]`** (never
credits phantom budget, even on an impossible over-spend); the wallclock refund is **floored** (a
fractional second stays reserved, never released); the **run slot is never refunded** (the `runs`
dimension keeps bounding *how many*, independent of *how much*).

Reporting is **exact on every exit path**. `SoftLoop.run` was refactored so the whole body runs in
`_run_body` and `run()` attaches the `GoalBudget`'s true spend once, via `replace`, to whatever
outcome comes back — seal, remand, or halt. A remand that burned tokens can no longer be
over-refunded (which would have let the governor believe it had budget it had already spent — a
latent K11 under-count). *Test:* `test_governor_settles_actual_spend_so_more_runs_fit_exactly`
(4 runs fit where ceiling-charge fit 2).

## 3. Part 2 — Multi-goal concurrency under the K11 parent

**`ConcurrentScheduler`** runs up to `max_concurrency` goals in parallel, each an **isolated child**
of the one `EconomicGovernor`. The K11 tree is explicit: the governor is the **parent** budget, each
in-flight goal a **child** holding a reserved allocation, and the invariant **Σ children.reserved ≤
parent** holds across arbitrary parallelism because admission is atomic:

- The governor is now **thread-safe**. `try_admit` **fuses check-and-charge under a lock**, so the
  check-then-charge race (two children both passing the check against the same free budget, then
  both charging) is impossible. Every totals mutation (`try_admit`/`charge`/`settle`/`remaining`)
  is taken under that lock.
- **Isolation:** each goal has its own `run_id`, workspace, and `GoalBudget`; each admitted
  allocation is `settle`d exactly once on completion, so one goal's outcome never corrupts another's
  accounting or leaks its reservation.
- **Halt, don't spin (§9.4):** refused with nothing in flight ⇒ `BUDGET_EXHAUSTED`. Refused *with*
  goals running ⇒ not exhausted: it applies **backpressure**, waiting for an in-flight `settle` to
  free budget and retrying — never dropping the goal, never busy-waiting.

*Tests* (deterministic — a `threading.Barrier(3)` proves genuine simultaneity, not interleaving; a
governor that serialized would break the barrier and fail):
`test_concurrent_scheduler_caps_concurrency_at_the_k11_parent_and_halts` (exactly 3 children fit a
300/ceiling-100 parent, the rest halt, Σ reserved == parent) and
`test_concurrent_scheduler_runs_all_isolated_under_exact_metering` (9 isolated children, exact spend
tracked). Re-ran 5× — no flakes.

## 4. The architectural finding (CER-1) — the K8 boundary on live concurrency

Falsifying "concurrency just means threading the loop" surfaced a real constitutional boundary:

> The institutional **ledger is single-writer by design (K8)** — one SQLite connection, a
> single-writer guard. Running whole `SoftLoop`s in parallel threads through **one shared ledger**
> would violate K8 (and SQLite's own thread guard) at the mechanism level.

So the constitutionally-correct model is **parallel *generation*, serial *integration*** (FP-1,
PAEOS-0/K8) — which is exactly what this milestone builds: `ConcurrentScheduler` parallelises
**execution** (`run_one`); the governor (the shared parent) is made thread-safe; **integration into
the single-writer ledger is deliberately *not* parallelised**. `run_one` must be safe to call from a
worker thread, and the driver owns serialization of the commit.

**Derived, not invented (CER-6):** wiring a *live* concurrent self-host run therefore forces one of
two integration designs, each with a **kernel touchpoint** that belongs to the founder (CER-5/F2),
so it is **surfaced here, not implemented**:
1. **Serialized shared ledger** — `check_same_thread=False` on the SQLite connection + a commit lock
   (small `kernel/ledger_sqlite.py` change → F2 HARD-LOOP → founder ratification), or
2. **Per-goal isolated ledgers + one Integrator** — each child seals to its own store; a single
   serial Integrator replays seals into the institutional ledger (larger; closest to the PAEOS-1
   Integrator role).

Recommendation (§6) names #1 as the minimal next step. This milestone deliberately ships the
*mechanism* (no kernel change) and leaves the live-integration kernel touchpoint for a ratified
follow-on — mirroring M1, where the scheduler/governor mechanism was built and tested before the
live run.

## 5. Scope, gates, honesty

- **Changed files (four):** `runtime/scheduler.py` (thread-safe governor + `settle` + `try_admit` +
  `ConcurrentScheduler`), `runtime/orchestrator/__init__.py` (`RunOutcome` spend fields + `_run_body`
  refactor), `runtime/triage.py` (`GoalBudget.spent_wallclock`), `tests/runtime/test_scheduler.py`.
- **No kernel or constitution change.** F1 GREEN (kernel 2644/20000), AI-010 Port Independence holds
  (scheduler imports only stdlib + core ports), ruff/pyright clean, **340 tests pass**.
- **Not done this session (honest):** a *live* parallel self-host run — it requires the §4 kernel
  touchpoint, which is the founder's to ratify. The sequential live path (M1) is unaffected;
  `ops/autonomous_run.py` still uses `ContinuousScheduler` (K8-safe) unchanged.

## 6. Recommendation

Ratify Milestone 2 (exact metering + the concurrency mechanism). On ratification: merge the four
files ff-only, verify remote CI green, tag. Then the natural next step is the **live-concurrency
integration** via §4 option 1 (the SQLite single-writer touchpoint) as its own founder-ratified,
F2-gated task — at which point `ops/autonomous_run.py` can offer a `ConcurrentScheduler` mode.
