# Gate C — Provider Adapter Registry and Extensibility Checkpoint

## Candidate

- Branch: `codex/control-plane-recovery-s1-clean-recovered`
- Candidate implementation: `1574c3ec5e558b368211e2c7b79560c36ee37963`
- A-08 architecture candidate: `647a016e72f87cc21b1b4141e479cf5740c1067b`
- Scope: Gate C Tasks 1–5 (descriptor registry, transport registry, policy migration,
  durable-key compatibility, and family-decorrelation centralization)

## Verification evidence

- Focused descriptor-policy suite: **31 passed**.
- Migration suite: **4 passed**.
- Architecture/A-08/decorrelation suite: **53 passed**.
- Applicable model-router + runtime suite (gateway test excluded from restricted loopback):
  **643 collected, 643 passed**.
- Complete non-gateway repository suite: **903 collected, 903 passed**.
- Whole-package model-router Pyright: **0 errors, 0 warnings, 0 informations**.
- Full repository Ruff: **637 findings**; model-router/test scope: **306 findings**.
- `git diff --check`: clean at each implementation checkpoint.
- Provider/credential activity: **none**; no live admission probe or production dispatch occurred.

## Implemented invariants

1. Provider facts are represented by validated, immutable descriptors. Future provider keys can be
   registered without editing the compatibility enum.
2. Wire behavior is selected through an explicit transport registry; Cline envelope and
   OpenAI-compatible adapters retain their existing boundaries and no hidden retries are added.
3. Catalog privacy, credentials, AIMD limits, policy ordering, quota telemetry, durable state, and
   probe evidence consume descriptor/string keys while preserving existing SQLite rows.
4. Invalid provider identities fail closed before persistence; no aliasing or silent normalization
   is permitted.
5. A-08 has one canonical family mapping and rejects catalog/receipt provider-family conflicts.
   Unknown families and dynamic aliases remain fail closed where physical identity is unavailable.

## Disposition

`CHECKPOINT_RECORDED — NOT A CONSTITUTIONAL RATIFICATION`

This record is an implementation checkpoint only. Gate C cannot be sealed until the RED
transcripts and an independent, candidate-bound physical L14/L17 audit receipt are available.
The current Codex session has no machine-captured auditor receipt for this candidate. The full
Ruff/Pyright repository baselines and restricted loopback gateway environment also remain open
quality blockers. No Gate B/C closure, production dispatch, or SAKG resumption is authorized.

## Counts and debt

- Worker admission: **Admitted: 0 | Rejected: 1 | Remediated: 0**.
- Court: **Sealed: 0 | Remanded: 0 | Remediated: 0**.
- `DEBT-0058`: **OPEN**.
- Strict sealed progress: **12/48 complete | 36 remaining**.
- Required next evidence: preserve standalone RED baselines, obtain physical decorrelated audit
  receipt, disposition repository static debt, and reconcile restricted gateway test failures.
