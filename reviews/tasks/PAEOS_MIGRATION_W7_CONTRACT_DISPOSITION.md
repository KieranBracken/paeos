# Sentium Ecosystem Migration — Wave 7 (W7) Formal Contract Disposition & Inspiration Capability Exposure

**Document Type:** Formal Wave 7 Court Disposition & Conformance Record  
**Migration Phase:** Wave 7 — `expose_full_inspiration_capability`  
**Authoritative Dependency DAG:** [`07_MIGRATION_DEPENDENCY_DAG.yaml`](file:///Users/bob/GitHub/paeos/reviews/architecture/founder_ecosystem_target_architecture_v0.1_migration_analysis/07_MIGRATION_DEPENDENCY_DAG.yaml)  
**Governing Target Architecture:** [`FOUNDER_ECOSYSTEM_TARGET_ARCHITECTURE_v0.2.md`](file:///Users/bob/GitHub/paeos/architecture/FOUNDER_ECOSYSTEM_TARGET_ARCHITECTURE_v0.2.md)  
**Predecessors:** Wave 5 (`COURT_SEALED`), Wave 6 (`COURT_SEALED`)  
**Exit Gate Status:** ALL 5 DAG EXIT GATES + ROLLBACK + CANARY SATISFIED  
**Date:** 2026-09-06 00:10 BST  

---

## 1. Executive Summary & Wave 7 Scope

Wave 7 formally exposes full Inspiration Engine (LOF) capability through the Idea Graph under Section 19/4 and Section 22 of the Target Architecture:
- **Idea Graph Role:** Exposes typed capability links (`ExperimentCandidate`, `HardenedFeedbackOutcome`, `CertificationReport`) without usurping execution or capital authority.
- **Physical Code Movement:** `false` (Zero code moved across repositories; adapter implemented in `contracts/idea_graph_inspiration_adapter.py`).
- **State Migration:** `none` (LOF native stores remain independent and immutable).
- **Rollback Boundary:** `disable_idea_graph_adapters` (Disabling the adapter halts Idea Graph capability routes without mutating underlying LOF or Idea OS data).

---

## 2. Exit Gate Certification & Invariants

All exit gates specified in `07_MIGRATION_DEPENDENCY_DAG.yaml` are formally satisfied and verified by unit tests in [`tests/contracts/test_idea_graph_inspiration_adapter.py`](file:///Users/bob/GitHub/paeos/tests/contracts/test_idea_graph_inspiration_adapter.py):

### Exit Gate 1: `novelty_contradiction_experiment_lineage_preserved` (CLAIM-W7-01 & CLAIM-W7-02)
- **Verification:** `tests/contracts/test_idea_graph_inspiration_adapter.py:test_experiment_lineage`, `test_contradiction_preservation`
- **Invariants:**
  - Experiment candidates are deterministically hashed via canonical RFC 8785 JSON bytes over `(idea_id, concept_ids, source_hashes, hypothesis, mechanism, test_design)`. Repeated candidate creation with identical inputs generates byte-identical SHA-256 package hashes and `EXP-{hash[:12]}` IDs.
  - Claims of live execution or capital authority in test designs fail closed immediately (`ForbiddenAuthorityError`).
  - Contradictions and falsified hypotheses are preserved permanently as `RejectedKnowledgeRecord` envelopes with explicit rejection categories (`CONTRADICTION_UNRESOLVED`, `DOCTRINE_POLLUTION_RISK`) to prevent cyclic re-proposal.

### Exit Gate 2: `signature_and_replay_fail_closed` (CLAIM-W7-03)
- **Verification:** `tests/contracts/test_idea_graph_inspiration_adapter.py:test_feedback_signature_replay`
- **Invariants:**
  - All feedback outcomes must include cryptographic signatures, registered signing keys, and unique nonces.
  - Replayed nonces fail closed with `FeedbackReplayError`.
  - Untrusted or unrecognized signing keys fail closed with `InvalidSignatureError`.
  - Missing or blank cryptographic signatures fail closed with `InvalidSignatureError`.

### Exit Gate 3: `mock_runner_cannot_certify` (CLAIM-W7-04)
- **Verification:** `tests/contracts/test_idea_graph_inspiration_adapter.py:test_mock_runner_cannot_certify`
- **Invariants:**
  - Mock runners and synthetic outcome stubs (`runner_type == "MOCK"` or `synthetic == True`) are strictly quarantined.
  - Attempting to certify a mock runner outcome for distillation or promotion raises `MockCertificationProhibitedError`. Only verified production shadow or live experiment outcomes can receive a `CertificationReport`.

### Exit Gate 4: `rights_aware_dataset_and_distillation_tests` (CLAIM-W7-05)
- **Verification:** `tests/contracts/test_idea_graph_inspiration_adapter.py:test_rights_aware_dataset`
- **Invariants:**
  - Distillation datasets constructed from certified outcomes strictly evaluate the associated `RightsPolicy`.
  - When `can_train_on_raw_text=False`, raw text is scrubbed (`raw_text=None`), a mandatory rights restriction notice is inserted, and only derived features/embeddings are retained.
  - When permitted (`can_train_on_raw_text=True`), full text is passed through cleanly.

### Exit Gate 5: `legacy_outcome_path_differential_parity` (CLAIM-W7-06)
- **Verification:** `tests/contracts/test_idea_graph_inspiration_adapter.py:test_legacy_outcome_path_differential`
- **Invariants:**
  - The legacy dictionary-based outcome ingestion path is retained for backward compatibility during migration.
  - Differential testing verifies that metrics processed through the hardened cryptographic path exactly match those emitted by the legacy path, while providing signature verification, anti-replay nonce tracking, and synthetic outcome gating.

### Rollback Boundary: `disable_idea_graph_adapters` (CLAIM-W7-07)
- **Verification:** `tests/contracts/test_idea_graph_inspiration_adapter.py:test_rollback_boundary`
- **Invariants:**
  - Calling `adapter.disable()` immediately halts all candidate creation, feedback ingestion, certification, and dataset generation with `AdapterDisabledError`.
  - Zero state mutation occurs in LOF historical records. Enabling restores normal operation cleanly.

---

## 3. Conformance Summary

| Exit Gate | Test Target | Result |
| :--- | :--- | :--- |
| **Gate 1** | `test_experiment_lineage`, `test_contradiction_preservation` | **PASS** (Deterministic RFC 8785 package hash, contradiction preservation) |
| **Gate 2** | `test_feedback_signature_replay` | **PASS** (Cryptographic signature validation, nonce replay rejection) |
| **Gate 3** | `test_mock_runner_cannot_certify` | **PASS** (Mock runner certification strictly prohibited) |
| **Gate 4** | `test_rights_aware_dataset` | **PASS** (Rights policy redaction of raw text in distillation datasets) |
| **Gate 5** | `test_legacy_outcome_path_differential` | **PASS** (Differential metrics parity between legacy and hardened paths) |
| **Rollback** | `test_rollback_boundary` | **PASS** (Disable adapter halts operations without side effects) |
| **Canary** | `CLAIM-W7-08-CANARY-DISCRIMINATION` | **PASS** (Court non-vacuity discrimination verified) |
