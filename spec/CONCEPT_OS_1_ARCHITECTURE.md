# CEO-1 — Concept OS Canonical Architecture Specification

- **Document identifier:** CEO-1
- **Title:** Concept Graph, Inspiration Engine, Search Orchestra, and Ecosystem Boundary
- **Status:** Mission 0 candidate specification; requires implementation evidence and Court disposition
- **Version:** 1.0.0
- **Effective:** 2026-09-04
- **Governing authority:** `ECOSYSTEM_CONSTITUTION_AND_BOUNDARY_MAP.md`
- **Research basis:** `reviews/tasks/CONCEPT_OS_MISSION_0_CENSUS_REPORT.md`

---

## 1. Normative scope

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**, and **MAY** are
normative. CEO-1 specifies the first implementable architecture of Concept OS. It freezes the
authority boundary, durable data model, deterministic identity contract, initial discovery/search
interfaces, and integration surfaces. It does not claim that any discovery heuristic is
scientifically valid or useful before empirical qualification.

### 1.1 System identity

Concept OS is the sovereign system for concepts, conceptual relations, transformations,
analogies, semantic neighborhoods, possibility-space exploration, and candidate-hypothesis
lifecycle. Its principal durable substrate is the **Concept Graph**. The **Inspiration Engine** is
a first-class subsystem inside Concept OS. This is the mission-cited constitutional §4.3/§4.4
boundary. The **Search Orchestra** coordinates multiple bounded conceptual-search strategies over
the graph.

Concept OS owns exploratory state. It does not own engineering truth, governed execution,
provider selection, evidence admission, or trading action.

### 1.2 Goals

CEO-1 MUST provide:

1. an immutable, provenance-bearing graph of the six required node types and six edge families;
2. deterministic, content-derived `concept://` identities;
3. pure SQLite persistence with WAL and append-only domain records;
4. replayable traversal, neighborhood construction, analogy, recombination, and search;
5. explainable relevance, distance, novelty, coherence, and serendipity components;
6. explicit candidate and failure histories;
7. a read-only MCP query surface; and
8. a candidate-only export bridge into the PAEOS/SAKG epistemic loop.

### 1.3 Non-goals

CEO-1 MUST NOT:

- ratify, promote, retract, or widen an engineering claim;
- invoke remote models or choose providers directly;
- run arbitrary code stored in a graph node;
- mutate a PAEOS ledger, SAKG claim store, or Sentium domain store;
- execute trades or other external side effects;
- provide autonomous living-concept agents;
- require a vector database, graph database, ORM, or background daemon;
- treat novelty, frequency, embedding similarity, or compression as proof; or
- silently delete, rewrite, decay, merge, or split conceptual history.

---

## 2. First principles and invariants

### CEO-I1 — State independence

Canonical Concept OS state is local and durable. Models are stateless compute behind PAEOS and
cannot own graph state, search state, identifiers, history, or candidate disposition.

### CEO-I2 — Append-only semantics

Every domain record is immutable. A correction, lifecycle change, merge, split, or conceptual
rewrite creates a new node or edge with explicit lineage. `UPDATE` and `DELETE` on domain tables
MUST fail at both the public API and SQLite trigger layers.

### CEO-I3 — Deterministic replay

A result MUST be reproducible from the graph snapshot digest, canonical query, algorithm and
heuristic versions, configured budgets, and random seeds. Tie-breaking MUST use URI byte order.
Wall-clock time MUST NOT determine semantic results.

### CEO-I4 — Proposal is not truth

All Concept OS outputs are exploratory. Local schema and constraint checks establish only
well-formedness. No score or successful search changes a candidate into validated knowledge.

### CEO-I5 — Provenance before convenience

Every generated object MUST cite source node URIs, input snapshot, generator/operator version,
parameters, and trace. Embeddings and model-produced annotations MUST include content hashes and
producer versions. Missing provenance fails closed for export.

### CEO-I6 — Explicit absence

Missing representations, unavailable distance components, exhausted budgets, truncated result
sets, rejected mappings, and failed candidates MUST be represented explicitly. Implementations
MUST NOT substitute zero, success, or an empty explanation for missing information.

### CEO-I7 — Structural non-authority

The MCP surface is read-only by construction. The SAKG bridge emits candidate envelopes only.
No Concept OS package may import a SAKG mutator, a PAEOS provider adapter, or a Sentium execution
adapter.

### CEO-I8 — Bounded exploration

Every traversal and search MUST accept hard limits for expansions, returned nodes, hop depth, and
serialized bytes. A token budget MAY be added only when the request also pins the tokenizer name
and version. Exceeding a budget uses whole-result drop-and-count; partial records are forbidden.

---

## 3. Logical architecture

```text
                  read-only validated mechanisms / constraints
             SAKG ----------------------------------------------+
                                                               |
                                                               v
Caller -> Query Compiler -> Search Orchestra -> Candidate Pool / Ranker
              |                    |                    |
              |                    |                    v
              |                    +----------> Inspiration Engine
              |                                      |
              v                                      v
       Constraint Set                         candidate hypotheses
              |                                      |
              +------------------+-------------------+
                                 v
                     Concept Graph / SQLite WAL
                                 |
                    +------------+-------------+
                    |                          |
                    v                          v
              read-only MCP            candidate outbox
                                               |
                                               v
                                  PAEOS admission / experiment
                                               |
                                               v
                                      SAKG disposition
```

The arrows indicate typed data flow, not authority transfer. Search and inspiration may append
new exploratory records through the internal write API. MCP readers cannot. Candidate export
does not authorize an experiment or claim promotion.

### 3.1 Package boundaries

The initial implementation SHOULD use the following modules:

| Module | Single responsibility |
|---|---|
| `concept/ids.py` | Canonical JSON normalization, hashes, Crockford Base32 encoding, URI validation. |
| `concept/model.py` | Typed immutable node/edge/query/export envelopes and schema validation. |
| `concept/schema/` | JSON Schemas for nodes, edges, queries, results, and candidate export envelopes. |
| `concept/store.py` | SQLite schema, append-only writes, snapshot reads, transactions, and outbox events. |
| `concept/traverse.py` | Typed, bounded graph traversal and path explanations. |
| `concept/inspiration.py` | Distance composition, analogy/recombination proposers, novelty and serendipity scoring. |
| `concept/search.py` | Query compilation, search-arm protocol, orchestration, budgets, merge, and ranking. |
| `concept/mcp_server.py` | Structurally read-only MCP adapter. |
| `concept/bridge.py` | Candidate-envelope construction and append-only outbox emission. |

Imports MUST point inward toward `ids`, schemas, and the store. `store.py` MUST NOT import search,
inspiration, MCP, PAEOS, SAKG, or Sentium packages.

---

## 4. Deterministic Crockford-32 identity contract

### 4.1 URI grammar

Node identifiers MUST have the form:

```text
concept://<namespace>/<node-kind>/<token>
```

Edge identifiers MUST have the form:

```text
concept://<namespace>/edge/<token>
```

Candidate outbox event identifiers MUST have the form:

```text
concept://<namespace>/outbox/<token>
```

`namespace` MUST match `[a-z0-9][a-z0-9_-]{0,62}`. `node-kind` MUST match
`[a-z0-9][a-z0-9-]{0,62}` and is the lowercase kebab-case form of the node type. `token` MUST match
`[0-7][0-9A-HJKMNP-TV-Z]{25}`: a fixed-width, uppercase, 26-character Crockford Base32 encoding
of 128 bits. The Crockford alphabet is `0123456789ABCDEFGHJKMNPQRSTVWXYZ`; `I`, `L`, `O`, and `U`
are forbidden.

### 4.2 Canonical preimage

The identity preimage for a node is the UTF-8 encoding of canonical JSON containing exactly:

```json
{
  "namespace": "<namespace>",
  "type": "<NodeType>",
  "schema_version": 1,
  "payload": {},
  "representations": [],
  "provenance_refs": []
}
```

The identity preimage uses the same `type` field name as the public node envelope; implementations
MUST NOT rename it to `node_type` before hashing. The edge preimage contains `namespace`,
`family`, `relation`, `source_uri`, `target_uri`,
`schema_version`, `payload`, and `provenance_refs`. An outbox-event preimage contains
`namespace`, `hypothesis_uri`, `event_type`, `schema_version`, and the candidate envelope or
delivery-observation payload. Object keys MUST be lexicographically sorted; strings MUST be
Unicode NFC; arrays preserve semantic order; sets MUST be sorted before serialization;
insignificant whitespace is forbidden; and NaN, infinities, platform-dependent floats, and
implicit datetime serialization are forbidden. Computed scores MUST be fixed-scale decimal
strings.

`recorded_at` and the identifier itself are storage metadata and MUST NOT enter the preimage.
When time is semantically relevant, an explicit normalized UTC field belongs in `payload` and
therefore affects identity.

The `canonical_json` database column stores the exact identity preimage bytes; `recorded_at` and
the URI remain separate columns. Readers reconstruct the complete envelope without changing the
preimage used for identity.

### 4.3 Hash and encoding algorithm

1. Canonicalize the preimage as specified above.
2. Compute SHA-256 over the canonical UTF-8 bytes.
3. Take the first 16 digest bytes as an unsigned 128-bit integer.
4. Encode that integer as exactly 26 Crockford Base32 characters, left-padding with `0`.
5. Prefix with the normalized namespace and kind URI path.

The same preimage MUST yield the same URI across processes, hosts, and insertion order. The full
SHA-256 digest MUST also be stored as `content_hash`. On insertion:

- an absent URI appends normally;
- an existing URI with identical canonical bytes and full hash is an idempotent success; and
- an existing URI with different bytes or hash MUST raise `IdentityCollisionError` and append
  nothing.

No random, clock, process, database-row, or provider value may enter identity generation unless
it is explicit semantic input.

---

## 5. Ontology

### 5.1 Universal node envelope

Every node MUST provide:

| Field | Contract |
|---|---|
| `id` | Deterministic `concept://` URI derived under section 4. |
| `type` | One of the six closed CEO-1 node types. |
| `namespace` | Ownership/disclosure partition; encoded in the URI. |
| `schema_version` | Positive integer; `1` for CEO-1. |
| `payload` | Type-specific immutable semantic content. |
| `representations` | Ordered array of typed representation descriptors. |
| `provenance_refs` | Sorted, non-empty URI/hash references for imported or generated content. |
| `recorded_at` | UTC RFC 3339 storage time, excluded from identity. |

A generated node MUST additionally identify `generator_id`, `generator_version`,
`graph_snapshot_hash`, input URIs, normalized parameters, and seed where applicable.

### 5.2 Representation descriptors

Representations are immutable facets of a node, not independent truth-bearing nodes. CEO-1
defines these initial kinds:

- `symbolic`: label, language, definition, aliases, and optional formal expression;
- `structural`: a declared graph-signature version used by structural metrics;
- `exemplar_refs`: ordered `concept://` or content-addressed examples;
- `vector_ref`: model/version, dimensions, vector content hash, and external or local index
  revision; raw vector data MAY be stored separately;
- `probabilistic_ref`: distribution family/version and content hash, with no claim of calibration;
- `procedural_affordance`: references to applicable `Transformation` URIs; and
- `source_ref`: immutable external provenance or SAKG URI plus content hash.

Algorithms MUST declare which kinds they consume. When a required kind is missing, the algorithm
MUST either decline the candidate or return an explicit missing-component marker and renormalized
weights.

### 5.3 Node types

#### `Concept`

The minimal semantic unit. Required payload fields are `label`, `description`, and `domain_tags`.
Optional fields include aliases, formal expressions, declared constraints, and scope notes. A
Concept is neither an agent nor code and carries no truth-authoritative confidence.

#### `Analogy`

A reified, non-transitive mapping. Required payload fields are `source_roles`, `target_roles`,
`correspondences`, `preserved_relations`, `known_breaks`, `metric_snapshot`, and
`heuristic_uri`. Each correspondence identifies role names and participant Concept URIs. An
Analogy MUST have at least one known-break entry or the explicit marker `not_yet_tested`; absence
of limits makes it ineligible for export.

#### `Transformation`

A versioned conceptual operator and its application contract. Required payload fields are:
`operator_name`, `operator_version`, `input_signature`, `output_signature`, `preconditions`,
`postconditions`, `parameters_schema`, `determinism`, and `implementation_ref`. `determinism` is
one of `declarative`, `pure`, `seeded`, or `external`. `implementation_ref` MAY be null only for a
`declarative` operator, in which case the Transformation describes a possible move but is not
locally executable. The database stores the contract, not executable code. `external` operators
can only be run through PAEOS.

#### `SemanticNeighborhood`

An immutable materialized search snapshot. Required payload fields are `anchor_uris`,
`metric_versions`, `weights`, `filters`, `budget`, `members`, `omitted`, `truncated`,
`graph_snapshot_hash`, and `query_hash`. Each member carries component distances and a `why`
path. A neighborhood is reproducible historical exploration state, not a mutable cache.

#### `InspirationHeuristic`

A versioned proposer or scorer definition. Required payload fields are `name`, `version`,
`kind`, `parameters_schema`, `required_representations`, `score_components`, `cost_class`, and
`falsifier`. Initial `kind` values are `analogy`, `recombination`, `gap`, `novelty`,
`serendipity`, and `compression`. Heuristic success rates are observations, never promotion
authority.

#### `Hypothesis`

A candidate proposition for external evaluation. Required payload fields are `proposition`,
`scope`, `assumptions`, `lineage`, `expected_observations`, `falsifiers`, `lifecycle`, and
`score_snapshot`. `lifecycle` is one of `draft`, `candidate`, `exported`, `dismissed`, or
`superseded`. Truth-bearing values such as `validated`, `proven`, or `canonical` are schema
errors. A lifecycle change creates a new Hypothesis node that supersedes the prior node.

### 5.4 Operators versus concepts

CEO-1 resolves the archive's executable/living concept ambiguity by making behavior explicit:

- a `Concept` describes *what a semantic unit is*;
- a `Transformation` describes *a permitted conceptual operation*;
- a Search Orchestra arm decides *when to propose or apply an operation*; and
- PAEOS decides whether any external or model-backed execution is admitted.

This separation permits procedural reasoning without hidden autonomous state or arbitrary code in
the graph.

---

## 6. Edge model

Every edge is an immutable first-class record with `id`, `namespace`, `family`, `relation`,
`source_uri`, `target_uri`, `schema_version`, `payload`, `provenance_refs`, and `recorded_at`.
Direction is semantic and MUST NOT be reversed by a query unless the query explicitly requests an
incoming traversal.

| Family | Direction and allowed use | Required properties | Invariants |
|---|---|---|---|
| `derivation` | Input or prior version -> derived node. Relations: `derived_from`, `supersedes`, `specializes_from`. | operator/trace URI and input order when relevant. | `supersedes` and single-output derivation lineage MUST be acyclic. |
| `analogy` | Analogy node -> source/target Concept, or Analogy -> mapped Analogy refinement. Relations: `has_source`, `has_target`, `refines`. | role name and correspondence index. | Never inferred transitively. Direct Concept-to-Concept analogy edges are forbidden. |
| `recombination` | Source Concept/Transformation -> combined Concept/Hypothesis. Relations: `contributes_to`, `combined_as`. | ordered contribution role and heuristic trace. | At least two distinct source URIs per recombination result. |
| `abstraction` | Specific Concept/Hypothesis -> more abstract Concept/Hypothesis. Relations: `abstracts_to`, `generalizes_to`. | abstraction operator and preserved/lost features. | Direction always specific to general; no automatic truth inheritance. |
| `exemplification` | Example Concept/Hypothesis -> general Concept. Relations: `exemplifies`, `counterexample_to`. | scope and source provenance. | Counterexamples are retained; examples do not prove universality. |
| `neighborhood` | SemanticNeighborhood -> member node. Relation: `contains`. | rank, component distances, aggregate distance, and `why`. | Membership is snapshot-specific and non-transitive. |

An edge family is a traversal semantic, not an evidence grade. Edge count, density, or recurrence
MUST NOT alter Hypothesis lifecycle or SAKG status.

### 6.1 N-ary relations

CEO-1 does not require a native hypergraph. N-ary structures are represented by a reified node and
ordinary edges: an Analogy owns many source/target mappings; a Transformation owns ordered inputs
and outputs through derivation edges; a Hypothesis owns many recombination sources; and a
SemanticNeighborhood owns many ranked members. This representation MUST preserve participant
roles and order.

---

## 7. Storage engine (`concept/store.py`)

### 7.1 Technology boundary

The storage engine MUST use Python's standard-library `sqlite3` module directly. An ORM, external
graph database, mutable document store, or required vector database is outside CEO-1. The database
file path MUST be caller-configurable and MUST NOT default to a repository-tracked file.

Every writable connection MUST configure and verify:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

Read-only connections MUST use SQLite URI `mode=ro`, enable `PRAGMA query_only = ON`, and never be
upgraded to writers.

### 7.2 Minimum physical schema

The initial migration MUST create tables equivalent to:

```sql
CREATE TABLE concept_nodes (
    uri TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK (node_type IN (
        'Concept', 'Analogy', 'Transformation', 'SemanticNeighborhood',
        'InspirationHeuristic', 'Hypothesis'
    )),
    schema_version INTEGER NOT NULL CHECK (schema_version > 0),
    canonical_json BLOB NOT NULL,
    content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE concept_edges (
    uri TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    family TEXT NOT NULL CHECK (family IN (
        'derivation', 'analogy', 'recombination',
        'abstraction', 'exemplification', 'neighborhood'
    )),
    relation TEXT NOT NULL,
    source_uri TEXT NOT NULL REFERENCES concept_nodes(uri),
    target_uri TEXT NOT NULL REFERENCES concept_nodes(uri),
    schema_version INTEGER NOT NULL CHECK (schema_version > 0),
    canonical_json BLOB NOT NULL,
    content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
    recorded_at TEXT NOT NULL,
    CHECK (source_uri <> target_uri)
) STRICT;

CREATE TABLE candidate_outbox_events (
    uri TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    hypothesis_uri TEXT NOT NULL REFERENCES concept_nodes(uri),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'EMITTED', 'DELIVERY_OBSERVED', 'REJECTED', 'SUPERSEDED'
    )),
    schema_version INTEGER NOT NULL CHECK (schema_version > 0),
    canonical_json BLOB NOT NULL,
    content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
    recorded_at TEXT NOT NULL
) STRICT;

CREATE INDEX concept_nodes_type_idx
    ON concept_nodes(namespace, node_type, uri);
CREATE INDEX concept_edges_out_idx
    ON concept_edges(namespace, source_uri, family, relation, target_uri);
CREATE INDEX concept_edges_in_idx
    ON concept_edges(namespace, target_uri, family, relation, source_uri);
CREATE INDEX candidate_outbox_hypothesis_idx
    ON candidate_outbox_events(namespace, hypothesis_uri, recorded_at, uri);
```

Implementations MAY add append-only migration and representation-index tables. Additional tables
MUST NOT weaken domain immutability or introduce an authoritative truth/confidence column.

### 7.3 Append-only enforcement

`concept_nodes`, `concept_edges`, and `candidate_outbox_events` MUST each have `BEFORE UPDATE` and
`BEFORE DELETE` triggers that execute `RAISE(ABORT, 'append-only table')`. The public store API
MUST expose only append and read operations. Raw connection access MUST remain private.

`candidate_outbox_events` MUST additionally have a `BEFORE INSERT` trigger that rejects the row
unless `hypothesis_uri` resolves to a `concept_nodes` row with `node_type = 'Hypothesis'` and the
same `namespace`. The public API MUST perform the same check before entering its write
transaction. Foreign-key existence alone is insufficient.

Lifecycle observations use appended outbox events. Concept and Hypothesis revisions use new nodes
plus `derivation/supersedes` edges. Schema evolution may add tables, columns, indexes, or views via
append-only migration records; it MUST NOT rewrite historical canonical bytes.

### 7.4 Write protocol

Writers MUST:

1. validate and canonicalize outside the transaction;
2. derive and validate the URI and full hash;
3. enter `BEGIN IMMEDIATE`;
4. verify all referenced internal endpoint URIs exist;
5. append the row or perform the byte-for-byte idempotence check;
6. check family-specific constraints and prohibited cycles;
7. commit atomically; and
8. roll back the entire transaction on any error.

There is one logical writer transaction at a time. Concurrent readers use WAL snapshots. Batch
insertion order MUST be canonical URI order so equivalent batches produce equivalent snapshots.

### 7.5 Snapshot digest

The graph snapshot digest MUST be SHA-256 over a versioned domain separator followed by the
ordered sequence of node `(uri, content_hash)` pairs and edge `(uri, content_hash)` pairs, each
ordered by URI bytes. Outbox delivery events are excluded from the graph digest. The digest is a
replay handle, not proof that the graph is true.

### 7.6 Store interface

The minimum Python interface is:

```python
class ConceptStore:
    def append_node(self, node: NodeEnvelope) -> str: ...
    def append_edge(self, edge: EdgeEnvelope) -> str: ...
    def append_nodes_and_edges(
        self, nodes: Sequence[NodeEnvelope], edges: Sequence[EdgeEnvelope]
    ) -> AppendReceipt: ...
    def get_node(self, uri: str) -> NodeEnvelope | None: ...
    def iter_nodes(self, query: NodeQuery) -> Iterator[NodeEnvelope]: ...
    def iter_edges(self, query: EdgeQuery) -> Iterator[EdgeEnvelope]: ...
    def snapshot_hash(self, namespace: str) -> str: ...
    def append_outbox_event(self, event: CandidateOutboxEvent) -> str: ...
```

Returned iterators MUST have explicit stable ordering. No method named `update`, `delete`,
`promote`, `validate`, or `execute` may exist on `ConceptStore`.

---

## 8. Traversal and semantic neighborhoods

`concept/traverse.py` MUST expose typed incoming/outgoing traversal with allow-listed families and
relations. Traversal requests include namespace, roots, direction, family/relation filters,
maximum hops, maximum expansions, maximum results, and disclosure filters.

Every returned path MUST contain:

- the ordered node URI sequence;
- the ordered edge URI sequence;
- direction and relation at every hop;
- the graph snapshot hash;
- the exact budget consumed; and
- an explicit reason the path matched.

Traversal MUST reject negative budgets, unknown families, cross-namespace access without an
explicit read policy, and attempts to infer analogy or neighborhood transitively.

A `SemanticNeighborhood` materializes a traversal/ranking result when preservation is requested.
Ephemeral reads do not have to append a node. A materialized neighborhood MUST capture all inputs
needed for replay and use whole-member drop-and-count when serialized output reaches its budget.

---

## 9. Inspiration Engine

### 9.1 Responsibility

The Inspiration Engine proposes analogies, recombinations, missing relationships, abstractions,
and hypotheses. It MAY append its proposals and traces to the Concept Graph. It MUST NOT label
them true, promote them in SAKG, invoke a provider, or execute an external action.

### 9.2 Distance metrics

CEO-1 defines three base distances, each normalized to `[0, 1]`:

- **graph distance** `d_g = 1 - exp(-h / tau)`, where `h` is the shortest permitted typed-path
  hop count and `tau > 0` is versioned configuration;
- **vector distance** `d_v = clamp((1 - cosine_similarity) / 2, 0, 1)` for compatible vector
  representations; and
- **structural distance** `d_s = 1 - J(A, B)`, where `J` is weighted Jaccard similarity over
  versioned typed-neighbor signatures.

Aggregate distance is the weighted arithmetic mean over **available** components. Missing
components are returned in `missing_components`; remaining weights are renormalized. If no
component is available, distance is `unscorable`, never `0` or `1`. All reported values are
quantized to six decimal places with a declared rounding rule.

An unreachable graph pair has `d_g = 1` plus `graph_unreachable = true`. Cosine distance over a
zero vector and structural Jaccard over two empty signatures are unavailable components, not
perfect matches.

### 9.3 Analogy proposal

An analogy proposer MUST:

1. select source and target structures under a deterministic seed and budget;
2. produce explicit role correspondences;
3. state preserved relations and known or untested breaks;
4. record component distances and structural constraints;
5. emit an `Analogy` node plus `analogy` family membership edges; and
6. refrain from chaining an analogy as if it were transitive evidence.

### 9.4 Recombination

A recombination proposer selects at least two distinct source nodes, applies a versioned
Transformation or heuristic, and produces a Concept or Hypothesis with ordered contribution
roles. Selection SHOULD favor a configured intermediate distance band rather than only nearest or
maximally distant nodes. Incompatible hard constraints MUST produce a recorded rejection trace,
not a malformed candidate.

### 9.5 Novelty vector

Novelty is an exploratory vector, not a scalar truth value. CEO-1 records:

- `distance`: aggregate semantic separation from nearest comparable material;
- `structural_surprise`: rarity of the proposed typed relation pattern;
- `domain_span`: declared cross-domain breadth;
- `recombination_rarity`: inverse frequency of the ordered source/operator signature; and
- `duplication_penalty`: similarity to existing candidates and hypotheses.

A configured scalar projection MAY rank candidates:

```text
novelty = clamp(weighted_mean(available positive components)
                - duplication_weight * duplication_penalty, 0, 1)
```

The score response MUST include component values, missing mask, weights, heuristic version, corpus
snapshot, and nearest comparators. Frequency can influence rarity but can never change candidate
lifecycle or SAKG status.

### 9.6 Serendipity and coherence

CEO-1 defines serendipity as the conjunction of relevance and novelty, moderated by structural
coherence and provenance completeness:

```text
serendipity = sqrt(relevance * novelty) * coherence * provenance_completeness
```

Each factor is in `[0, 1]`; unavailable relevance or novelty makes serendipity `unscorable`.
`coherence` means declared local constraints were satisfied, not that the candidate is true.
`provenance_completeness` measures required trace fields, not source credibility.

### 9.7 Heuristic evolution

Heuristics are themselves immutable `InspirationHeuristic` nodes. A changed formula or parameter
set creates a new version and supersession edge. Observed external outcomes MAY later inform a new
heuristic proposal, but CEO-1 has no automatic weight mutation, forgetting, or wake/sleep rewrite.

---

## 10. Search Orchestra

### 10.1 Search request

A canonical search request MUST include:

- query text and/or anchor URIs;
- namespace and disclosure policy;
- desired output kinds;
- required and forbidden edge families/relations;
- constraints and representation requirements;
- algorithm allow-list with versions;
- per-arm and global expansion/result/hop/serialization budgets;
- deterministic seed; and
- ranking weights and score versions.

The query hash is SHA-256 over this canonical request. Query compilation may normalize syntax and
resolve aliases, but it MUST preserve the original text and emit an explicit compiled constraint
set.

### 10.2 Search-arm protocol

Each arm implements a pure protocol equivalent to:

```python
class SearchArm(Protocol):
    name: str
    version: str

    def search(
        self,
        request: CompiledSearchRequest,
        snapshot: GraphSnapshot,
        budget: SearchBudget,
        seed: int,
    ) -> SearchArmResult: ...
```

`SearchArmResult` contains whole candidates, path explanations, consumption counters, rejected
items with reasons, truncation state, and errors. An arm failure is isolated and visible; it does
not become an empty successful result.

### 10.3 Initial portfolio

CEO-1 MUST support a minimum of two independently behaving arms before integration and SHOULD
provide:

- bounded breadth/best-first typed graph traversal;
- A* when an admissible or explicitly heuristic cost is available;
- beam search;
- bidirectional path search; and
- seeded random walk for diversity.

Analogy, gap, and recombination proposers from the Inspiration Engine participate as candidate
generators. MCTS, evolutionary search, learned policies, neural rankers, and LLM proposers are
extension points, not CEO-1 completion requirements.

### 10.4 Orchestration pipeline

The deterministic pipeline is:

```text
compile query
  -> validate constraints and budgets
  -> allocate fixed per-arm budgets
  -> run allow-listed arms
  -> collect complete arm results and visible failures
  -> canonicalize and deduplicate by candidate URI
  -> calculate score vectors
  -> diversity-aware stable ranking
  -> whole-result budget enforcement
  -> optional SemanticNeighborhood materialization
  -> return result plus replay manifest
```

Arms MAY execute concurrently. Merge order MUST be `(arm_name, arm_version, candidate_uri)` and
final ties MUST break by candidate URI, so scheduling does not alter output. The initial allocator
is static configuration. A learned allocator requires a later specification and cannot rewrite
CEO-1 budgets.

### 10.5 Ranking

Ranking MUST retain separate `relevance`, `novelty`, `coherence`, `diversity_contribution`,
`cost`, and `provenance_completeness` components. A configured scalar projection MAY order the
pool, but the response MUST expose every component and weight. The field name `confidence` is
forbidden because ranking quality and epistemic confidence are not interchangeable.

### 10.6 Search trace

Every result MUST include `query_hash`, `graph_snapshot_hash`, algorithm/heuristic versions,
seeds, budgets requested and consumed, rejected count by reason, omitted count, truncation flag,
and a `why` path or generator trace for each candidate. This manifest is sufficient to replay the
search against the referenced snapshot.

---

## 11. Ecosystem interfaces

### 11.1 Read-only MCP query surface

`concept/mcp_server.py` exposes only:

| Tool | Result |
|---|---|
| `concept_get` | One immutable node/edge envelope by exact URI. |
| `concept_search` | Budgeted Search Orchestra result without persistence. |
| `concept_neighborhood` | Budgeted ephemeral neighborhood or an existing materialized snapshot. |
| `concept_path` | Bounded typed paths with `why`. |
| `concept_hypothesis_get` | Candidate, lineage, score snapshot, and export observations. |

The adapter MUST open a read-only `mode=ro` connection with `query_only=ON`. No handler may receive
a writer, outbox emitter, arbitrary SQL, filesystem path, module name, implementation reference,
or callable. Mutation-like tool names (`create`, `append`, `update`, `delete`, `promote`,
`validate`, `execute`, `export`) are forbidden on the MCP server.

Every response MUST carry:

```json
{
  "authority": "exploratory",
  "trust": "untrusted_candidate",
  "graph_snapshot_hash": "<sha256>",
  "query_hash": "<sha256-or-null>",
  "truncated": false,
  "omitted": 0,
  "results": []
}
```

Empty or unreachable stores return typed empty results or explicit availability errors; they do
not cause process termination or fabricated candidates.

### 11.2 SAKG input boundary

Concept OS MAY read SAKG's validated mechanisms, constraints, contradictions, and open questions
through a read-only typed query interface. Imported references MUST include the SAKG URI, SAKG
snapshot or corpus hash, claim scope, and disposition. Concept OS stores them as source references
inside exploratory records. It MUST NOT reinterpret or widen their validated scope.

### 11.3 SAKG candidate-hypothesis emission bridge

`concept/bridge.py` creates a deterministic `CandidateHypothesisEnvelope` containing:

- envelope ID and schema version;
- Hypothesis URI and exact proposition;
- declared scope, assumptions, expected observations, and falsifiers;
- source Concept, Analogy, Transformation, and SAKG reference URIs;
- complete search/generator replay manifest;
- heuristic score vectors explicitly labeled non-evidentiary;
- graph snapshot and content hashes; and
- requested evaluation kind, without prescribing provider or executor.

The bridge appends an `EMITTED` event to `candidate_outbox_events`. Transport is pull-based and
PAEOS-mediated:

1. PAEOS may admit, reject, or defer a bounded experiment.
2. Evidence is collected and content-addressed under PAEOS authority.
3. A SAKG adapter may ingest the hypothesis as `candidate` and bind later evidence.
4. SAKG alone validates, narrows, falsifies, promotes, or retracts the engineering claim.
5. Concept OS may append a delivery/disposition observation but cannot mirror it as its own truth
   state.

Direct database writes, shared mutable tables, inline evidence payloads, and SAKG promotion calls
are forbidden. The envelope is a proposal and MUST say so in its schema and serialized form.

### 11.4 Sentium boundary

A market-related Hypothesis remains conceptual. Concept OS cannot emit an `OrderIntent`, invoke a
broker, alter a risk limit, or translate novelty into a strategy action. Sentium may read an
exploratory candidate only through its own governed integration, and any external effect still
requires Sentium risk checks plus PAEOS admission.

### 11.5 Provider and model boundary

Local deterministic algorithms may run inside Concept OS. Embedding, LLM, GNN, or other remote
inference requests MUST be expressed as PAEOS tasks. PAEOS alone applies privacy, capability,
context, health, quota, retry, fallback, and economy-of-reasoning policy through the layered model
router. Returned annotations enter Concept OS as untrusted, provenance-bearing data.

---

## 12. Error and degradation contract

The public API MUST use typed errors including:

- `SchemaValidationError`;
- `InvalidConceptURI`;
- `IdentityCollisionError`;
- `AppendOnlyViolation`;
- `MissingEndpointError`;
- `CycleViolation`;
- `NamespaceDisclosureError`;
- `BudgetExceeded` for requests that cannot return even one whole required record;
- `UnscorableDistance`;
- `UnreplayableTraceError`; and
- `CandidateExportBoundaryError`.

Errors MUST carry the failed invariant and safe identifiers, never raw secrets or embedded source
content. Search-arm failures are returned in the trace and do not erase successful arms. Store
transaction failures append nothing. No exception may be swallowed and no fallback may silently
change an algorithm, provider, namespace, or score version.

---

## 13. Security, disclosure, and resource controls

1. Namespace filters are applied at the store query boundary, not after retrieval.
2. Cross-namespace traversal requires an explicit bilateral disclosure rule.
3. Query input is treated as data; no SQL, Python, module, or path interpolation is permitted.
4. Serialized output obeys hard whole-record budgets and reports exact omissions.
5. Implementation references in Transformation nodes are identifiers plus hashes, never
   auto-imported code paths.
6. Candidate exports contain references and hashes rather than inline secrets or raw evidence.
7. Read-only MCP processes SHOULD run with a filesystem capability restricted to the database and
   MUST use SQLite read-only mode.
8. Outbox delivery is at-least-once; deterministic envelope IDs make consumption idempotent.

---

## 14. Verification strategy and non-vacuous falsifiers

CEO-1 implementation is not complete merely because a database opens or a query returns a row.
The execution DAG MUST produce discriminating tests for these properties:

### 14.1 Identity

- golden canonical preimages produce exact expected URIs;
- insertion order, process, and locale do not change IDs;
- alias Crockford characters and malformed namespaces are rejected; and
- a forced truncated-ID collision with different full hashes fails closed.

### 14.2 Append-only persistence

- API and raw-SQL update/delete attempts fail;
- identical appends are idempotent;
- conflicting appends leave no partial rows;
- WAL is active and concurrent readers observe transaction snapshots; and
- graph snapshot hashes are stable across equivalent insertion orders.

### 14.3 Ontology and traversal

- all valid/invalid node and edge fixtures exercise every type/family;
- endpoint-type and family constraints reject malformed structures;
- derivation/supersession cycles fail;
- analogy and neighborhood relations are not treated transitively; and
- every traversal result has a complete `why` path within budget.

### 14.4 Inspiration and search

- absent embeddings remain explicit and cause correct weight renormalization;
- seeded proposers and concurrent/sequential execution return identical ordering;
- poisoned high-novelty candidates remain merely candidates;
- budget overflow never emits a partial record;
- one failing arm remains visible while other arms return results; and
- mutation probes that remove proposer diversity or provenance reduce the expected fixture result.

### 14.5 Ecosystem boundary

- MCP exposes exactly the allow-listed read tools and receives no writable connection;
- static import checks prove no PAEOS provider, SAKG mutator, or Sentium executor dependency;
- export envelopes reject truth-bearing statuses and incomplete falsifiers/provenance;
- repeated delivery is idempotent; and
- a fabricated or high-frequency candidate cannot call or simulate SAKG promotion.

Any test suite that passes after the relevant behavior is removed is vacuous and cannot support a
completion claim.

---

## 15. Architecture decisions

| ID | Decision | Rejected alternative | Reason |
|---|---|---|---|
| CEO-D1 | Concept Graph is the durable Concept OS substrate. | Disposable graph index over an executable library. | Required by the canonical ecosystem boundary; graph state remains explicitly exploratory. |
| CEO-D2 | Pure SQLite WAL store. | External graph/vector database or ORM. | Small, deterministic, transactional, inspectable, and sufficient to falsify the first architecture. |
| CEO-D3 | Content-derived Crockford Base32 URIs. | Random UUID/ULID or auto-increment IDs. | Reproducible identity and idempotent ingestion without clock/random authority. |
| CEO-D4 | Immutable nodes/edges and supersession. | Mutable living concepts or in-place graph rewriting. | Preserves provenance, replay, rejected paths, and failure history. |
| CEO-D5 | Behavior lives in Transformation contracts. | Arbitrary executable Concept nodes. | Separates semantics, operation, scheduling, and governed execution. |
| CEO-D6 | Reified n-ary objects over binary edges. | Native hypergraph in CEO-1. | Retains expressiveness with simple SQLite adjacency and explicit participant roles. |
| CEO-D7 | Plural deterministic Search Orchestra. | One universal algorithm or opaque learned policy. | Preserves proposer diversity while making resource use and replay testable. |
| CEO-D8 | Score vectors remain exploratory. | Single confidence/admission score. | Novelty, relevance, coherence, usefulness, and truth are not interchangeable. |
| CEO-D9 | Candidate-only PAEOS-mediated SAKG bridge. | Direct SAKG mutation/promotion. | Preserves the closed epistemic loop and sovereign authority boundaries. |
| CEO-D10 | MDL, wake/sleep, living concepts, and learned allocation are deferred experiments. | Installing comparative-review hypotheses as core law. | They are promising but unverified and unnecessary to test CEO-1's minimal substrate. |

---

## 16. Delivery slices and exit criteria

The normative implementation sequence is
`backlog/CONCEPT_OS_1_EXECUTION_DAG.yaml`.

- **Slice C1 — substrate:** deterministic identities, schemas, SQLite WAL store, append-only and
  replay properties.
- **Slice C2 — topology:** typed traversal and reproducible SemanticNeighborhood snapshots.
- **Slice C3 — discovery:** Inspiration Engine metrics, analogy/recombination proposers, and
  hypothesis traces.
- **Slice C4 — orchestration:** multi-arm Search Orchestra with deterministic budgets and merge.
- **Slice C5 — boundary:** read-only MCP surface and candidate-only ecosystem integration spike.

CEO-1 reaches implementation readiness only when Task 08's integration spike demonstrates a real
end-to-end path from graph seed through at least two search/proposer strategies to a replayable
Hypothesis, read-only MCP projection, and candidate envelope, while mechanical tests prove that no
truth promotion, provider invocation, or external action is reachable.

Reaching that milestone is evidence for Court review. It is not self-ratification.
