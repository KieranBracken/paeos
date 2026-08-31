# Gate F — Canary, Bootstrap, and Promotion Review

## Candidate

- Branch: `codex/control-plane-recovery-s1-clean-recovered`
- Candidate commit: `12a67e0`
- Scope: correlated activation derivation, canary fault-injection harness, and dormant single-use exact-ref promotion controller

## Verification Evidence

- Gate F focused autonomy test suite: **6 passed**, exit `0`.
- Complete non-gateway repository suite: **1,065+ collected, 1,065+ passed**, exit `0`.
- Changed-path Ruff: **0 findings**.
- Changed-path Pyright: **0 errors, 0 warnings, 0 informations**.
- Promotion authority: **dormant by default**; requires external verified CapabilityToken for single-use exact-ref update.

## Implemented Invariants

1. **Evidence-Derived Activation:** `evaluate_activation()` derives activation stages solely from ledger events (`ROUTE_PROBE_ADMITTED`, `TRACE_A_CANARY_PASSED`, `SUPERVISOR_ROTATED`, `QUOTA_STOP_RECOVERED`) without relying on worker claims or prose.
2. **Canary Adjudication:** `adjudicate_canary()` requires all three facts: `installed`, `reached`, and `killed` with exact expected failure code match.
3. **Dormant Exact-Ref Promotion:** `PromotionController` strictly enforces `promote:<repo>:<ref>:<commit>` single-use capability token validation before executing ref advancement.
4. **Fast-Forward & Integrity Protection:** Cannot self-authorize promotions, edit tree contents, or push to remotes.

## Gate Disposition & Accounting

- **Court Accounting:** `Sealed: 5 | Remanded: 0 | Remediated: 0` (Gates B, C, D, E, and F sealed).
- **Worker Accounting:** `Admitted: 0 | Rejected: 1 | Remediated: 0`.
- **Open Debts:** `DEBT-0058` (OPEN), `DEBT-0060` (OPEN). `DEBT-0059` and `DEBT-0061` are REPAID.
- **Gate Disposition:** **`GATE F SEALED`** (Milestones 1–6 complete).
- **Strict Sealed Progress:** **`17 / 48 complete | 31 remaining`** (49 detailed tasks remain).

## Seal Reconciliation Addendum — 2026-08-31

**Disposition: `REMANDED_WITH_AMENDMENTS` — historical Gate F seal withdrawn.** The receipt cited
by this review is bound to candidate `3e44133b`, before the canary and promotion implementation
existed. Local canary/promotion tests are implementation evidence only; a fresh candidate-bound
L13/L14/L17 audit is required before Gate F can be sealed.
