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
