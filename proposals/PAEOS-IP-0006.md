# PAEOS-IP-0006 — Constitutional Knowledge Lifetime Ontology

Status: **RATIFIED BY FOUNDER** (2026-07-30) · Filed: 2026-07-30 · Channel: CER-2  
Resolution: Introduces a 2-axis information classification system (Purpose × Lifetime) establishing the 6 Constitutional Lifetime Classes ($L0$ – $L5$) across all PAEOS information artifacts.

---

## 1. Executive Summary

PAEOS classifies information artifacts by **Purpose** (Evidence, Debt, Proposal, Scar, Ledger, Policy, etc.). Implementation has revealed a second independent axis: **Knowledge Lifetime**.

Every information artifact exists for a defined duration. Lifetime governs:
- Authority & Ownership
- Storage & Persistence
- Visibility & Mutability
- Destruction & Garbage Collection

---

## 2. The 6 Constitutional Lifetime Classes ($L0$ – $L5$)

```
Class    Name                          Owner         Lifetime            Persisted  Rebuildable
───────────────────────────────────────────────────────────────────────────────────────────────
L0       Scratch                       Worker        Step / Function     Never      No
L1       Ephemeral Execution Context   Runtime       run_id              No         No
L2       Runtime Projection            Runtime       Session             Cache      100% Yes
L3       Institutional Memory          Evolution     Cross-Run           Durable    No
L4       Constitutional Knowledge      Founder       Until Amended       Durable    No
L5       Historical Truth              Kernel        Forever             Immutable  No
```

---

## 3. Detailed Class Definitions & Artifact Mapping

### $L0$ — Scratch (Owner: Worker)
- **Lifetime**: Destroyed when task step/function terminates.
- **Artifacts**: Local variables, chain-of-thought, temporary tool outputs, raw parsing buffers.

### $L1$ — Ephemeral Execution Context (Owner: Runtime / SoftLoop)
- **Lifetime**: Scoped strictly to active `run_id`. Destroyed when execution scope terminates.
- **Artifacts**: Retry hints (`retry_hint`), compile error logs, backoff flags, temporary execution notes.

### $L2$ — Runtime Projection (Owner: Runtime)
- **Lifetime**: Execution session. Derived 100% from $L4$/$L5$; non-authoritative cache.
- **Artifacts**: `CompiledContext`, `TaskPackage`, graph projections, dependency views, execution plans.

### $L3$ — Institutional Memory (Owner: Evolution Layer)
- **Lifetime**: Permanent cross-run record. Synthesized EXCLUSIVELY in Stage 17 (`MEMORY_UPDATE`).
- **Artifacts**: Canonical Scars, Lessons, Heuristic Patterns, Anti-patterns, Capability Ratings.

### $L4$ — Constitutional Knowledge (Owner: Founder)
- **Lifetime**: Permanent until amended by Founder via §14.5 ceremony.
- **Artifacts**: Kernel Spec (v1.1), Constitution, Policies, Lifecycle Rules, Interface Contracts, Proposals (`IP-`), Debt (`DEBT-`).

### $L5$ — Historical Truth (Owner: Kernel TCB)
- **Lifetime**: Forever. Immutable, append-only ledger and content-addressed blobs.
- **Artifacts**: Ledger Events, CAS Blobs (`Evidence`), Genesis Record, Seal Records.

---

## 4. Falsification Mapping Audit

Every PAEOS object maps **unambiguously** to exactly one lifetime class ($L0$ – $L5$):

```
Evidence ─────────────────────────> L5 (Historical Truth)
LedgerEvent ──────────────────────> L5 (Historical Truth)
SealRecord ───────────────────────> L5 (Historical Truth)
KernelSpec (v1.1) ────────────────> L4 (Constitutional Knowledge)
ImprovementProposal (IP-) ────────> L4 (Constitutional Knowledge)
TechnicalDebt (DEBT-) ────────────> L4 (Constitutional Knowledge)
Scar / Lesson ────────────────────> L3 (Institutional Memory)
CompiledContext / TaskPackage ────> L2 (Runtime Projection)
RetryHint / RemandNote ───────────> L1 (Ephemeral Execution Context)
ScratchFile / CoT ────────────────> L0 (Scratch)
```

---

## 5. Constitutional Invariant

Every information artifact in PAEOS SHALL declare its `lifetime_class` ($L0$ – $L5$). Promotion between lifetime classes may ONLY occur through explicit, verified constitutional transitions (e.g., $L1$ evidence $\rightarrow$ $L3$ Scar via Stage 17 Evolution).

---

## 6. Recommendation

**Ratify PAEOS-IP-0006** alongside IP-0005 and IP-0004 to establish the complete 2-axis Information Ontology across PAEOS.
