# SAKG Archaeology — 01 Original Vision

**System:** Systems Architecture Knowledge Graph (SAKG)  
**Location:** `/Users/bob/GitHub/SAKG`  
**Specification Version:** v1.0.0 (Approved 2026-07-23)  

---

## 1. Primary Purpose & Definition

The SAKG was originally defined as a **domain-agnostic platform for representing, organizing, querying, and reasoning over engineering knowledge**.

Key thesis:
> *"This is not an encyclopedia. It is a formal specification for a computational model of engineering reasoning."*

The SAKG defines a stable, computable substrate upon which:
- Engineering principles,
- Component graphs,
- Causal mechanisms,
- Design trade-offs,
- Architectural laws, and
- Failure modes

can be represented as machine-queryable graph entities with strict schema and provenance.

---

## 2. Constitutional Foundation

SAKG is governed by a supreme **SAKG Constitution** (12 Articles) establishing:
1. **Specification-First Methodology**: Code must never precede formal specification.
2. **Causal & Invariant Grounding**: Engineering knowledge is not text matching; it is structural and causal relation.
3. **Immutable Decision History**: Decisions are recorded in ADRs; changes require Architecture Change Proposals (ACPs).
4. **Domain Independence**: Core ontology must remain domain-agnostic while supporting domain-specific extensions.

---

## 3. Core Ontology Taxonomy

From SAKG Phase 0.2–0.5 specs:
- **Entities**: Systems, Subsystems, Components, Functions, Constraints, Invariants, Hazards, Mechanisms, Failures.
- **Relationships**: `DEPENDS_ON`, `IMPLEMENTS`, `CONSTRAINS`, `VERIFIES`, `MITIGATES`, `CAUSES`, `EXEMPLIFIES`, `MUTATES`.
- **Reasoning Model**: Graph traversal over causal paths to evaluate trade-offs, verify non-vacuity, and trace failure blast radius.

---

## 4. Key Unresolved Questions for PAEOS

1. **Knowledge Substrate vs Reasoning Substrate**: Does SAKG own physical systems architecture knowledge while Concept OS owns semantic proximity / concept blending?
2. **PAEOS Integration**: Is SAKG the knowledge graph that PAEOS queries during L03 Re-Derivation and L06 Trade-off Analysis?
