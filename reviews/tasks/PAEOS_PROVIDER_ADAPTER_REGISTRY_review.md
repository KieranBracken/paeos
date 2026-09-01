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

## Fresh Gate C revalidation — 2026-09-01

Current recovery HEAD `8706917` was revalidated without source or test edits. The focused
provider-registry, transport, descriptor-policy, architecture, A-08, decorrelation, and state
compatibility set passed **156/156** (exit `0`). The broader model-router/runtime set passed
**819/819** with the restricted loopback gateway fixture excluded. The complete non-gateway
repository suite passed **1107/1107** (exit `0`). Changed-path Ruff reported **0 findings** and
changed-path Pyright reported **0 errors, 0 warnings, 0 informations**. Full-repository static
debt and the restricted gateway environment remain separate unresolved quality findings.

The discriminative synthetic-provider proof is preserved at
`/private/tmp/gate-c-registry-discriminative-20260901.json` (SHA-256
`2e82a7077d3bc4c4ebdc7e7d125630aa95fe1c4b2900108414509ce5bb87a759`): the pre-registry parent
`764ae085` fails closed with `ModuleNotFoundError`, while current HEAD registers and resolves a
provider without core enum/table edits (exit `0`). This is a compatibility-boundary proof, not a
live-provider admission.

The intermittent manifest-classification symptom was stress-tested in nine independent focused
runs plus two complete-suite seeds; all completed runs passed. Raw logs remain under
`/private/tmp/gate-c-manifest-stress/` and `/private/tmp/gate-c-flake-stress/`. No reproducible
source defect was established, so no speculative fix was applied.

This record remains an implementation/evidence checkpoint. A candidate-bound non-GLM L14/L17
receipt for the current HEAD, L17 reconciliation, and a Founder/Court disposition remain
required before Gate C can be sealed. External progress is unchanged at **14/48 complete | 34
remaining**; `DEBT-0060` remains OPEN.
