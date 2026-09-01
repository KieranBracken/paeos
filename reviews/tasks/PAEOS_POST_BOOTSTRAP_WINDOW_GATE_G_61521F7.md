# Post-Bootstrap Evidence Window and Gate G Revalidation — Candidate 61521f7

Date: 2026-09-02
Recovery branch: `codex/control-plane-recovery-s1-clean-recovered`
Implementation candidate: `61521f7429462a4e015feb285cb20a5b39c78294`

## Scope and authority

The Founder-authorized Gate F `COURT_SEALED` disposition permits one isolated bootstrap
integration and this post-bootstrap evidence-window attempt. All activity below is bound to the
fresh external state root
`/private/tmp/paeos-gate-f-bootstrap-state-61521f7-v2`; no production state, protected ref,
main/trunk, merge, push, credential value, or SAKG state is in scope.

## Post-bootstrap single-flight attempt

One Cline SDK admission probe was dispatched exactly once:

- Probe: `post-bootstrap-route-001`
- Provider/model/family: `cline-pass` / `z-ai/glm-5.3-flash` / `glm`
- Profile UUID: `6f05f1b8-297d-46cf-8e4c-5af5fc0c31da` (value only as an identifier)
- Auth epoch: `4`
- Result: `REJECTED`, typed reason `AUTH_FAILED`, process exit `1`
- Admission result SHA-256: `ae6e2072ec3405e4bbc7b044039ae5d6c445ac1e16aa114a5298a7f2bb3aaded`
- Failure lease SHA-256: `ed72f05a0403189f8e09548ffbc1b9a56845a5f2f2bd94b95e7452a237e602d8`
- Released lease SHA-256: `28007d8fd669aa787a233ea4db7f6f5abfb952e37eac0623cf64796089b0ec68`

Raw files remain under
`/private/tmp/paeos-gate-f-bootstrap-state-61521f7-v2/worker-admission/post-bootstrap-route-001/`.
No identical retry was made. The typed authentication failure is a blocker requiring a new
authentication state; it is not an admission, a live route proof, or a Court seal.

## Gate G read-only revalidation

The read-only command was executed once against the same external ledger:

```text
/Users/bob/GitHub/paeos/.venv/bin/python -m ops.revalidate_paeos_lifecycle \
  --ledger /private/tmp/paeos-gate-f-bootstrap-state-61521f7-v2/ledger.db \
  --state-root /private/tmp/paeos-gate-f-bootstrap-state-61521f7-v2 \
  --repository /private/tmp/paeos-control-plane-recovery-s1-clean-recovered \
  --run-id gate-f-bootstrap-61521f7 --json
```

Exit code was `2`, as required for unresolved lifecycle evidence. The raw JSON stdout SHA-256 is
`1cf080e0578aed2acf88a4883c043794feb0be3c6dfcb1b03701a2108973d420`; stderr was empty with
SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The verified ledger head is
`3cab1e7bab66592399f56ef5a00fcd03ac68f02809293efe9167e4a7998687e8`. Every layer L01–L19 is
`UNPROVEN` with reason `NO_COMMITTED_EVIDENCE`; Court counts from this ledger are
`Sealed: 0 | Remanded: 0 | Remediated: 0`. The only ledger row remains the previously verified
`FOUNDER_BOOTSTRAP_SEALED` event; no live route, Trace-A, rotation, quota-stop, promotion, or
layer evidence was fabricated.

The Gate G implementation contract suite was independently rerun in this worktree:
`13/13` tests passed, exit `0` (`runtime.lifecycle_audit`, `runtime.court_reconciliation`, and
`ops.revalidate_paeos_lifecycle` tests). This verifies the auditor machinery, not lifecycle
completion.

## Exact disposition

```text
POST_BOOTSTRAP_WINDOW: BLOCKED_UNPROVEN
GATE_G_STATUS: READ_ONLY_REVALIDATION — NOT SEALED
REASON: AUTH_FAILED live admission probe; ledger lacks L01-L19 evidence
```

The next permissible recovery step is a new, operator-established authentication epoch followed
by distinct no-retry admissions. After three valid route admissions, the coordinator must record
one clean supervisor rotation, one forced quota-stop recovery, three independent Trace-A canary
facts, and then the five distinct single-flight disposable-ref promotions required by Gate F.
Each promotion requires its own evidence and physical Builder/Auditor decorrelation. `DEBT-0060`
and `RB-0027` remain OPEN. No promotion, merge, protected-ref/main/trunk mutation, or SAKG
resumption occurred in this window.
