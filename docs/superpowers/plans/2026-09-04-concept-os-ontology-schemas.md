# Concept OS Ontology Schemas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze CEO-1's six node types, six edge families, search contracts, and candidate-only export envelopes as immutable Python values and Draft 2020-12 JSON Schemas.

**Architecture:** `concept/model.py` owns dependency-light frozen dataclasses, closed literal unions, recursive immutable JSON values, construction-time invariants, and lossless serialization. Checked-in schemas under `concept/schema/` independently constrain serialized data with closed objects and discriminated branches; fixtures and tests exercise both representations as public contracts.

**Tech Stack:** Python 3.12+ dataclasses and typing, JSON Schema Draft 2020-12, pytest, jsonschema, Ruff, Pyright, PAEOS AST linter.

**Spec:** `spec/CONCEPT_OS_1_ARCHITECTURE.md` sections 5, 6, 10, and 11.3; `backlog/CONCEPT_OS_1_EXECUTION_DAG.yaml` task `TASK-02-ONTOLOGY-SCHEMAS`.

## Global Constraints

- Node types are exactly `Concept`, `Analogy`, `Transformation`, `SemanticNeighborhood`, `InspirationHeuristic`, and `Hypothesis`.
- Edge families are exactly `derivation`, `analogy`, `recombination`, `abstraction`, `exemplification`, and `neighborhood`.
- Analogy payloads require a known break or the exact marker `not_yet_tested`.
- Hypothesis lifecycle excludes truth-bearing states including `validated`, `proven`, and `canonical`.
- Ranking payloads never expose a field named `confidence`.
- Candidate exports identify exploratory proposals and label all score vectors non-evidentiary.
- Every envelope is immutable, provenance-bearing, namespace-consistent, and serializes without hidden mutable containers.

---

### Task 1: Contract Fixtures and Schema Tests

**Files:**
- Create: `tests/concept/fixtures/nodes/valid/*.json`
- Create: `tests/concept/fixtures/nodes/invalid/*.json`
- Create: `tests/concept/fixtures/edges/valid/*.json`
- Create: `tests/concept/fixtures/edges/invalid/*.json`
- Create: `tests/concept/test_node_schemas.py`
- Create: `tests/concept/test_edge_schemas.py`
- Create: `tests/concept/test_search_schema.py`
- Create: `tests/concept/test_candidate_envelope_schema.py`
- Create: `tests/concept/test_node_schema_closed_coverage.py`
- Create: `tests/concept/test_edge_schema_closed_coverage.py`

**Interfaces:**
- Consumes: CEO-1 serialized field names and URI grammar from `concept.ids`.
- Produces: discriminating examples and assertions for every allowed branch and required falsifier.

- [ ] Create one complete valid fixture per node type and per edge family plus invalid fixtures for closed sets, missing fields/provenance, analogy limits, lifecycle truth terms, self-loops, and relation mismatches.
- [ ] Write schema tests that call `Draft202012Validator.check_schema`, validate every valid fixture, reject every invalid fixture, and directly probe search/candidate invariants.
- [ ] Run the six schema suites and verify RED because the four schema files do not exist.

### Task 2: Frozen Python Model Tests

**Files:**
- Create: `tests/concept/test_model.py`

**Interfaces:**
- Consumes: the requested public names from `concept.model`.
- Produces: constructor, immutability, validation, serialization, and round-trip expectations for later store/search consumers.

- [ ] Write tests importing all envelopes, payloads, representation descriptors, validation helpers, and closed-set constants.
- [ ] Assert type/payload agreement, family/relation agreement, URI namespace agreement, recursive immutability, round trips, candidate-only semantics, and forbidden fields/statuses.
- [ ] Run `tests/concept/test_model.py` and verify RED because `concept.model` does not exist.

### Task 3: Draft 2020-12 Schemas

**Files:**
- Create: `concept/schema/node.schema.json`
- Create: `concept/schema/edge.schema.json`
- Create: `concept/schema/search.schema.json`
- Create: `concept/schema/candidate_hypothesis.schema.json`

**Interfaces:**
- Consumes: test fixture contracts from Tasks 1–2.
- Produces: standalone Draft 2020-12 validators with local `$defs`, closed objects, URI/hash/time patterns, discriminated payload branches, and forbidden epistemic fields.

- [ ] Implement the node schema and run node schema/coverage tests to GREEN.
- [ ] Implement the edge schema and run edge schema/coverage tests to GREEN.
- [ ] Implement search and candidate schemas and run their suites to GREEN.
- [ ] Validate all four schema documents with `Draft202012Validator.check_schema`.

### Task 4: Frozen Python Values and Validators

**Files:**
- Create: `concept/model.py`
- Modify: `concept/__init__.py`

**Interfaces:**
- Consumes: `validate_concept_uri` from `concept.ids` and JSON-compatible mappings.
- Produces: `NodeEnvelope`, `EdgeEnvelope`, `SearchRequest`, `SearchResult`, `CandidateHypothesisEnvelope`, `CandidateOutboxEvent`, six node payload classes, six edge payload classes, seven representation descriptors, `from_dict`, `to_dict`, and validation helpers.

- [ ] Implement recursive freeze/thaw helpers and strict primitive/URI/hash/RFC3339 validators.
- [ ] Implement representation descriptors and six node payload dataclasses with closed dispatch.
- [ ] Implement six edge payload dataclasses and family/relation dispatch, including self-loop rejection.
- [ ] Implement search result/request and candidate/outbox envelopes with non-evidentiary/truth-authority guards.
- [ ] Export the public model API and run `test_model.py` plus all schema suites to GREEN.

### Task 5: Acceptance and Non-Vacuity Verification

**Files:**
- Verify: `concept/model.py`, `concept/schema/*.json`, `tests/concept/**`

**Interfaces:**
- Consumes: all Task 02 deliverables.
- Produces: reproducible acceptance evidence for Court review.

- [ ] Run every pytest command listed in the task specification separately.
- [ ] Verify valid node/edge fixture counts are each at least six.
- [ ] Run Ruff over `concept/model.py` and `tests/concept/`.
- [ ] Run Pyright over `concept/model.py`.
- [ ] Run `runtime.ast_linter.check_ast` over every Concept OS source/test Python file.
- [ ] Run the complete `tests/concept/` suite and inspect `git diff --check` and status.
