# PAEOS Migration Wave 6 (W6) — Federate KAE and LOF Acquisition/Evidence
## FOUNDER / COURT DISPOSITION

**Disposition:** **COURT_SEALED**  
**Sealed Date:** 2026-09-05  
**Milestone:** Migration Wave 6 (W6) of Migration DAG (`07_MIGRATION_DEPENDENCY_DAG.yaml`)  
**Court Run Identifier:** `court-run-w6-20260905-230557`  
**Adjudication Mechanism:** Canonical PAEOS Verification Court (`runtime.court.Court`)  
**Evidence Bundle Path:** `/Users/bob/GitHub/paeos/reviews/tasks/PAEOS_MIGRATION_W6_EVIDENCE_BUNDLE.json`  
**Evidence Bundle SHA-256:** `c1a978be8743abd4c96c1f8508dcd29dabf3033e50fb1b1314aec2525b967173`  
**Contract Disposition Document:** `/Users/bob/GitHub/paeos/reviews/tasks/PAEOS_MIGRATION_W6_CONTRACT_DISPOSITION.md`  
**Contract Disposition SHA-256:** `84ee2d7e2204834610424243f44ad264de03057ac774d67581042180950ecc2d`  
**Predecessors:** Wave 2 (`COURT_SEALED`), Wave 5 (`COURT_SEALED`)  
**Next Permitted Intake:** Migration Wave 7 (W7) — `expose_full_inspiration_capability`  

---

## 1. Procedural Adjudication & Invariant Verification

1. **Deterministic Court Adjudication:** Executed through `runtime.court.Court()` under `Role.VERIFIER` with reproducible command assertions in `kernel.sandbox.sandbox_runner()`.
2. **Adjudication Outcome:** `VerdictOutcome.PASS` (all 7 claims reproduced, 0 unmet claims).
3. **CANARY-0002 Discrimination:** Proven. The Court verifier actively discriminates against malformed payloads and invalid hashes.

---

## 2. Gate Verification Audit

| Claim ID | Exit Gate Name | Finding | Court Verdict |
| :--- | :--- | :--- | :--- |
| `CLAIM-W6-01-SOURCE-RIGHTS-ROUND-TRIP` | `source_rights_and_hash_round_trip` | RightsPolicy losslessly round-trips; citation text masked on restricted rights; raw access fails closed. | **PASS** |
| `CLAIM-W6-02-CONTENT-HASH-CITATION-PARITY` | `content_hash_and_citation_parity` | KAE CAS digest equals LOF source hash; byte-span coordinates and span hashes match exactly. | **PASS** |
| `CLAIM-W6-03-DEDUPLICATION-AND-ISOLATION` | `deduplication_and_isolation` | Duplicate intakes deduplicate idempotently; failed records isolated into quarantine. | **PASS** |
| `CLAIM-W6-04-REVOKED-SOURCE-HANDLING` | `revoked_source_handling` | Revoked sources marked TAINTED, citations suppressed, raw access refused fail-closed. | **PASS** |
| `CLAIM-W6-05-CORPUS-QUERY-EQUIVALENCE` | `historical_corpus_query_equivalence` | Corpus queries by type, credibility, and venue match native LOF query results. | **PASS** |
| `CLAIM-W6-06-ROLLBACK-BOUNDARY` | `rollback_boundary_verification` | Disabling adapter halts federation without mutating source estate. | **PASS** |
| `CLAIM-W6-07-CANARY-DISCRIMINATION` | `canary_discrimination` | Non-vacuous test proves verifier rejects malformed hashes. | **PASS** |

---

## 3. Epistemic & Accounting Ledger

- **Wave Sealed:** Migration Wave 6 (W6)
- **Cumulative Migration Accounting:**
  - `Sealed Waves:` 7 / 11 (W0, W1, CP-Proof, W2, W3, W4, W5, W6)
  - `Court Adjudications Sealed:` 8
  - `Active Technical Debt:` 0
  - `Active Court Remands:` 0
- **Next Wave Legally Unblocked:** Wave 7 (`expose_full_inspiration_capability`)
