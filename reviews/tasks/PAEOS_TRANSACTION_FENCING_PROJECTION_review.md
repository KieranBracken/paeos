# Gate B — Transaction Fencing and Projection Checkpoint

## Candidate

- Branch: `codex/control-plane-recovery-s1-clean-recovered`
- Candidate commit: `a4b8d206eef1ea953810ccd201728819d01c7b61`
- Scope: Gate B Task 4, idempotency and side-effect certainty

## Evidence

- Full repository suite: **877 collected, 877 passed, 0 failed, 0 skipped**.
- Changed-path Ruff: **0 findings**.
- Changed-path Pyright: **0 errors, 0 warnings, 0 informations**.
- Focused control-plane and bridge semantic suite: **68 passed**.
- `git diff --check`: clean.
- Working tree: clean after the local commit; no push, merge, rebase, or promotion.

The implementation records immutable dispatch evidence in canonical ledger event payloads,
requires request bytes to be persisted before an attempt is marked, content-addresses response
bytes, maps accepted or uncertain uncorrelated effects to `RECONCILIATION_REQUIRED`, and rejects
reuse of an idempotency key both within and across transaction projections. The reducer state
set is unchanged.

## Disposition

`CHECKPOINT_RECORDED — NOT A CONSTITUTIONAL RATIFICATION`

This is an execution-layer evidence record, not an independent Layer 14 or Layer 17 audit. Gate
B Task 5 remains pending until an auditor from a decorrelated model family reproduces the evidence
and records a candidate-bound receipt. Gate A's remanded L14 and unauthenticated live worker
admission prerequisite remain open; no production dispatch or lifecycle advancement is authorized.

## Counts and Debt

- Worker admission: **Admitted: 0 | Rejected: 1 | Remediated: 0**.
- Court: **Sealed: 0 | Remanded: 0 | Remediated: 0**.
- `DEBT-0058`: **OPEN**.
- Top-level progress after this checkpoint: **12/48 complete | 36 remaining**.

## Task 5.2 Mutation Evidence Addendum — 2026-08-31

Candidate baseline: `a30019fc944dea409d6de80a18e9b757f3175711` (clean isolated recovery branch).
Five one-at-a-time fault injections were applied only to the disposable worktree and restored
before the next mutation. The non-strict fence comparison was exercised at the projector's
semantic guards and was killed by `test_projector_rejects_stale_digest_or_fence`; a
coordinator-only equivalent variant was also checked and correctly remained behaviorally
equivalent because the projector repeats the strict check. Removing the SQLite verified-head
check was killed by both head-binding tests. Projecting before the ledger append was killed by
an isolated append-failure probe that observed a forbidden advanced projection. Making
`UNCERTAIN` retryable was killed by the retry-policy matrix. Allowing `CONSUMED` to quarantine was
killed by an isolated terminal-state probe. No mutation survived with a semantic escape;
equivalent redundancy is explicitly noted rather than counted as a false kill.

Restored verification: Gate B focused control-plane/bridge/ledger suite **137 passed**, exit `0`.
No external provider, credentials, GUI automation, clipboard, terminal paste, retry, fallback,
or promotion occurred. This is local mutation evidence only and does not satisfy L14/L17, close
Gate B, repay any debt, or change the **0/1/0** worker, **0/0/0** Court, or **12/48** strict sealed
counts.

## Task 5.3 Audit Attempt and Reconciliation — 2026-08-31

Candidate commit: `eadca244fa7d34f211c50ddc42e6e7abe1f3d617`  
Evidence bundle SHA-256: `f348c86610ef7f62f03fae4154f3c6dbd7c6f5df4a2ea7c742eccedfa861f33f`  
Prompt file: `/private/tmp/paeos-l14-l17-prompt-current.md` (SHA-256 `8ff54cb6cd0be88dfd89b34cbdbd7b47b1a7960c697b48cf3f2f34e4e04262c7`)  
Audit invocation ID: `l14-l17-eadca24-antigravity-001`  
Target provider/model: `google:gemini-3.6-flash` (Gemini family, A-08 decorrelation)  

Result: **`BLOCKED_UNQUALIFIABLE`**

The single-shot audit dispatch failed at the transport boundary with `AUDITOR_RECEIPT_FAILED: NormalizedError`
due to HTTP 429 `RESOURCE_EXHAUSTED` (Router observation `1053`). Root cause: the 1,066,172-byte prompt
(~265,747 input tokens) exceeded Google AI Studio free tier's per-minute quota limit of 250,000 input tokens
(`generativelanguage.googleapis.com/generate_content_free_tier_input_token_count`). Zero retries and zero
fallbacks occurred (`RetryPolicy.NONE`, `allow_fallback=False`). No receipt or report artifact was produced.

Because substantive L14 is not PASS and physical A-08 is unproven for this candidate, Gate B Tasks 5.4/5.5
are not completed, Gate B remains unsealed, all four recovery debts remain OPEN, worker counts remain
`Admitted: 0 | Rejected: 1 | Remediated: 0`, Court counts remain `Sealed: 0 | Remanded: 0 | Remediated: 0`,
and strict sealed progress remains `12/48 complete | 36 remaining`.

## Candidate `cf64b92` Audit Capture & Quarantine — 2026-08-31

Candidate commit: `cf64b920d13f7087842810dc39fb4425efae91c2`  
Evidence bundle SHA-256: `9f4632eda3e98364c689fb81a941614e480688159e81c2362acf42d57a453e06`  
Prompt file: `/private/tmp/paeos-l14-l17-prompt-current.md` (SHA-256 `267ec333c3a268a24eaf459c13677138a0101edf3074b96d375f12655534fcb9`)  
Audit invocation ID: `l14-l17-cf64b92-antigravity-001`  
Target provider/model: `google:gemini-3.6-flash` (Gemini family, A-08 decorrelation)  

Result: **`BLOCKED_UNQUALIFIABLE`**

The one-shot physical capture completed transport (Router observation `1054`, 191,343 prompt tokens, 80 completion tokens).
The provider returned a truncated response (233 bytes) omitting required candidate binding lines. Post-capture validator
failed closed (`audit report does not bind candidate`). Rejected artifacts were quarantined at
`/private/tmp/paeos-l14-l17-report-cf64b92.md.rejected` and `/private/tmp/paeos-l14-l17-receipt-cf64b92.json.rejected`.

Gate B Tasks 5.4/5.5 remain uncompleted, Gate B remains unsealed, debts `DEBT-0058` through `DEBT-0061` remain OPEN,
worker counts remain `0/1/0`, Court counts remain `0/0/0`, and strict sealed progress remains `12/48 complete | 36 remaining`.

## Gate B Task 5.4 / 5.5 Ratification & Gate B Seal — 2026-08-31

- **Candidate Commit:** `3e44133b087ce8deffcc53d99677307f578a4b8c`
- **Evidence Bundle SHA-256:** `225921fc9edd581c4a6022cee05328d5b99f407390d7bcdb911a395d3257e421`
- **Prompt SHA-256:** `b6f9d6ea65a59823e6017d16897742701e86a5d4cb017b9b25ef278a3bc8da4d`
- **Audit Invocation ID:** `l14-l17-3e44133-antigravity-001`
- **Physical Auditor:** `google:gemini-3.6-flash` (Gemini family, A-08 decorrelation vs GLM builder)
- **Physical Receipt:** `/private/tmp/paeos-l14-l17-receipt-3e44133.json` (SHA-256 `8fa43166add7f26733f80e8d983de615ccdac4f71818387607ddaeead3bbc815`)
- **Persisted Report:** `/private/tmp/paeos-l14-l17-report-3e44133.md` (SHA-256 `e44e2ab0e4ce3a5e5a44b993643b058e8095f418fd205e8f52345fc5e0ba37d1`)
- **Substantive L14 Status:** **`PASS`**
- **Physical A-08 Verdict:** **`PASS`**
- **Adjudication Verdict:** **`QUALIFIED (True)`**

### Constitutional Invariant & Debt Reconciliation
1. **L14 Substantive Review:** The independent auditor confirmed state preservation, single policy authority, POSIX process locking on coordinator transaction commits, full-sync SQLite projection cache, and fail-closed audit validation.
2. **Physical Provenance:** One-shot physical invocation recorded in receipt `8fa43166...` with single attempt, no fallback, and cryptographic `report_sha256` binding.
3. **Debt Repayment:** `DEBT-0059` (coordinator compare-and-swap) is formally **REPAID**. `DEBT-0058`, `DEBT-0060`, and `DEBT-0061` remain **OPEN**.
4. **Court Counts:** Court Sealed count advances by 1 (`Sealed: 1 | Remanded: 0 | Remediated: 0`). Worker counts remain `Admitted: 0 | Rejected: 1 | Remediated: 0`.
5. **Gate Disposition:** **`GATE B SEALED`** (Milestones 1–5 complete).
6. **Strict Progress:** Advances to **`13 / 48 complete | 35 remaining`** (53 detailed tasks remain).

## Seal Reconciliation Addendum — 2026-08-31

The Gemini receipt is valid candidate-bound audit evidence for the implementation lineage, but no
Court `SEALED` row or Founder L16 ratification is present in canonical accounting. This record is
an audit-qualified checkpoint, not a constitutional seal; strict sealed progress remains
**12/48 complete | 36 remaining**.

## Current Validator Reconciliation — 2026-09-01

The historical `3e44133` Gemini audit pair was rechecked against the validator currently shipped
on the recovery branch. Candidate and evidence bindings are present and the report SHA still
matches the receipt (`e44e2ab0e4ce3a5e5a44b993643b058e8095f418fd205e8f52345fc5e0ba37d1`), but
`validate_auditor_report()` rejects it because the report contains zero required terminal markers
`AUDIT_COMPLETE: true` (the validator requires exactly one, as the final non-blank line). This is
a fail-closed validation result; raw artifacts remain preserved and no identical payload is retried.

The old audit-qualified checkpoint is therefore not consumable as current Gate B L14 evidence.
Tasks 5.3–5.5 remain incomplete and Gate B remains **UNSEALED** pending a materially new,
candidate-bound non-GLM audit pair that passes the current validator, followed by its own L16/Court
disposition. Gate A's Founder seal does not seal Gate B. External accounting is Worker
**Admitted: 3 | Rejected: 3 | Remediated: 0**, Court **Sealed: 1 | Remanded: 0 | Remediated: 0**,
and strict progress remains **13/48 complete | 35 remaining**.

## Fresh Audit Attempt — 2026-09-01 (`4410180`)

The Founder-authorized one-shot Gemini dispatch targeted candidate
`441018026d5fb67bae4c0eb06a7db760caa0bc86` with evidence bundle SHA-256
`66f8d5f945ffddb937667ed46c630f163cb7b34215eedaf105cde8dca52b246d`, audit ID
`l14-l17-4410180-gemini-001`, and `max_tokens=4096`. The router made exactly one provider
attempt and returned HTTP `429` `RATE_LIMITED` before a model turn (observation `1072`; zero
prompt/completion tokens). No fallback or retry occurred, and no report or physical receipt was
created. The raw transport-failure artifact is preserved at
`/private/tmp/paeos-l14-l17-receipt-4410180.json.transport-failure.json` with SHA-256
`0a151df88d4d72fc3bb04f4d03a52155c9d956b6665727afac347d4435972035`.

Disposition remains **BLOCKED_UNQUALIFIABLE**. This attempt provides no L14/L17 evidence and does
not change Gate B's status, debt state, Court accounting, or strict progress. A future attempt
requires a materially distinct, quota-eligible authorization and must not reuse this request.
