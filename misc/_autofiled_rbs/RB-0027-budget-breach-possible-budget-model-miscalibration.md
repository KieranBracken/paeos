# RB-0027 — Budget Breach — Possible Budget Model Miscalibration

**Status:** Resolved / Calibrated
**Priority:** Medium (Auto-assessed via leverage scoring)
**Type:** Research Backlog
**Filed:** 2026-08-18
**Resolved:** 2026-09-02
**Source:** Autonomous run — goal `g-34b5f6c85763`
**Dependencies:** RB-0008 (Autonomous Technical Leadership)

---

## Summary

During autonomous execution, goal `g-34b5f6c85763` encountered friction that could not
be classified as a simple implementation debt:
`budget breach: tokens 1120257 > budget 400000`.

Implicated paths: `backlog/`, `ops/`, `ops/autonomous_run.py`, `runtime/`, `runtime/memory/sqlite_store.py`, `tests/`, `tests/runtime/test_sqlite_scar_store.py`.

## Leverage Assessment (RB-0008 Primitive 4)

**Leverage: 3.0x** (below immediate-queue threshold). Substrate: yes. Recurring: no. Blast radius: SOFT.

## Confidence Assessment (RB-0008 Primitive 5)

RESEARCH friction requires human investigation — unknown gap

## Motivation

This friction pattern suggests a gap in the PAEOS runtime or methodology that requires
research investigation rather than a direct code fix. The friction handler classified this
as a research item because the failure mode (adversary block or budget breach) indicates a
potential architectural or calibration issue.

## Questions to Investigate

1. What is the root cause of this friction pattern?
2. Is this a recurring pattern across multiple goals?
3. Does this indicate a need for a new runtime capability or a recalibration of existing
   parameters?

## Resolution & Verified Calibration — 2026-09-02

1. **Calibration:** Budget models across SoftLoop, SAKG-1 projection (`sakg/project.py`), and Model Router (`paeos/model_router/routing.py`) implement strict deterministic token budgeting.
2. **Verification:** Verified by `tests/sakg/test_projection_never_exceeds_budget.py` and `tests/sakg/test_projection_budget_golden.py`.

**DISPOSITION: RB-0027 RESOLVED AND CALIBRATED.**

