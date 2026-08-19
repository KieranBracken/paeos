# Candidate Architecture A: Goal-Centric / Hierarchical Architecture

This proposal analyzes Candidate Architecture A for the PAEOS Canonical Execution Model based on the core structures found in `kernel/types.py`, `kernel/ledger.py`, and `runtime/orchestrator/__init__.py`.

## 1. What is the fundamental unit?
The fundamental unit of execution and state change is the **TransitionRequest** (the four-tuple transition contract). Every state change requires exactly four components:
1. **Authority** (`CapabilityToken`)
2. **Goal** (`GoalId` and `RunId`)
3. **Evidence** (`tuple[EvidenceRef, ...]`)
4. **Validation** (`ValidationClaim`)

In the ledger itself, the fundamental unit of storage is the **Event**, which represents a single committed action with a `schema_ver`, `kind`, and JSON `payload`.

## 2. Who owns the topology?
The topology is owned by the **Orchestrator** (specifically, the `SoftLoop` in `runtime/orchestrator/__init__.py`). It acts as a Phase-1 capstone that rigidly composes the entire execution spine (Intake -> Triage -> Design -> Plan -> Implement -> Court Verification -> Adversarial Review -> Seal). The runtime itself holds no opinions; it simply walks the build chain and orchestrates the autonomous run, while decisions are deferred to the kernel, court, and gates.

## 3. How does branching/parallelism work in this model?
Parallelism operates on a **generate-then-serialize** model. While generation and execution (e.g., parallel goals via a `ConcurrentScheduler`) can happen concurrently out-of-band, institutional commit is strictly serialized.
The ledger explicitly prohibits forks (`ForkRejected`) and enforces a single writer (`SingleWriterViolation`). Parallel processes feed into a single integration point (guarded by `_append_lock` in `Ledger.append()`), which serializes the parallel generation onto one dense, unforked chain.

## 4. Is this compatible with PAEOS's append-only Ledger?
**Yes, entirely.** This architecture is fundamentally designed around the append-only, single-writer ledger constraints.
- The single-writer K8 integration point natively supports concurrent generation without violating ledger integrity.
- The ledger guarantees (Append-only, Hash-chained, Single-writer) strictly defeat fork attacks (T7).
- All outcomes—whether sealed, remanded, or halted—are tracked, and budgets are metered against the actual paths taken, flowing perfectly into the append-only record without requiring mutating or deleting past rows.
