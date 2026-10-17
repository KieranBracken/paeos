# PAEOS_SOFTLOOP_ORIGIN_AND_AUDIT_FORENSICS

## 1. Executive Finding
SoftLoop was **intentionally implemented as a partial/vertical operational slice** ("Phase-1 Soft-Loop Integration Milestone"). The discrepancy is not due to architectural drift, but rather a staged implementation plan where the 19-layer constitution represents the final doctrine, while SoftLoop represents a verified, functional subset ("Phase 1") designed to bootstrap the system. Previous audits did not establish 19-layer conformance because their explicit scope was to verify the Phase 1 milestone criteria, not the entire constitution.

## 2. The 19-Layer Constitutional Lifecycle
- **Authoritative Source:** `operations/ENGINEERING_LIFECYCLE.md` (Committed July 21, 2026, before implementation began).
- **Status of Each Layer:** Documented as the canonical operational doctrine (v1.0 frozen). It is normative architecture, and `kernel/types.py` enforces the 21 `StageId` constants mathematically. However, the runtime currently implements only a subset.

## 3. SoftLoop Historical Timeline
- **Jul 28, 2026 (Commit `6272a181e24099f3ee7aaf7d58a33d075c37a1ab`)**: `runtime/orchestrator/__init__.py` created. The commit is titled "Phase-1 Soft-Loop Integration — unattended end-to-end run (§157 / R2->R3)".
- **Subsequent Commits (Jul 30 - Aug 1)**: Enhancements added for live-agent flows, information barriers, adversary gates, and triage fast-paths (commits `ecf9ef3`, `575c71d`, etc.).

## 4. SoftLoop Original Design Intent
SoftLoop was explicitly designed as the "Phase-1 capstone" (see docstring of `runtime/orchestrator/__init__.py`). Its intent was to compose a vertical slice of the spine into one autonomous run, demonstrating "ALL §157 properties: 4 roles in order; sealed change; court-passed." It was never claimed to be the final, complete 19-layer runtime.

## 5. 19-Layer Lifecycle Historical Timeline
- **Jul 21, 2026 (Commit `671206f`)**: `operations/ENGINEERING_LIFECYCLE.md` added. ("paeos 1 through 8.1 documentaiont and env set up - this is pre implementation of paeos").
- **Jul 27, 2026 (Commit `5d9daaf` / `a72efd4`)**: `kernel/types.py` added `StageId` enum with all 21 stages.

## 6. Constitutional-vs-Runtime Divergence
The divergence exists because the constitution (`ENGINEERING_LIFECYCLE.md`) defines the full target architecture, while the runtime (`SoftLoop`) implements the "Phase-1" bootstrap. The constitution is the destination; SoftLoop is the current vehicle.

## 7. Previous Audit Inventory

| Audit | Date/Commit | Scope | What it actually verified | What it did NOT verify | Result |
|---|---|---|---|---|---|
| `B1-SOFTLOOP_review.md` | Jul 28, 2026 | Phase-1 Soft-Loop Integration Milestone | `stages_run == [DESIGN, PLAN, IMPLEMENT, ADVERSARIAL_REVIEW]`, roles, budget, information barrier. | Did not verify L01-L07 or L17-L19. Did not verify `RE_DERIVE` or `RESEARCH`. | PASS (Phase-1 goal met) |
| `5.5-implementation-audit/07_IMPLEMENTATION_VERDICT.md` | Pre-Wave-1 | PAEOS-4/5 Corpus Completeness | Evaluated missing schemas, storage logic, and boot sequence for Wave-1 readiness. | Did not evaluate runtime 19-layer operational compliance. | GO (Conditional) |

## 8. Claude/PAEOS Development Reconstruction
- SoftLoop was itself created under the governance of the B-series implementation tasks (specifically B1.C / B1-SOFTLOOP). 
- The Claude agents building SoftLoop were executing against the reduced workflow, as evidenced by the `B1-SOFTLOOP_review.md` which confirms the system executed `[DESIGN, PLAN, IMPLEMENT, ADVERSARIAL_REVIEW]`.
- Agents believed they were completing a "Phase 1" milestone, not redefining the overarching constitution.

## 9. Runtime Execution-Path Reconstruction
- **Canonical Path:** `cli/paeos.py (demo/self-host)` → `ControlPlane` (acquires capability, mints token) → `SoftLoop.run` (starts loop) → `AgentDispatcher` → `AgentRuntime`.
- **Governance Status:** This path IS governed. The capability broker and gates enforce the transitions, even if the transitions are a subset of the 19 layers.
- **Bypass Paths:** `tests/` and direct script invocations (e.g., `ops/autonomous_run.py`) script the loop or bypass the network stack, but they still invoke `SoftLoop` or `Gate.propose_transition` directly, meaning they remain subject to kernel rules (though they don't test the full distributed lifecycle).

## 10. Layer-by-Layer Conformance Matrix

| Layer | Specified | Implemented | Canonically Reachable | Tested | Audited | Governed | Evidence |
|---|---|---|---|---|---|---|---|
| L01 Intake | Yes | Yes | Yes (Implicit) | Yes | Yes | Yes | `cli/paeos.py create_goal` |
| L02 Triage | Yes | Partial | Yes | Yes | Yes | Yes | `SoftLoop` triage call |
| L03 Re-Derivation | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L04 Ideation | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L05 Research | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L06 Trade-off | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L07 Mitigation | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L08 System Design | Yes | Yes | Yes | Yes | Yes | Yes | `SoftLoop` Phase 1 |
| L09 Critique | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L10 Adv. Review | Yes | Yes | Yes | Yes | Yes | Yes | `SoftLoop` Review |
| L11 Formal Planning | Yes | Yes | Yes | Yes | Yes | Yes | `SoftLoop` Phase 1 |
| L12 Implementation | Yes | Yes | Yes | Yes | Yes | Yes | `SoftLoop` Phase 1 |
| L13 Verification | Yes | Yes | Yes | Yes | Yes | Yes | `SoftLoop` Court |
| L14 Ind. Audit | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L15 Doc & Ledger | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L16 Promotion | Yes | Yes | Yes | Yes | Yes | Yes | `SoftLoop` Seal |
| L17 Retrospective | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L18 Extraction | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |
| L19 Evolution | Yes | No | No | No | No | No | `ENGINEERING_LIFECYCLE.md` |

## 11. Why Previous Audits Could Have Passed
1. **Intentional Vertical Slice (Highest Evidence):** `B1-SOFTLOOP_review.md` explicitly states the goal was a "Phase-1 Soft-Loop Integration Milestone". 
2. **Audit Scope Limitation:** Audits were explicitly scoped to verifying Phase-1 properties (e.g., information barriers, 4 sequential roles), not the entire constitution.

## 12. Contradictions / Unknowns
- **Unknown:** Exactly how or when the transition from the Phase 1 `SoftLoop` to the full 19-layer orchestrator was scheduled. The audits state "On founder ratification, Phase 1's soft-loop substrate is sealed; the remaining frontier is the live-agent adapter... toward R4 self-hosting," but do not clearly define when Phase 2 (full lifecycle expansion) begins.

## 13. Architectural Implications for RCL
- RCL MUST be designed to accommodate the full 19-layer lifecycle, as `ENGINEERING_LIFECYCLE.md` and `kernel/types.py` firmly establish it as the canonical doctrine.
- RCL should not hardcode expectations based on `SoftLoop`'s 6-step loop.
- RCL must integrate with `ReasoningState`, `Checkpoint`, and `ContextPolicy` because these primitives are already designed to support the full 19 layers (e.g., ContextPolicy filters specifically target multi-agent debate and re-derivation scenarios).

## 14. Recommended Next Investigation
- Investigate the `ContextPolicy` implementation inside `runtime/context_compiler.py` to map exactly which policies correspond to which of the 19 layers, to understand how RCL must inject state across the un-implemented layers.

## Conclusion
1. **Was SoftLoop intentionally partial?** Yes, it was explicitly implemented as a "Phase-1" vertical slice.
2. **Was it ever intended to represent all 19 layers?** No.
3. **Did previous PAEOS work actually execute through SoftLoop?** Yes, the self-hosting capability explicitly dispatched through the reduced Phase-1 SoftLoop.
4. **What exactly did previous audits verify?** They verified that the SoftLoop correctly composed the kernel, court, and barriers for a restricted 4-role (DESIGN, PLAN, IMPLEMENT, ADVERSARY) slice.
5. **Why did those audits not establish full 19-layer conformance?** Because L01-L19 conformance was outside the scope of a Phase-1 milestone.
6. **Is there evidence of architectural drift/regression?** No, there is evidence of staged implementation. 
7. **What must be established before RCL implementation continues?** We must accept that SoftLoop is an incomplete runner and design RCL against the documented `StageId` and `ENGINEERING_LIFECYCLE.md` architecture, utilizing `kernel/state.py` mechanisms.
