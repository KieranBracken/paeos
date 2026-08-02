# Phase 3 M3 — Live Concurrency: Implementation Review

**Date**: 2026-08-02
**Milestone**: Phase 3, M3 — K8 single-writer ratification under parallel generation + live
multi-goal concurrency (`ConcurrentScheduler`).
**Reviewer Role**: Auditor / Self-Adversarial Review
**Branch**: `phase3-m3-live-concurrency` (base `ce23f5e`, "Phase 3 M2: exact-spend metering +
multi-goal concurrency under the K11 parent").

## VERDICT: RATIFIED (code) — LIVE RUN HELD FOR FOUNDER AUTHORIZATION

The concurrency touchpoints are lawful and green. The **genuine live multi-goal concurrent
self-hosting run** was **not** executed: it spawns live `claude` subprocesses and spends real
tokens (configured ceiling 8M tokens / ~20h / 8 runs), an outward-facing, hard-to-reverse action
reserved for explicit Founder authorization. This review ratifies the *mechanism*; the *live seal*
remains pending that authorization.

## Summary of Findings

- **BLOCKER**: 0
- **MAJOR**: 0
- **MINOR**: 0
- **OBSERVATION**: 2
  - O1 — The codebase requires Python ≥ 3.12 (PEP 695 `type` aliases in `kernel/ledger.py`); the
    system default `python` here is 3.10.13 and fails to import. Tests pass only under
    `.venv/bin/python` (3.13.5). Interpreter floor should be pinned/enforced (candidate debt).
  - O2 — The live run is deferred by design, not by defect (see Verdict).

---

## The Touchpoint (K8 under parallel generation)

The principle: **parallel generation, serial integration.** Goals run concurrently, but every
institutional commit onto the ledger's hash chain is strictly serialized, so the chain stays dense
and unforked. Two layers enforce this:

| Layer | File | Mechanism |
|---|---|---|
| Chain integration (K8) | `kernel/ledger.py` | `Ledger.append` wraps read-head → derive-seq → chain-hash → `append_row` in `_append_lock` (`threading.Lock`). Concurrent callers each take the *next* seq in turn. |
| Durable store | `kernel/ledger_sqlite.py` | `check_same_thread=False` lets worker threads share the connection; a reentrant `threading.RLock` (`append_row` calls `count`) serializes **every** connection op, so the non-concurrency-safe SQLite connection is only ever touched by one thread at a time. |
| L3 authoring | `ops/autonomous_run.py` | `evolution_lock` keeps the sole L3 committer (Evolution Layer, IP-0005) serial under parallel execution. |
| Scheduling | `runtime/scheduler.py` (M2, base) | `ConcurrentScheduler` caps in-flight goals at `max_concurrency` under one K11 `EconomicGovernor` parent; `ops/autonomous_run.py` selects it when `max_concurrency > 1`. |

Belt-and-braces is deliberate: the SQLite lock alone would serialize a single connection, but
`_append_lock` also protects the read-head/derive-seq compose step above the store, so correctness
does not depend on which `LedgerStore` backend is installed (in-memory or SQLite).

## Evaluation Checklist

### 1. Constitutional Compliance
- **Status**: PASS
- **Details**: Enforces **K8 single-writer / FR-5** under concurrency without weakening it. No new
  seq is minted outside the lock; fork rejection (`ForkRejected` on duplicate seq PK) is intact and
  is the atomic backstop if any path ever bypassed the lock.

### 2. Architectural Drift
- **Status**: PASS
- **Details**: No new authority, stage, or invariant. `ConcurrentScheduler` runs children under the
  existing K11 `EconomicGovernor` parent; `max_concurrency == 1` collapses to the sequential
  `ContinuousScheduler`. Locks are integration mechanics, not new law.

### 3. Duplication of Mechanisms
- **Status**: PASS
- **Details**: The two locks are non-redundant (different scopes: compose-and-commit vs. raw
  connection). No parallel scheduler/governor was introduced; concurrency is a mode of the M2
  scheduler.

### 4. Bypassing Mechanisms
- **Status**: PASS
- **Details**: No route appends a row without `_append_lock`; `SqliteLedgerStore` exposes no
  unlocked connection accessor. The court/evidence path (`kernel/evidence.py`) still gates on T2.

### 5. Simpler Implementation Possible
- **Status**: PASS
- **Details**: A single global lock would work but couple correctness to the SQLite backend; the
  layered locks keep the `LedgerStore` Protocol backend-agnostic. `_normalized_result`
  (`kernel/evidence.py`) is the minimal fix for CER-1 (below), not a rewrite.

### 6. Better Derivation
- **Status**: PASS
- **Details**: Derived directly from K8 (single-writer) + K11 (budget conservation) + IP-0005 (sole
  L3 committer). No novel derivation.

---

## CER-1 — live-sealing robustness (surfaced by the M2 concurrent run)

`kernel/evidence.py` gained `_normalized_result`: `verify_deterministic` (the T2 gate) now compares
stdout **modulo trailing whitespace**. A live agent reporting `"PASS"` for a command that prints
`"PASS\n"` was being remanded though it reproduced perfectly. Anti-forgery (T2) is preserved: exit
code and stdout *content* are still compared exactly, so a command doing different work still
differs. This is a prerequisite for a genuine live concurrent seal, hence in scope for M3.

## Verification Evidence (run 2026-08-02, `.venv/bin/python` 3.13.5)

```
pytest tests/kernel/test_ledger.py tests/kernel/test_ledger_sqlite.py \
       tests/kernel/test_evidence.py tests/runtime/test_scheduler.py
→ 46 passed
Full suite: pytest -q → all passed (0 failures)
```

Concurrency is proven, not asserted:

- `tests/kernel/test_ledger_sqlite.py::test_concurrent_appends_produce_one_dense_unforked_chain`
  — worker threads append in parallel; result is one dense, unforked chain.
- `tests/runtime/test_scheduler.py::test_concurrent_scheduler_caps_concurrency_at_the_k11_parent_and_halts`
  — a `Barrier(3)` proves three goals run **at once**, capped under the K11 parent.
- `tests/runtime/test_scheduler.py::test_concurrent_scheduler_runs_all_isolated_under_exact_metering`
  — parallel children isolated under exact spend metering.
- `tests/kernel/test_evidence.py` — trailing-whitespace tolerance added **and** content-difference
  still caught (CER-1 anti-forgery preserved).

## Files in this commit (scoped)

- `kernel/ledger.py` — `_append_lock` (K8 integration point)
- `kernel/ledger_sqlite.py` — `check_same_thread=False` + reentrant connection `RLock`
- `kernel/evidence.py` + `tests/kernel/test_evidence.py` — CER-1 trailing-whitespace tolerance
- `ops/autonomous_run.py` — `ConcurrentScheduler` wiring via `max_concurrency`
- `tests/kernel/test_ledger_sqlite.py` — concurrent-append chain integrity test
- `reviews/phase3_m3_live_concurrency.md` — this review

Intentionally excluded (unrelated to this milestone, left uncommitted): `tests/test_smoke.py`
(import hardening) and the many pending docs/specs/DEBT files in the working tree.

---

## Founder Ratification

Requested: ratification of the K8 concurrency touchpoint + `ConcurrentScheduler` mechanism as
**RATIFIED**, and an explicit decision on whether to authorize the **live multi-goal concurrent
self-hosting run** (real `claude` subprocesses, real token spend). The mechanism is green and
lawful; the live seal awaits Founder authorization.

> **Founder decision:** ▢ Ratify mechanism · ▢ Authorize live run (specify budget / concurrency /
> backlog) · ▢ Hold
