# SAKG Task 20 `[T-BASELINE]` — Local Court Checkpoint

**Disposition:** `COURT_SEALED`

## Candidate and local evidence

- Candidate commit: `08aaae95ff687db1f1c2337557a37aee126b517e`
- Isolated state root: `/private/tmp/paeos-tbaseline-actual-run-016`
- Run ID: `t-baseline-trace-a-actual-016`
- Goal ID: `g-2f5ad90b1da5`
- Local SoftLoop status: `SEALED`
- Local seal: `e1847bed784a1f4d52704d33e636e1e20ca3fb8b29d5b80a425e3c8da58409ee`
- Local artifact bundle: `2a93b08c21b61f2d121500887a51a036d9c270dfd6fe42f05bdcf292c63d58eb`
- Local ledger head: `a923339f1369e7b636688b17b55580a266554f20e8b809fe5ab175b7d485da29`
- Local report SHA-256: `7cf9181a8721f04c67e3f49e3ca380317b636a9cbe498e8348f508aa7b48f208`

## Verification

- RED phase: baseline module absent; focused collection exited `2` as expected.
- GREEN Court phase: 4 focused tests passed, exit `0`.
- Baseline CLI report: exit `0`, required `research_spawns_delta`, `remands_delta`, and
  `tokens_delta` keys present.
- Empty-graph and unreachable-SAKG tests passed; Ruff and Pyright exited `0`.
- Local Court accounting: `Sealed: 1 | Remanded: 0 | Remediated: 0`.
- Local scripted runtime does not establish Builder != Auditor.

## Physical audit result — qualified Gemini 3.7 pair

- Candidate-bound audit bundle: `/private/tmp/paeos-sakg-task-20-l14-l17-bundle-08aaae9.json`
- Bundle SHA-256: `e5e44d4fa6b018452e9c734f52ea8364d40333707dad10d0d516f28de8942e82`
- Prompt: `/private/tmp/paeos-sakg-task-20-l14-l17-prompt-08aaae9.md`
- Prompt SHA-256: `63703afb78fb40102440ec4f3ebd89e1ce5be26c064d7f8727d90716ce7586d4`
- Authorization: Google `gemini-3.7-flash`, one shot, no fallback or retry.
- Audit ID: `l14-l17-08aaae9-gemini37-001`
- Returned report: `/private/tmp/paeos-sakg-task-20-l14-l17-report-08aaae9.md`
- Returned report SHA-256: `871f0ca5a126c6a34c3426c91e800e1e232576d74073f70c8de4a40f6aca8e9c`
- Returned receipt: `/private/tmp/paeos-sakg-task-20-l14-l17-receipt-08aaae9.json`
- Returned receipt file SHA-256: `7d5f874a1e33d07629ec54ea0ce8fc5b65cabe37d5ef78d280fe2ad0fc43caf7`
- Returned canonical receipt SHA-256: `00d0d9b6cc06da78886eb2586d9813e27ae8894da3a7c21a0b53c6535d473ce4`
- Actual audit ID/model in receipt: `l14-l17-08aaae9-gemini37-001` / Google `gemini-3.7-flash`
- Provider attempts: `1`; returned receipt reports no fallback chain beyond the selected model
- Mechanical validation against the Gemini 3.7 contract: **QUALIFIED** with
  `report_status=PASS`, `a08_verdict=PASS`, and `qualified=True`.
- Candidate binding: `08aaae95ff687db1f1c2337557a37aee126b517e`; bundle binding:
  `e5e44d4fa6b018452e9c734f52ea8364d40333707dad10d0d516f28de8942e82`; review scope:
  `ad68ddfeb6234eec413f0d94e6ac3e9b66a1b72ae0b02ff40ebc704bcfa60776`.
- A-08 is **PASS** (`gemini` auditor != `glm` builder), with exactly one provider attempt and
  no fallback. The earlier Gemini 3.6 authorization mismatch remains preserved as rejected
  evidence; it is not counted as this seal.
- No retry, fallback, code change, promotion, merge, or main/trunk mutation occurred.

## Court disposition

The Founder supplied `COURT_SEALED` for Task 20 after the qualified Gemini 3.7 physical audit.
Task-window accounting is `Sealed: 1 | Remanded: 0 | Remediated: 0`. Strict physical progress
advances from **25/48** to **26/48 complete | 22 remaining**. Task 20 is sealed; the next
milestone intake is not opened by this record.
