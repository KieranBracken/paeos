# PAEOS Milestone 42 — `[I-LIFETIME-CONFORMANCE]` / R4 Runtime Object Classifier

**Disposition:** `COURT_SEALED`  
**Sealed:** 2026-09-03  
**Candidate:** `8e92bae07e48bf98b39d436cd5af0464917a2f65`  
**Candidate checkout:** `/private/tmp/paeos-r4lifetime-worker-001`  
**Program branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Predecessor:** Milestone 41 `[I-CEREMONY-WALK]`, candidate `fba0a21a664b9e5f8d7f76dfc04e53bcc24a42cd`

## Court basis

The Founder/Court disposition is recorded from the supplied qualified physical audit. The
candidate is an isolated worker commit; this governance seal does not promote, merge, or copy its
source into `main` or `trunk`.

The requested public API was already present in the implementation lineage at
`9b7b9795497b1da34e1542b26c2edff1b14da78f`. Candidate `8e92bae` strengthens the conformance
coverage and binds the public export and delegation behavior to a focused test. No duplicate
implementation claim is made.

## Local L13 / Court evidence

- Hermetic SoftLoop run: `i-r4lifetime-trace-a-003`
- State root: `/private/tmp/paeos-r4lifetime-run`
- Worker root: `/private/tmp/paeos-r4lifetime-worker-001`
- SoftLoop status/verdict: `SEALED` / `PASS`; Court exit `0`
- SoftLoop seal hash: `72ccf5e8a9c68ecf50b31ad2736bfdf19daa62a924f01fa2957b173963a6d229`
- Ledger head and chain-validity digest: `1a46ac0227ae0e5fd4c5901de254b8af433da561ebe36568605d67baf726c93f`
- SoftLoop result SHA-256: `3bed46af3d147927072cbe1e43f4c3c993626385b4099d678972d4e06d8a896c`
- Focused test: `3/3` passed, exit `0` (`tests/runtime/test_lifetime_classify_obj.py`)
- Public API probe: `classify_obj-verified`, exit `0`
- Full `tests/runtime`: exit `0`
- Ruff on candidate files: exit `0`, `All checks passed!`
- Pyright on candidate files: exit `0`, `0 errors, 0 warnings, 0 informations`
- AST anti-pattern check on candidate files: exit `0`, no violations

Candidate file digests:

- `runtime/lifetime.py`: `4959977a73722f2a43c828c799d22f8bf6019b8f977f25ec44b4a3b52876e71b`
- `tests/runtime/test_lifetime_classify_obj.py`:
  `d8a32c58f5bf81757dd8e74a8483f116e8cab15f71475ecc9c949dd3ef5fc2e7`

## Physical L14/L17 audit evidence

- Audit ID: `m42-r4lifetime-8e92bae-nvidia-001`
- Auditor: NVIDIA `meta/llama-3.2-11b-vision-instruct` (family `llama`)
- Builder recorded by receipt: `cline-pass` / `z-ai/glm-5.3-flash` (family `glm`)
- A-08 decorrelation: `PASS` (`llama != glm`)
- Provider attempts: exactly `1`; fallback chain contains only the configured NVIDIA route
- Candidate SHA-256: `8e92bae07e48bf98b39d436cd5af0464917a2f65`
- Evidence bundle SHA-256: `f22702e1698f9fc8836de9840089d215823e1d163413e1bbf8070c4ad566f050`
- Bundle path: `/private/tmp/paeos-r4lifetime-m42-bundle.json`
- Receipt path: `/private/tmp/paeos-r4lifetime-m42-receipt.json`
- Receipt file SHA-256: `6f3a62421ff6addcfe118c90066a320461d1a2ca224e1733557f490acedd0a6f`
- Canonical receipt SHA-256: `87595e177a044480f024bb5397e20294803983860f3c77670214a9be191a6016`
- Report path: `/private/tmp/paeos-r4lifetime-m42-report.md`
- Report SHA-256: `262afcbf88e8c94d9de32498f64a122942ac47853f36fc0a7a2fb36d6c02674d`
- Mechanical artifact adjudication: `report_status=PASS`, `a08_verdict=PASS`,
  `qualified=True`

The receipt/report pair was independently revalidated against the exact candidate, bundle,
review-scope, builder identity, and expected accounting (`Worker: 0/0/0`; `Court: 1/0/0`).

## Findings and preserved anomalies

The substantive report recommends handling an unregistered object type rather than allowing a
`KeyError`. This is not a defect for this milestone: the intake and candidate test explicitly
require a meaningful `KeyError` for an undeclared artifact type, and the implementation preserves
that fail-closed behavior.

The earlier one-shot Google Gemini 3.6 dispatch was rejected with `worker accounting mismatch`;
its `.rejected`, `.rejection.json`, and report artifacts remain preserved under
`/private/tmp/paeos-r4lifetime-m42-*`. The qualified pair recorded here is the later NVIDIA
physical pair, not that rejected Google attempt. The candidate manifest declares a GPT builder and
`llama != gpt`, while the physical receipt records the host builder as GLM; this provenance
discrepancy is retained rather than normalized away. The current prompt digest is
`c03beabb04f63b506e60f461dcab044b431604dee261797174b1153a22a8141e`, while the candidate manifest
contains `c16fe6ac4c6bdf44c7c8da4c31220a8f054e4ced5b5d4370286cab2d6761ca14`; this metadata drift
does not alter the exact candidate/bundle/report/receipt bindings and is carried as follow-up debt.

## Accounting and next intake

- Window accounting: `Sealed: 1 | Remanded: 0 | Remediated: 0`
- Strict physical progress: **`30/48 complete | 18 remaining`** (29 → 30)
- Next intake: Milestone 43 `[I-CER-BASELINE]` / L02-C1 Ceremony Enforcement Realization,
  opened in `reviews/tasks/PAEOS_MILESTONE_43_I_CER_BASELINE_INTAKE.md`
- No source change in the host checkout; no retry, fallback, promotion, merge, or `main`/`trunk`
  mutation occurred.

