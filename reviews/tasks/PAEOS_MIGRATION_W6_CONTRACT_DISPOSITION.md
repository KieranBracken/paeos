# Sentium Ecosystem Migration — Wave 6 (W6) Formal Contract Disposition & KAE/LOF Federation

**Document Type:** Formal Wave 6 Court Disposition & Conformance Record  
**Migration Phase:** Wave 6 — `federate_kae_and_lof_acquisition_evidence`  
**Authoritative Dependency DAG:** [`07_MIGRATION_DEPENDENCY_DAG.yaml`](file:///Users/bob/GitHub/paeos/reviews/architecture/founder_ecosystem_target_architecture_v0.1_migration_analysis/07_MIGRATION_DEPENDENCY_DAG.yaml)  
**Governing Target Architecture:** [`FOUNDER_ECOSYSTEM_TARGET_ARCHITECTURE_v0.2.md`](file:///Users/bob/GitHub/paeos/architecture/FOUNDER_ECOSYSTEM_TARGET_ARCHITECTURE_v0.2.md)  
**Exit Gate Status:** ALL 5 EXIT GATES SATISFIED  
**Date:** 2026-09-06 00:05 BST  

---

## 1. Executive Summary & Wave 6 Scope

Wave 6 establishes the federation boundary between KAE (Knowledge Acquisition Engine) and LOF (Inspiration Engine / Laboratory of the Future) under Section 19/4 and Section 22 of the Target Architecture:
- **Logical Acquisition Ownership:** KAE is the canonical logical acquisition owner (`DomainOwner.KAE`).
- **Research Consumer Role:** LOF consumes normalized `ArtifactRef.v1` and `EvidenceRef.v1` envelopes while preserving full research domain metadata (dossiers, credibility, triage tier, venue, rejected knowledge).
- **Physical Code Movement:** `false` (Zero code moved across repositories; KAE adapter resides in `contracts/kae_lof_federation_adapter.py`).
- **State Migration:** `none` (Table splitting is strictly prohibited; existing LOF and KAE databases remain independent).
- **Rollback Boundary:** `disable_federation_adapters` (Disabling adapter restores independent native paths without reverse transforms or state corruption).

---

## 2. Exit Gate Certification & Invariants

All exit gates specified in `07_MIGRATION_DEPENDENCY_DAG.yaml` are formally satisfied and verified by automated unit tests:

### Exit Gate 1: `source_rights_and_hash_round_trip` (CLAIM-W6-01)
- **Verification:** [`tests/contracts/test_kae_lof_federation_adapter.py:test_source_rights`](file:///Users/bob/GitHub/paeos/tests/contracts/test_kae_lof_federation_adapter.py)
- **Invariant:** `RightsPolicy` (`can_train_on_raw_text`, `can_train_on_features`, `retention_days`, `is_public_domain`) round-trips losslessly through federation. If `can_train_on_raw_text=False`, citation spans are masked (`[REDACTED: RIGHTS_RESTRICTED]`) and raw content access fails closed with `PermissionError`, while cryptographic byte-anchors remain intact.

### Exit Gate 2: `content_hash_and_citation_parity` (CLAIM-W6-02)
- **Verification:** [`tests/contracts/test_kae_lof_federation_adapter.py:test_citation_parity`](file:///Users/bob/GitHub/paeos/tests/contracts/test_kae_lof_federation_adapter.py)
- **Invariant:** KAE CAS digest equals LOF `content_hash` and `source_hash` byte-for-byte. Byte-anchored citation spans match exact byte coordinates (`byte_start`, `byte_end`, `line_start`, `line_end`) and SHA-256 span digests.

### Exit Gate 3: `deduplication_and_isolation` (CLAIM-W6-03)
- **Verification:** [`tests/contracts/test_kae_lof_federation_adapter.py:test_dedup_and_isolation`](file:///Users/bob/GitHub/paeos/tests/contracts/test_kae_lof_federation_adapter.py)
- **Invariant:** Submitting duplicate content hashes or canonical URIs deduplicates cleanly, returning the canonical package without duplicate graph or CAS allocations. In batch federation, malformed records are isolated into quarantine without aborting valid items.

### Exit Gate 4: `revoked_source_handling` (CLAIM-W6-04)
- **Verification:** [`tests/contracts/test_kae_lof_federation_adapter.py:test_revoked_source`](file:///Users/bob/GitHub/paeos/tests/contracts/test_kae_lof_federation_adapter.py)
- **Invariant:** Revoked, quarantined, or retracted sources are marked `revoked=True`, assigned `TrustLabel.TAINTED`, have citations suppressed, and fail closed with `RevokedSourceAccessError` on raw content requests, while preserving audit tombstone records.

### Exit Gate 5: `historical_corpus_query_equivalence` (CLAIM-W6-05)
- **Verification:** [`tests/contracts/test_kae_lof_federation_adapter.py:test_query_equivalence`](file:///Users/bob/GitHub/paeos/tests/contracts/test_kae_lof_federation_adapter.py)
- **Invariant:** Querying the federated corpus by `source_type`, `min_credibility`, and `venue_type` yields query-equivalent results matching native LOF source records.

---

## 3. Conformance Summary

| Exit Gate | Test Target | Result |
| :--- | :--- | :--- |
| **Gate 1** | `test_source_rights` | **PASS** (Rights policy round trip, redaction, permission enforcement) |
| **Gate 2** | `test_citation_parity` | **PASS** (KAE CAS hash parity, byte-span coordinates exact) |
| **Gate 3** | `test_dedup_and_isolation` | **PASS** (Idempotent deduplication, isolated quarantine on failure) |
| **Gate 4** | `test_revoked_source` | **PASS** (Fail-closed on revoked source, TAINTED trust label, tombstone) |
| **Gate 5** | `test_query_equivalence` | **PASS** (Deterministic query equivalence across source filters) |
| **Rollback** | `test_rollback_boundary` | **PASS** (Adapter deactivation verified, zero state mutation) |
