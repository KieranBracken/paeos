# 04_DATAFLOW_ANALYSIS: Layer Dataflow and Execution Context

This document outlines the dataflow architecture between the 19 canonical layers. It is derived from `spec/PAEOS-9-execution-architecture.md`.

## The Inner Loop Dataflow

The 19 layers form the outer loop (the "spine"). However, execution at *every* single layer runs through a strict inner loop that crosses trust boundaries.

1.  **Kernel Invocation (Z1)**: The kernel's `open_stage()` function mints a `TaskPackage` and a `CapabilityToken` for the current stage.
2.  **Context Compilation (Z2)**: The Context Compiler pulls the applicable rules, contracts, and graph snapshots (goal, rule, dependency, scar, etc.) and compiles them deterministically into a content-hashed `RuntimeContext`.
3.  **Task Package Compilation (Z2)**: Generates the deterministic worker package from the `RuntimeContext`.
4.  **Worker Execution (Isolated Z2)**: The dispatched agent (e.g., Planner, Builder, Researcher) reasons within its sandbox. It can only interact with its allowed MCP tools and only write to its explicitly allowed scopes.
5.  **Artifacts & Evidence Generation (Z2 → Z1)**: The worker produces artifacts (saved to CAS) and evidence.
6.  **Gate & Evidence Re-run (Z1)**: The kernel checks the four-tuple requirement (Authority, Goal, Evidence, Validation). Deterministic evidence is re-run by the kernel. The gate either returns `COMMITTED` (advances the stage) or failure (`REMAND`, `REJECT`, `QUARANTINE`, `ABORT`).

## Trust Zone Crossings

- **Z1 (Kernel, Trusted)**: Holds authority, validates transitions, interacts with the ledger.
- **Z2 (Untrusted)**: The orchestrator, compiler, and dispatcher.
- **Isolated Z2 (Sandbox)**: The actual worker sessions.

Data crossing from Z2 to Z1 must always be accompanied by valid evidence and a CapabilityToken. The worker is entirely untrusted and "rents" reasoning power; the kernel verifies the output.

## Feed-Forward Dataflow (The Evolution Loop)

The pipeline is not linear; it is a loop that feeds itself.

-   **L17 (Retrospective) & L18 (Knowledge Extraction)**: Produce "scars" and skills based on the success or failure of the previous task.
-   **Context Recompilation**: Scars and new skills are written to the CAS/Ledger. When the Context Compiler runs for the *next* task, it pulls these new scars into the `RuntimeContext`.
-   **Active Guards**: A failure on Task A becomes an active guard (a scar) injected at `L03`, `L08`, `L09`, and `L13` for Task B.

## Evidence Back-Pressure

Evidence does not just flow forward; it acts as back-pressure. If L13 (Verification) fails, the gate emits a `REMAND` outcome, pushing the state backward to L12 (Implementation). This ensures that a defective task never falls off the end of the pipeline.

## Information Barrier Handoffs

Workers do not communicate directly. The output of one worker (e.g., Builder) is serialized to the CAS. The kernel constructs an Information Barrier bundle (IBM bundle) and passes *only* the bundle to the next worker (e.g., Verifier or Adversary).
