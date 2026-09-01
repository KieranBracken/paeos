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

## Current candidate L14/L17 reconciliation — 2026-09-01

Candidate `f0be9ab1a59ac8053213aacb70d26472739b217d` received a fresh one-shot physical Gemini
audit using bundle `a5438c86b820e914d57c09e9e209cbb12e074fc9c1b961b682bb0f910d06d6af`. The
persisted report is `/private/tmp/paeos-gate-c-l14-l17-report-f0be9ab-compact.md` (SHA-256
`ab2e8c0bbe8735ee0db5cb5745418a03bd134ed3bb3c579ea0c716ce3f126b55`); the physical receipt is
`/private/tmp/paeos-gate-c-l14-l17-receipt-f0be9ab-compact.json` (file SHA-256
`fec1775655c0d9460d4ce452bfb7f4be0846b4046fb380deaf939792060302c4`, canonical receipt SHA
`b2f09e29b9ddc060bc866ab3eba84a6e35ce362f0664d487ff415275384eaed6`).

Local pair adjudication returned `report_status=PASS`, `a08_verdict=PASS`, `qualified=True`;
the transport recorded one Google `gemini-3.6-flash` attempt, no fallback, and `gemini != glm`.
The report-bound per-audit accounting is Worker **0/1/0** and Court **0/0/0**. L17 is therefore
recorded as a qualified implementation checkpoint.

One report finding says `DEBT-0058` is open; that is stale relative to the canonical Founder Gate A
seal, which repaid `DEBT-0058`. The canonical current debt is `DEBT-0060` only. This is preserved
as a reconciliation note, not silently promoted to a new debt or used to reject the otherwise
qualified pair. The report also correctly identifies that the synthetic canary ladder is not a
ratified Z0 canary set.

Gate C remains **NOT GATE-SEALED** pending the Z0 canary boundary, L17 reconciliation, and a
separate Founder/Court disposition. No later gate or SAKG work is authorized.

## Gate C Z0 canary catalog proposal — 2026-09-01

The verifier prepared an external proposal catalog for `CANARY-0003` through `CANARY-0009`,
covering instruction fidelity, architecture escape, raw-evidence separation, restart, privacy,
self-ratification, and prompt injection. The catalog digest is
`581e956b1cf50db7067dc508f2df4287c7e5e88882e864a503def946955e219f`; catalog summary SHA-256 is
`cf30d731383e57c744d0ea7e327c411fe953e28a7b4252d17723e33bcb2686f2`. The external proposal root
is `/private/tmp/paeos-gate-c-z0-proposal-20260901/`; the ratified constitution was not changed.

The ladder passed **7/7** ordered install/reach/kill checks and retained one healthy control
`REMAND` (exit `2`, no kill). These are synthetic verifier-owned preparation artifacts and do
not constitute Z0 ratification or a Gate C seal. The final Court request is
`/private/tmp/paeos-gate-c-court-disposition-request-20260901.md`, SHA-256
`32eaa77764a2054ce62081ae3cf0d067c00e2bcb7b53274bd5e1cea071b50158`. Gate C remains unsealed
until Founder ratification of the exact catalog and a separate L16/Court disposition.
