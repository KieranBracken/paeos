# PAEOS Milestone 40 Intake — `[I-DURABLE-SCARS]` / RB-0026

**Status:** `OPEN/QUEUED` (not sealed)  
**Opened:** 2026-09-03  
**Predecessor:** L17 Retrospective, candidate `fd17d209b6dbf0aead8ff5137f213439b13e580a`  
**Specification:** `ops/backlogs/intake-rb0026-durable-scars.json`  
**Specification SHA-256:** `e8b867d6814fbce12ad9d7f160df156220a91111c36b6d4a2af5f7609eef7cfc`

## Objective

Make PAEOS institutional memory durable: the SoftLoop ScarStore must persist scars to SQLite in
the configured state directory, and `ops/autonomous_run.py` must inject the durable store.

## Required deliverables

1. Implement `SqliteScarStore` in `runtime/scar_store.py` with `record_scar`, `match_scars`,
   and `all_scars` compatible with the existing ScarStore interface.
2. Colocate the database at `<state_dir>/scars.db`.
3. Update `runtime/orchestrator/__init__.py` and `ops/autonomous_run.py` to inject it when
   `state_dir` is configured.
4. Add `tests/runtime/test_scar_store.py`, including cross-process persistence over one path.

## Acceptance

- A scar recorded by one store instance is returned by `match_scars` on a fresh instance over
  the same path.
- Full relevant test suite passes.
- `ops/autonomous_run.py` constructs the durable store when `state_dir` is set.

## Execution boundary

Use the isolated SoftLoop state root `/private/tmp/paeos-scarstore-run`. No direct architectural
source edits are authorized by this intake; source changes must be produced by the bound worker
and then independently reproduced and audited. This intake does not authorize promotion, merge,
or protected-ref mutation.

The older `reviews/tasks/PAEOS_INTAKE_M40_*` documents are historical records and are not the
authoritative status for this newly opened queue item.
