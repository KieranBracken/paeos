# SAKG Task 16 [I-PROJ] — Physical L14/L17 Checkpoint

**Disposition:** `QUALIFIED_AND_SEALED`

## Candidate and evidence binding

- Candidate commit: `2cedea82da2d775a878055a6d8eb3dd05c929883`
- Evidence bundle: `/private/tmp/paeos-sakg-task-16-l14-l17-bundle-2cedea8.json`
- Evidence bundle SHA-256: `227e5f2e6528e16c70b92e86734c2ea187864da2c9019201ee5edc16e057e117`
- Prompt SHA-256: `bf03d1e9c67a278f3897fae8ed413c1ba7e7c093a27f30fb6d536b32c8d299bc`
- Audit ID: `l14-l17-2cedea8-gemini37-001`
- Report: `/private/tmp/paeos-sakg-task-16-l14-l17-report-2cedea8.md`
- Report SHA-256: `2d25328ed69a3e37ee0080582016310f0e47307f5a4961f3c9e34e7c234a7ca5`
- Receipt: `/private/tmp/paeos-sakg-task-16-l14-l17-receipt-2cedea8.json`
- Receipt file SHA-256: `911fda16c4bb35f7654a3cbea31e87b114d878492f19fd21705459192b3c8baf`
- Canonical receipt SHA-256: `8a9d0bf0b4a61c3b14960f8a755fad98c1d4a5a1ae64cdb63cc2bdea1b601489`

## Physical verification

- Auditor: Google `gemini-3.7-flash`, Gemini family
- Builder: `cline-pass` / `z-ai/glm-5.3-flash`, GLM family
- A-08 decorrelation: `PASS` (Gemini != GLM)
- Provider attempts: `1`; fallback chain contained only the selected Gemini route
- Artifact adjudication: `report_status=PASS`, `a08_verdict=PASS`, `qualified=True`
- Report completion marker: `AUDIT_COMPLETE: true`

The auditor report binds the exact candidate and bundle and verifies deterministic ranking, hard
whole-result budget omission/counting, mandatory `why` paths, advisory `trust=untrusted`, and
reproducible corpus/query hashes. It also records the present repository test filename
`tests/sakg/test_sakg_projection.py` in place of the intake's absent
`tests/sakg/test_projection.py`; this drift remains visible and is not silently normalized.

## Local evidence and accounting

- Hermetic SoftLoop local seal: `2645db5e6e23b1f76726a555ef5ee9d44a4835d7b12a7328c37eeb6054ce1a5b`
- Local artifact bundle: `31f658d7c00169139c87d4a3ef4f509845a19e635b3dec0df89878b755a03bb2`
- Actual projection tests: `15 passed`, exit `0`
- `pyright sakg/`: exit `0`; zero errors/warnings
- `ruff check sakg/ tests/sakg/`: exit `0`; zero findings
- Task 16 window accounting: **Sealed: 1 | Remanded: 0 | Remediated: 0**
- Strict physical progress: **22/48 complete | 26 remaining**

No promotion, merge, source mutation, or protected-ref mutation occurred as part of this audit
ingestion.
