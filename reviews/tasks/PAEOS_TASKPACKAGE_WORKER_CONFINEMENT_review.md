# Gate E — TaskPackage Worker Confinement Review

## Candidate

- Branch: `codex/control-plane-recovery-s1-clean-recovered`
- Candidate commit: `b2ea143`
- Scope: frozen implementation contract, execution binding, provenance data policy, egress manifest compiler, production task compiler, typed worker broker, capability-detected OS sandbox backend, and isolated verification proof views

## Verification Evidence

- Gate E focused test suite: **35 passed**, exit `0`.
- Complete non-gateway repository suite: **1,059+ collected, 1,059+ passed**, exit `0`.
- Discriminative mutations: Path traversal escape, data class downgrade, and contract hash mismatch verified killed in `test_worker_confinement_mutations.py`.
- Changed-path Ruff: **0 findings**.
- Changed-path Pyright: **0 errors, 0 warnings, 0 informations**.
- Direct shell / unconfined worker execution: **denied**; raw worker shell replaced with typed broker operations.

## Implemented Invariants

1. **Frozen Implementation Contract:** Immutable schema and canonical SHA-256 hash validate allowed paths, required artifacts, acceptance commands, and rollback actions.
2. **Execution Binding:** Cryptographically binds transaction key, contract hash, base commit, worktree, worker profile hash, supervisor profile hash, policy hash, and egress manifest hash.
3. **Data Classification & Egress Policy:** Enforces `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, and `SECRET` data classes; `SECRET` data is strictly forbidden from remote egress.
4. **Production Task Authority:** `ProductionTaskCompiler` mints exact Ed25519 `CapabilityToken` grants (`file:read:<path>`, `patch:apply:<path>`, `test:run:<cmd>`, `scope:request`, `artifact:submit:<art>`) through `CapabilityBroker`.
5. **Typed Worker Broker:** `WorkerOperationBroker` mediates all worker actions through capability checks and workspace containment, preventing arbitrary shell escapes.
6. **OS Sandbox Confinement:** `PortableSandboxBackend` applies POSIX process group isolation and `setrlimit` resource caps (CPU, memory, open files, file size).
7. **Isolated Proof Views:** `create_verification_views()` generates distinct baseline, candidate, and verifier directory views with verifier manifest hashing.

## Gate Disposition & Accounting

- **Court Accounting:** `Sealed: 4 | Remanded: 0 | Remediated: 0` (Gates B, C, D, and E sealed).
- **Worker Accounting:** `Admitted: 0 | Rejected: 1 | Remediated: 0`.
- **Open Debts:** `DEBT-0058` (OPEN), `DEBT-0060` (OPEN). `DEBT-0059` and `DEBT-0061` are REPAID.

- **Gate Disposition:** **`GATE E SEALED`** (Milestones 1–7 complete).
- **Strict Sealed Progress:** **`16 / 48 complete | 32 remaining`** (50 detailed tasks remain).

## Seal Reconciliation Addendum — 2026-08-31

**Disposition: `REMANDED_WITH_AMENDMENTS` — historical Gate E seal withdrawn.** The qualified
receipt is bound to candidate `3e44133b`; this Gate E implementation was added after that
candidate and is not covered by the receipt. Preserve the implementation and local tests, but
obtain a fresh candidate-bound L14/L17 audit before counting Gate E or advancing to Gate F.

## Current candidate checkpoint — 2026-09-01

The recovered Gate E implementation is bound to candidate `dd4345bc84c3d7b260eb77e5f82362600113ca82`.
The original GLM worker orchestration halted fail-closed after a recorded budget breach; its
successful editor operations were reconstructed from preserved transcript evidence and then
independently corrected for a replay artifact, typing, and lint quality. The implementation
commit is `f0b134d509f6e09e2c45a07af25226a4146e09b9`; the bound implementation report is included
in the candidate at `docs/superpowers/plans/2026-09-01-gate-e-taskpackage-worker-confinement-implementation-report.md`.

Independent candidate verification is **33/33 focused** and **1,140/1,140 non-gateway** tests
passed (exit `0`), with changed-path Ruff and Pyright clean and `git diff --check` clean. The
qualified Gemini L14/L17 pair binds evidence bundle SHA-256
`19dc1d100377d1b2271d74048c4571e73ae8a73ec5097dfd9ca5f17620c73ac0`, report SHA-256
`9be9f08c6e28f7dde682100e353a3a1229ea8f622c7be58851b8242820218405`, receipt-file SHA-256
`b17346ecae61a5283e5ce5aac83c45304e059c11042efe0764d1b19c350bef5e`, and canonical receipt
SHA-256 `eb8b624e1e9f8a843823b0b132897f9841d46cbc7f08fb1db402ee3424be53ee`. Physical auditor
`google/gemini-3.6-flash` is Gemini family, distinct from the GLM builder; A-08 passed with one
attempt and no fallback. The candidate-bound checkpoint is
`reviews/tasks/PAEOS_GATE_E_L14_L17_DD4345B_CHECKPOINT.md`.

This is qualified L14/L17 evidence, not a Court seal. Worker/Court request-local accounting is
`0/1/0` and `0/0/0`; `DEBT-0060` remains OPEN. A separate Founder/Court disposition is required
before Gate E can be counted or Gate F can begin. No promotion, merge, main/trunk mutation,
production dispatch, or SAKG resumption is implied.

## Founder/Court seal — 2026-09-01

The Founder supplied the candidate-bound `COURT_SEALED` disposition for Gate E candidate
`dd4345bc84c3d7b260eb77e5f82362600113ca82`, binding the qualified Gemini report
`9be9f08c6e28f7dde682100e353a3a1229ea8f622c7be58851b8242820218405`, canonical receipt
`eb8b624e1e9f8a843823b0b132897f9841d46cbc7f08fb1db402ee3424be53ee`, and evidence bundle
`19dc1d100377d1b2271d74048c4571e73ae8a73ec5097dfd9ca5f17620c73ac0`. Gate E is therefore
**SEALED**. `DEBT-0060` remains OPEN and is carried forward. Strict sealed progress is now
**17/48 complete | 31 remaining** and Gate F progression is authorized. The full
candidate-bound record is `reviews/tasks/PAEOS_GATE_E_FOUNDER_COURT_DISPOSITION_DD4345B.md`.
