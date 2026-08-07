# PAEOS — Project Instructions & Governance Rules

Welcome to **PAEOS** (Portable AI Engineering Operating System).

## Mandatory Operational Governance Rules

On every task execution, you MUST read and obey all governance principles in the `operations/` directory:

1. **`operations/CONSTITUTIONAL_REFLECTION_PRINCIPLE.md`**:
   - **Mandatory Constitutional Review**: Every completed task MUST conclude with a Constitutional Review testing spec assumptions against empirical implementation reality.
   - **3 Mandatory Outputs**:
     - Retrospective (`reviews/` & Ledger)
     - Technical Debt (`ledger/debt/`)
     - Improvement Proposals (`proposals/`) — generated when reality warrants a specification or architectural change.
   - **Reality Has Legislative Priority**: Empirical implementation evidence dominates written spec assumptions.

2. **`operations/FOUNDER_IMPLEMENTATION_PRINCIPLES.md`**:
   - One roadmap task to merge per session.
   - Every merge leaves main releasable (tests green, pyright strict).
   - Passing evidence, not assertion.
   - Founder ratification required for constitutional changes (CER-5).

3. **`operations/ENGINEERING_LIFECYCLE.md`**:
   - Strict 19-stage lifecycle execution.
   - Stage 17 (`MEMORY_UPDATE`) is the single canonical writer for Layer 3 Institutional Scars.

4. **`operations/IMPLEMENTATION_REVIEW_PROTOCOL.md`**:
   - Mandatory end-of-task review in `reviews/tasks/<task_id>_review.md`.

## Key Architectural Principles

- **Memory Lifetime Hierarchy (IP-0004 / IP-0005)**:
  - **Layer 1 (Ephemeral Working Memory)**: Destroyed when task step finishes.
  - **Layer 2 (Execution Context)**: Scoped strictly to `run_id` (`TaskPackage` retry hints, compile diagnostics). Destroyed when execution scope terminates.
  - **Layer 3 (Institutional Memory)**: Permanent cross-run scars/lessons. Synthesized EXCLUSIVELY by Evolution during Stage 17 (`MEMORY_UPDATE`).
