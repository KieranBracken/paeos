# SAKG Task 13 — Physical L14/L17 Audit Checkpoint

**Date:** 2026-09-03  
**Task:** `[F-TRADEOFF-FIX]` Golden tradeoff fixtures and precedent joins  
**Recovery branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Candidate commit:** `b2ef99c0ca484b919ed89b52287d746f6b4ac8aa`  
**Disposition:** `QUALIFIED / COURT_SEALED` (Founder-provided disposition recorded below)

## Candidate and evidence bindings

- Candidate commit: `b2ef99c0ca484b919ed89b52287d746f6b4ac8aa` (Git object verified).
- Evidence bundle: `/private/tmp/paeos-sakg-task-13-l14-l17-bundle-b2ef99c.json`.
- Evidence bundle SHA-256: `ea3cb850b98a6519afab7cd9df453a31a13a9795fb9139f0469537e1305b850f`.
- Prompt: `/private/tmp/paeos-sakg-task-13-l14-l17-prompt-b2ef99c.md`.
- Prompt SHA-256: `1b76ec20dc0dc19e6163b3861c3ef1f099a0f341bd855102b0eaed08d8a665d6`.

## Physical receipt pair

- Report: `/private/tmp/paeos-sakg-task-13-l14-l17-report-b2ef99c.md`.
- Report SHA-256: `1ba70ff96f3daedfe9ff9083da36ee1c656946b09eaefac160b001db35368175`.
- Receipt: `/private/tmp/paeos-sakg-task-13-l14-l17-receipt-b2ef99c.json`.
- Receipt file SHA-256 (raw bytes): `97a2bad513f530f7b6315cc17e36081a36d68a2e73f83a2ecca7b4217f10202f`.
- Receipt canonical SHA-256 (schema `paeos.auditor-physical-receipt/1`): `dfa25a2a14f69c1c8bcb178625c5e200c379886fe56aeec7491f07642e4aaa0e`.
- Receipt audit ID: `l14-l17-b2ef99c-gemini-physical-004`.
- Actual auditor: Google / `gemini-3.6-flash` / family `gemini`.
- Builder on record: `cline-pass` / `z-ai/glm-5.3-flash` / family `glm`.
- Provider attempts: `1`; fallback chain contains only `google:gemini-3.6-flash`.
- A-08 decorrelation: `PASS` (`gemini != glm`).
- Receipt-bound report SHA-256: `1ba70ff96f3daedfe9ff9083da36ee1c656946b09eaefac160b001db35368175`.

## Mechanical adjudication

The repository artifact-pair validator was run against the persisted pair. It returned:

```text
report_status=PASS
a08_verdict=PASS
qualified=True
```

The report contains the exact candidate and bundle bindings, one `L14_STATUS: PASS`, substantive
findings, the expected Worker/Court accounting, and the final `AUDIT_COMPLETE: true` marker. The
fresh scoped Task 13 verification run returned `16 passed in 0.15s` with exit code `0`. Earlier
post-integration verification also recorded `115/115` `tests/sakg` tests, clean Ruff/Pyright, and
clean AST anti-pattern checks.

Historical failed attempts remain preserved and are not erased: four local Court remands, two
truncated Gemini reports, and one provider `503` transport failure. They are evidence of prior
back-pressure, not silently converted into passes.

## Accounting

- Task 13 physical audit window: **Sealed: 1 | Remanded: 4 | Remediated: 0**.
- Strict physical program progression: **19/48 complete | 29 remaining**.
- No main/trunk promotion, merge, or protected-ref mutation was performed.

## Post-adjudication artifact-path drift

After the pair above was validated and this checkpoint was committed, a concurrent process
replaced the files at the same `/private/tmp` paths with a different pair targeting
`gemini-3.7-flash` (audit ID `l14-l17-b2ef99c-gemini37-001`). The replacement pair is mechanically
qualified when validated against its own receipt scope, but it is **not substituted** for the
user-authorized `gemini-3.6-flash` pair recorded above. Current replacement hashes are report
`85191188638f638bdfcd27b0bba75cfd58d17790200af180521437b041168c5d`, raw receipt
`195722580f5188b997fd2a2ec204ce09eb57baccc620c7c7dbb8ec57f0dd3ada`, and canonical receipt
`8d9fdc5d6236645d77172004b7b828b67638aae3d165525ff62fd49d46efbab6`. The original validated
hashes remain the authoritative Task 13 record above; the path replacement is logged as an
artifact-integrity anomaly and must be reconciled before any later audit relies on those paths.
