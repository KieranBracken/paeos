# PAEOS Milestone 43 — `[I-CER-BASELINE]` / L02-C1 Ceremony Enforcement Realization

**Disposition:** `COURT_SEALED`
**Sealed:** 2026-09-03
**Candidate:** `e761351faeb8f4bf6fb25218ae7e97eb413f190b`
**Program branch:** `codex/control-plane-recovery-s1-clean-recovered`
**Predecessor:** Milestone 42 `[I-LIFETIME-CONFORMANCE]`, candidate
`8e92bae07e48bf98b39d436cd5af0464917a2f65`

## Court basis

The Founder directs `COURT_SEALED` after mechanical revalidation of the supplied, candidate-bound
physical L14/L17 report and receipt. This disposition records the isolated candidate and advances
the physical programme ledger. It does not promote or merge candidate source and does not mutate
`main` or `trunk`.

## Local L13 / Court evidence

- Hermetic SoftLoop run: `i-cer-baseline-trace-a-004`
- State root: `/private/tmp/paeos-cer-baseline-run`
- Worker root: `/private/tmp/paeos-cer-baseline-worker-001`
- SoftLoop status/verdict: `SEALED` / `PASS`; Court exit `0`
- SoftLoop seal hash:
  `11043daf9c35e76a7a45b8419b12ca16b87a55120b29c7f8158cc910041c784e`
- Ledger head and chain-validity digest:
  `5f4eabd3d5a1bf006d4cad459780389ca72ed81755e828cb851a643cc3877b42`
- SoftLoop result SHA-256:
  `e1f1b411690c86d35e28512bddba95e7f239550e094a694a2160ed9e055d7714`
- Focused ceremony suite: `14/14` passed, exit `0`
  (`tests/runtime/test_ceremony_contract.py` and `tests/runtime/test_ceremony_walk.py`)
- Contract suite: `9/9` passed, exit `0` (`tests/runtime/test_ceremony_contract.py`)
- Ruff on the candidate scope: exit `0`, `All checks passed!`
- Focused Pyright: exit `0`, `0 errors, 0 warnings, 0 informations`

The evidence covers canonical L01–L19 obligation ordering, Trace-A's eleven K1 discharge stubs,
Trace-B's all-execute contract, conservative resolution of an unknown ceremony depth to Trace-B,
and fail-closed rejection of a missing or out-of-order obligation walk.

Candidate file digests:

- `runtime/ceremony.py`:
  `cdf93ca2c09f72f2921804542ef2ad41e9914bfd5dcefe8f5d30cf096116f69c`
- `tests/runtime/test_ceremony_walk.py`:
  `db1a062d296d47221912e67a0e1d0c926ad6356076ab24cfe284ac2cd10455b6`

## Physical L14/L17 audit evidence

- Audit ID: `m43-cer-baseline-e761351-nvidia-001`
- Auditor: NVIDIA `meta/llama-3.2-11b-vision-instruct` (family `llama`)
- Builder recorded by receipt: `cline-pass` / `z-ai/glm-5.3-flash` (family `glm`)
- A-08 decorrelation: `PASS` (`llama != glm`)
- Provider attempts: exactly `1`; fallback chain contains only the configured NVIDIA route
- Candidate SHA-256: `e761351faeb8f4bf6fb25218ae7e97eb413f190b`
- Evidence bundle path: `/private/tmp/paeos-cer-baseline-m43-bundle.json`
- Evidence bundle SHA-256:
  `12dbc843b14cbb6c4e8aca608bc109faf84cc590a37e3c966e8354bea32a24b2`
- Receipt path: `/private/tmp/paeos-cer-baseline-m43-receipt.json`
- Physical receipt file SHA-256:
  `a3990a99436037dcb00782d2d4c506370376b4ec55112b9c23d4c2c0ac2729cb`
- Canonical receipt SHA-256:
  `cceeeb13f062130a6d64f9d38b7846acaaff5c9c73d2cf741b0338098c6ea777`
- Report path: `/private/tmp/paeos-cer-baseline-m43-report.md`
- Report SHA-256:
  `e4c317558f6e96cba4537cf71e561f28608c4e7ab1b2326d809776ebd4bec411`
- Review-scope SHA-256:
  `06187ec929f5e898c4a62eef08dae63efdaf23125f89ed214d8db15f2ee3b2a8`
- Mechanical artifact adjudication: `report_status=PASS`, `a08_verdict=PASS`,
  `qualified=True`
- Bound accounting: `Worker: Admitted: 0 | Rejected: 0 | Remediated: 0`; `Court: Sealed: 1 |
  Remanded: 0 | Remediated: 0`

The reported `ccee...777` value is the receipt's canonical self-hash, not the SHA-256 of the
receipt file bytes. Both values are retained above to prevent an identity ambiguity.

## Findings and preserved anomalies

The substantive report confirms that the evidence presented a ceremony contract, deterministic
`ceremony_for` behavior, and a fail-closed `validate_obligation_walk` path. Its prose is treated as
an independent assessment of the embedded evidence, not as proof that the remote auditor executed
tools or independently reran the tests. The local Court logs above remain the reproduction record.

The candidate manifest identifies the isolated builder as GPT/Codex and states `llama != gpt`,
whereas the physical receipt records the host-side builder identity as GLM and establishes
`llama != glm`. This provenance discrepancy is preserved and not normalized away. Qualification
is based on the mechanically validated physical receipt contract, whose exact candidate, bundle,
review scope, report binding, actual model family, single attempt, and single-route chain pass.

## Accounting and next intake

- Window accounting: `Sealed: 1 | Remanded: 0 | Remediated: 0`
- Strict physical progress: **`31/48 complete | 17 remaining`** (`30/48` → `31/48`)
- Next intake: Milestone 44 `[I-L15-SIZING]` / L15 Dynamic Context Sizing, opened in
  `reviews/tasks/PAEOS_MILESTONE_44_I_L15_SIZING_INTAKE.md`
- No source change in the host checkout; no provider transmission, retry, fallback, promotion,
  merge, or protected-ref mutation occurred during this disposition.
