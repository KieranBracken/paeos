# Ecosystem Constitution and Boundary Map

**Status:** CANONICAL / FOUNDER-DIRECTED  
**Version:** 1.0  
**Effective:** 2026-09-04  
**Authority:** Founder/Court governance record for the PAEOS ecosystem

## Purpose and constitutional rule

This document is the canonical boundary map for the seven-repository ecosystem. A repository,
directory, model, or user interface does not acquire sovereignty merely by existing. Sovereignty
means owning a stable class of authoritative state, an explicit decision boundary, and the
evidence required to change that state. Every other component is a subsystem, substrate, or
application with a narrower contract.

The dependency graph is deliberately acyclic at the authority layer:

```text
Human / applications
        │ proposals, intents, observations
        ▼
Orca-strator (council and interaction subsystem)
        │ governed tasks and proposals
        ▼
PAEOS (constitutional execution and verification sovereign)
   ┌────┴───────────────┐
   │                    │
   ▼                    ▼
 SAKG ◄──── validated ─ Concept OS
   ▲                    │
   └── evidence-bound ──┘
        │
        ▼
Sentium (trading application sovereign)
```

The arrows describe permitted calls and evidence flow, not ownership transfer. Models and
providers are stateless compute behind PAEOS; they never become a source of authoritative state.

## Four Sovereign Systems

### 1. PAEOS — Policy, Arbitration, Execution, and Oversight System

PAEOS is the constitutional execution and governance sovereign. It owns task intake and
decomposition, capability and policy checks, model/provider invocation policy, deterministic
execution, evidence collection, Court adjudication, promotion gates, replay, scars, debt, and
the canonical execution ledger. Its state is local and durable even when workers or providers
disappear. PAEOS may execute an experiment, but it does not decide that an experiment is an
engineering truth or a profitable trade.

PAEOS exclusively decides legality, admission, sequencing, budget, retries/fallback policy,
evidence sufficiency, and whether an artifact may be promoted. It forbids domain truth ownership,
conceptual sovereignty, trading strategy decisions, council composition, and UI/session ownership.

### 2. SAKG — Structured Engineering Knowledge Graph

SAKG is the sovereign authority for defensibly true engineered-system knowledge. It owns typed
claims, ontology and taxonomy, provenance, source/evidence grades, contradiction and falsification
records, scope, transfer confidence, and promotion/retraction of knowledge claims. Its canonical
state is a versioned claim graph backed by durable content-addressed evidence references and an
append-only provenance ledger.

SAKG validates or falsifies candidate mechanisms produced elsewhere. It forbids execution
authority, provider selection, task admission, raw-document dumping, unproven universal laws,
and silently converting an analogy into a claim.

### 3. Concept OS — Conceptual Exploration and Transformation System

Concept OS is the sovereign for concepts, relations, transformations, analogies, and the
possibility space. The **Concept Graph** is its principal substrate, not a fifth sovereign. The
**Inspiration Engine** is a first-class discovery subsystem inside Concept OS. Concept OS can
generate candidate hypotheses, semantic neighborhoods, recombinations, and transformation paths;
it cannot ratify them as engineering truth.

Concept OS exclusively owns conceptual topology, transformation provenance, exploration state,
and candidate generation. It forbids PAEOS policy gates, SAKG claim promotion, provider governance,
and Sentium execution or financial authority.

### 4. Sentium — Domain Trading Application System

Sentium is the application sovereign for market-facing workflows: instruments, portfolios,
strategies, risk limits, user-facing trading operations, and broker/exchange integration. It may
request PAEOS-governed analysis or execution and may consume SAKG-validated domain knowledge. Its
canonical state is its domain store (orders, positions, strategy versions, and audit trail), not
the PAEOS ledger or SAKG graph.

Sentium forbids mutation of the constitution, direct model/provider bypass, promotion of universal
claims, and treating Concept OS speculation as a trading instruction. PAEOS remains the gate for
any autonomous action with external effects.

## Subsystem and substrate resolutions

### Orca-strator over PAEOS

Orca-strator is a council and interaction subsystem/application **over** PAEOS, not a competing
execution kernel and not a dumb GUI. It owns council composition, deliberation topology and UX,
human interaction, session management, model-preference presentation, and proposal visualization.
It submits typed proposals and governed tasks to PAEOS. PAEOS alone decides legality, execution,
verification, admission, budget, and promotion. Orca-strator may display a decision; it may not
self-ratify one.

### Inspiration Engine inside Concept OS

The Inspiration Engine remains a first-class subsystem inside Concept OS. It owns discovery,
analogy search, recombination, and novelty scoring with links back to Concept Graph nodes. It does
not own a claim ledger or a provider policy. Its outputs are explicitly candidates that require
PAEOS evidence-bound experiments and SAKG validation.

### Concept Graph as Concept OS substrate

The Concept Graph is the durable graph/index substrate for Concept OS. It stores concepts,
relations, transformations, provenance pointers, and candidate status. It is not a sovereign
system and cannot issue a constitutional, engineering, or trading decision.

### Library of Fire into KAE/Corpus substrate

Library of Fire ceases to be an independent sovereign repository. Its raw corpus, archive metadata,
and acquisition history survive as an immutable **Corpus substrate**. A KAE/Corpus ingestion
capability normalizes, hashes, and indexes that material; SAKG then derives structured claims and
provenance from cited corpus items. Raw documents are never dumped directly into the structured
SAKG claim graph, and corpus presence is not evidence of truth.

### cli_orchestrator resolution

Generic worker, queue, and orchestration machinery currently associated with `cli_orchestrator`
is absorbed into PAEOS, where it is subject to the same policy, evidence, and Court gates. If the
remaining behavior is Sentium-specific, the surviving adapter is renamed
`sentium-agent-runtime`, `sentium-cli`, or `sentium-operator`. Duplicate generic worker runtimes
are deprecated; there is one generic execution contract owned by PAEOS.

## Closed Epistemic Loop

SAKG and Concept OS form a closed epistemic loop, with PAEOS as the evidence-bearing experimental
bridge:

1. SAKG exposes validated mechanisms, typed constraints, contradictions, and open questions.
2. Concept OS abstracts, transforms, and recombines those inputs; the Inspiration Engine searches
   the Concept Graph and emits candidate hypotheses.
3. PAEOS turns a candidate into a bounded, reproducible experiment or analysis, collecting raw
   evidence and Court decisions.
4. SAKG evaluates the evidence, records falsifiers and transfer confidence, then promotes,
   narrows, or rejects the claim.
5. The resulting validated mechanism and unresolved frontier return to Concept OS for the next
   exploration cycle.

No Concept OS output is truth by novelty, and no SAKG claim is widened merely because it was
recombined. A failed experiment is useful evidence and remains linked to the candidate that it
constrains.

## Graduated Claim Scoping and transfer confidence

Every SAKG claim carries a scope class, validated domains, evidence references, failed or
counterexample references, mechanism identity, and a transfer-confidence record. Transfer
confidence is recorded separately for each destination domain and for any cross-domain assertion;
the universal field is nullable until a specific Court-approved threshold is met.

The permitted progression is:

```text
observation → domain scar → domain principle → cross-domain pattern
→ generalized mechanism → candidate law → strongly established law
```

Widening requires additional independent evidence, not rhetoric. A claim is never made universal
because it appears in two domains. Transfer confidence considers domain diversity, independent
replication, invariance of the proposed mechanism, adversarial failures, boundary conditions,
time stability, and the quality of each source. A third domain is not an automatic promotion
either; it is merely one input to the evidence threshold. SAKG must preserve narrower scopes when
the evidence does not justify a wider one.

Minimum promotion record:

| Field | Requirement |
|---|---|
| `scope_class` | One of the graduated classes above; no implicit universal default |
| `domains_validated` | Named domains with independent evidence references |
| `evidence_refs` / `failure_refs` | Content-addressed positive and negative evidence |
| `mechanism_id` | Stable explanation of what is believed to transfer |
| `transfer_confidence` | Per-domain and cross-domain values with rationale and date |
| `promotion_decision` | SAKG/Court decision, reviewer family, and retraction conditions |

## Trust boundaries and dependency law

- **Evidence boundary:** raw observations and test outputs enter PAEOS as immutable,
  content-addressed evidence. A model summary is a proposal, never evidence by itself.
- **Knowledge boundary:** only SAKG may promote a structured engineering claim. SAKG consumes
  cited corpus and PAEOS evidence; it does not rewrite either source.
- **Concept boundary:** Concept OS may read validated knowledge and produce candidates. Candidate
  status is explicit and cannot cross into SAKG as a validated claim without the loop.
- **Action boundary:** Sentium requests actions through PAEOS. External side effects require
  Sentium risk checks plus PAEOS admission and Court/audit requirements.
- **Interaction boundary:** Orca-strator can coordinate people and models but cannot bypass PAEOS
  or alter authoritative state.
- **Provider boundary:** provider adapters perform stateless computation. Builder and auditor
  families must differ (A-08); provider output cannot mutate state directly.

## Formal Component Boundary Table

| Component | Classification | Exclusive responsibilities | Forbidden responsibilities | Authoritative state & persistence backend | Inbound / outbound APIs; permitted dependency directions | Evidence & trust boundary | Deprecation / physical consolidation roadmap |
|---|---|---|---|---|---|---|---|
| PAEOS | Sovereign System | Policy, task lifecycle, execution, budgets, Court, admission, promotion gates, replay | Domain truth, concept generation, council UX, trading strategy ownership | Tasks, history, tools, diffs, debt, scars, seals, ledger; CAS + append-only ledger/SQLite | Intake/task/evidence/Court APIs; calls workers/providers and reads SAKG/Concept OS; no reverse authority edges | Sole execution/evidence admission boundary; models are untrusted compute | Freeze contract; consolidate generic orchestration here; enforce CI DAG and retire duplicate runtimes |
| PAEOS Kernel, CAS & Ledger | Substrate | Typed artifacts, content hashes, signatures, durable chain, deterministic replay | Semantic claim promotion or UI | CAS blobs, signed evidence, ledger events; filesystem CAS + durable ledger | Evidence, seal, replay APIs; all PAEOS subsystems depend inward | Hashes/signatures and non-vacuous Court evidence are required | Keep as one kernel substrate; remove repository-local shadow ledgers |
| Orca-strator | Subsystem | Council membership/topology, deliberation UX, sessions, model preference UI, proposal visualization | Execution admission, evidence verification, self-ratification | Council/session/proposal views; session store with PAEOS references | Proposal/task API to PAEOS; read-only SAKG/Concept views; never calls providers around PAEOS | Human/model proposals are untrusted until PAEOS admission | Preserve as thin council layer; remove generic workers and duplicate policy code |
| SAKG | Sovereign System | Typed engineering claims, ontology, provenance, contradiction, scope, transfer confidence, promotion/retraction | Task execution, provider policy, raw corpus dump, trading action | Versioned claim graph and provenance; graph store + CAS references + append-only claim ledger | Claim/query/validate/promote APIs; consumes PAEOS evidence and KAE corpus refs; emits validated mechanisms to Concept OS | High-trust only after cited, graded, falsifiable evidence and Court/SAKG decision | Consolidate divergent graph models; retain one canonical claim/provenance service |
| KAE | Subsystem | Corpus acquisition, normalization, hashing, extraction, citation indexing | Claim promotion, execution, untraceable summarization | Ingest manifests and extraction indexes; object store/CAS | Ingest API from Corpus; emits immutable refs/citations to SAKG; no direct Concept truth | Raw source remains provenance-bearing but not automatically true | Merge Library acquisition code here; retire standalone Library service endpoints |
| Library of Fire / Corpus | Substrate | Immutable raw corpus/archive and acquisition history | Structured claims, execution, universalization | Raw documents, metadata, source hashes; immutable object/CAS archive | Read/ingest refs to KAE; no calls to PAEOS or Concept OS | Lowest trust zone; every derivative must cite a content hash and extraction step | Physically archive repository as corpus store; preserve hashes and migrate adapters to KAE |
| Concept OS | Sovereign System | Concepts, relations, transformations, possibility-space exploration, candidate lifecycle | Engineering truth, policy gates, provider calls, trading execution | Concept Graph and exploration sessions; graph DB/index + CAS provenance | Graph/hypothesis APIs; reads SAKG validated mechanisms, submits candidates to PAEOS; no direct SAKG promotion | Candidate outputs are exploratory and explicitly lower trust than validated claims | Freeze graph contract; absorb Inspiration Engine; retire competing concept sovereigns |
| Concept Graph | Substrate | Durable semantic topology, relation/transform records, provenance pointers | Sovereign decisions or claim promotion | Nodes, edges, transforms, candidate status; graph/index store + CAS | Graph query/mutation only through Concept OS; SAKG refs are read-only inputs | Provenance links required; graph adjacency is not evidence | Consolidate divergent graph schemas under Concept OS |
| Inspiration Engine | Subsystem | Analogy search, recombination, novelty and candidate generation | Truth, execution, provider governance, claim promotion | Discovery traces and candidate refs; Concept OS graph/session store | Discovery API inside Concept OS; emits candidates to Concept OS/PAEOS intake | Heuristic output; confidence is exploratory and cannot become SAKG confidence | Keep inside Concept OS; remove any standalone sovereignty or claim ledger |
| Sentium | Application | Market domain state, strategy, risk, user product, broker/exchange workflows | Constitution mutation, direct provider bypass, universal claims | Orders, positions, strategies, risk and user audit; domain DB + immutable event log | Domain APIs; requests PAEOS tasks/actions and reads SAKG claims; no direct worker/provider authority | External side effects require PAEOS admission; market data is time-scoped evidence | Rename Sentium-specific CLI adapter; keep generic runtime in PAEOS |
| `cli_orchestrator` | Application adapter / transitional subsystem | Compatibility commands and Sentium-facing operator surface | Duplicate generic orchestration, policy, ledger, or Court | Compatibility config only; PAEOS/Sentium stores remain authoritative | Translates CLI requests to PAEOS/Sentium APIs; no direct kernel bypass | Adapter output is untrusted request metadata | Absorb generic parts into PAEOS; rename Sentium residue and delete duplicate runtime |
| Workers, tools & provider adapters | Subsystem | Stateless computation, tool execution, model calls, return of observations | Owning state, retries outside policy, self-promotion, direct external side effects | No authoritative state; ephemeral process plus returned CAS evidence | Invoked by PAEOS capability API; return typed results only; never call SAKG promotion directly | Builder/auditor family separation; outputs require reproducible command and hash | Deduplicate adapters; keep one policy-controlled transport layer |
| Founder / Court boundary | Application/governance boundary | Constitutional intent, remand/seal decisions, exceptions and roadmap authorization | Silent runtime mutation or unrecorded promotion | Signed dispositions and governance records; repository docs + CAS evidence | Receives reports and proposals; authorizes PAEOS state transitions | Highest human trust, still requires non-vacuous evidence and preserved remands | Keep dispositions append-only; no informal override channel |

## API and ownership contract

The minimum stable interfaces are:

- PAEOS `Intake`, `Task`, `Evidence`, `CourtSeal`, `Replay`, and `PromotionGate` APIs.
- SAKG `Claim`, `ClaimScope`, `EvidenceGrade`, `TransferAssessment`, `Contradiction`, and
  `Validate/Promote/Retract` APIs.
- Concept OS `Concept`, `Relation`, `Transformation`, `Hypothesis`, `Explore`, and
  `CandidateExport` APIs.
- Sentium `MarketObservation`, `Strategy`, `RiskCheck`, `OrderIntent`, and `ExecutionReceipt`
  APIs, with order intent routed through PAEOS.
- Orca-strator `CouncilSession` and `Proposal` APIs, which terminate at PAEOS intake.
- KAE/Corpus `IngestManifest`, `SourceRef`, and `ExtractionRecord` APIs, which provide citations
  to SAKG and never claims directly.

Dependency direction is therefore `Corpus → KAE → SAKG → Concept OS → PAEOS evidence loop`, with
`Orca-strator → PAEOS` and `Sentium → PAEOS` for governed actions. Read references may point back
to evidence, but authority edges must not point from an application or discovery subsystem into a
sovereign’s decision store.

## Physical consolidation roadmap

1. **Freeze:** publish this map and add dependency-direction checks to every repository.
2. **Inventory:** enumerate state stores, APIs, duplicated workers, claim graphs, and corpus hashes;
   create adapters without changing authority.
3. **Consolidate:** absorb generic `cli_orchestrator` machinery into PAEOS; move Library of Fire
   acquisition into KAE while preserving immutable corpus hashes; make Concept Graph and
   Inspiration Engine internal to Concept OS.
4. **Migrate:** replay and compare state, evidence, and provenance; require Founder/Court seal for
   each physical move. No directory move is evidence of a successful migration.
5. **Deprecate:** mark old endpoints read-only, publish removal dates, and delete only after
   consumer inventory, replay proof, and a sealed disposition.

## Constitutional invariants

1. PAEOS owns canonical execution/governance state; models and providers are stateless.
2. Sovereigns communicate through typed, content-addressed APIs and evidence, not shared mutable
   internals.
3. Conceptual novelty is not engineering truth; corpus presence is not validation.
4. Claims widen only through graduated scope and explicit transfer confidence; two domains never
   imply a universal law.
5. Builder and auditor families differ for every physical audit (A-08).
6. Missing, unverified, or contradictory evidence fails closed; remands remain visible and are
   not optimized away.
7. No application, UI, worker, or provider may bypass PAEOS admission or mutate another
   sovereign’s authoritative state.
8. Every physical consolidation is reversible until independently evidenced and Court-sealed.
