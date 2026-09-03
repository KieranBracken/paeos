# SAKG Task 16 — `[I-PROJ]` Intake Opened

**Date:** 2026-09-03  
**Status:** `QUEUED` (implementation not started)  
**Prerequisite:** Task 15 `[I-TRAVERSE]` physical L14/L17 checkpoint and Founder/Court disposition
sealed for candidate `fbb52403b16af0a581848938f274fd266ec0cd9e`.

## Canonical intake binding

The canonical item at index 15 (Task 16) in `ops/backlogs/sakg-1-intakes.json` is:

```text
[I-PROJ] Implement the projection engine — budget, ranking, why, provenance.
```

Canonical deliverables:

- `sakg/project.py` with a hard `max_tokens` ceiling;
- whole-result drop-and-count semantics (never mid-structure truncation);
- mandatory `why` path on every result;
- reproducible `corpus_hash` and `query_hash` values;
- `tests/sakg/test_projection.py`;
- `tests/sakg/test_projection_budget_golden.py`;
- `tests/sakg/test_projection_never_exceeds_budget.py`;
- `tests/sakg/test_projection_every_result_has_why.py`;
- `tests/sakg/test_projection_reproducible_hashes.py`.

Acceptance commands from the canonical intake:

```text
uv run pytest tests/sakg/test_projection.py -q
uv run pytest tests/sakg/test_projection_budget_golden.py -q
uv run pytest tests/sakg/test_projection_never_exceeds_budget.py -q
uv run pytest tests/sakg/test_projection_every_result_has_why.py -q
uv run pytest tests/sakg/test_projection_reproducible_hashes.py -q
uv run pyright sakg/
```

Existing `PAEOS_SAKG_TASK_16_L14_L17_CHECKPOINT.md` and
`PAEOS_SAKG_TASK_16_FOUNDER_COURT_DISPOSITION.md` are stale historical records for a different
projection label and remain unchanged. This newly named intake is the canonical Task 16 frontier;
implementation must proceed through the authorized isolated SoftLoop.
