# SAEOS-1 — Canonical SAKG Architecture

> **Status:** RATIFIED BY FOUNDER PROXY (2026-08-06)
> **Document ID:** SAEOS-1
> **Date:** 2026-08-06
> **Mission:** RB-0005 "Mission 0: Discover SAKG" (Phases A, B, C)
> **Method:** Repository-as-Evidence-Not-Law (Option C) + CER-1 first-principles re-derivation
> **Authority:** Ratified by Founder Proxy under A4 delegation (2026-08-06).


---

## §0 Provenance and Method

This specification is the output of Mission 0 as defined in
`backlog/research/RB-0005-mission-zero-sakg-discovery.md`. It was produced by
executing three phases in order:

- **Phase A — Repository Census** (§1): every SAKG-bearing artifact across the
  corpus was located, read, and dated into a lineage map.
- **Phase B — CER-1 Derivation** (§2): SAKG was re-derived from first principles
  *without* inheriting the corpus framing, then the derivation was compared
  against the census and every finding classified ✓ / Δ / × / Ω.
- **Phase C — Canonical Architecture** (§3–§9): the surviving ideas, plus the
  gaps the derivation exposed, assembled into one specification.

**Naming note (requires ratification).** The document identifier `SAEOS-1` was
fixed by the mission brief. The corpus nowhere expands "SAEOS". The reading
adopted here — and offered for founder correction — is **S**emantic
**A**rchitectural **E**ngineering **O**perating **S**ystem, the sibling series to
PAEOS (Portable AI Engineering Operating System), where `SAEOS-n` numbers the
spec series and `SAKG` names the artifact those specs describe. See finding
**×1** for the deeper acronym collision this sits on top of.

---

## §1 Phase A — Repository Census

### §1.1 Corpus scope

Searched: `/Users/bob/GitHub/paeos` (this repo, all of `spec/`, `backlog/`,
`proposals/`, `reviews/`, `ledger/`, `operations/`, `methodology/`),
`/Users/bob/GitHub/SAKG`, `/Users/bob/GitHub/Concept Graph `,
`/Users/bob/GitHub/orca-strator`, `/Users/bob/GitHub/Library Of Fire`.

`Library Of Fire` is an **empty directory** — the system referenced throughout
RB-0001/RB-0003 as an ecosystem participant has no artifacts. Recorded as a
census fact, not a defect.

**Evidence-location caveat (material).** Two of this document's primary sources
are **uncommitted working-tree state**, not committed history, at the time of the
census:

- `spec/PAEOS-9-execution-architecture.md` — lineage **L4**, the ratified
  consumption contract and the most-cited source in this document. On
  `origin/main` the corresponding file is `spec/PAEOS-9-runtime-bootstrap.md`;
  the execution-architecture document (with §10 SAKG Integration) exists only in
  the founder's local checkout.
- `backlog/research/RB-0005-…` and the rest of `backlog/research/` — untracked.

The content was read directly and is quoted faithfully, but a reader on a clean
clone **cannot resolve these citations**. Committing that work is a founder act
and a precondition for this document's traceability (§11) to be verifiable by
anyone else. Recorded here rather than silently relied upon.

### §1.2 Lineage map

Four distinct lineages exist. They are **not** revisions of one another; they are
three separate attempts plus one external consumption contract, and they
disagree.

| # | Lineage | Location | Date | Status found | Volume |
|---|---------|----------|------|--------------|--------|
| **L1** | Phase 0.x Foundational Drafts | `SAKG/*.txt` (0.1–0.5) | 2026-07-06 | Exploratory, abandoned mid-series (0.6+ never written) | ~40 KB |
| **L2** | Engineering-Intelligence / Engineering Universe | `SAKG/Engineering-Intelligence/` | 2026-07-23 | Phase 01 "COMPLETE", frozen as Engineering Universe v1.1 | ~110 KB |
| **L3** | SAKG v1.0 System Specification | `SAKG/SAKG_v1.0/` | 2026-07-23 | **Approved** (single commit `4b191d0`) | ~85 KB |
| **L4** | PAEOS consumption contract | `paeos/spec/PAEOS-9-execution-architecture.md` §10 | Phase 3 | Ratified within PAEOS | 39 references |

### §1.3 Lineage detail

**L1 — Phase 0.x Foundational Drafts** (`0.1_constitutionV1.txt`,
`PHASE 0.2 — Core Ontology Specification.txt`, `Phase 0.3 — Relationship
Ontology.txt`, `Phase 0.4 — Metadata Schema.txt`, `Phase 0.5 — Reasoning
Model.txt`)

Informal, first-person, thinking-aloud drafts. Content: a 9-category top-level
taxonomy; ~25 root object types; 15 relationship families with an estimate of
"100–300 distinct relationship types"; a "Universal Semantic Schema" of 25–35
dimensions; a 9-mode reasoning model (Retrieval, Comparison, Recommendation,
Diagnosis, Optimization, Synthesis, Critique, Analogy, Prediction).

Three self-corrections occur mid-series and are the most valuable content in the
lineage:
1. (0.2) *"I don't think the central node of the graph should be Concept. I think
   it should be Decision."*
2. (0.3) A third fundamental element beyond nodes and edges — **Decisions** as
   evaluations performed over the graph — and a three-layer split
   (Knowledge / Relationship / Decision).
3. (0.4) Systems are made of *state, events, transitions, decisions, constraints*
   — the ontology must model **time**, not just facts.

The series ends proposing nine RFC-style documents (RFC-0001…0009) as the real
Phase 0. **None were written.** L1 terminates here.

**L2 — Engineering-Intelligence** (`Phase01_COMPLETE.md` 51 KB,
`issue_tracker.md`, `acps/acp-001…003`, `Future Systems/Concept Graph Search
Framework.md`)

A parallel effort under a different name ("Engineering Intelligence Platform",
"Engineering Universe"). Contains the coordinate system, engineering domains,
knowledge atlas, classification / coverage / validation frameworks, and a formal
`01.8 Freeze` declaring **Engineering Universe v1.1**.

Critically, L2 contains the corpus's only adversarial review: `issue_tracker.md`
triages 20 issues (IT-01…IT-20) from ChatGPT and NotebookLM reviews — 4 🔴
Blockers, 6 🟠 Major, 8 🟡 Medium, 2 🟢 Minor. The blockers are real and were
partially resolved into ACPs and then into ADR-010…013 of L3:
- IT-01 Governance vs. Autonomous Discovery Paradox → Candidate Namespace
- IT-02 Multiple Inheritance Schema Collision → Entity-Component System
- IT-03 Recursive Domains vs. Global Coordinates → flatten domains
- IT-04 Coordinate vs. Knowledge Object Collision → decouple *where* from *what*

Issues **IT-05 through IT-20 were never resolved** — notably IT-05 (no Truth
Maintenance / belief revision), IT-16 (missing design intent, decisions,
assumptions), IT-19 (coverage measurement paradox) and IT-20 (reasoning model
prematurely defined). They remain open in the corpus.

**L3 — SAKG v1.0** (`SAKG_Constitution.md`, `SAKG_System_Specification/01…11`,
`ADR_Register.md`, `ACP_Specification.md`)

The most formal artifact: a 12-article Constitution claiming supreme authority; an
11-part System Specification; 18 ADRs; a 5-layer architecture (Foundation /
Acquisition / Knowledge / Reasoning / Application) with explicit dependency rules;
a 9-phase roadmap (Phase 0 Foundations → Phase 8 System Integration); a
list of ~30 supporting specifications still to be written (Part 11).

Marked **Approved**, version 1.0.0, 2026-07-23. **Zero implementation exists.**
The nine phases require all architecture frozen before code (Art. II, ADR-004);
the repo contains one commit and no source beyond a `build_docs.py` helper in L2.

**L4 — PAEOS-9 §10** (`spec/PAEOS-9-execution-architecture.md`)

The only lineage authored *from the consumer's side*, and the only one grounded in
a running system. It specifies a 5-method read-only MCP surface
(`query_architectures`, `dependency_impact`, `tradeoff_precedents`,
`pattern_retrieval`, `memory_augment`), maps 6 consumption points onto PAEOS's 12
local graphs and lifecycle stages, and establishes the governing constraint:
**"SAKG is augmentation, never authority"** — never on the TCB path, never
evidence, never a gate. §10.4 proves PAEOS is complete without it.

### §1.4 Adjacent-system evidence

- **Concept Graph** (`/GitHub/Concept Graph `, 11 docs, 2026-07-27/30): the
  "Concept OS" research programme — an *Operating System for Discovery*. Explores
  seven concept-representation models (A–G, currently favouring hybrid),
  explicitly non-committal. Overlaps SAKG's ambition substantially; the corpus
  never draws a boundary between them. No git history.
- **ORCA-strator** (`/GitHub/orca-strator`): a **built** system — FastAPI backend,
  React frontend, provider router (DeepSeek/Qwen/OpenRouter/OpenAI/local), cost
  circuit breaker, 5 council skill files, live pipeline logs. Reality: an agent
  council orchestration cockpit. RB-0001/RB-0003 assume a far broader
  "ecosystem deliberation coordinator" role that does not yet exist.
- **PAEOS research backlog**: RB-0001 (deferred pending SAKG), RB-0003 (SAKG as
  ontology critic in a council), RB-0004 (KAE, High Priority *Post-SAKG*), RB-0005
  (this mission). All four treat SAKG as a prerequisite dependency.

### §1.5 Census conclusions

1. The corpus contains **three incompatible definitions** of what SAKG is, and
   they were written within 17 days of one another.
2. **Nothing has been implemented.** Total code: one `build_docs.py`. All
   evidence is specification-grade, not execution-grade — which under
   "Reality Has Legislative Priority" means the corpus carries *low* evidentiary
   weight against PAEOS's Phase-3 empirical reality.
3. The single strongest idea, appearing independently in L1, L3 (ADR-018) and
   PAEOS's own decision-graph, is **Decision as the central object**.
4. The only lineage with a real, specified consumer is **L4**, and L4 was written
   without reference to L1–L3.

---

## §2 Phase B — CER-1 First-Principles Derivation

### §2.1 The derivation

Method: derive from the need, not from the corpus. The question is *not* "what is
a knowledge graph" but **"what must exist for PAEOS and the wider ecosystem that
does not exist today?"**

**Start from the deficiency.** PAEOS at Phase 3 executes autonomous, evidence-
gated engineering. Its Context Compiler decides relevance by *reachability* — the
sub-graph reachable from a goal's touch-set across 12 local graphs
(PAEOS-9 §4.3, §5). This is deterministic, auditable, and complete with respect
to *this repository at this moment*. PAEOS-9 §13.11 carries the residual honestly:
*"a relevant fact with no graph edge to the goal"* is silently dropped, and
*"SAKG is the intended widener of the horizon."*

That gives the first law.

> **FPL-1 — The Horizon Law.** Relevance-as-reachability is bounded by edges that
> exist in the current repository. Knowledge that is relevant but has no local
> edge — because it belongs to another project, another era, or another team — is
> structurally unreachable. SAKG exists to hold exactly that class of knowledge.
> **Anything reachable locally is not SAKG's job.**

> **FPL-2 — The Outcome Law.** PAEOS emits evidence continuously and seals it at
> promotion. But the highest-value engineering knowledge — *did this decision hold
> up?* — materializes **after** the goal closes, and therefore cannot exist in any
> artifact PAEOS produces at seal time. A knowledge graph that stores only what
> was decided is an archive. One that stores what happened *because* of the
> decision is memory. SAKG must be **longitudinal**: decisions joined to their
> realized outcomes over time.

> **FPL-3 — The Non-Authority Law.** PAEOS's guarantees derive from determinism,
> reproducibility, and independent verification. Cross-project, statistical,
> semantically-retrieved knowledge is none of those. Therefore SAKG must be
> **structurally incapable** of gating — not merely forbidden by policy. If a
> poisoned SAKG can change whether a goal promotes, the architecture is wrong.

> **FPL-4 — The Context Economy Law.** The binding constraint on an agentic
> engineering OS is not storage or query expressivity; it is the **context
> window**. A graph that answers a query with 200 nodes has failed regardless of
> correctness. SAKG's primary interface obligation is therefore a *projection*
> contract — ranked, budget-bounded, explainable — not a query language.

> **FPL-5 — The Population Law.** An empty knowledge graph has zero value, and
> manual population does not scale. Bootstrapping is the dominant risk, ahead of
> ontology design. Therefore the acquisition path must be **automatic and
> byproduct-driven** or SAKG will never leave draft.

> **FPL-6 — The Decay Law.** Engineering knowledge rots: dependencies change,
> benchmarks age, platforms die. PAEOS already models this (K2: findings expire;
> Evidence is *bound, expiring*). Knowledge without an expiry or falsifier
> degrades silently into confident wrongness. Every SAKG assertion must carry a
> validity window and a falsifier.

> **FPL-7 — The Provenance Law.** Knowledge crossing a system boundary is untrusted
> data, never instruction and never evidence (PAEOS T9). Every node must carry
> provenance sufficient for a consumer to re-verify or discard it.

> **FPL-8 — The Separation Law.** Representation and reasoning are independent
> concerns. A store that also judges cannot be replaced, audited, or decorrelated
> from the judgment it feeds.

**Derived answer to "what must a SAKG be?"**

> SAKG is the **longitudinal, cross-project, evidence-bound memory of
> architectural decisions and their realized outcomes**, exposed through a
> budget-bounded projection interface, populated primarily as a byproduct of
> engineering execution, and architecturally incapable of authority.

It is **memory**, not judgment. It is a **horizon-widener**, not a knowledge base.
Its unit is the **Decision**, not the Concept.

### §2.2 Classification against the census

#### ✓ Validated Ideas — enduring, backed by evidence

| ID | Idea | Source | Why it survives |
|----|------|--------|-----------------|
| **✓1** | **Decision is the central object** | L1 (0.2, 0.3), L3 ADR-018 | Independently re-derived three times: by L1's self-correction, by L3's ADR-018, and by PAEOS's own decision-graph (PAEOS-9 §5 ADR-style records with `constitutional_basis`). Convergent independent derivation is the strongest evidence class in the corpus. Confirmed by **FPL-2** (Outcome Law) — decisions are the only nodes to which outcomes can attach. |
| **✓2** | **Graph-first; relationships are first-class** | L3 Art. I, X; ADR-001 | PAEOS independently arrived at 12 typed local graphs with semantic edges (PAEOS-9 §5) without reference to L3. Two independent derivations, one of them in a running system. |
| **✓3** | **Separation of representation from reasoning** | L1 (0.3 three layers), L3 Art. IV, ADR-003 | Matches derived **FPL-8**, and matches PAEOS's kernel/agent split and decorrelation requirement (A-08). A store that judges cannot be independently audited. |
| **✓4** | **Evidence-backed, provenance-preserving knowledge** | L3 Art. VII, IX; ADR-005 | Matches derived **FPL-7** and PAEOS K1 (no promotion without evidence). "Evidence outranks authority" is the same principle as PAEOS's "passing evidence, not assertion". |
| **✓5** | **Context-dependence; no universally optimal solution** | L3 Art. XI, ADR-008 | Matches PAEOS L06 trade-off matrix and Ω-24. A recommendation without assumptions/applicability/limits is inadmissible in both systems. |
| **✓6** | **Candidate namespace; knowledge has status states** | L2 IT-01, L3 ADR-011 | Matches derived **FPL-5** — autonomous population is impossible if every item needs human review. Maps cleanly onto PAEOS's `declared → verified` promotion lattice. **Retained with an amendment** (see ×5). |
| **✓7** | **ECS / facets instead of multiple inheritance** | L2 IT-02, L3 ADR-010 | A real defect (schema collision) met with a correct, evidence-driven fix. Enables extension without ontology surgery — required by **FPL-1**, since cross-project knowledge arrives in shapes not anticipated. |
| **✓8** | **Domains are flat coordinates, not hierarchies** | L2 IT-03, L3 ADR-012 | Avoids arbitrary taxonomy debates; concepts legitimately belong to several domains. Empirically motivated by an observed contradiction between Phase 1.1 and 1.2. |
| **✓9** | **Cross-domain pattern transfer** | L1 (0.4 analogies), L3 Art. XII, ADR-009 | Genuinely valuable (caching/feedback recurring across disciplines) and cheap to preserve as an *edge type*. **Validated as a capability, demoted as a priority** (see Δ1). |
| **✓10** | **Controlled evolution via formal change proposals** | L3 ADR-017, ACP spec | Structurally identical to PAEOS CER-2/CER-5. Should be **unified** with it rather than duplicated (see ×3). |
| **✓11** | **Trade-offs, failure modes, constraints as first-class objects** | L1 (0.3 families 5–7), L3 ADR-018 | Required by ✓1: a Decision node is meaningless without the Options, Constraints, and TradeOffs it resolved. |

#### Δ Weak / Debt Ideas — fail first-principles challenge

| ID | Idea | Source | Why it fails | Disposition |
|----|------|--------|--------------|-------------|
| **Δ1** | **Domain agnosticism as a day-one requirement** | L3 Art. VI, ADR-002 | An unbounded scope commitment with no falsifier and no consumer. It imposes a real, permanent cost (the ontology must stay generic enough for civil engineering, medicine, economics) to buy a speculative benefit no named consumer has requested. Every actual consumer in the corpus — PAEOS-9 §10, ORCA-strator, RB-0003 — asks for *software/systems architecture* knowledge. | Replace with **software-architecture-first, extension-ready**. Preserve the ECS facet mechanism (✓7) so other domains can be added when a consumer exists. Record as debt. |
| **Δ2** | **"Architecture fully specified before implementation"** | L3 Art. II, ADR-004 | Directly contradicts PAEOS's hardest-won principle — *"Reality Has Legislative Priority: empirical implementation evidence dominates written spec assumptions"* (`CONSTITUTIONAL_REFLECTION_PRINCIPLE`) and CER-1's *"the runtime MUST assume the current architecture is incomplete until evidence suggests otherwise."* Empirically falsified in-corpus: nine sequential frozen phases produced ~235 KB of specification and zero executable artifacts in one month. | Reject as constitutional law. Retain the weaker, true claim: *implementation must not silently create architecture* (PAEOS CER-6). |
| **Δ3** | **Implementation independence taken to unfalsifiability** | L3 Art. §2.10, ADR-007, §9.6 | The spec names no storage model, no query syntax, no cardinality, no latency budget, no size bound. A specification that forbids every concrete commitment **cannot be conformance-tested** — nothing can fail it. PAEOS requires falsifiers on every rule (K6). | Retain *portability* as a goal. Require every SAEOS spec to state at least one mechanically checkable conformance assertion. |
| **Δ4** | **Ontology inflation: 100–300 edge types, 25–35 semantic dimensions, 20–40 root types** | L1 (0.2, 0.3, 0.4) | Numbers asserted by introspection, with no consumer requirement behind any of them. Each type is permanent surface area, and L2's IT-11 ("Relationship Vocabulary Fragmentation") and IT-14 ("Overlapping & Ambiguous Object Types") are the predicted consequence, observed. | Collapse to the **minimum set the five ratified PAEOS-9 §10.1 methods require** (§4). Grow only on demonstrated consumer need. |
| **Δ5** | **A Reasoning Layer inside SAKG** | L3 §4.6, §5.8; L1 (0.5) | Violates ✓3/**FPL-8** as soon as it is built: SAKG would own trade-off analysis, path evaluation, and explanation generation — duplicating PAEOS L06/L07 and ORCA-strator's councils, and creating a second, un-decorrelated judge. L2's own review flagged this (IT-20: *"Reasoning Model Prematurely Defined"*). | Move reasoning **out** of SAKG core into consumers. SAKG exposes traversal and projection primitives only. |
| **Δ6** | **Confidence without decay** | L3 §2.12, Art. VII | Confidence is modelled as a static scalar. Combined with L2's unresolved IT-05 (no Truth Maintenance), a downgraded foundational claim never propagates. Violates derived **FPL-6**. | Every assertion gains a validity window + falsifier; confidence is recomputed, never stored as ground truth. |
| **Δ7** | **Coverage Framework — measuring coverage of "all engineering"** | L2 `01.6 Coverage Framework` | Unfalsifiable: the denominator is unknowable. L2's own triage caught it (IT-19 "Coverage Measurement Paradox") and deferred it. | Replace with **consumer-relative** metrics: query hit-rate, precedent-acceptance rate, no-SAKG baseline delta (PAEOS-9 §10.3). |
| **Δ8** | **Nine sequential phases with hard dependency ordering** | L3 §8.12 | Serializes all risk to the end: Phase 5 (Reasoning) and Phase 7 (Applications) — where value is proven — come last, after four frozen predecessor phases. Guarantees maximum sunk cost before first falsification. | Replace with thin vertical slices, each ending in a measurable consumer benefit (§8). |

#### × Contradictions — divergence between early notes and Phase 3 PAEOS reality

| ID | Contradiction | Detail | Resolution proposed |
|----|---------------|--------|---------------------|
| **×1** | **The acronym names three different systems** | **S**ystems Architecture KG (L3, L1) · **S**oftware Architecture KG (PAEOS-9 §10) · **S**emantic Architectural KG (RB-0005). These are not stylistic variants. L3's scope is *all engineering knowledge from any discipline* (education, scientific discovery, cross-domain analogy at textbook scale). PAEOS-9's scope is *software-architecture precedent for its own engineering loop*. One is a civilization-scale encyclopedia; the other is a project memory. | **Founder decision required.** This specification adopts RB-0005's **Semantic Architectural Knowledge Graph** and the narrow scope (§3.1), because it is the founder's most recent framing and the only scope with a specified consumer. L3's broader ambition is preserved as an explicit extension path, not deleted. |
| **×2** | **L3 does not know its own first customer** | L3 §9.9 and §11.9 enumerate expected consumers — CGSF, Design Review Engine, Idea OS, educational platforms, scientific discovery — and **PAEOS is not among them**. Meanwhile PAEOS-9 §10 is the only fully specified consumption contract in existence, written from a running Phase-3 system. L3's architecture was optimized for hypothetical consumers while the real one went unrepresented. | The **PAEOS-9 §10.1 method set is treated as ratified requirement**, and the ontology is derived backwards from it (§4, §5). |
| **×3** | **Two constitutions both claim supremacy** | `SAKG_Constitution.md`: *"This Constitution takes precedence over all other SAKG documents."* `operations/ENGINEERING_LIFECYCLE.md`: *"Operational doctrine for all PAEOS-based engineering: PAEOS Runtime, Sentium, Orca-Strator, Inspiration Engine, Library of Fire, **SAKG**, and every future project."* Both are founder-authored. Unresolved, they produce two ACP/proposal processes, two ADR registers, two review protocols. | **Founder decision required.** Recommended: PAEOS lifecycle governs *engineering process* (how SAKG gets built); the SAKG Constitution is demoted to *domain principles* (what SAKG believes about knowledge) with the conflicting articles (II, VI) amended per Δ1/Δ2. One ACP process: PAEOS CER-2. |
| **×4** | **Incompatible ambitions for the same artifact** | L1 (0.5) and L3 (§4.6, ADR-018) build toward a **Decision Engine** emitting justified recommendations with confidence scores (*"Recommendation: Bloom Filter / Confidence: 0.94"*). PAEOS-9 §10.2 rules that SAKG output is *"never instruction, never evidence, never a gate authority"* — SUMMARY/INDEX-tier advisory material tagged `provenance: sakg`, untrusted and re-verifiable. The v1.0 Decision Engine's flagship output is, to its only real consumer, **inadmissible**. | Not fatal but must be stated. SAKG **may** compute rankings; consumers **must** treat them as untrusted priors. Derived **FPL-3** makes this structural (§3.3), not merely a rule. |
| **×5** | **Statistical promotion vs. evidence-gated promotion** | ADR-011 promotes Candidate → Canonical on thresholds: *"5+ references, 3+ domains, confidence >75%"*. PAEOS K1 admits nothing to canonical status without bound, reproducible evidence. Frequency is not evidence; it is popularity, and it is exactly the surface a poisoning attack targets (PAEOS-7.5 T3e). | Keep the candidate namespace (✓6); **replace the promotion rule**. Canonical status requires an evidence binding (an outcome, a benchmark, a sealed PAEOS goal). Frequency may *prioritize review*; it may never *constitute* promotion. |
| **×6** | **The dependency arrow is empirically inverted** | L3 §11.10 positions SAKG as *"foundational infrastructure"* — a universal substrate everything else is built on. RB-0001/RB-0003/RB-0004 all defer to it as a prerequisite. But PAEOS reached Phase 3 autonomous self-hosting **without SAKG**, and PAEOS-9 §10.4 proves PAEOS is *complete* without it. | SAKG is **not** foundational. It is a **downstream quality multiplier** on a system that is already correct. This inverts the roadmap: SAKG must earn its place against a measured no-SAKG baseline, and must be droppable with zero correctness impact. |
| **×7** | **L2 and L3 froze different things under different names** | L2 declares "Engineering Universe v1.1" frozen (13 components). L3 declares "SAKG Specification v1.0" approved. Same date, same repo, overlapping content, different version numbers and vocabularies (Knowledge Space / Coordinate System vs. Foundation Layer / Ontology Component). Violates L3's own Art. V (One Canonical Definition). | This document supersedes both as the canonical architecture. L2 and L3 are retained as **evidence**, per RB-0005's method. |

#### Ω Missing Ideas — gaps required for ecosystem integration

| ID | Gap | Why it is required |
|----|-----|--------------------|
| **Ω1** | **Self-population from PAEOS exhaust** | Nothing in L1–L3 notices that PAEOS *already emits exactly what SAKG needs*: decision records with constitutional basis, trade-off matrices (L06), mitigation catalogues (L07), scars with root-cause bundles, sealed evidence, and promotion outcomes. L3 treats acquisition as its hardest problem (Phase 2, plus IT-01's "thousands per hour" ingestion crisis). Derived **FPL-5** says this is the dominant risk — and it is **largely already solved**, for free, by a system that runs today. This is the single largest missed opportunity in the corpus. |
| **Ω2** | **The outcome feedback loop** | L1 (0.5 Layer 9 "Learning") gestures at it; nothing specifies how a *realized* outcome updates the decision that produced it. Without this, SAKG stores what was decided, never what worked — precisely the encyclopedia L3 Art. I disclaims. Required by derived **FPL-2**. |
| **Ω3** | **Context-budget projection contract** | No document in the corpus treats the token budget as an architectural constraint. L3's Query Component specifies parsing, planning, and result generation but no notion of *how much* comes back. Required by derived **FPL-4**; fatal for the only real consumer, whose SCOPE stage is budget-governed. |
| **Ω4** | **Knowledge decay and falsifiers** | No TTL, no expiry, no `falsifier_watch` analogue, no Truth Maintenance (L2's IT-05, unresolved). Required by derived **FPL-6**. |
| **Ω5** | **Cross-project identity and isolation** | SAKG spans repositories by definition (**FPL-1**), yet nothing specifies how the *same* component in two repos is identified, or how project A's proprietary architecture is prevented from leaking into project B's query results. A cross-project graph without a tenancy model is a confidentiality incident waiting to happen. |
| **Ω6** | **A threat model for SAKG itself** | PAEOS-7.5 threat-models PAEOS, and PAEOS-9 §10.2 defends PAEOS *against a lying SAKG*. Nobody has specified how SAKG resists poisoning of **its own** corpus — which matters the moment a second consumer trusts it more than PAEOS does. |
| **Ω7** | **The SAKG ↔ Concept Graph boundary** | Concept OS claims: a graph of concepts, reasoning over them, cross-domain discovery, hybrid representation, verification. SAKG claims the same list. Neither repo mentions the other's boundary. Unresolved, this is a straight duplication of effort across two multi-month programmes. |
| **Ω8** | **The ORCA-strator contract** | RB-0001/RB-0003 route ecosystem deliberation to SAKG as an "ontology critic" council member. But a graph has no opinions — it has retrievals. As-built ORCA-strator recruits *model-backed agents* with skills. No contract exists for how a passive store participates in an active council. |
| **Ω9** | **Measured value / cold-start behaviour** | PAEOS-9 §10.3 requires SAKG be measured against a no-SAKG baseline and *"dropped with zero correctness impact"* if it stops paying. No SAKG document contains any notion of being measured, or of what it returns when empty. Without this, ×6 cannot be adjudicated. |
| **Ω10** | **Write-path authority and single-writer discipline** | L3 §4.5 says the Acquisition Layer is the only entry point. But if PAEOS emits (Ω1), does PAEOS write directly? PAEOS enforces single-writer integration (K8/I9) *inside* its boundary; nothing defines writer discipline *across* the boundary. |

---

## §3 Phase C — Canonical Architecture: Position and Boundary

### §3.1 Definition

> **SAKG (Semantic Architectural Knowledge Graph)** is the longitudinal,
> cross-project, evidence-bound memory of **architectural decisions and their
> realized outcomes**. It exists to widen the relevance horizon of engineering
> systems beyond what is reachable in any single repository, and it is
> architecturally incapable of authority over the systems it serves.

Scope is **software and systems architecture first**. Other engineering
disciplines are an extension path (§4.4), not a v1 requirement — Δ1.

### §3.2 System boundary

**SAKG is responsible for:**
1. Representing architectural decisions, their alternatives, constraints,
   trade-offs, and realized outcomes as a typed graph.
2. Preserving provenance, evidence references, confidence, and validity windows
   for every assertion.
3. Ingesting decision exhaust from producer systems through one governed path.
4. Exposing budget-bounded, ranked, explainable projections over the graph.
5. Isolating knowledge by project namespace and enforcing disclosure policy.
6. Decaying, superseding, and refuting its own contents as outcomes arrive.

**SAKG is NOT responsible for** *(each line closes a Δ or ×)*:
1. **Deciding anything.** No verdicts, no gates, no promotion. (**FPL-3**, ×4)
2. **Reasoning.** No trade-off analysis, no synthesis, no critique, no
   recommendation engine. Consumers reason; SAKG retrieves. (Δ5, IT-20)
3. **Storing raw documents.** Evidence is referenced by hash/URI, never copied.
4. **Being the source of truth for any consumer's local state.** PAEOS's 12 local
   graphs remain authoritative (PAEOS-9 §5.0). (×6)
5. **Representing all engineering knowledge.** (Δ1)
6. **Governing its consumers' processes.** (×3)
7. **Concept representation research** — that is Concept OS's programme. (Ω7)

### §3.3 The three structural non-authority guarantees

Derived **FPL-3** requires that non-authority be *structural*, not policy. Three
mechanisms enforce it:

1. **Read-only egress.** SAKG's consumer interface exposes no mutating method.
   Writes arrive only on the ingest path (§6.1), which no consumer's query
   capability can reach.
2. **Tier-tagged output.** Every projection result is tagged
   `provenance: sakg`, `tier: SUMMARY|INDEX`, `trust: untrusted`. PAEOS's Context
   Compiler admits it as advisory material only, folded in with its own
   provenance hash so "with SAKG" and "without SAKG" are two distinct,
   each-reproducible context states (PAEOS-9 §10.4).
3. **No evidence minting.** SAKG cannot produce an object of type `Evidence` in
   any consumer's schema. It emits `EvidenceRef` — a *pointer* to evidence that
   lives elsewhere and must be independently re-verified. A consumer that wants
   to rely on it must fetch and verify the original.

Consequence: a fully poisoned SAKG degrades suggestion quality and cannot advance
a defective goal past any gate.

---

## §4 Semantic Node Schemas

### §4.1 Design rule

Node types are derived **backwards from the five ratified PAEOS-9 §10.1 methods**
(×2), not forwards from taxonomy intuition (Δ4). Twelve core types — against
L1's 20–40 and L3's open-ended set.

### §4.2 Universal envelope

Every node carries the same envelope. This is the ECS `Entity` (✓7); type-specific
content lives in facets.

```yaml
Node:
  id:            URI            # sakg://<namespace>/<type>/<ulid>
  type:          NodeType       # §4.3 closed set at v1
  namespace:     ProjectRef     # tenancy + isolation boundary (Ω5)
  facets:        {name: {...}}  # ECS components; extension without schema surgery (✓7)
  label:         string
  summary:       string         # <= 280 chars; the SUMMARY-tier projection unit (Ω3)

  # Provenance (L7, ✓4)
  provenance:
    origin:      OriginRef      # producing system + run/goal id
    author_kind: enum(human, agent, ingest, inferred)
    ingested_at: timestamp
    source_hash: sha256         # content-addressed source artifact

  # Evidence (✓4) — references only, never copies (§3.2.3)
  evidence:      [EvidenceRef]

  # Epistemic state (Δ6, ×5, L6)
  status:        enum(candidate, canonical, superseded, refuted)
  confidence:    float          # DERIVED, never authored; recomputed on change
  valid_from:    timestamp
  valid_until:   timestamp|null # null = open; decay policy applies (Ω4)
  falsifier:     string|null    # what observation would refute this (Ω4, K6)

  # Coordinates (✓8) — flat, multi-valued, never hierarchical
  coordinates:   {dimension: [value]}
```

**Invariants.**
- `confidence` is **derived**, never authored (Δ6). Any recomputation of a node's
  confidence propagates along `derived_from` and `supports` edges — the Truth
  Maintenance obligation L2's IT-05 left open.
- `candidate → canonical` requires an **evidence binding**, never a frequency
  threshold (×5). Frequency may raise review priority only.
- A node whose `falsifier` is observed transitions to `refuted`. Refuted nodes are
  **retained** — a refuted decision is high-value knowledge (✓1, **FPL-2**).
- Nothing is ever deleted; supersession only (✓4, L3 ADR precedent).

### §4.3 The twelve core node types

| Type | Role | Serves method |
|------|------|---------------|
| **Decision** | *The central node* (✓1). A choice made in a context, with alternatives considered and a rationale. Carries `constitutional_basis` when produced by a governed system. | all |
| **Problem** | The need a decision answers. | `pattern_retrieval` |
| **Option** | A candidate that was considered — **including rejected ones**. Rejected options are the corpus's scarcest, most valuable knowledge. | `tradeoff_precedents` |
| **Constraint** | A limit that pruned the space (latency, memory, budget, regulation, physics). | `tradeoff_precedents` |
| **Objective** | A property being optimized. | `tradeoff_precedents` |
| **TradeOff** | An explicit exchange between two Objectives/Constraints, with the axis and the resolution. | `tradeoff_precedents` |
| **Mechanism** | A reusable way something works (caching, replication, consensus, backpressure). Cross-domain by nature (✓9). | `pattern_retrieval` |
| **Pattern** | A named recurring structure, **including anti-patterns**. | `pattern_retrieval` |
| **Component** | An architectural element that exists in a system: service, module, interface, data store. | `query_architectures`, `dependency_impact` |
| **Outcome** | *The Ω2 fix.* What actually happened after a Decision was realized: held / degraded / reverted / caused-incident, with the observation window and measurement. **The only node type that may be created long after its subject.** | `query_architectures`, `memory_augment` |
| **Scar** | A failure class with `root_cause`, `detection_signature`, `guard_action`. Mirrors PAEOS's scar-graph so scars round-trip losslessly (Ω1). | `memory_augment` |
| **EvidenceRef** | A *pointer* to evidence living elsewhere: hash, URI, kind, and re-verification instructions. Never the artifact itself (§3.3.3). | all |

**Extension.** New types require a demonstrated consumer need and a ratified
change (✓10, Δ4). New *facets* on existing types require only namespace
registration — this is where domain extension (Δ1) happens without touching the
core.

### §4.4 Edge model

Eight families, not L1's 15–22 with 100–300 members (Δ4). Every edge is itself an
object carrying `confidence`, `evidence`, `context`, `valid_from/until`,
`provenance` — L1 (0.3) got this right and it is retained.

| Family | Members | Purpose |
|--------|---------|---------|
| **Structural** | `part_of`, `instance_of`, `specializes` | Composition and typing |
| **Dependency** | `depends_on`, `calls`, `provides`, `consumes` | The blast-radius substrate for `dependency_impact` |
| **Decisional** | `decides`, `considered`, `rejected`, `rationale_for`, `constrained_by`, `optimizes_for` | Binds Decision to Problem/Option/Constraint/Objective — the ✓1 core |
| **Consequential** | `resulted_in`, `caused`, `mitigated`, `regressed` | Decision → Outcome; the **FPL-2** longitudinal spine |
| **Trade-off** | `trades_off_with`, `improves_at_cost_of` | The `tradeoff_precedents` substrate |
| **Evidential** | `supported_by`, `contradicted_by`, `measured_by` | Provenance and Truth Maintenance propagation |
| **Similarity** | `analogous_to`, `alternative_to`, `replaces` | Cross-project and cross-domain transfer (✓9); the `memory_augment` substrate |
| **Temporal** | `supersedes`, `derived_from`, `precedes` | Versioning and lineage |

**Edge invariants.** Dependency edges within a namespace must be acyclic (a cycle
is an ingest defect). `analogous_to` is never transitive. Cross-namespace edges
are permitted only between nodes whose disclosure policies both allow it (Ω5).

---

## §5 Graph Query Interfaces

### §5.1 The projection contract (Ω3, FPL-4)

**Every query is budget-bounded.** This is the interface's defining property, and
its absence from the entire corpus is Ω3.

```
Projection Request:
  method:        one of §5.2
  subject:       node id | pattern | signature | touch-set
  namespace:     ProjectRef[]        # tenancy scope; default = caller's own
  budget:
    max_tokens:  int                 # HARD ceiling on serialized response
    max_nodes:   int
    tier:        SUMMARY | INDEX     # never FULL — SAKG cannot flood context
  filters:
    min_confidence:  float
    as_of:           timestamp       # time-travel; honours valid_from/until (Ω4)
    status:          [canonical, candidate, refuted]   # default [canonical]

Projection Response:
  results:  [ {node_summary, score, why} ]   # `why` = the traversal path taken
  provenance:  {sakg_version, corpus_hash, query_hash}
  truncated:   bool
  omitted:     int
  trust:       "untrusted"           # constant; §3.3.2
  tier:        SUMMARY | INDEX
```

**Rules.**
1. The response **must** fit `max_tokens`. Over-budget results are dropped and
   counted in `omitted`, never silently truncated mid-structure.
2. Every result carries `why` — the traversal path and the filters applied. An
   unexplainable result is a defect. This makes SAKG's contribution auditable in
   the same way PAEOS-9 §4.5 makes SCOPE replayable.
3. `corpus_hash` + `query_hash` make any projection **reproducible**, preserving
   the consumer's deterministic `content_hash` (PAEOS-9 §10.4).
4. `status` defaults to `[canonical]`. Retrieving `candidate` knowledge requires
   explicit opt-in (×5).
5. No method mutates. Ever (§3.3.1).

### §5.2 Methods

The five methods are **fixed by PAEOS-9 §10.1** and reproduced here as ratified
requirement (×2). Each is defined as a traversal, so SAKG never reasons (Δ5).

| Method | Traversal | Returns |
|--------|-----------|---------|
| `query_architectures(pattern)` | Match `Component`/`Pattern` sub-graphs structurally similar to the caller's touch-set; walk `decides`/`resulted_in` to their Decisions and Outcomes. | Prior designs shaped like this, **with what happened to them**. |
| `dependency_impact(component)` | Transitive closure over the Dependency family from `component`; join to `Outcome` nodes of type regressed/caused-incident. | Historical blast radius — what actually broke. |
| `tradeoff_precedents(axes)` | Match `TradeOff` nodes on the given axes; walk to the `Decision` that resolved them and its realized `Outcome`. | How this trade-off was resolved before, and whether it held. |
| `pattern_retrieval(problem)` | From `Problem`, walk `decides`/`considered` to Options, Mechanisms, Patterns; include anti-patterns and `rejected` options. | Reusable patterns **with scars attached**. |
| `memory_augment(signature)` | Semantic neighbours of a scar/precedent signature via the Similarity family. | Semantic neighbours — *explicitly* subordinate to the consumer's deterministic signature-match floor (PAEOS-9 §10.2, T3). |

`memory_augment` is the only semantically-retrieved method and is therefore the
primary poisoning surface (Ω6). Its results are always ranked **below** a
consumer's exact-match results, and it is the first method disabled under
degradation (§7).

### §5.3 What the interface deliberately omits

No general-purpose query language at v1 (Δ3/Δ4). Five methods with hard budgets
are conformance-testable; an open query language is not, and it would let a
consumer accidentally make SAKG load-bearing — the failure mode **FPL-3** forbids.

---

## §6 Integration Contracts

### §6.1 PAEOS — producer and consumer

PAEOS is the **first and reference** consumer, and simultaneously the **primary
producer** (Ω1). Two contracts, deliberately separate.

**(a) Consumption — read-only, capability-gated.** Exactly as ratified in
PAEOS-9 §10:
- SAKG is one substrate MCP server (`sakg`, PAEOS-7.6 §8), deny-by-default, on a
  role's allow-list only where its stage benefits.
- Queried by the Context Compiler's SCOPE stage as an augmentation tier layered
  **over** the 12 local graphs, never replacing them.
- Consumption points unchanged: L04, L06, L07, L08, L10, L11, L18, L19, and scar
  matching at L03/L08/L09/L13.
- **Never consulted for** capability decisions, evidence adjudication, seal,
  classification authority, or promotion.

**(b) Production — the exhaust contract (Ω1, Ω10).** This is new, and it is the
mechanism that solves the population problem L3 treated as its hardest phase.

```
PAEOS goal reaches L16 (Promotion) and seals
        │
        ▼
L15 emits a SAKG Emission Bundle (append-only outbox, in-repo)
        │  Decision   ← from the decision-graph (ADR records + constitutional_basis)
        │  TradeOff   ← from the L06 trade-off matrix
        │  Option     ← from L04 candidates, INCLUDING rejected ones
        │  Constraint ← from the L11 implementation contract
        │  Component  ← from the L08 architecture artifact set
        │  Scar       ← from the scar-graph (root-cause bundle, A-10)
        │  EvidenceRef← hashes only; evidence never leaves PAEOS
        ▼
SAKG ingest reads the outbox (pull, never push)
        │
        ▼
Nodes land as `candidate` in namespace = the producing project
```

**Contract rules.**
1. **One-way, post-seal, pull-based.** SAKG never writes into PAEOS and never
   participates in a live run. Emission happens after promotion, so nothing SAKG
   does can affect the goal that produced it. This preserves K8 single-writer
   discipline across the boundary (Ω10): PAEOS writes its outbox; SAKG writes its
   own graph; neither writes the other's.
2. **Evidence never leaves.** Only `EvidenceRef` hashes cross. Re-verification
   requires going back to PAEOS's CAS.
3. **Outcomes flow back later (Ω2).** When a scar, incident, or regression is
   later attributed to a sealed decision, L17/L19 emits an `Outcome` node bound to
   that Decision. **This is the loop that makes SAKG memory rather than archive.**
4. **Namespace and disclosure are set at emission**, by the producing project
   (Ω5).
5. **Measured (Ω9).** Every consumption is logged against the no-SAKG baseline in
   PAEOS's cost meter (PAEOS-9 §9, §10.3). If SAKG stops paying for itself it is
   removed from allow-lists with zero correctness impact (×6).

### §6.2 Concept Graph (Concept OS) — boundary contract (Ω7)

The corpus has never drawn this line, and both programmes are actively spending
against the overlap. Proposed division, on the axis that actually separates them:

| | **SAKG** | **Concept Graph / Concept OS** |
|---|---|---|
| **Subject** | Decisions that were *made*, in real systems | Concepts and how they might be *represented* |
| **Epistemics** | Retrospective, evidence-bound | Generative, hypothesis-forming |
| **Truth source** | Realized outcomes | Verification of constructed claims |
| **Commitment** | Committed schema (§4) | Deliberately uncommitted (Models A–G) |
| **Failure if wrong** | Bad priors, degraded suggestions | Wrong research direction |

> **Boundary rule:** SAKG records **what was decided and what happened**. Concept
> OS explores **how knowledge could be represented and discovered**. Where they
> meet — `Mechanism`, `Pattern`, `analogous_to` — SAKG is the *source of
> evidence-bound instances* and Concept OS is the *consumer of them*.

**Contract:** Concept OS reads SAKG through the same untrusted, budget-bounded
projection interface as any consumer. **Concept OS never writes to SAKG** —
hypotheses are not decisions, and admitting them would violate ✓4 and ×5. If a
Concept OS hypothesis is later realized in a system, it re-enters SAKG through
that system's PAEOS exhaust (§6.1b), carrying real evidence.

### §6.3 ORCA-strator — the council contract (Ω8)

RB-0001/RB-0003 route deliberation to SAKG as an "ontology critic". As-built,
ORCA-strator recruits *model-backed agents with skills*, and **a graph has no
opinions**. Resolving this without violating **FPL-3**:

> SAKG joins councils as a **retrieval service, not a voting member.**

- ORCA-strator recruits agents. When a council needs architectural precedent, the
  **agent** queries SAKG through the §5 projection interface and argues from the
  results, in its own voice, carrying its own accountability.
- SAKG holds no vote, no weight, and no confidence in any deliberation outcome. A
  store that votes is a store with authority (**FPL-3**).
- Retrieved material enters deliberation tagged `provenance: sakg, trust:
  untrusted`, exactly as in PAEOS (§3.3.2). A council may not treat it as
  settled.
- **Cross-project scope is a capability**, not a default: ORCA-strator must supply
  an explicit namespace scope, and SAKG enforces disclosure policy per namespace
  (Ω5).
- Deliberation *outcomes* re-enter SAKG only if they become decisions in a
  governed project — i.e. through §6.1b, never directly from a council.

### §6.4 Contract summary

| System | Reads | Writes | Authority granted |
|--------|-------|--------|-------------------|
| **PAEOS** | ✅ §5, capability-gated | ✅ via post-seal outbox only (§6.1b) | none — augmentation only |
| **Concept Graph** | ✅ §5 | ❌ never | none |
| **ORCA-strator** | ✅ §5, via recruited agents | ❌ never | none; no vote |
| **Future consumers** | ✅ §5 | ❌ unless a governed producer | none |

**One write path. Zero authority. Universally.**

---

## §7 Degradation and Failure Behaviour

Mandated by ×6 and PAEOS-9 §10.4: SAKG must be droppable.

| Condition | Behaviour |
|-----------|-----------|
| **SAKG empty (cold start, Ω9)** | Returns `results: []` with `omitted: 0`. This is a **valid, expected** response, not an error. Every consumer must be correct on day one against an empty graph. |
| **SAKG unreachable** | Consumer omits the augmentation tier and proceeds on local graphs alone. No retries on the critical path. |
| **Budget exceeded** | Return the top-ranked subset within budget; report `truncated: true` and `omitted: n`. Never overflow the caller's context. |
| **Corpus poisoning suspected (Ω6)** | Disable `memory_augment` first (§5.2), then all semantic methods; structural methods (`dependency_impact`) degrade last. |
| **Confidence collapse** | Nodes below `min_confidence` are withheld, never silently upranked. |
| **Consumer measures no benefit (Ω9)** | Removed from allow-lists. Zero correctness impact by construction. |

**Falsifier for this specification (Δ3, K6):** if, after one measurement window, a
consumer cannot demonstrate benefit against its no-SAKG baseline — fewer research
spawns, fewer design remands, or better triage priors — then SAKG as specified
here is not worth its cost, and this document should be reverted rather than
extended.

---

## §8 Delivery Path

Replaces L3's nine frozen sequential phases (Δ8, Δ2). Each slice ends in a
measurable consumer benefit; no slice depends on a frozen predecessor.

| Slice | Scope | Falsifiable exit criterion |
|-------|-------|---------------------------|
| **S1 — Exhaust** | Emission bundle from PAEOS L15/L16 (§6.1b). No query surface. | A sealed PAEOS goal produces a valid bundle; round-trip is lossless. |
| **S2 — Store + one method** | Envelope (§4.2), Decision/Option/TradeOff/Outcome, `tradeoff_precedents` only. | Returns a real precedent from a real prior goal, within budget, with `why`. |
| **S3 — Outcome loop** | `Outcome` emission from L17/L19; Truth Maintenance propagation (Δ6, Ω2). | A regression attributed to a prior decision measurably lowers that decision's confidence. |
| **S4 — Remaining methods** | The other four §5.2 methods; full node set. | Each demonstrates benefit against the no-SAKG baseline (Ω9). |
| **S5 — Multi-tenancy** | Namespace isolation, disclosure policy, cross-project edges (Ω5). | A second project's graph is queryable, and a disclosure-denied node provably never leaks. |
| **S6 — Ecosystem** | ORCA-strator (§6.3) and Concept Graph (§6.2) contracts. | An ORCA council cites SAKG-retrieved precedent, correctly tagged untrusted. |

**S1 and S2 are the whole bet.** If SAKG cannot demonstrate value from PAEOS's own
exhaust with one method, the broader programme is not justified — and that is
knowable in one slice instead of nine phases.

---

## §9 Adversarial Self-Review (CER-1)

Per CER-1, this document attacks itself. Findings are **[MODIFY]** (folded in
above) or **[DEFEND]**; survivors are carried honestly.

**A1 — "You narrowed SAKG from a civilization-scale knowledge platform to a
project memory. That destroys the founder's vision."** **[DEFEND, with carry]**
The broad vision is preserved as an extension path: ECS facets (✓7), flat
coordinates (✓8), and cross-domain `analogous_to` (✓9) are all retained precisely
so the scope can widen. What is rejected is *committing to universality before a
single consumer exists* (Δ1). The narrower system is a strict subset — widening
later costs facets; narrowing later would cost a rewrite. **Carried:** this is a
genuine scope reduction and requires founder ratification (×1).

**A2 — "Deriving the ontology backwards from PAEOS-9's five methods makes SAKG a
PAEOS component, not a platform."** **[MODIFY]** Real risk. Mitigated by §6.2/§6.3
specifying two non-PAEOS consumers on the *same* interface, and by §4.4's
extension rule. But **carried**: v1 is unavoidably shaped by its only real
consumer. This is a deliberate trade — a shaped-but-real system over a
general-but-hypothetical one — and it is exactly the trade L3 got wrong (×2).

**A3 — "SAKG as memory-not-judgment abandons the Decision Engine, the most
exciting idea in the corpus."** **[DEFEND]** It relocates it, not abandons it. The
Decision Engine becomes a *consumer* (a PAEOS L06 worker, an ORCA council, a
future application) reading SAKG. This satisfies ✓3/**FPL-8**, keeps judgment
decorrelated from the store that feeds it, and lets multiple competing engines run
over one corpus. Building it *inside* SAKG would create a second un-auditable
judge (Δ5).

**A4 — "The exhaust contract makes SAKG's corpus reflect only what PAEOS
happened to build — a small, biased sample."** **[DEFEND, with carry]** True and
acknowledged. But a small corpus of *evidence-bound, outcome-joined real
decisions* is worth more than a large corpus of unverified extracted assertions —
that is ✓4 and ×5. External ingestion remains possible later, and must enter as
`candidate` requiring evidence binding to become canonical. **Carried:** sample
bias is real; PAEOS-9 §13.11's "systematically-biased SAKG" residual applies here
and is mitigated only by adversary decorrelation, not eliminated.

**A5 — "Budget-bounded projections mean the most relevant fact may be omitted
silently."** **[MODIFY]** Folded into §5.1: `omitted: n` and `truncated: bool` are
mandatory, so omission is always *visible*. **Carried:** visible ≠ recovered. This
is the same residual PAEOS-9 §13.10 carries for relevance-as-reachability, now
inherited one level up.

**A6 — "Two constitutions (×3) is a governance failure this document doesn't
fix."** **[DEFEND]** Correct — it cannot fix it. CER-5 forbids the runtime from
legislating. §2.2 ×3 states the conflict, recommends a resolution, and routes it
to the founder. That is the maximum authority available.

**A7 — "You classified L3 as low-evidence because it has no implementation, then
built on PAEOS-9 §10 which also has no SAKG implementation."** **[DEFEND]**
Asymmetric for a defensible reason: PAEOS-9 §10 is a *consumption* contract
authored by a system that runs, passed its adversarial court, and specifies its
own behaviour when SAKG is absent — which is the part already executing in Phase
3. L3 specifies the behaviour of a system that has never run. Both are unbuilt;
only one is anchored to executed reality.

**A8 — "Ω1 (self-population) is presented as a breakthrough but assumes PAEOS
emits clean structured decisions. Does it?"** **[MODIFY]** Partially. PAEOS
*produces* all the required artifacts (L06 matrices, L08 design sets, L11
contracts, decision-graph records, scars), but as prose documents, not as typed
emission bundles. Slice S1 (§8) exists precisely to build and test that
extraction. **Carried:** if L15 artifacts prove too unstructured to extract
losslessly, S1 fails and Ω1's value is overstated. **This is the specification's
single largest untested assumption.**

**Residual risks carried** (not eliminated): scope reduction pending ratification
(A1); consumer-shaped v1 (A2); corpus sample bias (A4); silent-but-counted
omission (A5); unfixable dual governance (A6); **and the S1 extraction assumption
(A8), which is load-bearing for the entire delivery path.**

---

## §10 Founder Decisions Required (A4 Ratification)

**All 7 decisions RATIFIED BY FOUNDER PROXY (2026-08-06) under A4 delegation:**

| # | Decision | Disposition | Status |
|---|----------|-------------|--------|
| **D1** | **Resolve the acronym (×1).** Systems / Software / Semantic Architectural Knowledge Graph. | Adopt **Semantic Architectural Knowledge Graph** per RB-0005, scoped to architectural decision memory (§3.1). | **RATIFIED** |
| **D2** | **Ratify or reject the scope reduction (Δ1, A1).** Domain-agnostic-from-day-one → software-architecture-first, extension-ready. | Ratify. Preserve extension via ECS facets. | **RATIFIED** |
| **D3** | **Resolve dual constitutions (×3).** | PAEOS lifecycle governs process; SAKG Constitution demoted to domain principles; Articles II and VI amended per Δ1/Δ2. One ACP process (CER-2). | **RATIFIED** |
| **D4** | **Confirm the SAEOS document series name.** Undefined in the corpus (§0). | Confirmed: **Semantic Architectural Engineering Operating System**. | **RATIFIED** |
| **D5** | **Approve the delivery path (§8) over L3's nine phases (Δ8).** | Approved: S1+S2 as the falsifiable bet. | **RATIFIED** |
| **D6** | **Approve the Concept Graph boundary (§6.2, Ω7).** Affects an independent programme. | Approved: Concept Graph remains independent. | **RATIFIED** |
| **D7** | **Accept or reject A8's carried risk** — the S1 extraction assumption. | Accepted, scoped: S1 is explicitly a falsification test. | **RATIFIED** |

**Disposition of prior artifacts:** L1, L2, and L3 are reclassified
from *specification* to **evidence** (RB-0005's method), retained in place,
superseded by this document as canonical architecture. Nothing is deleted.

---

## §11 Traceability

| This document | Derives from |
|---|---|
| Mission and method | `backlog/research/RB-0005-mission-zero-sakg-discovery.md` |
| CER-1 derivation stance | `operations/ENGINEERING_LIFECYCLE.md` §CER-1, §L03 |
| Consumption contract (§6.1a) | `spec/PAEOS-9-execution-architecture.md` §10; `spec/PAEOS-7.6-runtime-interface-contracts.md` §8 |
| Non-authority guarantees (§3.3) | PAEOS-9 §10.2; PAEOS-7.5 (T3, T3e, T9) |
| Emission contract (§6.1b) | PAEOS-9 §5 (12 local graphs); `ENGINEERING_LIFECYCLE.md` L15–L19 |
| Ecosystem contracts (§6.2–6.3) | `backlog/research/RB-0001`, `RB-0003`; `/GitHub/Concept Graph `; `/GitHub/orca-strator` |
| Validated ideas ✓1–✓11 | `/GitHub/SAKG/` L1, L2, L3 (cited per row in §2.2) |
| Knowledge acquisition boundary | `backlog/research/RB-0004-knowledge-acquisition-engine.md` |

**Status: RATIFIED BY FOUNDER PROXY (2026-08-06).** Proceeding to Phase D (`SAKG-1-backlog.yaml` generation & TDD implementation).

