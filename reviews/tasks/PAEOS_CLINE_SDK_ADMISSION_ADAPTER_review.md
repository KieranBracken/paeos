# PAEOS Cline SDK Admission Adapter — L14 Decorrelated Audit

**Date:** 2026-08-30
**Candidate:** `adf76c61972554f71f2c863b3113f07d19dd1a52` (`adf76c6`)
**Auditor role:** temporary Codex GPT-5.6 Sol Architect/Overseer
**Builder provenance on record:** Cline `cline-pass` / `z-ai/glm-5.3-flash` (GLM family)
**Disposition:** **BLOCKED_UNQUALIFIABLE**

## Scope and independence

This is a static and evidence-bound audit of the exact detached candidate reproduced in
`PAEOS_CLINE_SDK_ADAPTER_L13_EVIDENCE.md`. It did not consume builder prose as proof, did not run
a provider call, did not inspect credentials, did not run a live admission probe, and did not alter
the Court or lifecycle state.

The candidate's production implementation was built for the Cline/GLM worker route. The proposed
auditor is a different model family (OpenAI/GPT), satisfying the family inequality by declared
identity only. The local PAEOS router has no physical, signed receipt for this Codex session: its
`routing_observations` table contains historical Gemini/Llama transport observations, not an
auditor receipt bound to this review. A chat label or system declaration cannot substitute for the
required physical provenance.

## Invariant review

| Invariant | Finding | Result |
|---|---|---|
| Public SDK only; no private API or dynamic fallback | Qualified package closure, explicit entrypoints, hash checks, and public `ClineCore` lifecycle are used. | PASS (static) |
| Explicit local backend | Host start and capability snapshot require `backend_mode=local`; CLI exposes no auto/hub/remote fallback. | PASS (static) |
| Python approval precedes tool execution | Host forwards tool requests and blocks on a framed Python response; tests cover unauthorized tools and command expansion. | PASS (test evidence) |
| Hidden retry and attempt telemetry | Attempt correlation and one-attempt-per-turn checks reject duplicate attempts; mutation tests kill altered counts. | PASS (test evidence) |
| Profile and secret boundary | Private profile/lease paths, symlink checks, content-free secret quarantine, and CAS refusal are covered. | PASS (test evidence) |
| Legacy CLI cannot admit | `cline-cli-diagnostic` returns `ADAPTER_VERSION_UNQUALIFIED` without dispatch. | PASS (test evidence) |
| Non-vacuous negative evidence | 46 adversarial/mutation tests reproduce from the detached checkout. | PASS (test evidence) |
| Repository-wide static gate | Independent run reported 658 Ruff findings and 74 Pyright diagnostics. | **BLOCKER** |
| Full-suite environment | Restricted run reported 813 passed and 4 loopback-bind errors; elevated gateway rerun passed 4/4. | **BLOCKER FOR UNQUALIFIED ENVIRONMENT** |
| Physical Builder != Auditor receipt | No signed/physical receipt for this auditor session exists. | **BLOCKER** |

## Findings

### L14-001 — Auditor physical identity is unavailable (blocking)

The audit role requires an attributable physical model-family receipt, and the receipt must differ
from the GLM builder family. The current environment exposes no receipt for this Codex session and
the local router observations are not bound to this candidate or review. Therefore the different
family cannot be proven mechanically. This is `BLOCKED_UNQUALIFIABLE`, not a pass.

### L14-002 — Repository-wide quality gate is not green (blocking)

The exact candidate reproduces its focused gates, but repository-wide Ruff and Pyright remain
nonzero. The findings predate this task and were not mass-repaired because doing so would expand
scope and destroy forensic attribution. Gate A closure cannot consume a non-green static baseline.

### L14-003 — Restricted full-suite environment is not hermetic (blocking)

Four gateway tests cannot bind their loopback port under the restricted execution profile. They pass
under an explicitly elevated loopback run, but the restricted failure remains part of the evidence
and must be resolved by the execution environment or an approved test isolation change.

## Disposition and counts

Disposition is exactly **`BLOCKED_UNQUALIFIABLE`**. The candidate is not eligible for Task 10, Gate A
closure, controlled canary, unattended worker use, or any Gates B–G work that depends on Gate A.

Worker accounting remains **Admitted: 0 | Rejected: 1 | Remediated: 0**. Court accounting remains
**Sealed: 0 | Remanded: 0 | Remediated: 0**. No self-ratification, promotion, merge, credential
rotation, or lifecycle advancement occurred.

## Required unblock conditions

1. Produce a machine-captured, candidate-bound physical receipt for a proven non-GLM auditor, or
   route the review to an external auditor whose receipt is available to PAEOS.
2. Resolve or formally disposition the 658 Ruff and 74 Pyright baseline findings without silently
   changing this candidate's scope.
3. Re-run the exact L13 matrix from a clean candidate checkout and reconcile every count/hash.
