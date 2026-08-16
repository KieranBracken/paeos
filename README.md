# PAEOS — Portable AI Engineering Operating System

Welcome to **PAEOS** (Portable AI Engineering Operating System).

---

## 1. Operational Entry Points & Execution Commands

### A. Autonomous Pipeline Driver (Live Mission Execution)
Drives a backlog of goals through the 19-stage lifecycle autonomously using live worker sessions.

* **File**: `ops/autonomous_run.py`
* **Usage**:
  ```bash
  PYTHONPATH=. uv run python ops/autonomous_run.py <backlog.json> <state_dir> [max_concurrency] [max_runs]
  ```
* **Example (Running SAKG Mission 1)**:
  ```bash
  PYTHONPATH=. uv run python ops/autonomous_run.py ops/backlogs/sakg-1-intakes.json state_sakg/ 1 25
  ```

### B. CLI Control Plane (Manual & Inspection)
The operator CLI to create goals, advance stages, inspect states, or dump event logs.

* **File**: `cli/paeos.py`
* **Commands**: `create-goal`, `advance`, `seal`, `inspect`, `ledger`, `replay`, `demo`
* **Example (Running the Interactive Demo Flow)**:
  ```bash
  PYTHONPATH=. uv run python cli/paeos.py demo
  ```
* **Example (Dumping Ledger Event Log)**:
  ```bash
  PYTHONPATH=. uv run python cli/paeos.py ledger
  ```

### C. Test Suite & Verification Commands
* **Run Unit/Integration Tests**:
  ```bash
  uv run pytest
  ```
* **Run Strict Type Check**:
  ```bash
  uv run pyright
  ```
* **Run Linter**:
  ```bash
  uv run ruff check .
  ```

---

## 2. Mandatory Operational Governance Rules

On every task execution, agents and operators MUST obey all governance principles in the `operations/` directory:

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

---

## 3. Key Architectural Principles

- **Memory Lifetime Hierarchy (IP-0004 / IP-0005)**:
  - **Layer 1 (Ephemeral Working Memory)**: Destroyed when task step finishes.
  - **Layer 2 (Execution Context)**: Scoped strictly to `run_id` (`TaskPackage` retry hints, compile diagnostics). Destroyed when execution scope terminates.
  - **Layer 3 (Institutional Memory)**: Permanent cross-run scars/lessons. Synthesized EXCLUSIVELY by Evolution during Stage 17 (`MEMORY_UPDATE`).
