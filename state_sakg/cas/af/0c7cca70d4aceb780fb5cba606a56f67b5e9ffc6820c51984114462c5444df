# Constitutional Implementation Review: [Phase-1 Soft-Loop Integration]

**Date**: 2026-07-28
**Task**: Phase-1 Soft-Loop Integration Milestone (PAEOS-8 §157 / §12 R2→R3)
**Reviewer Role**: Auditor / Builder Self-Adversarial (all build-time roles)

## Summary of Findings

- **BLOCKER**: 0 · **MAJOR**: 0 · **MINOR**: 0 · **OBSERVATION**: 1

Deliverable: `runtime/orchestrator/__init__.py` — `SoftLoop` + `RunOutcome`/`RunStatus`. Evidence:
6 integration tests in `tests/runtime/test_soft_loop.py`; **271 total**; ruff clean (clean-cache);
pyright 0 errors (strict on kernel); F1 2644/20000. **F2-SOFT** (`runtime/orchestrator/`).

## The §157 Phase-1 goal — demonstrated end to end

The `SoftLoop` takes one intake to a sealed change, unattended, composing every Phase-1 component
over the sealed Phase-0 kernel:

| §157 property | How the loop shows it |
|---|---|
| **Planner → Builder → Verifier → Adversary** | `stages_run == [DESIGN, PLAN, IMPLEMENT, ADVERSARIAL_REVIEW]`; roles PLANNER/PLANNER/BUILDER/ADVERSARY (tested) |
| **Sealed change** | `RunStatus.SEALED` with a `SealRecord` over `(bundle, verdict, adversary, ledger_head)` (B0.9) |
| **Court-passed** | the court **reproduces** the builder's evidence (B1.E); PASS gates the seal |
| **Adversary-reviewed** | the isolated adversary runs over the sealed bundle only (B1.D `ReviewHarness`) |
| **Real information barriers** | the bundle is built by the IBM; `verify_isolation` runs before the adversary dispatches (SI-5) |
| **Scars written** | a court **remand** writes a scar that then matches the failure class (FR-6, tested) |
| **Triage fast/full path** | routine intake → ROUTINE budget; a `kernel/` intake → KERNEL_TOUCHING full path, recorded on the ledger (B1.G, tested) |
| **Matched scars injected** | a pre-written scar appears in the DESIGN package's `context_refs` (FR-6, tested) |
| **Budget halts** | a tight budget → `RunStatus.HALTED` at the second dispatch (K11, tested) |

## Evaluation Checklist

### 1. Constitutional Compliance
**PASS.** The runtime **holds no opinions** (7 §1.2): every decision is the kernel's / court's /
barrier's. It mints scoped capabilities, dispatches through the DEBT-0002-validated seam, has the
court reproduce evidence, runs the adversary behind the barrier, and seals — composing, never
overriding.

### 2. Architectural Drift
**PASS.** No new mechanism — `SoftLoop` wires B1.A–G + B0.9. The one loop-local event kind
(`goal_created`) mirrors the CLI's (B0.12); the run's state is fully on the ledger.

### 3–7. Duplication / Bypass / Simplicity / Derivation / Debt
**PASS.** Every step goes through the real component (scope enforcement, court re-run, barrier
check, budget charge, seal). The court gate cannot be bypassed — a forged result remands and the
seal never happens (tested). No hidden debt.

### 8. Security Implications
**PASS — the whole chain of custody holds unattended.** Forged evidence → remand (no seal); the
adversary never sees builder context; a kernel-touching intake cannot triage-inflate onto the fast
path; budget breach halts. Each defense is an already-reviewed component; the integration proves
they compose without a gap.

### 9. Runtime Implications
**PASS.** Sequential composition; the court's re-runs go through the DEBT-0005 sandbox; typed
outcomes (`SEALED`/`REMANDED`/`HALTED`).

### 10. Future Extensibility
**PASS.** The `AgentRuntime` adapter (Observation 1) turns the scripted run into a live one (R3→R4);
the loop is the seam the self-hosting backlog will call.

## OBSERVATIONS
1. **Scripted `AgentRuntime` = the R3 integration frontier.** The composition (the constitutional
   substance) is complete and tested; making the run *live* means implementing the B1.B `AgentRuntime`
   with the real Claude Agent SDK + worktree isolation (validated shape from the DEBT-0002 spike). That
   is the R2→R3 → R4 deployment step, tracked as the standing integration.

## Disposition

**Phase-1 goal met (§157): one unattended run takes an intake to a sealed, court-passed,
adversary-reviewed change behind real information barriers, with scars written and triage/budget
enforced.** This is the **R2→R3** rung. On founder ratification, Phase 1's soft-loop substrate is
sealed; the remaining frontier is the live-agent adapter (Observation 1) toward R4 self-hosting.

## Action Items
- [ ] **Founder (ratifier)**: ratify the Soft-Loop Integration → merge, remote CI, tag `b1-softloop`
      (+ a `phase-1-softloop` marker). Then: the live `AgentRuntime` adapter, and R4 self-hosting.
