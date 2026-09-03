# SAKG Task 15 — `[I-TRAVERSE]` Intake Opened

**Date:** 2026-09-03  
**Status:** `QUEUED` (implementation not started)  
**Prerequisite:** Task 14 `[I-BACKFILL]` physical L14/L17 checkpoint and Founder/Court disposition
sealed for candidate `542ebba88467629d3d68c335cb2720dbf8025cb2`.

## Canonical intake binding

The canonical item at index 14 (Task 15) in `ops/backlogs/sakg-1-intakes.json` is:

```text
[I-TRAVERSE] Implement traversal primitives over the 8 edge families.
```

Canonical deliverables:

- `sakg/traverse.py` — typed walks for every §4.4 edge family;
- acyclicity enforcement on dependency edges;
- one-hop, non-transitive `analogous_to` traversal;
- cross-namespace traversal gated on both disclosure policies;
- `tests/sakg/test_traverse.py`;
- `tests/sakg/test_traverse_dependency_acyclic.py`;
- `tests/sakg/test_traverse_analogous_not_transitive.py`;
- `tests/sakg/test_traverse_cross_namespace_gated.py`.

Acceptance commands from the canonical intake:

```text
uv run pytest tests/sakg/test_traverse.py -q
uv run pytest tests/sakg/test_traverse_dependency_acyclic.py -q
uv run pytest tests/sakg/test_traverse_analogous_not_transitive.py -q
uv run pytest tests/sakg/test_traverse_cross_namespace_gated.py -q
uv run pyright sakg/
```

Existing `PAEOS_SAKG_TASK_15_L14_L17_CHECKPOINT.md` and
`PAEOS_SAKG_TASK_15_FOUNDER_COURT_DISPOSITION.md` are stale historical records for a different
baseline/budget label and remain unchanged. This newly named intake is the canonical Task 15
frontier; implementation must proceed through the authorized isolated SoftLoop.
