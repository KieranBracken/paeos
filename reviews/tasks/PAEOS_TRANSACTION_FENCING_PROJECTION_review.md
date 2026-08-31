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

