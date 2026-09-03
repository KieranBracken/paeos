# PAEOS Milestone 44 Intake — `[I-L15-SIZING]` / L15 Dynamic Context Sizing

**Status:** `OPEN/QUEUED`
**Opened:** 2026-09-03
**Predecessor:** Milestone 43 `[I-CER-BASELINE]`, candidate
`e761351faeb8f4bf6fb25218ae7e97eb413f190b`
**Canonical references:** `operations/ENGINEERING_LIFECYCLE.md` (L15 Documentation & Ledger),
`operations/WORKFLOW_STATE_MACHINE.yaml` (L15 artifacts and gate),
`runtime/context_compiler.py`, `runtime/task_package.py`, and
`docs/PAEOS_MODEL_ROUTER_INFERENCE_MESH_SPEC.md` (context-size eligibility and PAEOS policy
authority).

## Sequence identity

Legacy `reviews/tasks/PAEOS_INTAKE_M44_*` records belong to an older Verification Engine Upgrades
sequence. They are immutable historical records and are not this milestone. This intake uses the
`PAEOS_MILESTONE_44_I_L15_SIZING_*` namespace and must not overwrite or reinterpret the legacy
records.

## Objective

Implement a deterministic, evidence-bearing L15 context-sizing contract that compiles the smallest
sufficient integration context for the selected physical model without dropping constitutional,
task, provenance, verification, audit, or ledger obligations. PAEOS owns sizing, admission, and
failure policy. Provider transports remain stateless wire adapters and may not silently truncate,
summarize, retry, reroute, or choose omissions.

## Required behavior

1. Compute an explicit input budget before dispatch from the selected model's verified context
   limit, reserved output tokens, protocol overhead, and a deterministic safety margin. Reject
   missing or unverified model-capacity metadata.
2. Treat constitutional invariants, capability boundaries, the current task contract, relevant
   candidate diffs, L13 evidence, L14 findings, and L15 ledger/disposition inputs as non-evictable.
   Optional context may be ranked only after those obligations fit.
3. Produce the same ordered context selection and digest for the same canonical inputs. Filesystem
   order, provider response order, wall-clock time, and mutable global state must not affect the
   result.
4. When mandatory inputs exceed the budget, fail closed with a typed, evidence-bearing sizing
   disposition. Silent truncation, tail clipping, lossy omission, or transport-layer recovery is
   forbidden.
5. Record the selected model identity, verified context limit, reserved output, overhead, safety
   margin, mandatory and optional input sizes, admitted/omitted item identities, final digest, and
   failure reason in the L15 institutional record.
6. Preserve state independence and layer separation: PAEOS retains canonical task/history/tool/
   diff/evidence state; the model is stateless compute; Layer 3 requests policy, Layer 2 makes the
   sizing/admission decision, and Layer 1 transports only the admitted request.
7. Preserve heterogeneous audit: the eventual L14/L17 reviewer family must differ from the builder
   family. Context pressure is never a reason to weaken or discharge A-08.

## Deliverables

- An isolated SoftLoop implementation in the existing context-compiler/task-package boundary,
  with the smallest supporting types necessary and no provider-specific policy in transport code.
- Discriminating tests for exact-fit, insufficient mandatory budget, deterministic ordering,
  output reservation, unverified capacity, and attempts to evict required evidence or
  constitutional inputs.
- A machine-readable sizing record suitable for L15 ledger/documentation synchronization and
  exact replay.
- Candidate-bound L13 reproduction evidence followed by an independent heterogeneous L14/L17
  physical report/receipt pair.

## Acceptance

- Focused tests pass against the candidate and fail against at least one sizing-policy mutation
  that reintroduces silent truncation or permits mandatory-input eviction.
- Existing context compiler, task package, model-router policy, and runtime regression suites pass;
  exact commands and outputs are retained.
- Static analysis and AST anti-pattern checks cover every changed Python file; inherited findings,
  if any, are disclosed rather than relabeled.
- The sizing decision is reproducible from durable inputs and its digest is bound into L15
  evidence before any Founder/Court disposition.
- The physical auditor family differs from the builder family, with one candidate-bound report and
  receipt; no self-audit, fallback, retry, promotion, merge, or protected-ref mutation is allowed.

## Execution boundary

Implementation is worker-owned and must be produced in an isolated SoftLoop sandbox. This intake
does not authorize direct host architectural edits, provider transmission, source promotion, merge,
or mutation of `main`/`trunk`. A local Court seal and qualified L14/L17 pair are evidence only;
Founder/Court disposition remains a separate governance action.
