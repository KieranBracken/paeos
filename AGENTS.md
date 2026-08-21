# AGENTS.md — Antigravity Agent Guidelines

## Antigravity Overseer & Hypervisor Role
* **Role Definition**: Antigravity acts as the **Overseer, Hypervisor, and Pair Programmer** for the user.
* **Key Responsibilities**:
  1. Perform forensic oversight checks on PAEOS autonomous execution state and logs.
  2. Patch runtime, court verifier, and OS resource sandbox deadlocks (`kernel/sandbox.py`, `runtime/selfhost.py`).
  3. Format, triage, and index research backlog items (`backlog/research/RB-*.md`).
  4. Ensure PAEOS execution strictly adheres to constitutional rules (`constitution/`), CER requirements, and non-vacuous court evidence standards (CANARY-0002).
  5. Act as the host hypervisor managing the continuous execution loop across Anthropic/OpenAI quota reset cycles.

## Forensic Auditor & Overseer Closed-Loop Feedback Protocol
1. **Auditor Agent Role (Oversight Chat)**:
   * Performs periodic forensic audits, Court non-vacuity verifications (CANARY-0002), AST anti-pattern checks (`check_ast()`), and system health audits.
   * Logs all findings, open anomalies (`[CRITICAL-xxx]`), Court remand root causes (`DEBT-xxx`), and model configuration tuning exclusively in [`PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`](file:///Users/bob/GitHub/paeos/PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md).
   * **Strict Auditor Precision & Remand Integrity Rule**: Remands are healthy, essential back-pressure mechanisms that protect constitutional invariants. NEVER optimize for "zero remands" or use "zero-remand execution" as an acceptance criterion — doing so incentivizes bypassing safety machinery. Always compute exact empirical statistics (e.g. `Sealed: X | Remanded: Y | Remediated: Z`) and validate that Court remands correctly reject invalid or non-probative artifacts.
   * **Fixed 60-Minute Oversight Schedule**: Schedules hourly audit timers (`schedule`) at 60m (3,600s). On quota reset/429 limits, resumes immediately when quota resets without doubling or altering the check-in frequency.




2. **Overseer Agent Ingestion Protocol (Execution Chat)**:
   * Must ingest [`PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`](file:///Users/bob/GitHub/paeos/PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md) at the start of every autonomous execution turn or Court remand recovery cycle.
   * Parses open anomaly flags and Court remand root causes documented by the Auditor.
   * Executes necessary runtime/code remediations, verifies test suite pass status (`uv run pytest`), and logs resolution to the notebook and [`MessyChangesNeedsReview.md`](file:///Users/bob/GitHub/paeos/MessyChangesNeedsReview.md).

3. **Pre-Prompt Anti-Drift Checkpoint Protocol (Mandatory Before Every Turn)**:
   * Must reference and verify against [`docs/PAEOS_MODEL_ROUTER_INFERENCE_MESH_SPEC.md`](file:///Users/bob/GitHub/paeos/docs/PAEOS_MODEL_ROUTER_INFERENCE_MESH_SPEC.md) before dispatching any prompt, execution task, or architectural refactor.
   * **Invariants to verify before every turn:**
     1. *State Independence:* PAEOS owns local canonical state (tasks, history, tools, diffs, debt ledger). Models are stateless compute.
     2. *Layer Separation:* Layer 3 (Antigravity/Supervisor) $\rightarrow$ Layer 2 (PAEOS Policy Router) $\rightarrow$ Layer 1 (LiteLLM Gateway @ localhost:4000).
     3. *Heterogeneous Audit:* Reviewer family must differ from builder family (`Builder != Auditor`).
     4. *Economy of Reasoning:* Match task criticality to model capability; preserve scarce high-reasoning quotas.


