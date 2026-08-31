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
