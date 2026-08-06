# KAE-1 — Knowledge Acquisition Engine (KAE) Architecture Specification

Status: **RATIFIED BY FOUNDER PROXY (2026-08-06)** · Version: 1.0.0
Authority: `backlog/research/RB-0004-knowledge-acquisition-engine.md` & `architecture/invariants.json`
Level: **specifications & runtime-subsystem** (`kae/` module in Zone 2).

---

# 1. Motivation & Core Architectural Problem

While PAEOS possesses execution, court verification, and local memory capabilities, it historically assumed that all necessary domain knowledge pre-existed within:
1. The local repository.
2. The constitution.
3. SAKG precedents.
4. LLM training weights.

When PAEOS encounters complete novelty or rapid frontier shifts (e.g. new database benchmarks, emerging neural architectures, external API changes), relying solely on internal weights leads to hallucination or sub-optimal choices.

**The Knowledge Acquisition Engine (KAE) makes external knowledge acquisition a first-class, evidence-bound subsystem of PAEOS.**

---

# 2. Key Invariants & Non-Authority Guarantees

1. **Un-Trusted External Ingestion**: External documents, papers, and web content fetched by KAE hold **zero ambient authority**. They can never modify the constitution (`AI-009`) or bypass T2 Court verification (`AI-004`).
2. **CAS Content Addressability**: Every acquired document is immutably hashed and stored in CAS (`kernel/cas.py`) before processing.
3. **Traceable Provenance**: Every extracted fact or architectural insight MUST reference its source URL, arXiv ID, DOI, or git commit hash.
4. **Freshness & TTL**: Acquired knowledge items carry explicit expiration timestamps and trust scores.

---

# 3. Component Architecture

```text
External Sources (arXiv, GitHub, PyPI, Web, Benchmarks)
   │
   ▼
[Source Adapters]  (Fetchers with rate-limiting & CAS storage)
   │
   ▼
[Extraction & Summarization Pipeline]  (Fact extraction, code snippet parsing)
   │
   ▼
[Knowledge Store]  (Typed Knowledge Nodes & Provenance Links)
   │
   ▼
[SAKG / ADE / Deliberation Integration]  (Queryable by SAKG, ADE, and Councils)
```

---

# 4. Data Model & Node Schema

## 4.1 `KnowledgeEnvelope` (JSON Schema)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "KnowledgeEnvelope",
  "type": "object",
  "required": ["knowledge_id", "source_uri", "cas_hash", "timestamp", "trust_score", "facts"],
  "properties": {
    "knowledge_id": { "type": "string" },
    "source_uri": { "type": "string" },
    "cas_hash": { "type": "string" },
    "timestamp": { "type": "string" },
    "trust_score": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "facts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["claim", "evidence_snippet"],
        "properties": {
          "claim": { "type": "string" },
          "evidence_snippet": { "type": "string" }
        }
      }
    }
  }
}
```

---

# 5. Delivery & Integration Slices

| Slice | Name | Scope & Deliverable |
| --- | --- | --- |
| **Slice K1** | Ingestion & CAS Storage | Source adapters (arXiv, GitHub API, Web) + CAS blob storage. |
| **Slice K2** | Fact Extraction & Schema Verification | Extraction pipeline + JSON Schema validation. |
| **Slice K3** | SAKG & ADE Knowledge Query Interface | Read-only MCP server surface for SAKG and ADE retrieval. |

---

# 6. Traceability Matrix

- **RB-0004**: Answers *"What knowledge exists?"*
- **AI-001**: Transport Independence — source adapters use pluggable HTTP interfaces.
- **AI-004**: External knowledge cannot gate court seals without T2 verification.
