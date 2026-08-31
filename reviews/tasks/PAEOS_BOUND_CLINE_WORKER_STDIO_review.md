# PAEOS Bound Cline Worker Stdio Transport — Implementation Review

**Recovery worktree:** `/private/tmp/paeos-control-plane-recovery-s1-clean-recovered`
**Branch:** `codex/control-plane-recovery-s1-clean-recovered`
**Candidate HEAD:** `15ef316dfe3152959e52cdee5aafb54eb4ce8fd2`
**Scope:** isolated control-plane recovery only; no main/trunk promotion.

## Implemented commits

- `bf0882a` — bound transport contracts and path/request validation
- `c72847d` — immutable worker tool-policy sidecar
- `b378642` — one-shot framed host event loop
- `38ba251` — create-only response, quarantine, and handoff persistence
- `5eedb8d` — explicit bound-cline CLI/runtime adapter and dormant scheduler guard
- `15ef316` — adversarial frame/deadline/path/exit hardening

## Verification

- Focused transport, policy, persistence, CLI, and compatibility tests: **35 passed, 0 failed**, exit `0`.
- Changed-path Ruff: **clean**.
- Changed-path Pyright: **0 diagnostics**.
- `node --check runtime/integrations/cline_sdk_host.mjs`: **passed**.
- Non-gateway collection after adding this slice: **1,093 tests collected** (gateway-server test intentionally excluded).
- A full non-gateway execution was attempted once with `PYTHONDONTWRITEBYTECODE=1` and pytest cache disabled. It exited `1` after the host filesystem reached `ENOSPC`; pytest setup raised `OSError: [Errno 28] No space left on device` for temporary directories and CAS fixtures. The run is not counted as test evidence and was not retried identically.

## Control-plane properties

- Dispatch is state-root/worktree bound, run-once, `shell=False`, and uses the existing canonical framed host protocol.
- Only `editor` and policy-approved exact `run_commands` requests are executable; separators, redirects, `cd`, `exec`, `env`, unknown tools, and path escapes fail closed.
- Provider-attempt overflow, malformed/out-of-order/oversized/truncated/post-terminal frames, timeout, cancellation, nonzero exit, and uncertain side effects return typed failures.
- Responses, quarantines, and handoffs are create-only and hash-bound. Quarantine metadata is content-free; worker prose is not persisted as authority.
- `BoundClineWorkerRuntime` is opt-in and requires a caller-supplied explicit physical model/qualification/worktree configuration. `autonomous_run` refuses to infer these from aliases.
- The legacy GUI/CDP/clipboard/AppleScript bridge was not reactivated or modified.

## Governance state preserved

```text
Worker: Admitted: 0 | Rejected: 1 | Remediated: 0
Court: Sealed: 0 | Remanded: 0 | Remediated: 0
DEBT-0058: OPEN
DEBT-0060: OPEN
L14/L17: not performed by the builder
Strict progress: 12 / 48 complete | 36 remaining (54 granular tasks)
```

This review is implementation evidence only. It does not close a debt, create a Court row, seal a
gate, advance the lifecycle, or resume SAKG.

## Antigravity handoff

Resume from the exact candidate HEAD above after reading:

1. `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
2. `docs/PAEOS_MODEL_ROUTER_INFERENCE_MESH_SPEC.md`
3. `operations/ENGINEERING_LIFECYCLE.md`
4. `docs/superpowers/specs/2026-08-31-paeos-bound-cline-worker-stdio-transport-design.md`
5. `docs/superpowers/plans/2026-08-31-paeos-bound-cline-worker-stdio-transport.md`

First recover disk capacity, then run a fresh full non-gateway verification with raw stdout/stderr
and an exit record. Inspect the transport diff and handoff before any operational worker dispatch.
Any L14/L17 review of GLM-built work must use a candidate-bound physical non-GLM receipt, with no
fallback or retry. Do not promote this branch, alter Court/lifecycle counts, close DEBT-0058 or
DEBT-0060, or resume SAKG without the independent operational evidence and adjudication required
by the notebook and lifecycle contract.
