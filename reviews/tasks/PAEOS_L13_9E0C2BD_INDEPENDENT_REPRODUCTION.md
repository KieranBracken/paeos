# L13 Independent Reproduction — Candidate `9e0c2bd`

**Date**: 2026-08-31
**Role**: Independent mechanical verifier
**Candidate**: `9e0c2bdfd6a80523bf176bc719843c611430b218`
**Verifier worktree**: `/private/tmp/paeos-l13-9e0c2bd` (detached, clean before and after)
**Disposition**: `L13_REPRODUCED`; no Court or Gate disposition is issued by this record

## Exact reproduction

The verifier ran the complete repository test tree with the known restricted gateway-server
fixture excluded:

```text
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest tests \
  --ignore=tests/model_router/test_gateway_server.py -rA
```

Result: **1,058 passed, 0 failed**, exit code `0`, elapsed `49.61s`.

Raw evidence is preserved outside the repository:

- stdout/stderr log: `/private/tmp/l13-9e0c2bd-nongateway-rerun.log`
  - bytes: `120791`
  - SHA-256: `31a0e724159c5f6f74f06ad308efe4ecebda0ce4885a1276fe6d6e34855e8482`
- exit-code record: `/private/tmp/l13-9e0c2bd-nongateway-rerun.exit`
  - contents: `0`
  - SHA-256: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`

The run includes the worker-admission, control-plane, bridge, supervisor, sandbox, autonomy,
mutation, lifecycle-audit, Court-reconciliation, and auditor-capture tests. No provider request,
credential access, browser/clipboard/AppleScript action, terminal paste, or source edit occurred.

## Negative evidence retained

An earlier full run in the same detached worktree logged **1,057 passed and 1 failed** at the SDK
manifest-model parameter. Its raw log remains at `/private/tmp/l13-9e0c2bd-nongateway.log` (SHA-256
`ef0f3683d77ded46cd8324c2b7ba3cd90c35eaeb4d6e841c789fb0c979eaaac9`). The shell harness used a
reserved zsh variable and did not write an exit-code file; that harness defect is not treated as a
test result. The failing parameter was then isolated and passed in `1.49s`. The clean rerun above
passed the entire non-gateway suite, so the first failure is classified as a timing-sensitive
probe flake under the test's 15-second SDK timeout, not silently discarded.

The gateway-server suite was excluded because it binds a loopback socket that is denied in this
restricted verifier environment. This exclusion is explicit; it is not converted to a pass. A
separate elevated-loopback run remains the appropriate evidence for those four tests.

## L13 boundary

This record establishes current-candidate mechanical reproduction only. It does not prove a live
worker admission, physical model provenance, Builder/Auditor decorrelation, a Court seal, a Gate
closure, or SAKG resumption. L14/A-08 is separately qualified in
`PAEOS_L14_L17_9E0C2BD_GEMINI_SOURCE_review.md`; the two records must remain conjunctive and
candidate-bound before an L16/Court decision is considered.

Canonical accounting remains Worker `Admitted: 0 | Rejected: 1 | Remediated: 0`, Court
`Sealed: 0 | Remanded: 0 | Remediated: 0`, strict progress `12 / 48 complete | 36 remaining`.
`DEBT-0058` and `DEBT-0060` remain open.
