# Audit Prompt Embedded-Evidence Delimiter Repair

## Candidate

- Branch: `codex/control-plane-recovery-s1-clean-recovered`
- Candidate commit: pending documentation commit
- Scope: `paeos/model_router/audit_prompt.py` and its regression tests

## Finding and repair

The fail-closed prompt validator located evidence delimiters with the first matching end marker
and counted protocol markers across the embedded evidence. A governance document or source diff
that quoted those strings could therefore be rejected as a duplicate control marker, making the
new self-contained audit bundle unusable. The repair parses the outer evidence block using the
first begin marker and last end marker, counts control markers only outside that block, and rejects
delimiter text outside the block. Evidence may quote protocol markers without changing controls.

## Verification

- RED regression: embedded evidence quoting phase and delimiter markers was rejected by the old
  validator.
- GREEN focused prompt suite: **9 passed**.
- Audit/CLI/routing suites: **38 passed**.
- Complete non-gateway suite: **1,024 passed**, exit `0`.
- Changed-path Ruff: clean.
- Changed-path Pyright: `0 errors, 0 warnings, 0 informations`.
- `git diff --check`: clean.
- A current self-contained bundle was generated locally and validated by the repaired builder;
  its secret scan passed after redacting credential-shaped fixture values.

## Disposition

`IMPLEMENTATION_REVIEW_ONLY — NOT L14/L17 OR GATE RATIFICATION`

No provider, credential, browser, clipboard, AppleScript, terminal-paste, retry, fallback,
promotion, or external transmission occurred. Existing blocked Gemini results are unchanged.
Worker counts remain **Admitted: 0 | Rejected: 1 | Remediated: 0**; Court counts remain
**Sealed: 0 | Remanded: 0 | Remediated: 0**; strict progress remains **12/48 complete | 36
remaining**.
