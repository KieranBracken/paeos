# Raw Architectural Propositions for Adversarial Review

The following are the raw structural execution models proposed for PAEOS. Persuasive rationale has been stripped to maintain epistemic isolation for adversarial critique.

**Model A (Goal-Centric / Hierarchical):** 
- Fundamental Unit: `TransitionRequest`
- Topology Ownership: Rigidly owned by a centralized Orchestrator capstone (`SoftLoop`).
- Concurrency: Parallel out-of-band task generation, strict serialization at ledger integration.

**Model B (DAG / Execution Graph):**
- Fundamental Unit: `TransitionRequest` mapping to `StageId` contexts.
- Topology Ownership: Orchestrator manages an explicit sequence graph (DAG).
- Concurrency: Parallel nodes execute concurrently, terminal state changes serialize at the ledger append lock.

**Model C (Event-driven / Blackboard):**
- Fundamental Unit: Autonomous reaction to observed ledger state.
- Topology Ownership: Emergent and completely decentralized. No central orchestrator.
- Concurrency: Agents tail the immutable ledger asynchronously and race to append state.

**Model D (Event-Sourced State Machine / Policy-Driven):**
- Fundamental Unit: `TransitionRequest` appended as an `Event`.
- Topology Ownership: Owned by Kernel Gates and explicit Policy, not an imperative script. Topology emerges from policy evaluating the current projected state.
- Concurrency: Optimistic concurrency. Parallel agents submit transitions; the single-writer ledger serializes valid transitions and rejects conflicting forks.
