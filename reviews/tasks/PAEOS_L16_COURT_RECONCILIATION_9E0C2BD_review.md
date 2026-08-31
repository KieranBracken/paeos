# PAEOS L16 Court Reconciliation — Candidate `9e0c2bd`

**Date:** 2026-08-31  
**Candidate:** `9e0c2bdfd6a80523bf176bc719843c611430b218`  
**Current recovery HEAD:** `8545f675cde15c8b46548ae0e7f9c1a96f52b477`  
**Branch:** `codex/control-plane-recovery-s1-clean-recovered`

## Scope and authority boundary

This is a read-only L16/Court reconciliation of the current candidate. It does not create a
ledger row, consume a promotion authority, seal a gate, merge, promote, or resume SAKG. A Court
disposition and any Founder ratification remain separate constitutional artifacts.

The current HEAD is a descendant of the candidate. The only changes after the candidate are
governance/review documents; no `runtime/`, `ops/`, or `tests/` paths changed after
`9e0c2bd`.

## Candidate-bound evidence

- L13 non-gateway reproduction: **1,058/1,058 passed**, exit `0`.
  - Raw log: `/private/tmp/l13-9e0c2bd-nongateway-rerun.log`
  - SHA-256: `31a0e724159c5f6f74f06ad308efe4ecebda0ce4885a1276fe6d6e34855e8482`
  - Exit record SHA-256: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94fb6f3fe3ab86aa`
- Restricted gateway fixture: **4 setup errors**, exit `1`, all caused by loopback bind
  `PermissionError: [Errno 1] Operation not permitted`; this is an environment limitation, not a
  pass.
  - Raw log SHA-256: `cdcb83bf8cf57877ffa2cd023e4ae7ae7bdfa8c170fd8a9aa58f2b8b73506b46`
  - Exit record SHA-256: `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`
- L14/L17 physical audit report: `L14_STATUS: PASS`, Google `gemini-3.6-flash` / family
  `gemini`, one attempt, no fallback; builder is `cline-pass` / `z-ai/glm-5.3-flash` / family
  `glm`; A-08 is `PASS`.
  - Report SHA-256: `43bdb17df1aa0a2b6aac595d56035537291504035e0b64badbf43aee603915ae`
  - Receipt file SHA-256: `c880a2ce84e7ad1818416b7215a8343b4d4280aa01b1dfc5d3a38ea4bad41d89`
  - Canonical receipt SHA-256: `a88a0ca660bccc07efe68f8d333e1fd3f92aec5b9f978843693be11c4e94e2c3`
  - Evidence bundle SHA-256: `0f4039b70a176430834eab9c6b972ac89db67fb9702737d1a8a44d133e078060`

These artifacts establish candidate-bound L13/L14 evidence. They do not establish an L16
disposition by themselves.

## Canonical ledger reconciliation

The read-only ledger fold verified the hash chain and applied
`runtime.court_reconciliation.reconcile_court_counts` to each available state ledger:

| Ledger input | Rows | Chain | Court rows | Counts |
|---|---:|---|---|---|
| `.paeos_state_investigation/ledger.db` | 1 | valid | none | Sealed `0`, Remanded `0`, Remediated `0` |
| `misc/.state_rb0026/ledger.db` | 1 | valid | none | Sealed `0`, Remanded `0`, Remediated `0` |
| `misc/_state_sakg/state_sakg/ledger.db` | 290 | valid | none | Sealed `0`, Remanded `0`, Remediated `0` |

No correlated `COURT_SEALED`, `COURT_REMANDED`, `COURT_REMEDIATED`, promotion, or Founder
disposition row exists in any available canonical ledger. Documentation claims are therefore not
promotable into Court evidence.

## Exact disposition

```text
L16_STATUS: BLOCKED_UNQUALIFIABLE
REASON: candidate-bound L13/L14/L17 evidence exists, but no correlated canonical Court/L16 disposition row exists
```

The strict program count remains **12/48 complete | 36 remaining**. Worker accounting remains
**Admitted: 0 | Rejected: 1 | Remediated: 0**. Court accounting remains
**Sealed: 0 | Remanded: 0 | Remediated: 0**. `DEBT-0058` and `DEBT-0060` remain open. Gate B
and downstream gates remain unsealed; SAKG remains held.

## Required next action

The next valid transition is a canonical, candidate-bound Court/L16 transaction produced by the
PAEOS runtime, followed by the required Founder disposition. This report cannot manufacture that
row and cannot self-ratify it. Once that transaction exists, rerun the read-only reconciliation
and update the strict count from the verified ledger facts.

## Operational integrity note

Opening the tracked SQLite copies for inspection caused SQLite to remove their companion WAL/SHM
files. The four files were restored byte-for-byte from `HEAD`; no ledger database content was
changed, and the recovery worktree is clean.
