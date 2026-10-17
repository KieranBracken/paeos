# SAKG Archaeology — 02 Current Repository State

**System:** Systems Architecture Knowledge Graph (SAKG)  
**Location:** `/Users/bob/GitHub/SAKG`  

---

## 1. Directory Structure

```text
/Users/bob/GitHub/SAKG/
├── 0.1_constitutionV1.txt
├── PHASE 0.2 — Core Ontology Specification.txt
├── Phase 0.3 — Relationship Ontology.txt
├── Phase 0.4 — Metadata Schema.txt
├── Phase 0.5 — Reasoning Model.txt
├── SAKG_v1.0/
│   ├── 00_README.md
│   ├── SAKG_Constitution.md
│   ├── ADR_Register.md
│   ├── ACP_Specification.md
│   └── SAKG_System_Specification/ (Parts 01–11)
└── Engineering-Intelligence/
```

---

## 2. Implementation Reality

- **Specification State**: High-maturity specifications (Parts 01–11 complete, Constitution, ADR Register, ACP Spec).
- **Code Realization**: The specification is complete, but concrete execution code in this repository is minimal; it exists as pure specification documents and raw ontology specs.
- **Dependency Inversion**: Some implementations claiming to be "SAKG" exist as embedded modules in other repos (e.g. `state_sakg/` in PAEOS or `orca-strator`), creating confusion between SAKG as a canonical specification vs. SAKG as a running database.

---

## 3. Debt & Drift Assessment

- **Drift**: Code implementations in sibling repositories drift from the formal v1.0.0 System Specification.
- **Gap**: Missing unified python package or HTTP server in `/Users/bob/GitHub/SAKG` itself.
