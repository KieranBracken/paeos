# Gate F — Canary, Activation, and Dormant Promotion Checkpoint

## Candidate

- Recovery branch: `codex/control-plane-recovery-s1-clean-recovered`
- Implementation commits: `38e91c0`, `175599b`, `6336808`
- Candidate scope: activation derivation, verifier-bound canary adjudication, hidden fault catalog,
  no-promotion runner, and dormant exact-ref promotion policy/controller.

This is an implementation checkpoint, not a Gate F seal.  The earlier historical Gate F seal in
`PAEOS_CANARY_BOOTSTRAP_PROMOTION_review.md` remains withdrawn; it cannot be reused for this
candidate.

## Fresh verification

- Gate F focused collection: **28 collected; 28 passed; 0 failed; 0 skipped; exit 0**.
- Changed-path Ruff: **0 findings**.
- Changed-path Pyright: **0 errors, 0 warnings, 0 informations**.
- `git diff --check`: **clean**.
- Synthetic no-promotion ladder: **3/3 distinct canaries PASS**. Raw inputs/results are retained
  under `/private/tmp/paeos-gate-f-ladder-001/`, `-002/`, and `-003/`; each was a single invocation,
  with no provider, browser, clipboard, ref update, merge, push, or promotion side effect.
- Disposable Git-plumbing test: exact feature-ref fast-forward, expected-head compare, ancestry,
  rollback parent/tree, prepared evidence, receipt persistence, and single-use token checks pass.

## Fail-closed properties

1. Activation counts require a unique transaction id and a valid evidence hash present in CAS.
   Duplicate rows are idempotent; changed provenance, conflicting Court dispositions, and critical
   failures force `SUPERVISED_RECOVERY_ONLY`.
2. Canary observations bind version, target, mutation, installer, and transaction identifiers to
   the verifier manifest.  Replayed, stale, cross-transaction, or out-of-order triples cannot pass.
3. The public fault catalog exposes only classes; the verifier catalog carries expected failure
   codes for all 19 required mutation classes.
4. The promotion controller is dormant unless an explicit Founder bootstrap manifest hash and
   complete correlated evidence are supplied.  It rejects protected refs, Trace-B, missing or
   homogeneous provenance, unresolved debt/incidents/reconciliation, missing rollback, and absent
   health evidence.  When enabled in a disposable repository, it can issue only one exact
   `git update-ref <ref> <reviewed> <expected>` operation.

## Repository-wide gates and open blockers

- Full non-gateway collection: **1,154** tests.  One loaded-host run reached 100% with **1,152
  passed and 2 failures** in pre-existing Cline adversarial timeout cases; the same five cases pass
  in isolation.  Raw output is preserved at `/private/tmp/paeos-gate-f-nongateway-final.log` and
  the isolated proof is recorded in the execution log.
- Repository Ruff: **557 findings** (`/private/tmp/paeos-gate-f-ruff-final.log`).
- Repository Pyright: **120 errors** (`/private/tmp/paeos-gate-f-pyright-final.log`).
  These are inherited repository-wide debt, not silently excused by a baseline and not introduced
  by the changed Gate F paths.
- The required live route-probe/rotation/quota evidence and a Founder bootstrap fact do not yet
  exist.  No promotion authority may be minted and Task 7 is forbidden.
- `DEBT-0060` remains **OPEN**.  The untracked `RB-0027-budget-breach-possible-budget-model-
  miscalibration.md` is preserved and intentionally excluded from this candidate.

## Accounting and disposition

- External Worker: **Admitted 3 | Rejected 3 | Remediated 0**.
- External Court: **Sealed 5 | Remanded 0 | Remediated 0**.
- Strict sealed program progress: **17 / 48 complete | 31 remaining**.
- Disposition: **`IMPLEMENTATION_CHECKPOINT — NOT GATE-SEALED`**.

Required next evidence is a candidate-bound L13 reproduction, a physically decorrelated Gemini
L14/L17 audit of the final candidate bundle, and a separate Founder/Court L16 disposition.  If the
bootstrap bundle remains blocked by static debt or missing live prerequisites, record the exact
remand; do not optimize for zero remands or self-ratify.
