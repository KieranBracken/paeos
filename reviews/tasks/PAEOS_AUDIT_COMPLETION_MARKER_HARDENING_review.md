# PAEOS Audit Completion-Marker Hardening Review

**Date:** 2026-09-01  
**Recovery branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Commit:** `42f670b08b149341aa6a1a7f06a6d02c3a39cc08`

## Finding

The candidate-bound Gemini response for `c4f54ca` passed the existing binding, status, and
accounting validators but ended mid-finding (`and---`). The validator had no terminal-completion
condition, so a physically valid receipt could qualify an incomplete substantive report. This is
non-vacuous-evidence risk at the L14 seam.

## Amendment

The report contract now requires:

- exactly one `AUDIT_COMPLETE: true` marker;
- the marker to be the final non-blank line; and
- a substantive `Findings:` line or `### Audit Findings` section containing text.

The generated prompt and system instruction state these requirements explicitly. Existing
candidate reports without the marker remain historical artifacts and are not retroactively
upgraded.

## Verification

- RED probe: `test_auditor_report_requires_terminal_completion_marker` failed before the change.
- Focused audit/prompt suite: **39/39 passed**, exit `0`.
- Complete non-gateway suite: **1,094/1,094 passed**, exit `0`; gateway-server fixture remains
  excluded by the restricted loopback policy.
- Changed-path Ruff: clean.
- Changed-path Pyright: **0 diagnostics**.

## Disposition

This is a control-plane hardening change only. It does not create a Court/L16 row, close
`DEBT-0058` or `DEBT-0060`, seal a gate, promote a ref, or resume SAKG. A fresh candidate-bound
non-GLM audit is required before consuming the hardened lineage.

