# PAEOS Gate F L13 Reproduction — Candidate 61521f7

Date: 2026-09-02  
Worktree: `/private/tmp/paeos-control-plane-recovery-s1-clean-recovered`  
Branch: `codex/control-plane-recovery-s1-clean-recovered`  
Implementation candidate: `61521f7429462a4e015feb285cb20a5b39c78294`

## Read-only reproduction

The Gate F focused test set was executed once with the recovery worktree's Python environment:

```text
python -m pytest -q tests/runtime/autonomy tests/kernel/test_promotion_policy.py tests/ops/test_run_autonomy_canary.py
```

The run exited `0` and emitted 28 progress dots with no failure, error, or skip markers. A
separate collection run reported `4 + 5 + 7 + 6 + 2 + 4 = 28` tests across the six files and also
exited `0`.

- Raw focused output: `/private/tmp/paeos-gate-f-l13-focused-61521f7.log`
- Focused log SHA-256: `a4ba55c7ec7daeede2ecfea3dda9a793665ee142066911215af4f033a9e8412a`
- Raw collection output: `/private/tmp/paeos-gate-f-l13-collect-61521f7.log`
- Collection log SHA-256: `ae947271d7970b7f431a07d6ee407c072d5f07d68962e24d35a89b1e9416bd8f`

No source, test, governance, credential, router, browser, clipboard, ref, merge, or promotion
state was changed by this reproduction. The unrelated untracked `RB-0027` artifact remains
preserved and excluded.

## Disposition

`L13_STATUS: REPRODUCED — 28/28 PASS`  
This is independent implementation reproduction evidence for the audited candidate. It is not an
L14/L17 audit, Court/L16 disposition, Gate F seal, bootstrap authority, promotion, or SAKG resume.
