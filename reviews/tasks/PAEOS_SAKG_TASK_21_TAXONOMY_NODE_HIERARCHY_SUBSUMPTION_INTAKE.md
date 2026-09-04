# SAKG Task 21 — Taxonomy Node Hierarchy Subsumption

**Milestone:** 45 of 48  
**Status:** **OPEN / QUEUED**  
**Opened:** 2026-09-04  
**Predecessor:** Milestone 44 `[I-L15-SIZING]` / L15 Dynamic Context Sizing

## Objective

Define and implement the SAKG taxonomy-node hierarchy subsumption contract. A child node may be
subsumed by a parent only when the relation is typed, acyclic, provenance-bearing, and compatible
with the parent’s scope and constraints. The contract must preserve node identity, expose
explanations and counterexamples, and fail closed on cycles, ambiguous parents, incompatible
scopes, or missing evidence. It must support deterministic replay and leave existing claims
unchanged until an explicit Court/SAKG promotion decision.

## Deliverables and acceptance

- A canonical taxonomy/subsumption specification and implementation in the SAKG boundary.
- Focused tests for valid transitive subsumption, cycle rejection, ambiguity rejection, scope and
  constraint incompatibility, provenance retention, deterministic ordering/digest, and no-op
  behavior for already canonical nodes.
- A machine-readable subsumption decision containing child/parent identifiers, relation type,
  evidence references, scope transfer assessment, explanation, and failure reason when rejected.
- Existing SAKG and Concept OS read/query contracts remain compatible; Concept OS candidates are
  not promoted as SAKG claims by this task.
- A reproducible local evidence bundle, non-vacuous Court record, and heterogeneous A-08 physical
  audit (builder family differs from auditor family) before any completion disposition.

## Constitutional constraints

SAKG remains the sole authority for engineering taxonomy and claim promotion. Concept Graph
relations are inputs or references, not authority. Taxonomy subsumption does not widen a claim’s
scope automatically and must carry per-domain transfer confidence. Raw corpus material remains
in the corpus/KAE substrate and is cited by content hash rather than copied into SAKG.

No provider transmission, retry, fallback, promotion, merge, or protected-ref mutation is
authorized by this intake. Milestone 45 is queued for isolated SoftLoop execution; no
implementation or seal is claimed here.
