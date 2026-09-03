# SAKG Task 13 — F-TRADEOFF-FIX Local Court Seal

**Date:** 2026-09-03  
**Task:** `[F-TRADEOFF-FIX]` Golden tradeoff fixtures and precedent joins  
**Recovery branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Candidate commit:** `b2ef99c0ca484b919ed89b52287d746f6b4ac8aa`  
**Disposition scope:** local SoftLoop/Court only; physical A-08 seal remains pending

## Remediation landed

The verified strong implementation was integrated from the authorized recovery CAS path into
`sakg/methods/tradeoff_precedents.py`. The committed source has SHA-256
`551344f9deba9a67a8a9435b4412de7fdb542c9400189f8a98917f032bb37b75`, exactly matching the
requested CAS artifact. Discriminating adversarial probes were added in
`tests/sakg/test_tradeoff_precedents_adversarial.py` (P1–P5, plus malformed-threshold coverage):
negated links, namespace filtering, confidence filtering, and strict node typing.

## Fresh local verification

The following checks were run after the integration commit:

* Task 13 scoped suites, including the five new adversarial probes: **16 passed**, exit `0`.
* Full `tests/sakg` suite: **115 passed**, exit `0`.
* `ruff check sakg/ tests/sakg/`: exit `0`, no findings.
* `pyright sakg/ tests/sakg/`: exit `0`, 0 errors, 0 warnings, 0 informations.
* `check_ast()` over the changed production/test files: no anti-pattern violations.

## Final corrected SoftLoop/Court window

The hermetic final window used a fresh state root and a scripted runtime whose output was
reproduced exactly by the Court:

* State root: `/private/tmp/paeos-ftradeoff-run-final-scripted-002`
* Run: `r-final-scripted-002`
* Goal: `g-4c1eb3ade75c`
* Worker identity: `scripted-final-worker-002` (synthetic, not a physical provider receipt)
* Outcome: `SEALED`; run exit `0`
* Seal hash: `8270dedaecf61e7deb45c660abe2e49a1ec5ac974b7f5f312a8abbb8549c9289`
* Verified ledger head: `5c7e95958dc72c2e6027ff4388cf6eea6343b0960b8a381641debfa5c1efb3d9`
* SealCommitted artifact bundle: `8da642ce2ccc6103c15f8e1ee141eb1db58ab5c703c252306c4a97e0a447ecfb`
* Verdict reference: `af09be2aaa68da4a3547345986d30cbee0593afd6e87574bd7b109d0f8459a5b`
* Adversary reference: `a55732c8ae472c9ab6cbebda2f8b6ef83a1a472351a50395b4247835e69ae55b`

The scripted harness used an in-process Court, so no Court JSONL file was emitted; the verified
SQLite ledger is the sole durable record for this local window. This limitation is preserved
explicitly and does not weaken the physical A-08 requirement below.

The local final-window accounting is **Sealed: 1 | Remanded: 0 | Remediated: 0**. The four
earlier Task 13 windows remain preserved as **Sealed: 0 | Remanded: 4 | Remediated: 0**; their
raw JSONL hashes and findings are recorded in
`reviews/tasks/PAEOS_SAKG_TASK_13_FTRADEOFF_REMAND.md` and `ledger/debt/DEBT-0068.md`.

## Provider and audit boundary

A live GLM SoftLoop attempt was made once and failed before Court execution with exit `1`:
`RuntimeError: cline CLI failed (exit -11): ERROR: SecItemCopyMatching failed -50`. No retry,
fallback, credential change, or provider substitution was performed. The successful final window
used a scripted worker and therefore provides local Court reproduction only. It does **not** prove
physical Builder != Auditor (A-08), and no heterogeneous Gemini L14/L17 receipt exists for
candidate `b2ef99c`.

## Canonical disposition

Task 13 is **locally Court-sealed** for the committed recovery candidate, but the strict physical
program counter remains **18/48 complete | 30 remaining**. A candidate-bound heterogeneous
L14/L17 audit must qualify this exact commit and bundle before Task 13 can advance the strict
counter or Task 14 can be dispatched. No main/trunk promotion, merge, or self-ratification was
performed.
