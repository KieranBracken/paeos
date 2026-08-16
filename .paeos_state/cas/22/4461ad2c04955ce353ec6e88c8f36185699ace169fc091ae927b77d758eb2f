# 08_CONSTRUCTION_SEQUENCE: Safe Implementation Sequence

Based on the forensic audit, the dependency DAG (`03_MISSING_DEPENDENCIES.md`), and the RCL integration points (`07_RCL_INTEGRATION_POINTS.md`), this document proposes the safe construction sequence for implementing the missing canonical architecture.

## Principles of Construction

1.  **Do not break the working vertical slice**: The existing `SoftLoop` (L01/L02 -> L08 -> L11 -> L12 -> L13 -> L10/L14 -> L16) must remain functional during construction.
2.  **Build upstream first**: Dataflow dictates that L03 must exist before L04 can consume its output.
3.  **Defer RCL integration**: RCL cannot be integrated into layers that do not exist. Build the cognitive layers first, then weave RCL into them.

## The Sequence

### Phase 1: The Cognition Pipeline (L03-L07, L09)
This phase bridges the gap between Triage (L02) and System Design (L08).

*   **Step 1.1**: Implement `L03 First-Principles Re-Derivation`. Inject this step between `RAW` and `INTAKE` / `TRIAGE` in `SoftLoop`.
*   **Step 1.2**: Implement `L04 Ambitious Ideation` and `L05 Frontier Research`.
*   **Step 1.3**: Implement `L06 Trade-off Analysis` and `L07 Trade-off Mitigation`.
*   **Step 1.4**: Implement `L09 Multi-Perspective Critique`. Inject this step between `DESIGN` and formal `PLAN` / `ADVERSARIAL_REVIEW`.

### Phase 2: The Evolution Loop (L17-L19)
This phase establishes the self-improvement and memory mechanisms post-execution.

*   **Step 2.1**: Implement `L17 Retrospective`. Trigger this after a successful `SEAL` or a terminal failure (`HALTED`/`ABORTED`).
*   **Step 2.2**: Implement `L18 Knowledge Extraction`. Connect this to the output of `L17` to generate versioned skills and scars.
*   **Step 2.3**: Implement `L19 Constitutional Evolution`. Hook this into the proposal generation of L18.

### Phase 3: State Synchronization (L15)
*   **Step 3.1**: Implement explicit `L15 Documentation & Ledger` sync. While ledger appends occur, the formal synchronization and documentation step needs explicit orchestration before `SEAL`.

### Phase 4: RCL Integration
With the cognitive layers constructed, the Reasoning Continuity Layer can now be safely woven in.

*   **Step 4.1**: Integrate RCL into `L03`, `L04`, and `L06`.
*   **Step 4.2**: Integrate RCL into `L09` and the existing `L08`, `L11`, and `L12` layers.
