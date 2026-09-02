# SAKG / Engineering Intelligence Platform — Comprehensive Source Inventory

This document surveys and indexes all candidate source materials across the workspace and adjacent repositories for the SAKG (Semantic/Systems Architecture Knowledge Graph / Engineering Intelligence Platform) programme.

---

## 1. Constitutional & Foundational Documents
* `/Users/bob/GitHub/SAKG/0.1_constitutionV1.txt`: Original SAKG constitution (v1), defining epistemic principles, knowledge graphs as first-class citizens, and architectural truth.
* `/Users/bob/GitHub/SAKG/SAKG_v1.0/SAKG_Constitution.md`: Formal SAKG v1.0 Constitution defining immutable principles, authority, and ontology invariants.
* `/Users/bob/GitHub/SAKG/Engineering-Intelligence/00-North-Star/`: Core vision and north star definitions for the Engineering Intelligence platform.
* `/Users/bob/GitHub/Concept Graph /00_PROJECT_VISION.md`: High-level vision of the conceptual graph intelligence layer.

---

## 2. Ontology & Schema Specifications
* `/Users/bob/GitHub/SAKG/PHASE 0.2 — Core Ontology Specification.txt`: Core entity types (Concepts, Claims, Systems, Decisions, Evidence, Constraints).
* `/Users/bob/GitHub/SAKG/Phase 0.3 — Relationship Ontology.txt`: Directional and semantic edge definitions (supports, refutes, depends_on, implements, bounds, invalidates).
* `/Users/bob/GitHub/SAKG/Phase 0.4 — Metadata Schema.txt`: Temporal, provenance, epistemic confidence, and author attribution schemas.
* `/Users/bob/GitHub/Concept Graph /02_CONCEPT_MODEL.md`: Concept representation, taxonomic hierarchy, and node properties.

---

## 3. Relationship, Semantic, Reasoning & Query Models
* `/Users/bob/GitHub/SAKG/Phase 0.5 — Reasoning Model.txt`: Epistemic inference engine, non-monotonic truth maintenance, contradiction detection, and belief propagation.
* `/Users/bob/GitHub/Concept Graph /03_SEARCH_ARCHITECTURE.md`: Subgraph retrieval, semantic similarity, and hybrid vector/symbolic querying.
* `/Users/bob/GitHub/Concept Graph /04_DISCOVERY_ENGINE.md`: Autonomous relationship discovery, link prediction, and hidden connection mining.
* `/Users/bob/GitHub/SAKG/SAKG_v1.0/ACP_Specification.md`: Architectural Concept Protocol (ACP) for exchanging architectural knowledge packets.

---

## 4. Previous Architecture Designs & System Specifications
* `/Users/bob/GitHub/SAKG/SAKG_v1.0/SAKG_System_Specification/`:
  - `01_Purpose.md`
  - `02_Core_Principles.md`
  - `03_Design_Goals.md`
  - `04_System_Architecture.md`
  - `05_Component_Architecture.md`
  - `06_Development_Workflow.md`
  - `07_Governance.md`
  - `08_Phase_Roadmap.md`
  - `09_Architectural_Boundaries.md`
  - `10_Normative_Definitions.md`
  - `11_Future_Specifications.md`
* `/Users/bob/GitHub/Concept Graph /07_CURRENT_ARCHITECTURE.md`: Architecture of the prototype concept indexing graph.
* `/Users/bob/GitHub/paeos/misc/ecosystem_prep/sakg/`:
  - `01_ORIGINAL_VISION.md`
  - `02_CURRENT_REPOSITORY_STATE.md`
  - `03_FIRST_PRINCIPLES_DESIGN_A.md`
  - `04_FIRST_PRINCIPLES_DESIGN_B.md`
  - `05_ADVERSARIAL_REVIEW.md`

---

## 5. Implementation Artifacts & Legacy State
* `/Users/bob/GitHub/SAKG/Engineering-Intelligence/Phase01_COMPLETE.md`: Implementation summary of Phase 01 Knowledge Space.
* `/Users/bob/GitHub/SAKG/Engineering-Intelligence/build_docs.py`: Documentation and ontology generation script.
* `/Users/bob/GitHub/paeos/misc/_state_sakg/`: Historical prototype state (CAS store, ledger database, court keys).

---

## 6. Research & Supporting Material
* `/Users/bob/GitHub/paeos/backlog/research/RB-0005-mission-zero-sakg-discovery.md`: Research backlog on Mission Zero SAKG discovery and knowledge bootstrapping.
* `/Users/bob/GitHub/paeos/backlog/research/RB-0004-knowledge-acquisition-engine.md`: Autonomous knowledge acquisition engine research.
* `/Users/bob/GitHub/paeos/backlog/research/RB-0007-architecture-discovery-engine.md`: Architecture discovery engine research.
* `/Users/bob/GitHub/Concept Graph /05_ALTERNATIVES_CONSIDERED.md` & `06_OPEN_RESEARCH_QUESTIONS.md`.
* `/Users/bob/GitHub/Concept Graph /10_PHASE3_COMPARATIVE_REVIEW.md`.

---

## 7. Superseded, Duplicate & Conflicting Documents
* Multiple competing versions of the SAKG Constitution exist (`0.1_constitutionV1.txt` vs `SAKG_v1.0/SAKG_Constitution.md`).
* Divergent concept graph models exist between `Concept Graph ` (vector-centric concept search) and `SAKG` (strongly typed symbolic ontology & epistemic calculus).
* `misc/ecosystem_prep/sakg/03_FIRST_PRINCIPLES_DESIGN_A.md` vs `04_FIRST_PRINCIPLES_DESIGN_B.md` explore contrasting storage architectures (Graph DB vs SQLite/CAS).
* **Treatment:** All above documents are classified as candidate source material, not canonical truth. They will undergo derivation and critique under PAEOS L03–L10.

---

## 8. Missing Expected Material
* A single, unified, formal storage engine and query API specification compatible with PAEOS CAS/Ledger immutability.
* A formalized parser/extractor bridging AST/code representations with high-level conceptual graph nodes.
