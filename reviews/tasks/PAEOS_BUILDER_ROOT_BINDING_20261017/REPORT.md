# Builder source/runtime root binding recovery checkpoint

Date: 2026-10-17
Branch: `codex/builder-qualification-bootstrap-20261017`
Base: `codex/pre-p3-clean-recovery-20261017`

## Scope and result

This checkpoint adds a narrow binding to the trusted Builder supervisor installer. The reviewed recovery checkout supplies the immutable code bundle; the explicitly selected runtime checkout supplies the interpreter, task queue, workspace, qualification records, and existing public verification identities. Omitting either option preserves the installer’s previous single-root behavior. Root paths must be absolute, existing directories and are resolved before use.

Four isolated installer tests cover default and partial bindings, fail-closed invalid roots, helper-level separation, and a mocked end-to-end install. The end-to-end test creates different source and runtime sentinels, then confirms the bundle contains only reviewed-source bytes, LaunchAgent runtime paths resolve under the runtime root, and all runtime files and existing request/response identities remain byte-for-byte unchanged. The supervisor activation is mocked; this test does not claim a live host install or worker start.

## PAEOS lifecycle evidence

Two fresh production Trace-B runs were preserved. `r-440d04b7` completed early lifecycle requests through CRITIQUE and stopped before Builder because the ordered L08 design and L09 findings artifacts were missing. `r-dec883cf` recorded lifecycle stage completions through ADVERSARIAL_REVIEW and was remanded at L10 with `CandidateIntegrityError`: the sealed-context verifier requires the configured physical model identity and signed envelope, while ChatBridge supplied only its compatibility identity. Neither run started Builder, produced a Builder response, reached Court, or qualified a task.

The recorded stages are physical execution observations only. They do not prove independent-family review, Court adjudication, or qualification. The local PAEOS run directories and raw response files remain outside this public checkpoint.

## Verification

- Installer tests: 4 passed.
- Existing trusted transport/readiness/client tests: 43 passed.
- Combined focused set: 47 passed.
- Ruff lint, Ruff formatting, Python bytecode compilation, and `git diff --check`: passed.
- The required full-suite attempt failed during collection with seven import errors for the unavailable `contracts.adapters` package. The failure affected four contract collectors and three runtime transport collectors loaded through the host’s shared editable environment. It was run once and not retried.
- Secret scan: no high-confidence credential matches across the branch-diff files and explicit implementation/evidence payload; paths and content hashes are recorded in `secret-scan.json`. The receipt and final manifest are checked again after generation.

## Gate disposition

**DEBT-0258 — owner: Chat 1, sole integrator.** `ALLOWED_NOW`: source/runtime binding checkpoint and the selected read-only Security Review. `HELD`: host installation, the single already-authorized fresh-ID `gpt-5.6-sol` qualification request, and a fresh admitted PAEOS DEBT-0258 task. Wake only after clean Security Review plus a fresh empty-queue/no-active-supervisor/bundle-hash/existing-identity preflight. An ambiguous qualification request is terminal; do not retry it.

**DEBT-0249 — owner: its existing separate worker.** `ALLOWED_NOW`: preserve its candidate and continue provider-free eligible work under its existing scope. `HELD`: a different-family review and any review-dependent adjudication or integration. Wake only when an eligible free route passes the current privacy and quota gates. Do not transport-switch a refused or consumed operation.

**DEBT-0260 — owner: separate worker not yet dispatched.** `ALLOWED_NOW`: none in this checkpoint. `HELD`: implementation and qualification. Wake only after DEBT-0258 qualifies, then use a fresh admitted PAEOS task and its own verification.

**DEBT-0117 — owner: its existing separate worker.** `ALLOWED_NOW`: preserve the successor and its explicit full-autonomy deferral. `HELD`: physical pre-P3 proof. Wake only after DEBT-0258 and DEBT-0260 qualify, then prove recursive remediation, genuine remand recovery, production-entrypoint restart, and exactly-once child/parent resumption.

**P3 — owner: PAEOS governance/Court.** `ALLOWED_NOW`: none. `HELD`: promotion. Wake only after every required pre-P3 gate has sealed evidence and the distinct Court observation, Court adjudication, and qualification requirements are satisfied.

The current authority/implementation gap is the missing accepted L10 sealed-context evidence path for the available ChatBridge runtime, together with the expired signed Builder qualification. This checkpoint changes no provider route, makes no provider call, installs no host bundle, and claims no Court disposition or P3 readiness.
