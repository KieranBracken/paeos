# PAEOS Mission 0 (Discover SAKG) — Phase A: Archaeological Census Report

**Document Type:** Forensic Archaeological Census Report  
**Mission:** RB-0005 (Phase A) — Mission 0: Discover SAKG  
**Repository Scope:** PAEOS (`sakg/`, `tests/sakg/`, `backlog/research/`, `ledger/debt/`, `reviews/`, `operations/`, `docs/`, `misc/`) & Ecosystem Boundary Map  
**Authority:** Antigravity Architect & Overseer  
**Date:** 2026-09-04  
**Execution Receipt:** `PHASE_A_CENSUS_EXECUTION_RECEIPT: RB-0005-A-20260904-R2`  

---

## Executive Summary

Pursuant to **RB-0005** (*The Archaeological Derivation Pattern / Repository-as-Evidence-Not-Law*), this forensic census synthesizes all architectural designs, historical spikes, sealed implementations, debts, remands, and ontological specifications governing the **Semantic Architectural Knowledge Graph (SAKG)**.

SAKG has transitioned from an early, un-implemented specification series into a **strictly verified, append-only, non-authoritative knowledge substrate (SAEOS-1 / SAKG-1)** integrated with PAEOS under the **Ecosystem Constitution and Boundary Map (v1.0, 2026-09-04)**.

---

## 1. What Was Built and Sealed in Tasks 01–21

The execution of the **SAKG-1 Backlog** (decomposing Slices S1 and S2) and subsequent Milestone 45 was completed, candidate-bound, and Court-sealed across 21 discrete tasks:

| Task ID | Canonical Objective / Backlog Node | Key Artifacts & Modules | Sealed Invariants & Deliverables |
| :--- | :--- | :--- | :--- |
| **Task 01** | `[I-STORE]` Pure SQLite Storage Engine | `sakg/store.py`, `tests/sakg/test_store.py` | Append-only SQLite WAL storage; no updates/deletes; immutable node/edge insertion; supersession-only versioning. |
| **Task 02** | `[I-EXTRACT]` AST Node & Tradeoff Extractor | `sakg/extract.py`, `tests/sakg/test_extract.py` | Deterministic layer artifact-to-envelope mapper; explicit `ExtractionGap` tracking (never silent field drop); ULID generation. |
| **Task 03** | `[I-INGEST]` Ingestion Pipeline | `sakg/ingest.py`, `tests/sakg/test_ingest.py` | Pull-based outbox ingestion; idempotent re-reads; all nodes land strictly as `status=candidate` in the producer namespace. |
| **Task 04** | `[I-TRAVERSE]` Traversal Engine | `sakg/traverse.py`, `tests/sakg/test_traverse.py` | Typed edge traversals across 8 families; acyclicity enforcement on `dependency` edges; non-transitive `analogous_to`. |
| **Task 05** | `[I-PROJ]` Context Projection Engine | `sakg/project.py`, `tests/sakg/test_projection.py` | Hard token budget ceiling (`max_tokens`); drop-and-count strategy (never mid-structure truncation); reproducible `query_hash` and `corpus_hash`. |
| **Task 06** | `[T-NONAUTH]` Non-Authority Boundary | `tests/sakg/test_nonauthority.py` | Structural read-only consumer egress; constant `trust: untrusted` tag; `tier ∈ {SUMMARY, INDEX}`; SAKG cannot mint `Evidence` (only `EvidenceRef`). |
| **Task 07** | `[I-TRADEOFF]` Tradeoff Precedents | `sakg/methods/tradeoff_precedents.py` | Single S2 method: matches `TradeOff` on axes, walks to resolving `Decision`, and joins realized `Outcome`. |
| **Task 08** | `[I-OUTBOX]` Post-Seal Outbox Writer | `runtime/emission/outbox.py` | PAEOS-side L15/L16 post-seal append-only outbox emitter; zero import of `sakg` from PAEOS kernel/runtime. |
| **Task 09** | `[I-MCP]` Read-Only MCP Server | `sakg/mcp_server.py`, `tests/mcp/test_sakg_server.py` | Exposes read-only `tradeoff_precedents` tool; deny-by-default; no mutating endpoints exist. |
| **Task 10** | `[F-ENVELOPE / F-BUNDLE]` Schema Validation | `sakg/schema/*.json`, `tests/sakg/test_roundtrip.py` | JSON Schema draft 2020-12 envelope validation; canonical JCS golden bytes; lossless round-trip property tests. |
| **Task 11** | Poisoned Corpus Defense Engine | `tests/sakg/test_poisoned_corpus_cannot_gate.py` | Mechanical proof that corrupted/poisoned SAKG assertions cannot gate PAEOS promotion or alter execution decisions. |
| **Task 12** | Frequency Never Promotes Invariant | `tests/sakg/test_frequency_never_promotes.py` | Proof that recurrence/frequency cannot promote candidate claims without explicit, verified evidence bindings. |
| **Task 13** | `[F-TRADEOFF-FIX]` Precedent & Fixture Hardening | `tests/sakg/fixtures/tradeoff/`, `sakg/methods/` | Golden tradeoff fixture corpus covering real axes and adversarial negative-link / min-confidence / strict-typing probes. |
| **Task 14** | `[I-BACKFILL]` Historical Outcome Backfill | `sakg/backfill.py`, `ledger/debt/DEBT-0062.md` | Maps `ledger/debt/` records into candidate `Outcome` nodes bound to `Decision` nodes; explicitly tagged `hand_attributed: true`. |
| **Task 15** | `[I-TRAVERSE]` Advanced Traversal Primitives | `sakg/traverse.py`, `tests/sakg/test_traverse_*.py` | Cross-namespace disclosure gating; directional reachability; acyclic dependency verification. |
| **Task 16** | `[I-PROJ]` Projection Budget & Why Verification | `sakg/project.py`, `tests/sakg/test_projection_*.py` | Mandatory `why` traversal path on every returned item; exact `omitted` count calculation. |
| **Task 17** | `[I-TRADEOFF]` Single S2 Method Finalization | `sakg/methods/tradeoff_precedents.py` | Pure traversal join from TradeOff → Decision → Outcome; exclusion of the 4 out-of-scope S4 methods. |
| **Task 18** | `[I-MCP]` MCP Protocol Surface Hardening | `sakg/mcp_server.py` | JSON-RPC stdio transport; untrusted tagging; graceful degradation on empty graph. |
| **Task 19** | `[T-NONAUTH]` Full Non-Authority Conformance | `tests/sakg/test_nonauthority_*.py` | Static check: zero `sakg` imports in `kernel/`, `runtime/`, `cli/`; proof that untrusted suggestions cannot gate goals. |
| **Task 20** | `[T-BASELINE]` Measurement & §7 Falsifier | `sakg/baseline.py`, `tests/sakg/test_baseline_harness.py` | Delta tracking (research spawns, L10 remands, tokens); clean degradation on empty/unreachable SAKG. |
| **Task 21** | Milestone 45: Taxonomy Subsumption | `sakg/subsumption.py` | Deterministic, append-only `subsumes` evaluator; graduated scope transfer; constraint compatibility; cycle/ambiguity rejection. |

**Current Test Suite Status:** `115/115` passing tests in `tests/sakg/` (100% green, 0 Ruff findings, 0 Pyright diagnostics).

---

## 2. Historical Spikes, Findings, and Loss Ratios (S-PROBE)

### 2.1 The S-PROBE Feasibility Spike (`reviews/spikes/sakg-s1-extraction-probe.md`)
- **Objective:** Empirically falsify assumption **A8** ("sealed PAEOS review artifacts can be losslessly converted to structured SAKG graph nodes") before writing production extraction code.
- **Methodology:** Evaluated 153 fields across 12 node types against 3 real Court-sealed Gate dispositions (`Gate A: 38B5395`, `Gate B: 993B6CC`, `Gate C: F0BE9AB`).
- **Results:**
  - **Verdict:** `NO-GO`
  - **Empirical Loss Ratio:** `0.503` (50.3% weighted information loss).
  - **Field Breakdown:** Extractable = 21 (13.7%), Partial = 110 (71.9%), Absent = 22 (14.4%).
  - **Root Cause of Loss:** Sealed prose markdown records omit direct structural markers for `EvidenceRef.hash`, `Constraint.statement`, `TradeOff.axis`, `Mechanism.id`, and `Pattern.name`.

### 2.2 Founder Gate A4 Disposition (`ledger/decisions/SAKG-1-G-S1-GO.md`)
- **Decision:** `PROCEED` (Conditional).
- **Mandate:** Instead of aborting SAKG, the Founder established a **Conditional Synthetic Operating Envelope**:
  1. Strict Trace-A serial workflow (concurrency = 1, `INTERNAL` data class).
  2. Extraction must be built against formal, structured schemas (`bundle.schema.json`) with an explicit gap ledger (`ExtractionGap`), rather than relying on regex parsing of unstructured prose.
  3. Provenance must remain `status=candidate` until independently verified.
  4. Authoritative promotion requires verified evidence bindings; frequency or model assertion is strictly prohibited as proof.

---

## 3. Explicit Architectural Gaps and Unverified Assumptions

| Category | Finding / Gap | Detail & Risk | Canonical Reference |
| :--- | :--- | :--- | :--- |
| **Unverified Assumption** | **A8 (Lossless Extraction from Prose)** | Falsified by S-PROBE. Resolved by introducing structured post-seal Emission Bundles (`runtime/emission/outbox.py`). Unstructured historical text cannot be losslessly extracted without human attribution. | `reviews/spikes/sakg-s1-extraction-probe.md`, `SAEOS-1 §9/A8` |
| **Architectural Gap** | **Ω2 (Automatic Outcome Feedback Loop)** | S2 implements the `Outcome` node type, but the *automatic* post-seal outcome observation and belief-revision loop is deferred to Slice S3. Current outcomes rely on hand backfill. | `SAEOS-1 §2.2/Ω2`, `DEBT-0062` |
| **Scope Limitation** | **S3–S6 Slices Unimplemented** | Only Slices S1 and S2 were authorized and built. S3 (Automatic Outcome Loop & Truth Maintenance), S4 (Remaining 4 methods: `query_architectures`, `dependency_impact`, `pattern_retrieval`, `memory_augment`), S5 (Cross-project multi-tenancy & disclosure gating), and S6 (ORCA-strator/Concept OS ecosystem adapters) remain out of scope. | `backlog/SAKG-1-backlog.yaml §dag_properties` |
| **Auditor Finding** | **Scope Incompatibility Explanations** | Physical L14/L17 audit of Task 21 (NVIDIA `llama-3.2-11b-vision-instruct`) observed that when child scope is not a subset of parent scope, `ScopeIncompatibilityError` lacked detailed multi-domain explanatory text. | `reviews/tasks/PAEOS_MILESTONE_45_SAKG_TASK_21_FOUNDER_COURT_DISPOSITION.md` |
| **Sovereignty Boundary** | **Concept OS vs SAKG Separation** | SAKG is retrospective, evidence-bound engineering memory (`Decision`, `Outcome`, `Mechanism`). Concept OS owns the possibility space, analogies, and hypothesis generation (`Concept Graph`, `Inspiration Engine`). Concept OS candidate hypotheses can *never* directly write into SAKG as validated truth without the closed epistemic experimental loop via PAEOS. | `ECOSYSTEM_CONSTITUTION_AND_BOUNDARY_MAP.md §Ecosystem Boundaries` |

---

## 4. Preserved Debts and Remand History Related to SAKG

PAEOS operates on strict empirical accounting where remands act as vital back-pressure mechanisms:

1. **`DEBT-0062` (Historical Outcome Backfill is Hand-Attributed) — [OPEN / Priority: MEDIUM]:**
   - *Compromise:* `sakg/backfill.py` maps historical debt and incident records into candidate `Outcome` nodes before the S3 automatic loop exists.
   - *Condition of Repayment:* S3 automatic loop emits immutable, candidate-bound observations that join directly to Decisions with independent evidence.
2. **`DEBT-0068` (Court Remand: Unmet Evidence Claims on Task 13) — [CLOSED / REPAID]:**
   - *Friction:* Task 13 (F-TRADEOFF-FIX) was remanded (`r-53f149dd0a0d`, 4 remand windows) because worker writes remained in isolated CAS and did not land in the candidate tree.
   - *Repayment:* Landed in commit `b2ef99c0`, verified with P1–P5 discriminating probes, sealed locally (`8270deda`), and qualified by a physical Gemini audit pair (`dfa25a2a`).
3. **`DEBT-0063` through `DEBT-0067` (Court Remands during F-BUDGET-FIX) — [CLOSED / REPAID]:**
   - *Frictions:* Shell syntax in Court sandbox, non-probative test assertions, and variable pytest execution timing in stdout.
   - *Repayments:* Replaced with Court-resolvable absolute venvs, `-qq` quiet output for byte-for-byte reproducibility, and non-vacuous assertions (`r-63dea6e1`, seal `bfbd0af2`).
4. **`DEBT-0072` & `DEBT-0073` (Task 21 Subsumption Remands) — [OPEN historical records]:**
   - *Friction:* Initial SoftLoop runs encountered bridge timeout (`r-380e4bfc`), timing output variance (`r-aa6bc788`), and A-08 typed identifier checks (`r-438efeb6`).
   - *Resolution:* Remediated in isolated run `r-530205f1` (seal `5e768d99`) and sealed under Milestone 45 disposition.

---

## 5. Key Ontology and Node Types

The SAKG ontology is defined across `sakg/schema/envelope.schema.json`, `sakg/store.py`, `sakg/extract.py`, and `ECOSYSTEM_CONSTITUTION_AND_BOUNDARY_MAP.md`:

### 5.1 Universal Node Envelope (`sakg/schema/envelope.schema.json`)
Every node is an ECS Entity with:
- **`id`:** URI (`sakg://<namespace>/<type>/<ulid>`).
- **`type`:** One of the 12 closed core types.
- **`namespace`:** Tenancy / boundary identifier.
- **`facets`:** Typed ECS components for domain-specific extension.
- **`provenance`:** `{origin: {system, run_id}, author_kind: enum(human, agent, ingest, inferred), ingested_at, source_hash}`.
- **`evidence`:** `[EvidenceRef]` (array of content-addressed hashes + URIs).
- **`status`:** `enum(candidate, canonical, superseded, refuted)`.
- **`confidence`:** Derived float $[0.0, 1.0]$ via truth maintenance (read-only, never authored).
- **`valid_from` / `valid_until` / `falsifier`:** Temporal validity window and falsification predicate.
- **`coordinates`:** Multi-dimensional flat coordinates.

### 5.2 The Twelve Core Node Types
1. **`Decision` (Central Object):** Architectural choices made in context with alternatives, rationale, and `constitutional_basis`.
2. **`TradeOff`:** Explicit balance between conflicting objectives/constraints along specified axes.
3. **`Option`:** Considered candidates, **explicitly retaining rejected options** as high-value negative knowledge.
4. **`Constraint`:** Invariant boundaries (memory, budget, latency, regulatory, physical).
5. **`Objective`:** System properties and metrics being optimized.
6. **`Problem`:** The motivating engineering need/question.
7. **`Mechanism`:** Reusable causal operational implementations (caching, consensus, circuit breakers).
8. **`Pattern`:** Recurring architectural configurations, naming, and anti-patterns.
9. **`Component`:** Physical/logical modules, interfaces, services, and data stores.
10. **`Outcome`:** Longitudinal realized post-seal results (held, degraded, reverted, caused-incident).
11. **`Scar`:** Historical failure classes containing `root_cause`, `detection_signature`, and `guard_action`.
12. **`EvidenceRef`:** Pointers (hash, URI, kind, reverification) to external immutable artifacts. SAKG never mints raw evidence.

### 5.3 Additional Hierarchical Concept
- **`TaxonomyNode` / Subsumption:** Formalized in Task 21 / Milestone 45. Allows typed `subsumes` DAG edges where parent scope covers child scope with explicit per-domain transfer confidence, preserving child/parent identities and rejecting cycles or conflicting constraints.

### 5.4 The Eight Registered Edge Families (`sakg/store.py`)
1. **`structural`:** `part_of`, `instance_of`, `specializes`.
2. **`dependency`:** `depends_on`, `calls`, `provides`, `consumes` *(strictly acyclic)*.
3. **`causal`:** `resulted_in`, `caused`, `mitigated`, `regressed`.
4. **`optimization`:** `optimizes_for`, `improves_at_cost_of`.
5. **`constraint`:** `constrained_by`, `bounds`.
6. **`tradeoff`:** `trades_off_with`, `resolves`.
7. **`problem`:** `addresses`, `considered`, `rejected`.
8. **`similarity`:** `analogous_to` *(non-transitive)*, `alternative_to`, `replaces`.

---

## 6. Synthesis and Readiness for Phase B (CER-1 First-Principles Derivation)

The archaeological census confirms:
1. **Substrate Stability:** Core SAKG storage, projection, outbox emission, MCP read-only server, and test harness are mature, reproducible, and fully Court-sealed.
2. **Epistemic Invariant:** SAKG is non-authoritative memory and a horizon widener; it does not decide, execute, or promote on frequency.
3. **Phase B Readiness:** All candidate ideas (L1–L4, S-PROBE, SAEOS-1, Boundary Map) have been inventoried, classified, and grounded with exact hashes and empirical test evidence, providing the required factual foundation to execute Phase B (CER-1 First-Principles Derivation).
