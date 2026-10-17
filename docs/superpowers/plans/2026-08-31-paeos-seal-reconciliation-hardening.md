# PAEOS Seal Reconciliation and Fail-Closed Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile unsupported Gate B–G seal claims and harden the new evidence, canary, provenance, and promotion paths so no incomplete artifact can be treated as sealed.

**Architecture:** Preserve the existing recovery branch and all raw receipts. Treat the `3e44133` Gemini receipt as valid only for that exact candidate; later commits require fresh evidence. Make lifecycle and Court reconciliation read-only and fail closed, make canary proof ordered and evidence-backed, and make promotion authority single-use and exact-ref bound without activating main/trunk changes.

**Tech Stack:** Python 3.13, frozen dataclasses, existing kernel ledger/CAS primitives, pytest, Ruff, Pyright, and the PAEOS model-router receipt contract.

**Spec:** `operations/ENGINEERING_LIFECYCLE.md`, `docs/superpowers/plans/2026-08-26-paeos-lifecycle-revalidation-sakg.md`, and `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`.

## Global Constraints

- Work only in `/private/tmp/paeos-control-plane-recovery-s1-clean-recovered`.
- Never modify or promote `main`/`trunk`; never delete raw receipts or rejected artifacts.
- No provider call, credential read, browser/CDP/clipboard/AppleScript action, retry, or fallback during local remediation.
- Builder and Auditor identity must be physical, candidate-bound, and fail closed on unknown or same-family evidence.
- Court counts come only from correlated ledger facts; documentation claims are observations, not evidence.
- SAKG remains paused while `DEBT-0058` or `DEBT-0060` is open.

## Task 1: Reconcile Seal Claims

**Files:** Create `reviews/tasks/PAEOS_GATE_SEAL_RECONCILIATION_review.md`; modify `operations/SAKG_RESUMPTION_MANIFEST.json`, `reviews/tasks/SAKG_RESUMPTION_DISPOSITION_review.md`, `operations/CURRENT_STATE.md`, `MessyChangesNeedsReview.md`, and the notebook.

- [ ] Record current `HEAD`, the exact `3e44133` receipt/report hashes, and the 41-file/2,727-line delta after that candidate.
- [ ] Classify the six later seal entries as `UNQUALIFIED_REMANDED`; preserve their commits and raw artifacts.
- [ ] Restore canonical accounting to the last defensible state (`12/48`, Worker `0/1/0`, Court `0/0/0`) unless a correlated ledger proves otherwise.
- [ ] Set the resumption disposition to `REMANDED_FOR_SPECIFIC_GAPS`; do not claim SAKG resumption.
- [ ] Commit documentation only after verifying the working tree contains no unrelated files.

## Task 2: Lifecycle and Court Fail-Closed Evidence

**Files:** Modify `runtime/lifecycle_audit.py` and `runtime/court_reconciliation.py`; extend `tests/runtime/test_lifecycle_audit.py` and `tests/runtime/test_court_reconciliation.py`.

- [ ] Add RED tests showing missing CAS/artifact evidence, missing required L13/L14/L17 records, duplicate or orphan Court dispositions, and unknown Builder/Auditor identity are rejected.
- [ ] Run the new tests once and capture the expected failures.
- [ ] Validate artifact hashes and required layer obligations against supplied read-only ledger/CAS inputs; do not infer execution from a stage row alone.
- [ ] Count only unique, correlated Court transactions and raise on unknown, conflicting, or same-family provenance.
- [ ] Run focused tests and static checks; commit the minimal implementation.

## Task 3: Canary and Promotion Safety

**Files:** Modify `runtime/autonomy/canary.py` and `runtime/autonomy/promotion.py`; extend `tests/runtime/autonomy/test_canary_harness.py`, `tests/runtime/autonomy/test_promotion_controller.py`, and `tests/kernel/test_promotion_policy.py`.

- [ ] Add RED tests for kill-without-install/reach, out-of-order events, empty evidence references, duplicate conflicting events, token reuse, stale target head, and missing exact-ref CAS.
- [ ] Run the tests once and capture expected failures.
- [ ] Require ordered installed → reached → killed events with exact failure code and non-empty evidence references.
- [ ] Bind promotion to a one-time authority consumption record and exact expected target head; keep actual ref mutation dormant unless a separately authorized Founder L16 action exists.
- [ ] Run focused tests and static checks; commit the minimal implementation.

## Task 4: Verification and Evidence Rebuild

- [ ] Remove only disposable `.pytest_cache`, `.ruff_cache`, and Python bytecode caches if needed to recover disk space; do not remove source, ledgers, receipts, or worktrees.
- [ ] Run focused tests, the complete suite, Ruff, Pyright, and `git diff --check` once each; preserve raw outputs and exit codes.
- [ ] Build a new candidate-bound bundle from the repaired `HEAD`; validate it locally without sending it.
- [ ] Obtain a fresh router-mediated non-GLM L14/L17 audit only when the Founder-authorized one-shot transport is available; never bypass the router or retry after failure.

## Completion Criteria

The branch is not considered complete until the reconciliation record is committed, all four fail-closed regressions pass, verification outputs are available, and Gate A/`DEBT-0058` plus `DEBT-0060` have explicit dispositions. No Gate B–G seal or SAKG resume claim is valid without a fresh candidate-bound L13/L14/L17 chain.
