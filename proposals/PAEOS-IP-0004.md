# PAEOS-IP-0004 — Ephemeral Execution Context vs. Constitutional Institutional Memory

Status: **RATIFIED BY FOUNDER** (2026-07-30) · Filed: 2026-07-30 · Channel: CER-2  
Resolution: Amends `PAEOS-IP-0004` to complement `PAEOS-IP-0005`. Establishes the distinction between **Ephemeral Execution Context** (transient operational state carried during retries) and **Institutional Memory** (constitutional knowledge governed by IP-0005).

---

## 1. Observation & Architectural Refinement

Previous drafts referred to transient retry state as "Operational Memory". As identified in constitutional analysis, calling operational execution state "memory" muddied the constitutional ownership model.

`PAEOS-IP-0005` establishes the overarching **Constitutional Memory Trilogy**:
- **Trigger**: Verification Court (determines failure / remand)
- **Author**: Evolution Layer (Stages 15–17, synthesizes root causes)
- **Commit**: Kernel TCB (persists institutional memory to Scar Store)

`PAEOS-IP-0004` defines the complementary operational requirement: **Ephemeral Execution Context** for retries within a single run without violating IP-0005's institutional memory authority.

---

## 2. Ephemeral Execution Context vs. Institutional Memory

| Attribute | Ephemeral Execution Context (IP-0004) | Institutional Memory (IP-0005) |
| :--- | :--- | :--- |
| **Concept** | Operational State & Retry Hints | Constitutional Knowledge & Scars |
| **Examples** | `retry_hint`, compile error logs, backoff flags, temporary hypotheses | Canonical Scars, Anti-patterns, Capability Ratings, Precedents |
| **Carrier** | In-memory `TaskPackage` / `RunState` | Durable Scar Store / Ledger |
| **Scope & Lifetime** | Scoped strictly to active `run_id`; **destroyed** when execution scope terminates | Permanent cross-run institutional record |
| **Ownership** | Operational Runtime (`SoftLoop`) | **Trigger**: Court $\rightarrow$ **Author**: Evolution $\rightarrow$ **Commit**: Kernel |

---

## 3. Proposed Axioms

### Axiom 1: Execution State Scoping
Operational subsystems (`SoftLoop`, Stages 1–14) may attach transient **Execution Context** (`retry_hint`, compiler diagnostics, backoff state) to a `TaskPackage` during retries within a single `run_id`. Execution Context is destroyed when the execution scope terminates and NEVER enters institutional memory.

### Axiom 2: Constitutional Memory Authority (IP-0005 Alignment)
Institutional Memory — including canonical Scars, Lessons, and Anti-patterns — is NEVER authored or committed by operational execution (`SoftLoop`). Institutional Memory is authored exclusively by **Evolution** (Stages 15–17) from accumulated ledger evidence and committed by the **Kernel TCB**.

---

## 4. Hierarchy of Principles

```
PAEOS-IP-0005 (Constitutional Authority of Institutional Memory)
   │
   ├── Defines: Trigger (Court) ──> Author (Evolution) ──> Commit (Kernel)
   │
   └── PAEOS-IP-0004 (Ephemeral Execution Context)
       └── Defines: Transient Execution Context carried in TaskPackage during retries.
```

---

## 5. Recommendation

**Ratify PAEOS-IP-0004 alongside PAEOS-IP-0005** to establish the complete separation between ephemeral operational state (`TaskPackage` execution context) and permanent constitutional knowledge (Kernel-committed institutional scars).
