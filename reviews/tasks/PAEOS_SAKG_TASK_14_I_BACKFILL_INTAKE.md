# SAKG Task 14 — `[I-BACKFILL]` Intake Opened

**Date:** 2026-09-03  
**Status:** `QUEUED` (implementation not started)  
**Prerequisite:** Task 13 physical L14/L17 checkpoint and Founder/Court disposition recorded for
candidate `b2ef99c0ca484b919ed89b52287d746f6b4ac8aa`.

## Canonical intake binding

The canonical item at index 13 (Task 14) in `ops/backlogs/sakg-1-intakes.json` is:

```text
[I-BACKFILL] Backfill historical Outcome nodes from ledger/debt + incident records.
```

Its canonical deliverables are:

- `sakg/backfill.py`, mapping `ledger/debt/DEBT-*.md` and incident records onto typed Outcome
  nodes bound to their Decisions;
- a tagged `ledger/debt/DEBT-00NN.md` record describing the compromise, S3 automatic-loop
  repayment condition, and risk;
- `tests/sakg/test_backfill.py`;
- `tests/sakg/test_backfill_outcomes_bound_to_decisions.py`;
- `tests/sakg/test_backfill_marked_hand_attributed.py`.

Acceptance commands from the canonical intake:

```text
uv run pytest tests/sakg/test_backfill.py -q
uv run pytest tests/sakg/test_backfill_outcomes_bound_to_decisions.py -q
uv run pytest tests/sakg/test_backfill_marked_hand_attributed.py -q
rg -q 'SAKG-1/I-BACKFILL' ledger/debt/DEBT-*.md
```

## Reconciliation note

Existing `PAEOS_SAKG_TASK_14_L14_L17_CHECKPOINT.md` and
`PAEOS_SAKG_TASK_14_FOUNDER_COURT_DISPOSITION.md` are stale records for a different historical
“Bundle Golden Bytes” label. They are preserved unchanged. This newly named intake is the
canonical Task 14 frontier and is the only one opened by this record. No Task 14 source or test
files have been modified yet; execution must proceed through the authorized isolated SoftLoop.

