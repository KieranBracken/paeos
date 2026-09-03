# SAKG Task 20 `[T-BASELINE]` — Founder/Court Disposition

**Disposition:** `COURT_SEALED`
**Date:** 2026-09-03

## Candidate and evidence binding

- Candidate commit: `08aaae95ff687db1f1c2337557a37aee126b517e`
- Evidence bundle SHA-256: `e5e44d4fa6b018452e9c734f52ea8364d40333707dad10d0d516f28de8942e82`
- Local SoftLoop state root: `/private/tmp/paeos-tbaseline-actual-run-016`
- Local seal: `e1847bed784a1f4d52704d33e636e1e20ca3fb8b29d5b80a425e3c8da58409ee`
- Local artifact bundle: `2a93b08c21b61f2d121500887a51a036d9c270dfd6fe42f05bdcf292c63d58eb`

## Physical heterogeneous audit

- Audit ID: `l14-l17-08aaae9-gemini37-001`
- Auditor: Google `gemini-3.7-flash` (Gemini family)
- Builder: `cline-pass` / `z-ai/glm-5.3-flash` (GLM family)
- A-08: `PASS` (Gemini != GLM)
- Provider attempts: `1`; fallback chain: selected route only
- Report: `/private/tmp/paeos-sakg-task-20-l14-l17-report-08aaae9.md`
- Report SHA-256: `871f0ca5a126c6a34c3426c91e800e1e232576d74073f70c8de4a40f6aca8e9c`
- Receipt: `/private/tmp/paeos-sakg-task-20-l14-l17-receipt-08aaae9.json`
- Receipt file SHA-256: `7d5f874a1e33d07629ec54ea0ce8fc5b65cabe37d5ef78d280fe2ad0fc43caf7`
- Canonical receipt SHA-256: `00d0d9b6cc06da78886eb2586d9813e27ae8894da3a7c21a0b53c6535d473ce4`
- Review-scope SHA-256: `ad68ddfeb6234eec413f0d94e6ac3e9b66a1b72ae0b02ff40ebc704bcfa60776`
- Mechanical artifact adjudication: `report_status=PASS`, `a08_verdict=PASS`, `qualified=True`

## Local Court evidence

- RED phase (module absent) exited `2` as expected.
- GREEN focused baseline suite: `4 passed`, exit `0`.
- Baseline CLI JSON emission: exit `0`; required delta keys present.
- Ruff: exit `0`; Pyright: exit `0`.
- Task-window accounting: `Sealed: 1 | Remanded: 0 | Remediated: 0`.

## Founder decision

The Founder authorizes the Task 20 seal based on the candidate-bound, mechanically qualified
Gemini 3.7 report/receipt pair and the non-vacuous local Court evidence. Strict physical program
progress advances from **25/48** to **26/48 complete | 22 remaining**. The earlier Gemini 3.6
identity-mismatch artifacts remain preserved as rejected evidence. No retry, fallback, source
change, promotion, merge, or main/trunk mutation is authorized or performed.
