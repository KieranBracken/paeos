# SAEOS-1 — Semantic Architectural Knowledge Graph (SAKG) Canonical Architecture Specification

**Document Identifier:** SAEOS-1  
**Title:** Canonical Architecture, Ontological Envelope, and Epistemic Governance for SAKG  
**Status:** CANONICAL / FOUNDER-RATIFIED SPECIFICATION  
**Version:** 1.0  
**Effective:** 2026-09-04  
**Governing Authority:** Ecosystem Constitution and Boundary Map v1.0 / RB-0005  
**Execution Receipt:** `PHASE_C_SAEOS1_INTEGRATION_RECEIPT: RB-0005-C-20260904-R1`  
**Prerequisites:** Sealed SAKG Tasks 01–21 (Milestones 19–38 & 45), 115/115 passing tests in `tests/sakg/`  

---

## 1. System Identity and Ecosystem Boundary

### 1.1 Core Definition
The **Semantic Architectural Knowledge Graph (SAKG)** is the sovereign authority for defensibly true, evidence-backed engineered-system knowledge across the ecosystem. It is an append-only, retrospective, causal memory substrate that models software architectures as constrained decision networks.

### 1.2 Ecosystem Boundary & Invariants
Per [`ECOSYSTEM_CONSTITUTION_AND_BOUNDARY_MAP.md`](file:///Users/bob/GitHub/paeos/ECOSYSTEM_CONSTITUTION_AND_BOUNDARY_MAP.md):
1. **Retrospective Evidence-Bound Memory:** SAKG records what physical reality, execution tests, and longitudinal outcomes have proven or falsified.
2. **No Speculation:** SAKG does not explore the open possibility space or synthesize analogies (Concept OS and the Inspiration Engine own candidate generation).
3. **No Execution or Promotion Authority:** SAKG cannot execute code, allocate budgets, invoke models, or gate PAEOS task promotion.
4. **Frequency Never Promotes Invariant:** The recurrence of a pattern or claim across corpora is correlation, not proof. Promotion requires explicit, content-addressed evidence and Court disposition.
5. **Non-Authority Input:** All SAKG projections into worker context are tagged `trust: untrusted` and cannot override constitutional invariants or task definitions.

```text
       ┌────────────────────────────────────────────────────────┐
       │                 Concept OS & Inspiration               │
       │           (Hypotheses & Possibility Space)             │
       └───────────────────────────┬────────────────────────────┘
                                   │ candidate hypotheses
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                  PAEOS Operating System                │
       │         (Execution, Sandboxing, Court Verifiers)       │
       └───────────────────────────┬────────────────────────────┘
                                   │ sealed evidence & outbox bundles
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │               SAKG Knowledge Sovereign                 │
       │    (Append-Only Graph, Provenance, Claim Scoping)      │
       └────────────────────────────────────────────────────────┘
```

---

## 2. Universal Node Envelope & Ontology

### 2.1 Universal ECS Node Envelope
Every entity in SAKG conforms to the universal schema (`sakg/schema/envelope.schema.json`):

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SAKG Node Envelope",
  "type": "object",
  "required": ["id", "type", "namespace", "provenance", "evidence", "status"],
  "properties": {
    "id": { "type": "string", "pattern": "^sakg://[a-z0-9_-]+/[a-z0-9_-]+/[0-9A-HJKMNP-TV-Z]{26}$" },
    "type": { "type": "string", "enum": [
      "Decision", "TradeOff", "Option", "Constraint", "Objective",
      "Problem", "Mechanism", "Pattern", "Component", "Outcome",
      "Scar", "EvidenceRef"
    ]},
    "namespace": { "type": "string" },
    "facets": { "type": "object" },
    "provenance": {
      "type": "object",
      "required": ["origin", "author_kind", "ingested_at", "source_hash"],
      "properties": {
        "origin": { "type": "object", "properties": { "system": { "type": "string" }, "run_id": { "type": "string" } } },
        "author_kind": { "type": "string", "enum": ["human", "agent", "ingest", "inferred"] },
        "ingested_at": { "type": "string", "format": "date-time" },
        "source_hash": { "type": "string", "pattern": "^[0-9a-f]{64}$" }
      }
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["hash", "uri", "kind"],
        "properties": {
          "hash": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
          "uri": { "type": "string" },
          "kind": { "type": "string" }
        }
      }
    },
    "status": { "type": "string", "enum": ["candidate", "canonical", "superseded", "refuted"] },
    "confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
  }
}
```

### 2.2 The Twelve Core Node Types
1. **`Decision` (Central Entity):** Architectural commitments made in a context. Captures alternatives considered, selected rationale, and constitutional basis.
2. **`TradeOff`:** Zero-sum balances between competing objectives/constraints along explicit axes.
3. **`Option`:** Evaluated options. **Explicitly preserves rejected options** (`rejected: true`) as high-value negative knowledge.
4. **`Constraint`:** Invariant boundaries (memory, token budget, latency, regulatory, physical).
5. **`Objective`:** Desired properties and metrics being optimized.
6. **`Problem`:** The driving engineering challenge.
7. **`Mechanism`:** Reusable causal implementations (e.g. SQLite WAL, Ed25519 capability tokens, circuit breaker).
8. **`Pattern`:** Architectural configurations and recognized anti-patterns.
9. **`Component`:** Physical/logical software modules, data stores, and interfaces.
10. **`Outcome`:** Longitudinal realized post-seal results (held, degraded, reverted, incident-caused).
11. **`Scar`:** Historical failure lessons containing root cause, detection signature, and preventative guard actions.
12. **`EvidenceRef`:** Pointers to external immutable CAS blobs. SAKG never mints raw evidence.

---

## 3. Storage, Ingestion, and Traversal Engine

### 3.1 Pure SQLite Append-Only Storage (`sakg/store.py`)
- **Engine:** SQLite with WAL mode and synchronous normal.
- **Immutability:** Zero `UPDATE` or `DELETE` statements on nodes/edges.
- **Versioning:** Supersession via `superseded_by` edges and `status=superseded`.
- **Tenancy:** Strict namespace isolation at the storage boundary.

### 3.2 The Eight Typed Edge Families
1. **`structural`:** `part_of`, `instance_of`, `specializes`.
2. **`dependency`:** `depends_on`, `calls`, `provides`, `consumes` *(strictly acyclic)*.
3. **`causal`:** `resulted_in`, `caused`, `mitigated`, `regressed`.
4. **`optimization`:** `optimizes_for`, `improves_at_cost_of`.
5. **`constraint`:** `constrained_by`, `bounds`.
6. **`tradeoff`:** `trades_off_with`, `resolves`.
7. **`problem`:** `addresses`, `considered`, `rejected`.
8. **`similarity`:** `analogous_to` *(non-transitive)*, `alternative_to`, `replaces`.

### 3.3 Context Projection & Budgeting (`sakg/project.py`)
- **Hard Token Budget:** Enforces `max_tokens` ceiling with a deterministic drop-and-count strategy (never mid-structure truncation).
- **Mandatory Traversal Path:** Every projected item includes a `why` traversal path from query origin to target node.
- **Reproducibility:** Emits deterministic `query_hash` and `corpus_hash`.

---

## 4. Subsumption Hierarchy & Graduated Claim Scoping

### 4.1 Taxonomy Subsumption Evaluator (`sakg/subsumption.py`)
- Formalized under Milestone 45 (Task 21).
- Evaluates `subsumes` DAG edges: A parent node subsumes a child node only if:
  1. Edge is typed as `subsumes` and preserves acyclicity.
  2. Both nodes carry verified provenance and evidence references.
  3. Parent scope covers child scope with explicit per-domain transfer confidence.
  4. Parent constraints are compatible with child constraints.
- Cycle attempts, ambiguous parent selections, and incompatible scopes fail closed.

### 4.2 Graduated Claim Scoping
Claims progress along a strict evidence-backed graduation ladder:
$$\text{Observation} \longrightarrow \text{Domain Scar} \longrightarrow \text{Domain Principle} \longrightarrow \text{Cross-Domain Pattern} \longrightarrow \text{Generalized Mechanism} \longrightarrow \text{Candidate Law} \longrightarrow \text{Established Law}$$

- Universal scope requires explicit Court-approved multi-domain empirical replication.
- Transfer confidence is computed per destination domain and never generalized from 2 domains.

---

## 5. Ecosystem Bridges & Integration Protocols

### 5.1 Post-Seal Emission Bridge (PAEOS $\longrightarrow$ SAKG)
- PAEOS invokes `runtime/emission/outbox.py` at state L15/L16 post-seal.
- Emits schema-validated `EmissionBundle` containing Decisions, TradeOffs, Rejected Options, Scars, and EvidenceRefs.
- SAKG's pull-based ingestion (`sakg/ingest.py`) reads outbox bundles idempotently into candidate nodes.

### 5.2 Citation & Corpus Ingestion Bridge (KAE $\longrightarrow$ SAKG)
- Knowledge Acquisition Engine (`RB-0004`) stores raw literature, RFCs, and external repositories in immutable CAS.
- Emits normalized citation manifests with exact byte-range/line hashes.
- SAKG consumes citations into `EvidenceRef` nodes, grounding claims in verified external literature.

### 5.3 Read-Only MCP Server Interface (`sakg/mcp_server.py`)
- Exposes `tradeoff_precedents` query tool to PAEOS workers and external agents via JSON-RPC stdio transport.
- Read-only, deny-by-default; zero mutating endpoints.
- Degrades gracefully on empty or unreachable graphs with zero crash behavior.

---

## 6. Execution Roadmap & Live Population (Mission 0 DAG)

Upon Founder Ratification of SAEOS-1, execution proceeds to **Phase D**:

```text
Phase D (Ratification & DAG Backlog)
    ↓
Task 22: PAEOS Historical Post-Seal Outbox Backfill & Ingest
    ↓
Task 23: SAKG Production SQLite Graph Ingestion & Live Indexing
    ↓
Task 24: KAE CAS Citation Parser & EvidenceRef Ingestion Pipeline
    ↓
Task 25: Automated Outcome Observation Loop (Slice S3)
    ↓
Task 26: SAKG Live Query & Ecosystem Validation Spike
```

**COURT_RATIFIED**
