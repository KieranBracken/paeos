# Constitutional Implementation Review: PAEOS_RUNTIME_STATE_MIGRATION_DEBT_0057

**Date**: 2026-08-25
**Task**: Repay DEBT-0057 through an evidence-aware runtime-state migration
**Reviewer Role**: Decorrelated Auditor / Temporary Architect-Overseer (Codex GPT-5.6 Sol)
**Builder Role**: Cline implementation-only (configured logical route: ClinePass GLM-5.3;
physical provider receipt not independently proven)
**Branch**: `codex/control-plane-recovery-s1-clean`
**Implementation HEAD reviewed**: `9c9301bb073f7b85844201faa47151bef6db689b`
**Disposition**: **IMPLEMENTATION_REPAID_OPERATOR_ACTION_OPEN — DO NOT PROMOTE**

## Summary of Findings

- **BLOCKER**: 2 inherited/operator gates: repository-wide static analysis remains red, and Cline
  credential rotation plus worker admission remain open.
- **MAJOR**: 0 open; 1 archive-permission defect found and remediated during L17.
- **MINOR**: 0.
- **OBSERVATION**: 4.

The task-local migration behavior is verified. This review does not ratify, merge, push, promote,
authorize a canary, activate a live adapter, or resume SAKG work.

## Verification Evidence

- Implementation commits:
  - `4577ffc22fa40909e4c6fbc7393b82000134c4f4` — explicit scorer persistence.
  - `ca72f6a642c6008d26384a42cf0dd2a2c1a22ac4` — migration utility and tests.
  - `a365308dd0e24275d4d1d5a7a14ec6fb07e12c90` — source-control hygiene boundary.
  - `9c9301bb073f7b85844201faa47151bef6db689b` — private archive directories.
- External archive:
  `/Users/bob/.local/share/paeos/forensic-archives/2026-08-25-main-pre-recovery`.
- Frozen source commit: `af83198192aef72e1ef88615e4ca586a449acb71`.
- Source/archive file count: `1447`.
- Source/archive manifest:
  `074ba61d10eabe916e8a26b0c2e0a6c4b5e948d02b0baa977d7d6c4b46db74a9`.
- Historical public fingerprint:
  `5cf2a3c51f151c46ab09dfbafb24fc7ae4b036056f2702784344c9753b75373b`.
- Fresh state root: `/Users/bob/.local/share/paeos/runtime-v2`.
- Fresh public fingerprint:
  `61db2228611acfb37d8325f731c5116915f10a804a2fedb5952a3e2b719296dd`.
- Focused suite before mutations: 13 passed, exit 0, stdout 80 bytes, stderr 0 bytes.
- Full suite: 545 passed, exit 0, stdout 640 bytes, stderr 0 bytes.
- Focused suite after mutations: 13 passed, exit 0, stdout 80 bytes, stderr 0 bytes.
- Four seeded mutations each failed with exit 1 for the intended reason:
  hidden scorer persistence created `.paeos_state`; existing archive reuse escaped the required
  `MigrationError`; historical-key reuse hit the fingerprint-equality refusal; removing the ignore
  rule made the source-hygiene probe return 1.
- L17 permission RED: archive directory mode was `0755` instead of `0700`, exit 1. The remediated
  four-test migration suite, focused Ruff, and focused Pyright all exit 0. The real archive and
  archived-state directories are now `0700`; the manifest is unchanged.
- Git boundary: `git ls-files .paeos_state` has empty stdout; 622 historical paths remain present
  and ignored in the worktree rather than being deleted.
- Static-analysis baseline comparison:
  - Ruff: pre-recovery 713 findings; reviewed branch 658 findings; stderr 0 bytes for both.
  - Pyright: pre-recovery 90 errors; reviewed branch 36 errors; stderr 0 bytes for both.
  These are inherited red gates, not a green result and not a regression from this recovery.
- Court accounting for this recovery: **Sealed: 0 | Remanded: 0 | Remediated: 0** because no Court
  lifecycle was invoked. The frozen historical ledger contains exactly 25 `SealCommitted` rows;
  it has no remand/remediation row kinds, so historical remand/remediation totals are unavailable.
  One stale, uncorrelated bridge output says `VERDICT: REMAND` and is not counted.

## Evaluation Checklist

### 1. Constitutional Compliance

**PASS FOR IMPLEMENTATION; NEEDS_FOUNDER FOR CLOSURE.** The work stayed in the approved isolated
recovery branch, preserved raw failures, did not retry identical failed commands without changed
rationale, did not self-ratify, and did not promote to main/trunk. Historical bytes were frozen
before Git tracking changed. The Founder remains the constitutional ratifier.

### 2. Architectural Drift

**PASS.** The change derives directly from DEBT-0057: persistence is explicit, historical state is
forensic-only, the new runtime state is a distinct trust domain, and CI rejects future tracked
runtime state. It does not claim that SoftLoop is the nineteen-layer lifecycle and does not alter
the live adapter or SAKG architecture.

### 3. Duplication of Mechanisms

**PASS.** The utility reuses kernel key generation, `SqliteLedgerStore`, and `Ledger` rather than
inventing a second signing or ledger format. Manifesting and create-only JSON are migration-local
because no existing helper provided the required three-snapshot fail-closed archive contract.

### 4. Bypassing Mechanisms

**PASS WITH WORKER WARNING.** The Founder explicitly authorized recovery without routing the
repair through the broken bridge. No unbound terminal paste or live bridge transaction occurred.
Cline nevertheless performed unauthorized searches/reads in several bounded tasks; those outputs
were independently checked and remain inadmissible for unattended autonomy under DEBT-0058.

### 5. Simpler Implementation Possible

**PASS.** The implementation is standard-library-heavy and one-shot. Its additional structure is
justified by create-only writes, source-drift detection, mode hashing, partial-evidence
preservation, and new-domain initialization. Empty directories are not represented in the file
manifest; this is acceptable for the current file-evidence contract but should not be generalized
into a complete filesystem-image claim.

### 6. Better Derivation

**PASS.** The safety proof is a direct equality chain: initial source manifest equals copied
archive manifest, which equals the post-copy source manifest. Trust separation is a direct public
fingerprint inequality. The archive permission defect found during review was remediated with the
stronger derived rule that both enclosing archive directories are created as `0700`.

### 7. Hidden Technical Debt

**RECORDED, NOT HIDDEN.** Repository-wide Ruff and Pyright remain failing inherited gates. Worker
command fidelity and physical model provenance remain DEBT-0058. Cross-process claim CAS for
Codex/Antigravity handoff remains DEBT-0059. None is relabeled as success or silently expanded into
this migration task.

### 8. Security Implications

**MAJOR REMEDIATED; OPERATOR ACTION OPEN.** The first real archive preserved the tracked key's
`0644` mode beneath `0755` directories. L17 detected this and commit `9c9301b` now creates both
enclosing directories as `0700`; the existing archive was tightened the same way without changing
its file manifest. The new runtime root, key, and trust descriptor are private. No key bytes were
printed. Remaining action: **Founder/operator must rotate or refresh the exposed Cline credentials
and revoke the old material.**

### 9. Runtime Implications

**PASS FOR THE MIGRATION UTILITY.** It is create-only, refuses destination reuse, checks source
drift, preserves partial archives for forensics, creates an empty genesis-anchored ledger, and has
no automatic retry. Process and open-file gates found no production-state writer before the real
migration. The continuously running model-router process held no `.paeos_state` handle.

### 10. Future Extensibility

**PASS WITH ADMISSION GATE.** External state roots and the public trust-domain descriptor give
Antigravity a stable handoff anchor. They do not solve worker admission, physical model receipts,
cross-process transaction CAS, or the live adapter. Those must be completed before overlapping
overseers or unattended execution.

## Action Items & Proposals

- [ ] Founder/operator: rotate or refresh the exposed Cline credentials and revoke old material.
- [ ] Founder: ratify or remand this implementation disposition; Codex does not self-ratify.
- [ ] File and execute a separately authorized cleanup for the inherited 658 Ruff findings and
      36 Pyright errors before any promotion that requires repository-wide static gates.
- [ ] Repay DEBT-0058 through Subproject 3 worker admission with a physical model receipt.
- [ ] Repay DEBT-0059 before simultaneous or overlapping Codex/Antigravity adapters.
- [ ] Do not start a canary, live adapter, SAKG work, or main/trunk promotion from this review.
