# 09_RECOMMENDED_TARGET: Next Implementation Goals

Based on the forensic audit and the dependency DAG of the missing layers, this document outlines the recommended next targets for implementation.

## 1. Halt RCL Construction
The Reasoning Continuity Layer (RCL) should be paused. RCL is designed to checkpoint intra-stage cognitive reasoning (e.g., Ideation, Trade-offs). Since these primary cognitive layers do not exist in the current `SoftLoop` runtime, RCL cannot be fully integrated, validated, or used.

## 2. Recommended Next Target: L03 (First-Principles Re-Derivation)
The immediate next target must be the construction of `L03 First-Principles Re-Derivation`.
*   **Why**: Dataflow dependency. L03 is the first missing layer in the cognitive pipeline after Triage (L02).
*   **Constitutional Importance**: Restores compliance with **CER-6** ("All Work Must Be Derived"). Currently, tasks proceed straight to Design/Plan without derivation, risking hallucinated constraints.
*   **Implementation Steps**:
    1.  Update `runtime/orchestrator/__init__.py` to explicitly orchestrate `StageId.RE_DERIVE` after `TRIAGE`.
    2.  Create the `re_derive` task package and prompt templates.
    3.  Ensure the Context Compiler maps the correct constitution constraints and goal dependencies to the `re_derive` context.
    4.  The output of this layer must be a formal "Derivation Artifact" saved to the CAS, which becomes required context for the next step (whether Ideation or Design).

## 3. Subsequent Targets
Once L03 is implemented and stabilized, the sequence should proceed strictly down the cognitive pipeline:
*   `L04 Ambitious Ideation`
*   `L05 Frontier Research`
*   `L06 Trade-off Analysis`
*   `L07 Trade-off Mitigation`
*   `L09 Multi-Perspective Critique`

Only after the cognitive pipeline is restored should development of the Reasoning Continuity Layer (RCL) resume.
