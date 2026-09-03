# PAEOS Milestone 43 Intake — `[I-CER-BASELINE]` / L02-C1 Ceremony Enforcement Realization

**Status:** `OPEN/QUEUED`  
**Opened:** 2026-09-03  
**Predecessor:** Milestone 42 `[I-LIFETIME-CONFORMANCE]`, candidate
`8e92bae07e48bf98b39d436cd5af0464917a2f65`  
**Canonical references:** `operations/ENGINEERING_LIFECYCLE.md` (L02 ceremony depth and K1
evidence), `operations/WORKFLOW_STATE_MACHINE.yaml` (`ceremony_depth`),
`runtime/ceremony.py`, and the L02 doctrine extraction in
`backlog/research/PAEOS_RESEARCH_BACKLOGS_CEREMONY_TDD_v0.1/`.

## Objective

Establish the L02/C1 ceremony-enforcement baseline as an executable, auditable conformance
contract. The implementation must enforce the already-canonical Trace-A/Trace-B doctrine; it must
not invent a new ceremony-depth algorithm, add a lifecycle layer, or lower ceremony due to model
uncertainty or resource pressure.

## Required behavior

1. Walk the canonical `L01` through `L19` obligation plan in order and record each layer's
   execution or lawful K1 discharge evidence.
2. For Trace-A, execute `L01`, `L02`, `L12`–`L16`, and `L19` when triggered; emit exactly one
   discharge stub for each of `L03`–`L11`, `L17`, and `L18`. No layer may silently disappear.
3. For Trace-B, execute all 19 layers and emit no discharge stubs.
4. Missing, empty, or unknown ceremony depth must conservatively resolve to Trace-B. L01, L02,
   L12–L16, and L19 are never dischargeable.
5. Every transition must remain gate-routed and evidence-bearing; out-of-order, duplicate,
   missing, or illegal discharge observations fail closed.
6. Preserve the Builder != Auditor boundary and emit candidate-bound L13 evidence for the
   implementation before any Court seal or physical audit.

## Deliverables

- Runtime enforcement and/or conformance changes limited to the isolated SoftLoop worker scope.
- `tests/runtime/test_ceremony_baseline.py` (or an equivalent focused suite) covering the positive
  and negative requirements above, including mutation/discriminating checks.
- A hermetic SoftLoop run under `/private/tmp/paeos-cer-baseline-run` with raw logs, CAS keys,
  ledger-chain verification, and exact `Sealed | Remanded | Remediated` accounting.
- A candidate-bound evidence bundle, substantive report, and independent heterogeneous L14/L17
  physical receipt pair.

## Acceptance

- `uv run pytest tests/runtime/test_ceremony_contract.py tests/runtime/test_ceremony_walk.py -q`
  (where the candidate supplies the ceremony-walk suite) passes without vacuous tests.
- The focused baseline suite passes, and the existing runtime/SoftLoop regression suites remain
  green.
- `uv run ruff check runtime/` and `uv run pyright runtime/` are run and their exact outputs,
  including pre-existing diagnostics if any, are recorded.
- AST anti-pattern checks and CANARY-0002 evidence-separation checks pass.
- Physical auditor family differs from the builder family; no self-audit, fallback, retry,
  promotion, merge, or protected-ref mutation is permitted.

## Execution boundary

Implementation is worker-owned and must be produced in the isolated SoftLoop sandbox. This intake
authorizes no direct architectural edits in the host checkout and no promotion to `main` or
`trunk`. A qualified physical audit is evidence only; the Founder/Court disposition remains a
separate governance action.

