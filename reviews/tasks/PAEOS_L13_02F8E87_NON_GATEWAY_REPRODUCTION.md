# PAEOS L13 Independent Reproduction — Candidate `02f8e87`

**Date:** 2026-09-01  
**Candidate implementation:** `02f8e87951ab8602dc441845439350027359e928`  
**Recovery HEAD after governance-only records:** `e6c4f58d448a6bbf34407a5f8b3a391dc6bdd9b7`  
**Branch:** `codex/control-plane-recovery-s1-clean-recovered`

## Execution

The recovery tree was clean before and after one fresh test invocation. The implementation
candidate is unchanged between `02f8e87` and `e6c4f58`; the descendant contains governance-only
review records. No provider, credential, browser, clipboard, AppleScript, worker, ledger, or
promotion activity occurred.

```text
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q -rA tests \
  --ignore=tests/model_router/test_gateway_server.py
```

- Exit code: `0`
- Passed: **1,094**
- Failed: `0`
- Errors: `0`
- Skipped/xfail: `0`
- Raw log: `/private/tmp/l13-02f8e87-nongateway.log`
- Raw log SHA-256: `93c6d4282d6995e07ee76a7ffebe420cfc5cb0234a16dfb462e9a37ab36e4b22`
- Exit record: `/private/tmp/l13-02f8e87-nongateway.exit`
- Exit record SHA-256: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`

`tests/model_router/test_gateway_server.py` remains excluded because it requires restricted
loopback binding; its setup limitation is not converted into a pass.

## Disposition

`L13_REPRODUCTION: PASS` for the candidate implementation scope. This is reproduction evidence
only. It does not create a Court/L16 ledger row, seal a gate, close `DEBT-0058` or `DEBT-0060`,
advance strict progress, or resume SAKG. The next valid transition is canonical Court/L16
reconciliation using this L13 evidence and the bound L14/L17 pair.
