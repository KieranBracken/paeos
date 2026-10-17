# 02_IMPLEMENTATION_MATRIX: The SoftLoop Reality

This matrix compares the 19-layer canonical doctrine (from `01_CANONICAL_INVENTORY.md`) against the current executable state of the repository, specifically analyzing `runtime/orchestrator/__init__.py` and the `kernel/` primitive set.

## Implementation Status Definitions

*   **IMPLEMENTED**: A functional, executable implementation exists in the runtime (even if mocked via `AgentRuntime`).
*   **PARTIAL/STUB**: Some infrastructure exists (e.g., kernel state constants, basic event emission) but the full cognitive or procedural step is missing from the orchestrator.
*   **MISSING**: The state is documented in the constitution but completely absent from the executable SoftLoop pipeline.

## The Matrix

| Layer | Name | `StageId` | Status | Evidence in Codebase |
|---|---|---|---|---|
| **L01** | Intake | `INTAKE` | **PARTIAL** | `Intake` dataclass exists in `orchestrator/__init__.py`. Replaced by `GOAL_CREATED` event. Does not use full L01 mechanics. |
| **L02** | Triage | `TRIAGE` | **IMPLEMENTED** | `triage()` called in `SoftLoop.run()`. Sets weight class and budget. |
| **L03** | First-Principles | `RE_DERIVE` | **MISSING** | Defined in `StageId` but missing from `SoftLoop._run_body()`. |
| **L04** | Ambitious Ideation | `IDEATE` | **MISSING** | Defined in `StageId` but missing from `SoftLoop._run_body()`. |
| **L05** | Frontier Research | `RESEARCH` | **MISSING** | Defined in `StageId` but missing from `SoftLoop._run_body()`. |
| **L06** | Trade-off Analysis | `TRADEOFF` | **MISSING** | Defined in `StageId` but missing from `SoftLoop._run_body()`. |
| **L07** | Trade-off Mitig. | `MITIGATION` | **MISSING** | Defined in `StageId` but missing from `SoftLoop._run_body()`. |
| **L08** | System Design | `DESIGN` | **IMPLEMENTED** | `SoftLoop._run_body()` runs `StageId.DESIGN` with the Planner session. |
| **L09** | Multi-Persp. Crit. | `CRITIQUE` | **MISSING** | Defined in `StageId` but missing from `SoftLoop._run_body()`. |
| **L10** | Adversarial Review| `ADVERSARIAL_REVIEW`| **IMPLEMENTED** | (Design-time L10 vs Audit L14) SoftLoop implements one `ADVERSARIAL_REVIEW` after Verification via `InformationBarrierManager`. |
| **L11** | Formal Planning | `PLAN` | **IMPLEMENTED** | `SoftLoop._run_body()` runs `StageId.PLAN` with the Planner session. |
| **L12** | Branch Implement. | `IMPLEMENT` | **IMPLEMENTED** | `SoftLoop._run_body()` runs `StageId.IMPLEMENT` with the Builder session. |
| **L13** | Verification | `VERIFY` | **IMPLEMENTED** | `SoftLoop` passes builder evidence to the `Court` for adjudication. |
| **L14** | Independent Audit | `VERIFY`/`ADV_REVIEW` | **PARTIAL** | SoftLoop executes `ADVERSARIAL_REVIEW` as a single isolated adversary pass post-verification. |
| **L15** | Doc. & Ledger | `LEDGER_SYNC` | **MISSING** | Ledger appends occur, but the explicit `LEDGER_SYNC` agent session is not orchestrated. |
| **L16** | Promotion Decision| `SEAL` | **IMPLEMENTED** | `SoftLoop._run_body()` finishes by calling `SealAuthority.seal()`. |
| **L17** | Retrospective | `RETROSPECT` | **MISSING** | Defined in `StageId` but missing from `SoftLoop._run_body()`. |
| **L18** | Knowledge Extract.| `MEMORY_UPDATE` | **MISSING** | Defined in `StageId` but missing from `SoftLoop._run_body()`. |
| **L19** | Const. Evolution | `IMPROVE_RUNTIME` | **MISSING** | Defined in `StageId` but missing from `SoftLoop._run_body()`. |

## Conclusion

The forensic analysis confirms that `SoftLoop` is an intentionally partial, vertical-slice implementation designed to bootstrap the core build-verify-seal mechanics. It explicitly bypasses the deep-reasoning layers (L03-L07, L09) and the self-evolution layers (L17-L19), confirming the discrepancy noted in the backlog.
