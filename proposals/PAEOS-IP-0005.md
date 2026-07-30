# PAEOS-IP-0005 — Constitutional Memory Authority & Separation of Powers

Status: **RATIFIED BY FOUNDER** (2026-07-30) · Filed: 2026-07-30 · Channel: CER-2  
Resolution: Establishes the constitutional authority trilogy for institutional memory creation across the 19-stage lifecycle.

---

## 1. Observation

A foundational separation-of-powers gap exists if operational execution components (`SoftLoop`) directly write institutional memory (Scars) into the persistent store during task execution.

Writing institutional memory is a constitutional act. It requires three distinct, decoupled constitutional roles:
1. Deciding that an execution anomaly occurred (**Trigger**).
2. Analyzing root causes across runs and authoring lessons (**Author**).
3. Committing approved lessons to the durable store (**Commit**).

---

## 2. The Constitutional Memory Trilogy

Institutional memory creation is strictly decomposed into three distinct constitutional acts:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. TRIGGER: Verification Court (Runtime / Stage 13)                         │
│ Determines that a task failed, remanded, or violated a claim.               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. AUTHOR: Evolution Layer (Runtime / Stages 15–17)                          │
│ Analyzes accumulated ledger evidence across runs, discovers recurring        │
│ patterns, and authors canonical Scars/Lessons during Stage 17 (MEMORY_UPDATE).│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. COMMIT: Kernel TCB (Kernel / Stage 17)                                    │
│ Verifies authority, validates signature invariants (K6), and commits the     │
│ canonical Scar to the durable Scar Store.                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Constitutional Axioms

### Axiom 1: Separation of Memory Powers
Operational execution workers (`Builder`) and operational loop orchestrators (`SoftLoop`) SHALL NEVER directly author or commit institutional memory.

### Axiom 2: Court Trigger Authority
Only the **Verification Court** (Stage 13) possesses the authority to trigger failure/remand incidents on the ledger.

### Axiom 3: Evolution Authorship
Only the **Evolution Layer** (Stages 15–17) possesses the authority to analyze cross-run ledger evidence and author canonical Scars.

### Axiom 4: Kernel Commit
Only the **Kernel TCB** possesses the authority to write committed Scars to the durable Scar Store after verifying invariants (K6).

---

## 4. Recommendation

**Ratify PAEOS-IP-0005** to establish the Constitutional Memory Authority trilogy across all PAEOS workloads.
