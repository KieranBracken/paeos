# Constitutional Implementation Review: GATE_F_CURRENT_REVALIDATION

**Date**: 2026-08-31  
**Task**: Revalidate the canary, activation, and dormant-promotion control surface and add the
planned no-promotion synthetic runner  
**Reviewer Role**: Temporary Architect/Overseer — implementation checkpoint

## Evidence

- Current recovery candidate: `5338429` (`docs(audit): record gate e revalidation`).
- Existing activation, canary-adjudication, and dormant promotion tests: **9/9 passed**, exit `0`.
- New `ops/run_autonomy_canary.py` contract tests: **5/5 passed**, exit `0`.
- Combined Gate F-focused suite: **14/14 passed**, exit `0`.
- Ruff on `runtime/autonomy`, `kernel/promotion.py`, the new runner, and their tests: **0 findings**.
- Pyright on the same changed-path scope: **0 errors, 0 warnings, 0 informations**.
- The runner validates an external state root, immutable verifier-owned inputs, a bounded sandbox
  directory, and a SHA-256 task-package binding; it persists raw manifest/observation bytes and a
  deterministic result exactly once. Incomplete canaries return `REMAND` with exit `2`.
- No worker/provider invocation, credential activity, browser/clipboard activity, ref update, or
  promotion occurred.

## Checklist

1. **Constitutional compliance — PASS.** The runner evaluates evidence and emits a result; it
   cannot mint authority, seal Court claims, or bootstrap promotion.
2. **No-promotion boundary — PASS.** Source and tests contain no ref-update, push, merge, browser,
   clipboard, or sleep/retry path.
3. **Evidence integrity — PASS.** Manifest hashes, mutation/target/installer hashes, raw input
   bytes, and deterministic result are bound under a private external transaction directory.
4. **Canary non-vacuity — PASS.** The existing adjudicator requires ordered installed/reached/killed
   facts, exact failure code, and a non-empty evidence reference.
5. **Replay resistance — PASS.** Reusing the same canary ID is refused before any second result
   write.
6. **Isolation — PASS.** Inputs must be regular files below an external state root; the sandbox
   path must exist and the Git worktree is never used as the state root.
7. **Activation derivation — OBSERVATION.** Local activation counters and canary results exist,
   but no live end-to-end Trace-A canaries, clean rotation, or forced quota-stop have been
   independently executed.
8. **Promotion safety — OBSERVATION.** The controller remains dormant in this recovery branch;
   Founder bootstrap evidence and exact-ref Git-plumbing mutation evidence are absent.
9. **Static debt — OBSERVATION.** Repository-wide inherited Ruff/Pyright debt remains outside
   this changed-path checkpoint and is not silently treated as resolved.
10. **Lifecycle separation — PASS.** This checkpoint is implementation evidence only; L14/L17 and
    Court/L16 remain separate adjudication steps.

## Disposition

`IMPLEMENTATION_CHECKPOINT — 14/14 VERIFIED; NOT GATE-SEALED`.

Fresh current-candidate L14/L17 evidence, Court/L16 reconciliation, live canary/rotation evidence,
and any Founder bootstrap disposition remain mandatory. Worker/Court remain **0/1/0** and
**0/0/0**; strict progress remains **12/48 complete | 36 remaining**; `DEBT-0058` and
`DEBT-0060` remain open.
