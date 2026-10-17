# 06_COMPLETENESS_CRITERIA: Definition of Done

This document establishes the Definition of Done (DoD) for a canonical PAEOS execution layer. For any of the missing layers (L03-L07, L09, L15, L17-L19) to be considered "IMPLEMENTED," they must meet all of the following criteria.

## Completeness Criteria for a Lifecycle Layer

1.  **Kernel Lattice Integration**:
    *   The state must be defined in `kernel/types.py` as a `StageId`. (Already true for all 19).
    *   Legal edges to and from the state must be defined in `kernel/lifecycle.py`. (Already true).
2.  **Orchestrator Execution (`SoftLoop`)**:
    *   The `SoftLoop._run_body()` function must explicitly orchestrate the state.
    *   It must mint a Task Package via `open_stage()`.
    *   It must invoke the `StagePlaybook` with the correct session role (e.g., `planner`, `researcher`, `reviewer`).
3.  **Context Compilation**:
    *   The Context Compiler must properly resolve the in-scope graphs for the new state.
    *   It must correctly map the appropriate `mcp_servers` and `skills` capability tokens to the state.
4.  **Artifact Emission & Validation**:
    *   The dispatched worker must produce the constitutionally required artifact (e.g., a formal Derivation, a Trade-off Matrix, a Retrospective).
    *   The artifact must be saved to the CAS.
5.  **Kernel Gating**:
    *   The transition out of the state must be gated by the kernel enforcing the four-tuple contract.
    *   The orchestrator must handle the failure routes (e.g., `REMAND`) appropriately if the gate fails.
6.  **Evidence Flow**:
    *   Evidence generated during the state must be properly bound (`artifact_hash`) and passed forward to the next state via the Information Barrier Manager (IBM) when crossing trust boundaries.
