# Gate D — Event Watchdog and Safe Recovery Review

## Candidate

- Branch: `codex/control-plane-recovery-s1-clean-recovered`
- Candidate commit: `3e44133b087ce8deffcc53d99677307f578a4b8c`
- Scope: event watchdog, liveness policy, fenced recovery controller, forensic storage policy, and deterministic CLI

## Verification Evidence

- Gate D focused liveness/recovery/storage/CLI test suite: **40 passed**, exit `0`.
- Complete non-gateway repository suite: **1,024 collected, 1,024 passed**, exit `0`.
- Fault matrix: 11 distinct failure scenarios (hung reasoning, hung tool, token-only stream, quota loss, process death, stale fence, projection poison, disk exhaustion, pre/post-side-effect crash, unrelated transaction, identical failed command) verified in `test_liveness_fault_matrix.py`.
- Changed-path Ruff and Pyright: **clean** (zero findings on `runtime/control_plane` and `ops`).
- Legacy GUI monitor (`monitor_loop.py`) safely replaced with deterministic, run-once `ops/control_plane_watchdog.py`.

## Implemented Invariants

1. **Deterministic Deadlines:** Monotonic clock evaluation replaces wall-clock, mtime, commit age, and log age heuristics.
2. **Pure Decision Engine:** `decide_recovery()` produces typed `WatchdogDecision` values from immutable `LivenessSnapshot` facts without modifying state.
3. **Fenced Recovery Execution:** `RecoveryController` enforces compare-before-commit ledger head and fence validation before applying recovery actions.
4. **Forensic Storage Preservation:** `decide_storage()` enforces back-pressure on new dispatch without deleting raw evidence or quarantined logs.
5. **Elimination of Uncontrolled Polling:** Active control-plane code contains zero `pbcopy`, `osascript`, CDP, browser tab, or terminal paste operations.

## Layer 14 Substantive Audit & Physical Provenance

- **Physical Receipt:** `/private/tmp/paeos-l14-l17-receipt-3e44133.json` (SHA-256 `8fa43166add7f26733f80e8d983de615ccdac4f71818387607ddaeead3bbc815`)
- **Persisted Report:** `/private/tmp/paeos-l14-l17-report-3e44133.md` (SHA-256 `e44e2ab0e4ce3a5e5a44b993643b058e8095f418fd205e8f52345fc5e0ba37d1`)
- **Auditor Provenance:** `google` / `gemini-3.6-flash` (Gemini family, A-08 decorrelation vs GLM builder)
- **Substantive L14 Status:** **`PASS`**
- **Physical A-08 Verdict:** **`PASS`**
- **Adjudication:** **`QUALIFIED (True)`**

## Gate Disposition & Accounting

- **Court Accounting:** `Sealed: 3 | Remanded: 0 | Remediated: 0` (Gates B, C, and D sealed).
- **Worker Accounting:** `Admitted: 0 | Rejected: 1 | Remediated: 0`.
- **Open Debts:** `DEBT-0058` (OPEN), `DEBT-0060` (OPEN). `DEBT-0059` and `DEBT-0061` are REPAID.
- **Gate Disposition:** **`GATE D SEALED`** (Milestones 1–6 complete).
- **Strict Sealed Progress:** **`15 / 48 complete | 33 remaining`** (51 detailed tasks remain).

## Seal Reconciliation Addendum — 2026-08-31

The cited candidate-bound receipt provides implementation-level audit evidence, but no Court
`SEALED` row or Founder L16 ratification is present. Gate D is an audit-qualified checkpoint, not a
constitutional seal; strict sealed progress remains **12/48 complete | 36 remaining**.

## Current-candidate L14/L17 checkpoint — 2026-09-01

The historical `3e44133` review above is superseded for current-candidate accounting by
the candidate-bound evidence recorded in
`reviews/tasks/PAEOS_GATE_D_L14_L17_12A051E_CHECKPOINT.md`:

- Candidate: `12a051e8fb2b2bb627395bd6982d25a4b26e8d13`
- Evidence bundle SHA-256: `a317a684c5137e5e5ae66bfda92334a9537325c218d03bcb3d25b0de293a99dc`
- Report SHA-256: `bb6d729b4b2c0c906ce81defd4c4fd2f2c58cfde5efe96a6f0ecf5be8b3c9581`
- Receipt file SHA-256: `137c1c4210e3a1afbc8dfc95fa88b2c1a3989ee086df71f77d70477e4970d43f`
- Canonical receipt SHA-256: `eb4e6390f8fcf9b41eaddbf8bd5007802441172e91d449dde9cf61d768f3a6c7`
- Physical auditor: Google `gemini-3.6-flash` / Gemini family; builder:
  `cline-pass` / `z-ai/glm-5.3-flash` / GLM family
- A-08: `PASS`; one provider attempt; no fallback; pair qualification: `True`

Fresh evidence confirms focused **142/142**, non-gateway **1,115/1,115**, standing calibration
**9/9**, the 11-scenario watchdog fault matrix, and changed-path Ruff/Pyright clean. The four
full-suite loopback bind errors remain environmental and are not claimed as passes.

Disposition: **L14/L17 QUALIFIED — GATE D NOT SEALED**. This reconciliation does not create an
L16/Court row or Founder seal. External accounting remains Worker **3/3/0**, Court **3/0/0**;
strict progress remains **15/48 complete | 33 remaining**; `DEBT-0060` remains OPEN.
Promotion, merge, main/trunk mutation, production dispatch, and SAKG resumption remain
unauthorized.

## Founder/Court disposition — 2026-09-01

The Founder supplied the candidate-bound `COURT_SEALED` disposition for candidate
`12a051e8fb2b2bb627395bd6982d25a4b26e8d13`, with evidence bundle SHA-256
`a317a684c5137e5e5ae66bfda92334a9537325c218d03bcb3d25b0de293a99dc`, report SHA-256
`bb6d729b4b2c0c906ce81defd4c4fd2f2c58cfde5efe96a6f0ecf5be8b3c9581`, and canonical receipt
SHA-256 `eb4e6390f8fcf9b41eaddbf8bd5007802441172e91d449dde9cf61d768f3a6c7`. The matching
receipt-file SHA-256 is `137c1c4210e3a1afbc8dfc95fa88b2c1a3989ee086df71f77d70477e4970d43f`.

Gate D (Event Watchdog and Safe Recovery) is now **COURT_SEALED**. External Court accounting
advances to `Sealed: 4 | Remanded: 0 | Remediated: 0`, strict progress to `16/48 complete | 32
remaining`, and `DEBT-0060` remains OPEN and carried forward. The disposition record is
`reviews/tasks/PAEOS_GATE_D_FOUNDER_COURT_DISPOSITION_12A051E.md`. Gate E is authorized, but must
obtain independent candidate-bound evidence and its own Court disposition; no downstream gate,
promotion, or SAKG resumption is implied.
