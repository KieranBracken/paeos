# PAEOS Milestone 41 Intake — `[I-CEREMONY-WALK]` L02/K1 Ceremony Walk

**Status:** `OPEN/QUEUED`  
**Opened:** 2026-09-03  
**Predecessor:** Milestone 40 `[I-DURABLE-SCARS]`, candidate `a2e3d49bc8cb8a199bf620c9d8ce4ec0f5fe5aac`  
**Canonical references:** `operations/ENGINEERING_LIFECYCLE.md` (L02, K1 evidence rule),
`operations/WORKFLOW_STATE_MACHINE.yaml` (`ceremony_depth`), and the approved next sequence in
`operations/CURRENT_STATE.md`.

## Objective

Exercise the existing L02 ceremony contract as a runtime obligation walk. The orchestrator
must consume `CeremonyContract.obligation_plan()` in canonical `L01 → L19` order, execute
non-dischargeable obligations, and record a K1 discharge stub for every lawfully discharged
Trace-A layer. This intake is a conformance walk over existing doctrine; it does not legislate
a new ceremony-depth algorithm or add a lifecycle state.

## Required deliverables

1. Wire the orchestrator's run path to walk the ceremony-resolved obligation plan rather than
   relying on an unconditional hard-coded stage sequence.
2. Record auditable layer observations and `layer_discharged` evidence for Trace-A, preserving
   the exact canonical order and routing transitions through `Gate.propose_transition`.
3. Add focused tests for:
   - Trace-A: all 19 layers represented; exactly 11 lawful K1 stubs for `L03–L11`, `L17`,
     and `L18`; `L01`, `L02`, `L12–L16` execute; `L19` executes only when triggered.
   - Trace-B: all 19 layers execute and no discharge stubs are emitted.
   - Missing or unknown trace: conservative Trace-B behavior, never a silent fast path.
   - Out-of-order, missing, or illegal discharge evidence: fail closed.
4. Produce candidate-bound L13 evidence and an independent heterogeneous L14/L17 audit pair.

## Acceptance

- `uv run pytest tests/runtime/test_ceremony_walk.py -q` passes with discriminating tests.
- Existing ceremony and SoftLoop tests remain green.
- `uv run ruff check runtime/` and `uv run pyright runtime/` results are recorded, including
  any pre-existing diagnostics rather than omitted.
- A hermetic single-flight SoftLoop run under `/private/tmp/paeos-ceremony-walk-run` seals
  with a reproducible evidence bundle and exact Court accounting.
- Auditor and builder families differ (A-08); no self-audit, fallback, retry, promotion, or
  protected-ref mutation is permitted.

## Execution boundary

Implementation must be produced by the bound worker inside the isolated SoftLoop sandbox.
This intake authorizes neither direct architectural edits in the host checkout nor promotion
to `main`/`trunk`; the next candidate remains subject to L13 reproduction, L14/L17 audit, and
Founder/Court disposition.
