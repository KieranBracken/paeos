# ADE-1 — Architecture Discovery Engine (ADE) Architecture Specification

Status: **RATIFIED BY FOUNDER PROXY (2026-08-06)** · Version: 1.0.0
Authority: `backlog/research/RB-0007-architecture-discovery-engine.md` & `architecture/invariants.json`
Level: **specifications & runtime-subsystem** (`ade/` module in Zone 2).

---

# 1. Motivation & Core Architectural Problem

Current PAEOS is excellent at validating engineering proposals once a single proposal is submitted.

However, evaluating a single proposal leaves the design space un-explored—the proposal evaluated may not be the optimal architecture.

**The Architecture Discovery Engine (ADE) systematically searches the architectural design space to generate, simulate, and filter candidate solution architectures BEFORE council debate and implementation begin.**

> **Research Philosophy:** The purpose of ADE is **not** to automatically invent architecture. Its purpose is to **systematically search the architectural possibility space** so that debate, councils, adversarial review, and governance evaluate the strongest available candidates rather than whichever idea happened to be proposed first.

---

# 2. Key Invariants & Non-Authority Guarantees

1. **Discovery is Non-Authoritative**: ADE candidate architectures are **proposals, not law**. They carry zero execution authority until evaluated by Councils (`RB-0001/0003`) and ratified under `CER-1`.
2. **Deterministic Candidate Blueprints**: Every generated candidate is represented as a formal, machine-readable `CapabilityDAG` schema.
3. **Pareto-Front Multi-Objective Filtering**: Candidates are scored across multiple competing dimensions (simplicity, performance, security, cost) rather than collapsed into a single scalar.

---

# 3. Component Architecture

```text
Problem Specification & Invariants
   │
   ▼
[Design Space Sampler]  (MCTS / Beam Search over subgraphs & capability DAGs)
   │
   ▼
[Candidate Generator]  (Generates N candidate blueprints: 10 - 30 candidates)
   │
   ▼
[Static Constraint & Cost Simulator]  (Filters invalid candidates & complexity spikes)
   │
   ▼
[Pareto Frontier Filter]  (Selects Top-K diverse candidates)
   │
   ▼
[Deliberation Council Input]  (Passes candidates to Council for Debate & Selection)
```

---

# 4. Data Model & Candidate Blueprint Schema

## 4.1 `ArchitecturalCandidate` (JSON Schema)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ArchitecturalCandidate",
  "type": "object",
  "required": ["candidate_id", "problem_id", "capability_dag", "estimated_complexity", "pareto_scores"],
  "properties": {
    "candidate_id": { "type": "string" },
    "problem_id": { "type": "string" },
    "capability_dag": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["node_id", "role", "deps"],
        "properties": {
          "node_id": { "type": "string" },
          "role": { "type": "string" },
          "deps": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "estimated_complexity": { "type": "integer" },
    "pareto_scores": {
      "type": "object",
      "required": ["simplicity", "performance", "security", "maintainability"],
      "properties": {
        "simplicity": { "type": "number" },
        "performance": { "type": "number" },
        "security": { "type": "number" },
        "maintainability": { "type": "number" }
      }
    }
  }
}
```

---

# 5. Delivery & Integration Slices

| Slice | Name | Scope & Deliverable |
| --- | --- | --- |
| **Slice D1** | Candidate Blueprint Schema & Sampler | `CapabilityDAG` schema + design space sampler. |
| **Slice D2** | Static Constraint & Cost Simulator | Static checker for circular dependencies and LOC/complexity spikes. |
| **Slice D3** | Pareto Filter & Council Handoff | Multi-objective Pareto selection engine + Council input formatter. |

---

# 6. Traceability Matrix

- **RB-0007**: Answers *"What candidate architectures should exist in the first place?"*
- **RB-0004**: Consumes knowledge from Knowledge Acquisition Engine (KAE).
- **RB-0001/0003**: Passes Top-K candidates to Deliberation Councils for debate.
