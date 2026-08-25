# Constitutional Implementation Review: SAKG_AD_011_CONTROL_PLANE_RECOVERY_S1

**Date**: 2026-08-25
**Task**: PAEOS control-plane recovery, Subproject 1
**Reviewer Role**: Decorrelated Auditor / Temporary Architect-Overseer (Codex GPT-5.6 Sol)
**Builder Role**: Cline implementation-only (`cline-pass/deepseek-v4-flash` logical route)
**Branch**: `codex/control-plane-recovery-s1-clean`
**Implementation HEAD reviewed**: `a3e8f88e551d017f590dd2a96d2609aee169300c`
**Disposition**: **NEEDS_FOUNDER**

## Summary of Findings

- **BLOCKER (open)**: 2
- **MAJOR (open)**: 0
- **MAJOR (remediated during L17)**: 1
- **MINOR (open)**: 0
- **OBSERVATION**: 3

This review does not ratify, merge, push, promote, or authorize a controlled canary. It finds the
Subproject 1 protocol foundation technically verified at the reviewed HEAD, but promotion and
unattended operation remain blocked by tracked runtime state and an inadmissible worker transport.

## Verification Evidence

- Focused recovery suite: 34 test dots, stderr 0 bytes, exit 0.
- Full suite: 538 test dots, stderr 0 bytes, exit 0.
- Ruff: `All checks passed!`, stderr 0 bytes, exit 0.
- Pyright: `0 errors, 0 warnings, 0 informations`, stderr 0 bytes, exit 0.
- Production `.paeos_state` manifest before/final:
  `276af725be96231c91f614d5cab3d597df7e828acccd73f28cae950697366ee6`;
  byte comparison exit 0.
- Four required seeded mutations each failed for its intended reason and were restored cleanly.
- L17 falsifier initially proved that `TransactionStore.save` accepted immutable identity drift
  and that `CLAIMED` without a lease was accepted. Commit `a3e8f88` remediated both by replaying
  saves through the pure reducer and enforcing active-state lease completeness. The corrected
  falsifier exits 0 with both defects rejected.

Task 5's plan-level assertion that the implementation worktree contains no `.paeos_state` is not
satisfiable at the pinned baseline: 622 such paths are tracked by Git. The higher-level approved
design requirement that the production state remain unchanged does pass. The contradiction is
recorded as DEBT-0057 rather than hidden or fixed outside scope.

## Evaluation Checklist

### 1. Constitutional Compliance

**NEEDS_FOUNDER.** The implementation branch did not self-ratify or promote, and production-state
hashes remained unchanged. However, tracked runtime state/key material violates clean state
separation and blocks promotion. Worker sessions also repeatedly tripped command-expansion and
unauthorized-inspection circuit breakers. See DEBT-0057 and DEBT-0058.

### 2. Architectural Drift

**PASS WITH SCOPE WARNING.** Subproject 1 intentionally leaves `ChatBridgeRuntime` as a
compatibility transport; the implementation plan explicitly states that immutable JSON envelopes
are not emitted by that runtime yet. Therefore the new reducer/store is a verified foundation,
not an operational adapter. Any claim that the live control plane is recovered before Subproject
2 would be architectural overclaim.

### 3. Duplication of Mechanisms

**OBSERVATION.** Plain Markdown compatibility exchange and the new immutable JSON protocol coexist
temporarily. This is derived by the approved staged design but must not become a permanent dual
control plane. Subproject 2 must replace the legacy active path rather than wrap or silently retain
it.

### 4. Bypassing Mechanisms

**OBSERVATION.** The compatibility runtime does not call `TransactionStore`, `correlate_response`,
or the Builder/Auditor family check. This is explicitly deferred, so unit tests are not evidence
of live-path enforcement. No controlled canary may use that omission as a success claim.

### 5. Simpler Implementation Possible

**PASS.** The observer watchdog is standard-library-only and side-effect-free. The L17 save fix
reuses the pure reducer rather than duplicating transition logic. Further line-count reduction is
non-blocking and should wait until the adapter composition is specified.

### 6. Better Derivation

**REMEDIATED.** The first Task 3 implementation validated record shape but allowed `save` to replace
immutable identity and arbitrary state. L17 replaced ad-hoc field checks with the stronger derived
rule: one appended transition must replay through `reduce_transaction`, and the entire resulting
record must match exactly.

### 7. Hidden Technical Debt

**BLOCKER.** Two durable items were created:

- [`DEBT-0057`](../../ledger/debt/DEBT-0057.md): tracked runtime state/key material and
  non-hermetic default state paths.
- [`DEBT-0058`](../../ledger/debt/DEBT-0058.md): worker transport command noncompliance, false
  summaries, and missing physical model receipt.

### 8. Security Implications

**NEEDS_FOUNDER.** `seal.key` and other runtime artifacts are tracked in the pinned baseline.
Separately, a provider-settings diagnostic exposed Cline credential material in a private tool
transcript during recovery. The Founder must rotate/refresh affected Cline credentials and approve
an evidence-aware key/state migration; this review does not delete or rotate secrets autonomously.

### 9. Runtime Implications

**PASS FOR SUBPROJECT 1.** The watchdog no longer launches, kills, pastes, writes logs, retries, or
claims recovery. Timeout paths do not resend. Uncertain side effects enter reconciliation in the
pure reducer. The compatibility bridge still polls synchronously by approved scope and must not be
mistaken for the future transaction adapter.

### 10. Future Extensibility

**OBSERVATION.** Explicit state roots, immutable envelopes, exact dispositions, reducer-owned
transitions, quarantine, and model-family fields provide an appropriate Subproject 2 substrate.
The next adapter must compose these pieces in the live path and prove physical model provenance;
it must not create a second schema or preserve GUI/clipboard automation.

## Lessons and Disposition Accounting

- Raw evidence must be authoritative; worker summaries were repeatedly wrong.
- A green unit/full suite did not expose immutable save drift; L17 falsification did.
- Scope statements must distinguish “foundation implemented” from “operational path active.”
- Remands are healthy back-pressure. This execution did not run a Court sealing lifecycle, so
  `Sealed | Remanded | Remediated` Court counts are not available and must not be fabricated.

## Action Items & Proposals

- [ ] Founder: decide whether to authorize a separate tracked-state/key migration for DEBT-0057.
- [ ] Founder/operator: rotate or refresh exposed Cline credentials and revoke old material.
- [ ] Keep this branch/worktree as-is; do not merge, push, or promote.
- [ ] Before unattended use, repay DEBT-0058 through Subproject 3 worker admission.
- [ ] If the Founder accepts Subproject 1 evidence, write and approve the separate Subproject 2
      Codex Overseer Adapter plan; do not start a live canary from this branch.
- [ ] Do not treat SoftLoop as the nineteen-layer lifecycle and do not resume SAKG work.
