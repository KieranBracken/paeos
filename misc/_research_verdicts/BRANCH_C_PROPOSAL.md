# Candidate Architecture C (Event-driven / Blackboard Architecture)

Based on a review of the PAEOS core components (`kernel/types.py`, `kernel/ledger.py`, `runtime/orchestrator/__init__.py`), here is an independent proposal regarding the Event-driven / Blackboard execution model and its viability as the Canonical Execution Model for PAEOS.

### 1. What is the fundamental unit?
In an Event-driven/Blackboard architecture, the fundamental unit of execution is the **autonomous reaction to an observed state**. Agents monitor a shared space (the blackboard) for specific patterns or events and react by placing new facts/results back onto the board. 

Currently, PAEOS defines the fundamental unit of state change as the `TransitionRequest` (`kernel/types.py`), a strict four-tuple (Authority, Goal, Evidence, Validation). In a blackboard model, the fundamental unit of coordination shifts from a choreographed sequential call (as seen in the orchestrator) to asynchronous event emissions (e.g., a "Goal Opened" event triggering a Planner).

### 2. Who owns the topology?
In a Blackboard model, the **topology is emergent and decentralized**. There is no central orchestrator deciding what happens next. Each agent or capability acts independently based on the state of the blackboard. 

This is a stark contrast to the current implementation. In `runtime/orchestrator/__init__.py`, the `SoftLoop` strictly owns the topology, running an explicit, synchronous pipeline: Triage -> Design -> Plan -> Implement -> Verification Court -> Adversary -> Seal. Adopting a blackboard model would require dismantling this explicit orchestrator in favor of independent agent event loops.

### 3. How does branching/parallelism work in this model?
Branching and parallelism are **natural, decentralized, and highly scalable**. Multiple agents can observe the same state and react concurrently. For example:
- Multiple builders could independently attempt to satisfy a plan, racing to append a valid solution.
- Multiple adversary agents could review a sealed bundle in parallel.
- Experimental or speculative branches can be spawned simply by emitting events, without requiring the orchestrator to manage thread pools or DAGs.

### 4. Is this compatible with PAEOS's append-only Ledger?
**Yes, it is highly compatible.** In fact, the PAEOS Ledger (`kernel/ledger.py`) is an ideal substrate for a blackboard. 
- It is an immutable, single-writer, hash-chained log.
- Agents can independently tail the ledger (or a state projection derived from it) to observe facts.
- When an agent completes its work, it attempts to append its result as a new `Event` to the ledger.
- Concurrency control is already handled gracefully by the `Ledger._append_lock` and the `SingleWriterViolation`/`ForkRejected` guards at the storage layer. If two agents race to append conflicting transitions, the ledger guarantees serializability and total ordering.

### Conclusion
While Candidate Architecture C is perfectly compatible with the underlying ledger data structure, it represents a fundamental paradigm shift from the current `SoftLoop` orchestration. It trades strict, procedural predictability for highly scalable, emergent parallelism.
