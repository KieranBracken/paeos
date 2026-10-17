# 03_MISSING_DEPENDENCIES: The Dependency DAG

This document analyzes the dependency graph for the missing constitutional layers identified in `02_IMPLEMENTATION_MATRIX.md`. The goal is to determine the natural implementation order based on dataflow and architectural prerequisites.

## Missing Layer Dependency Analysis

The missing layers fall into three primary groups: The **Cognition Pipeline** (L03-L07, L09), the **State Synchronization** (L15), and the **Evolution Loop** (L17-L19).

### 1. The Cognition Pipeline (L03-L07, L09)
These layers represent the deep-reasoning phases before formal design and implementation. They operate sequentially.

*   **L03 First-Principles Re-Derivation (`RE_DERIVE`)**:
    *   **Depends on**: `RAW` (Implicit entry point for substantial features).
    *   **Provides for**: `INTAKE`.
*   **L04 Ambitious Ideation (`IDEATE`)**:
    *   **Depends on**: `TRIAGE`.
    *   **Provides for**: `RESEARCH`, `TRADEOFF`.
*   **L05 Frontier Research (`RESEARCH`)**:
    *   **Depends on**: `IDEATE`. (Research is targeted at ideated solutions).
    *   **Provides for**: `TRADEOFF`.
*   **L06 Trade-off Analysis (`TRADEOFF`)**:
    *   **Depends on**: `IDEATE`, `RESEARCH`.
    *   **Provides for**: `MITIGATION`.
*   **L07 Trade-off Mitigation (`MITIGATION`)**:
    *   **Depends on**: `TRADEOFF`.
    *   **Provides for**: `DESIGN` (L08).
*   **L09 Multi-Perspective Critique (`CRITIQUE`)**:
    *   **Depends on**: `DESIGN` (L08).
    *   **Provides for**: `ADVERSARIAL_REVIEW` (L10).

### 2. State Synchronization (L15)
*   **L15 Documentation & Ledger (`LEDGER_SYNC`)**:
    *   **Depends on**: `VERIFY` (L13) / `ADVERSARIAL_REVIEW` (L14).
    *   **Provides for**: `SEAL` (L16). (Ensures records are integrated before sealing).

### 3. The Evolution Loop (L17-L19)
These layers represent the system's self-improvement mechanisms, running post-execution.

*   **L17 Retrospective & CER (`RETROSPECT`)**:
    *   **Depends on**: `SEAL` (L16) (or a terminal failure).
    *   **Provides for**: `MEMORY_UPDATE` (L18).
*   **L18 Knowledge Extraction (`MEMORY_UPDATE` / `EVOLVE`)**:
    *   **Depends on**: `RETROSPECT` (L17).
    *   **Provides for**: Context injection in future loops (Scars, Templates).
*   **L19 Constitutional Evolution (`IMPROVE_RUNTIME` / `RESTART`)**:
    *   **Depends on**: Triggered by L18 or external founder proposal.
    *   **Provides for**: Upgraded system components and rules.

## Dependency DAG (Mermaid)

```mermaid
graph TD
    %% Existing Nodes
    L01_Intake["L01 Intake (INTAKE)"]
    L02_Triage["L02 Triage (TRIAGE)"]
    L08_Design["L08 System Design (DESIGN)"]
    L10_Adversarial["L10/L14 Adversarial Review"]
    L11_Plan["L11 Formal Planning (PLAN)"]
    L12_Implement["L12 Branch Implementation (IMPLEMENT)"]
    L13_Verify["L13 Verification (VERIFY)"]
    L16_Seal["L16 Promotion Decision (SEAL)"]

    %% Missing Nodes
    L03_ReDerive["L03 Re-Derivation (RE_DERIVE)"]:::missing
    L04_Ideate["L04 Ideation (IDEATE)"]:::missing
    L05_Research["L05 Frontier Research (RESEARCH)"]:::missing
    L06_Tradeoff["L06 Trade-off Analysis (TRADEOFF)"]:::missing
    L07_Mitigation["L07 Trade-off Mitigation (MITIGATION)"]:::missing
    L09_Critique["L09 Multi-Perspective Critique (CRITIQUE)"]:::missing
    L15_LedgerSync["L15 Documentation & Ledger (LEDGER_SYNC)"]:::missing
    L17_Retrospect["L17 Retrospective (RETROSPECT)"]:::missing
    L18_Knowledge["L18 Knowledge Extraction (MEMORY_UPDATE)"]:::missing
    L19_Evolution["L19 Constitutional Evolution (IMPROVE_RUNTIME)"]:::missing

    %% Relationships
    L03_ReDerive --> L01_Intake
    L01_Intake --> L02_Triage
    L02_Triage --> L04_Ideate
    L04_Ideate --> L05_Research
    L04_Ideate --> L06_Tradeoff
    L05_Research --> L06_Tradeoff
    L06_Tradeoff --> L07_Mitigation
    L07_Mitigation --> L08_Design
    L08_Design --> L09_Critique
    L09_Critique --> L10_Adversarial
    L10_Adversarial --> L11_Plan
    L11_Plan --> L12_Implement
    L12_Implement --> L13_Verify
    L13_Verify --> L10_Adversarial
    L13_Verify --> L15_LedgerSync
    L15_LedgerSync --> L16_Seal
    L16_Seal --> L17_Retrospect
    L17_Retrospect --> L18_Knowledge
    L18_Knowledge --> L19_Evolution

    classDef missing fill:#f9f,stroke:#333,stroke-width:2px;
```
