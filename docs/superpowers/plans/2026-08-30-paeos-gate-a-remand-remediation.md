# PAEOS Gate A Remand Remediation Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with an independent verification checkpoint after each task. This plan is limited to Gate A evidence quality and worker-failure classification; it does not authorize live provider probes, Gate B-G advancement, ratification, or promotion.

**Goal:** Make Gate A remand evidence precise and non-vacuous while preserving the fail-closed boundary around credentialed worker admission.

**Architecture:** Keep Python as the sole admission-policy authority. Normalize raw transport failures before creating the typed rejection receipt, and validate the separate L14 report against the exact candidate/evidence contract before persistence. No change selects providers, retries a failed probe, reads credentials, or grants worker authority.

**Tech Stack:** Python 3.12+, frozen dataclasses, pytest, Ruff, Pyright, canonical JSON/hash evidence.

**Spec:** `docs/superpowers/specs/2026-08-30-paeos-auditor-physical-receipt-capture.md`, `docs/superpowers/plans/2026-08-29-paeos-cline-sdk-admission-adapter.md`, and `ledger/debt/DEBT-0058.md`.

## Global Constraints

- Preserve the eleven circuit breakers and never repeat the rejected live probe.
- Treat the worker as `UNADMITTED_BOOTSTRAP_CANDIDATE`; never close DEBT-0058 from these changes.
- Do not read, copy, hash, or log credentials or profile contents.
- Preserve raw stdout/stderr only as hashes in typed evidence receipts.
- Builder and Auditor physical families must remain distinct (`Builder != Auditor`).
- Do not modify `main`/`trunk`, merge, push, or advance Gate B-G.

---

### Task 1: Classify Raw Authentication Failures Precisely

**Files:**
- Modify: `runtime/integrations/cline_sdk.py`
- Test: `tests/runtime/test_cline_sdk_adapter.py`

**Interfaces:**
- Consumes: `_ProbeFailure` message and its raw stdout/stderr bytes.
- Produces: `AdapterFailureReceipt(normalized_error=NormalizedErrorType.AUTH_FAILED)` for explicit `AUTH_FAILED`, `Unauthorized`, or equivalent authentication text, with no retry and `SideEffectCertainty.PROVIDER_ACCEPTED`.

- [x] Step 1: Add a failing test that injects a transport failure whose structured message is generic but whose raw stderr contains `Unauthorized`, then assert the typed receipt is `AUTH_FAILED`.
- [x] Step 2: Run `uv run pytest -q tests/runtime/test_cline_sdk_adapter.py -k raw_auth` and confirm the new test fails because the current mapper returns `TRANSPORT_FAILED`.
- [x] Step 3: Implement a bounded, case-insensitive classifier over the already-captured failure message and raw bytes; do not persist raw content or perform a second call.
- [x] Step 4: Run the focused adapter tests, Ruff, and Pyright; confirm all pass.
- [x] Step 5: Commit as `fix(admission): preserve raw auth failure classification`.

### Task 2: Reject Vacuous or Incomplete L14 Reports Before Persistence

**Files:**
- Modify: `paeos/model_router/auditor_receipt.py`
- Modify: `ops/auditor_receipt_capture.py`
- Test: `tests/model_router/test_auditor_receipt.py`
- Test: `tests/ops/test_auditor_receipt_capture.py`

**Interfaces:**
- Consumes: `str` report content and `AuditorReceiptContract`.
- Produces: `validate_auditor_report(content, contract) -> None`, raising `AuditorReceiptError` unless the report is non-empty, names the exact candidate/evidence hashes, contains one allowed `L14_STATUS`, and includes `INVARIANT:` plus `REPRODUCTION:` lines for a remand.

- [x] Step 1: Add failing tests for missing candidate binding, missing status, and a remand without invariant/reproduction detail.
- [x] Step 2: Run the focused tests and confirm those tests fail against the current persistence path.
- [x] Step 3: Implement the pure validator and call it in the CLI before create-only report persistence.
- [x] Step 4: Add a passing fixture containing exact bindings, status, findings, `INVARIANT:`, and `REPRODUCTION:`.
- [x] Step 5: Run receipt/CLI tests, Ruff, Pyright, and the full suite; preserve any environment failures exactly.
- [x] Step 6: Commit as `fix(audit): require bound non-vacuous l14 findings`.

### Task 3: Record Remand Reconciliation and External Stop Boundary

**Files:**
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `ledger/debt/DEBT-0058.md`
- Create: `reviews/tasks/PAEOS_CLINE_SDK_ADMISSION_ADAPTER_L14_ANTIGRAVITY_002.md`

**Interfaces:**
- Consumes: the independently verified receipt/report hashes and Task 1-2 test outputs.
- Produces: durable evidence stating `REMAND_WITH_AMENDMENTS`, exact worker/Court counts, open static/L13 findings, and the non-secret operator prerequisite for a fresh probe.

- [ ] Step 1: Copy the exact receipt/report digests and disposition without changing the Court or debt status.
- [ ] Step 2: State that the report is a remand signal but not a clean L14 pass until the invariant/reproduction detail is present.
- [ ] Step 3: Record the only allowed next live action: a fresh SDK probe after a dedicated profile is authenticated and its non-secret UUID/auth epoch are supplied.
- [ ] Step 4: Run repository status and evidence-hash checks; commit as `docs(audit): reconcile gate a remand`.

### Stop Condition

After Task 3, stop before any credentialed probe. Task 10 requires a separately authorized operator authentication action, a frozen route tuple, and three new probe IDs; the first rejection stops the sequence. No Gate A closure, Court seal, Gate B-G implementation, or SAKG resumption follows automatically.
