# Candidate Architecture D: Event-Sourced State Machine / Policy-Driven

## Assessment
Candidate Architecture D (Event-Sourced State Machine / Policy-driven) is the natural and correct Canonical Execution Model for PAEOS. It aligns perfectly with the existing primitives and resolves the friction caused by the imperative, hardcoded orchestration currently present in the `SoftLoop`.

## 1. What is the fundamental unit?
The fundamental unit is the **`TransitionRequest`** (defined in `kernel/types.py` as a four-tuple of Authority, Goal, Evidence, and Validation) which results in an **`Event`** appended to the ledger. Instead of a function call in a procedural orchestrator, progress is modeled as discrete state transitions (e.g., moving from `DESIGN` to `PLAN`) proposed by independent actors.

## 2. Who owns the topology?
The topology is owned by **Policy (Kernel Gates & Capability Tokens)**, not an imperative orchestrator.
Currently, `runtime/orchestrator/__init__.py` (`SoftLoop`) hardcodes the execution DAG (DESIGN → PLAN → IMPLEMENT → Verification Court → Adversary Review → Seal). In a policy-driven model, the topology emerges dynamically. The kernel dictates valid state transitions and issues `CapabilityToken`s. Agents (Planner, Builder, Critic) act as autonomous reactors that observe the current state of the ledger, perform work, and propose the next valid transition.

## 3. How does branching/parallelism work in this model?
Parallelism is handled via **optimistic concurrency and the single-writer ledger**. 
Multiple agents can observe the ledger state, branch into isolated workspaces, and work concurrently (e.g., exploring multiple implementations or conducting parallel reviews). When they attempt to commit their work, they submit a `TransitionRequest`. Because `kernel/ledger.py` strictly enforces a single-writer, hash-chained log (`ForkRejected` on conflicting sequence numbers), the system naturally serializes concurrent branches. The first valid transition is appended, and competing parallel branches are either rejected or rebased.

## 4. Is this compatible with PAEOS's append-only Ledger?
Yes, it is fundamentally isomorphic to the append-only Ledger. 
The Ledger (`kernel/ledger.py`) is explicitly designed as an immutable log of `Event` objects. An event-sourced state machine treats this ledger as its single source of truth. The current system state is simply a projection derived by replaying the ledger. This fulfills the core PAEOS invariant (FR-5) where all authority and truth reside purely in the append-only log, removing the need for an external orchestrator to maintain state.
