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
