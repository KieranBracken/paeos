# RB-0005 — Mission 0: Discover SAKG (The Archaeological Derivation Pattern)

- **Status:** Research Backlog *(Not Proposal — No implementation authorised)*
- **Priority:** Critical *(Prerequisite for SAKG)*
- **Filed:** 2026-08-05
- **Origin:** Founder & Co-Lead synthesis on repository evidence processing, CER-1 first-principles derivation, and SAKG bootstrapping.

---

## 1. Executive Summary & Core Philosophy

When transitioning PAEOS from completing its own self-hosting kernel to building **SAKG (Semantic Architectural Knowledge Graph)**, we face a fundamental choice:

- **Option A (Ignore existing repos & start from scratch):** Rejects months/years of hard-won architectural insights, violating PAEOS's core rule: *Evidence over speculation*.
- **Option B (Treat current repos as absolute truth):** Inherits obsolete assumptions, unfinished spikes, technical debt, and abandoned experiments.
- **Option C (The PAEOS Way — Repository as Evidence, Not Law):** Interrogates existing codebases as an archaeological evidence corpus, re-deriving the target system from first principles (CER-1).

```mermaid
flowchart TD
    Repo[Existing Repositories & Docs] + FP[First-Principles Derivation - CER-1] --> Audit[Phase A & B: Archaeological Audit]
    Audit --> Evidence[Evidence & Comparative Synthesis]
    Evidence --> Spec[Phase C: Canonical SAKG Architecture Spec]
    Spec --> Ratify[Phase D: Founder Ratification]
    Ratify --> Build[Phase E: TDD Implementation]
```

---

## 2. Mission 0: Discover SAKG (Execution Blueprint)

Instead of prompting PAEOS to "Build SAKG", the initial mission is **"Mission 0: Discover SAKG"**.

### Phase A — Repository Census & Ingestion
- Audit all existing SAKG markdown files, design notes, proposals, spikes, and debt entries.
- Map the historical lineage of ideas, identifying what was built, what was abandoned, and what remains unverified.

### Phase B — First-Principles Derivation (CER-1)
- Re-derive SAKG from first principles ("What must a semantic architectural knowledge graph do?").
- Cross-reference the first-principles model against the repository census:
  - **Validated Ideas ($\checkmark$):** Enduring concepts backed by evidence.
  - **Weak / Debt Ideas ($\Delta$):** Assumptions that fail first-principles challenge.
  - **Contradictions ($\times$):** Divergences between early notes and Phase 3 PAEOS reality.
  - **Missing Ideas ($\Omega$):** Uncovered gaps needed for ecosystem integration.

### Phase C — Canonical Architecture Proposal
- Produce the unified, steel-topped `SAEOS-1-architecture.md` specification.
- Submit to the Founder for **A4 Ratification**.

### Phase D — TDD Implementation
- Only after ratification does PAEOS generate the DAG backlog (`SAKG-1-backlog.yaml`) and begin TDD implementation.

---

## 3. Why This Demonstrates PAEOS's Ultimate Value

> 💡 **The Ultimate Proof of PAEOS:**  
> **PAEOS proves its true value not merely by writing lines of code, but by taking years of evolving, partially completed research, separating enduring engineering truths from obsolete assumptions, and producing a coherent, evidence-backed architecture before a single line of new implementation is written.**

---

## 4. Expected Trigger
Execute **Mission 0: Discover SAKG** as the very first goal when initiating SAKG development.
