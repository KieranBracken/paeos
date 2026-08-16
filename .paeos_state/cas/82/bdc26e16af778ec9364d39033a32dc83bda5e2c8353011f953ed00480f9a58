# Candidate Architecture B (DAG / Execution Graph) Proposal

Based on an inspection of the PAEOS reasoning continuity structures (`kernel/types.py`, `kernel/ledger.py`, and `runtime/orchestrator/__init__.py`), here is an independent evaluation of Candidate Architecture B as the canonical execution model.

### 1. What is the fundamental unit?
The fundamental unit of execution in this architecture is the **State Transition** (represented by the `TransitionRequest`), which encapsulates a strict four-tuple: Authority (`CapabilityToken`), Goal, Evidence, and Validation. At the storage layer, this maps to an `Event` appended as a hash-chained `LedgerRow`. At the runtime layer, work is chunked into execution contexts tied to a specific `StageId` (e.g., DESIGN, PLAN, IMPLEMENT).

### 2. Who owns the topology?
The topology is owned by the **Orchestrator** (the `SoftLoop` / `StagePlaybook`). It is a "soft-loop" that composes the execution graph (intake → triage → design/plan → implement → court verification → adversarial review → seal). The Orchestrator manages the sequencing and information barriers, while the Kernel enforces the rules (capability boundaries, ledger appending). 

### 3. How does branching/parallelism work in this model?
Branching and parallelism occur in the **generation/execution phase**, completely decoupled from the institutional commit phase. Multiple agent sessions, goals, or validation tasks (e.g., isolated adversaries or verification courts) can run concurrently. As noted in the `Ledger` implementation, "parallel generation feeds it, but institutional commit is strictly serialized." 

### 4. Is this compatible with PAEOS's append-only Ledger?
**Yes, it is fully compatible.** The DAG architecture naturally collapses into a linear event log. Although nodes in the graph can execute concurrently, any terminal state change (a commit, a remand, a quarantine, a seal) must funnel through the `Ledger`'s `append()` method. The Ledger enforces a strict single-writer lock (`_append_lock`) and fork rejection (preventing two rows at the same sequence). Therefore, the distributed, branching runtime graph safely maps onto a totally ordered, append-only, hash-chained ledger.
