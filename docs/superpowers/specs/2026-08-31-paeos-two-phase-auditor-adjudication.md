# PAEOS Two-Phase Auditor Adjudication Design

**Status:** Founder-approved isolated recovery design; no Gate closure or promotion authority.

## Problem

PAEOS currently asks one external model to return an `L14_STATUS` while the physical receipt that
proves the model's identity is created only after that response returns. A self-contained Gemini
audit of candidate `a6e7270` therefore blocked on the absence of its own future receipt even though
the caller subsequently captured and validated that receipt. Earlier ad-hoc prompts also referred
to host-local evidence paths that a remote model could not read.

The capture path has a second mismatch: the receipt contract accepts only one provider attempt and
no fallback, but `ModelRouter` can still perform its normal short-429 retry and candidate fallback
before the receipt rejects the result. Post-response rejection is not equivalent to preventing an
unauthorized second transmission.

## Authority and Scope

This design repairs the existing Task 9A audit-evidence seam. It does not create a lifecycle state,
change L14 or L17 doctrine, ratify any candidate, close a debt, admit a worker, alter Court counts,
or authorize main/trunk promotion. The isolated recovery exception remains necessary because no
worker is admitted and the chat-bridge has no bound execution state.

## Invariants

1. **Substantive/physical separation:** the remote auditor judges only the sealed implementation
   evidence available in its request. PAEOS validates physical provenance after the response.
2. **Conjunctive qualification:** an audit qualifies only when the substantive report is `PASS`
   and the exact report-bound physical receipt passes A-08 and all receipt checks.
3. **No status upgrading:** a valid receipt never upgrades `REMAND_WITH_AMENDMENTS` or
   `BLOCKED_UNQUALIFIABLE` to `PASS`.
4. **Self-contained evidence:** canonical audit prompts embed non-empty evidence bytes and never
   depend on a host-local path being readable by the remote model.
5. **Router policy ownership:** no-retry/no-fallback behavior is expressed in a typed `TaskRequest`
   and enforced by `ModelRouter`; LiteLLM remains transport-only.
6. **One-shot evidence:** audit capture requests use `RetryPolicy.NONE` and
   `allow_fallback=False`. A provider failure ends the request without a second transmission.
7. **Immutable binding:** candidate SHA, evidence SHA-256, request fingerprint, response digest,
   report digest, provider/model/family, attempt count, and route remain bound exactly as today.
8. **No retroactive repair:** existing blocked reports remain blocked even when their receipts are
   valid. Only a fresh independently generated report can produce a new disposition.

## Design

### 1. Typed per-request routing limits

Add `RetryPolicy` to `paeos.model_router.types`:

```python
class RetryPolicy(str, Enum):
    NONE = "none"
    SINGLE_RATE_LIMIT = "single-rate-limit"
```

`TaskRequest` gains `retry_policy=RetryPolicy.SINGLE_RATE_LIMIT` and `allow_fallback=True`, so all
existing callers retain current behavior. `ModelRouter.route()` truncates the resolved candidate
chain to its first entry when fallback is disallowed. `_dispatch_with_single_retry()` retries a
short 429 only for `SINGLE_RATE_LIMIT`; `NONE` raises the first normalized error immediately.
These fields are included in the request fingerprint.

### 2. Canonical substantive-audit prompt

Create `paeos/model_router/audit_prompt.py` with a pure prompt builder and validator. The builder
accepts candidate SHA, evidence SHA-256, exact worker/Court counts, and UTF-8 evidence content. It
emits one canonical request containing these machine-readable declarations:

```text
AUDIT_PHASE: SUBSTANTIVE_EVIDENCE_REVIEW
PHYSICAL_RECEIPT_PHASE: POST_RESPONSE_CALLER_VALIDATION
PROVENANCE_ABSENCE_POLICY: DO_NOT_BLOCK_SUBSTANTIVE_REPORT
```

The prompt tells the auditor not to claim physical identity and not to treat the absence of its
future receipt as missing substantive evidence. It preserves the existing exact accounting and
status-line contract. The validator rejects missing/duplicate phase markers, empty embedded
evidence, missing candidate/evidence bindings, and path-only packages.

### 3. Typed combined adjudication

Add `AuditorReportStatus` and `AuditorArtifactAdjudication` to the receipt module. Report validation
returns the parsed status. `adjudicate_auditor_artifact_pair()` first validates the exact persisted
report/receipt pair and A-08, then returns:

```python
AuditorArtifactAdjudication(
    report_status=AuditorReportStatus.PASS,
    a08_verdict="PASS",
    qualified=True,
)
```

For `REMAND_WITH_AMENDMENTS` or `BLOCKED_UNQUALIFIABLE`, `qualified` is always false. Invalid or
unbound receipts continue to raise `AuditorReceiptError` rather than becoming prose dispositions.
This object is evidence metadata only; it has no Court, promotion, or ratification method.

### 4. Capture CLI integration

The capture CLI validates the canonical prompt before dispatch, constructs an audit request with
`RetryPolicy.NONE` and `allow_fallback=False`, and uses the combined adjudicator after persisting a
valid pair. It emits the report status and `qualified` flag alongside physical receipt metadata.
Provider-response validation failures continue to use the existing create-only rejection
quarantine. Pre-dispatch prompt failures make no provider call and create no report/receipt.

## Failure Semantics

- Invalid prompt: fail before router construction or provider contact.
- First provider failure: preserve normalized router telemetry and stop; no retry or fallback.
- Invalid report after a physical response: write the existing private quarantine triplet.
- Invalid receipt or A-08 mismatch: fail closed; never qualify the report.
- Valid receipt plus non-PASS report: persist the exact pair and return `qualified=false`.

## Verification

The change requires tests that would fail under the current implementation:

1. `RetryPolicy.NONE` prevents the short-429 retry.
2. `allow_fallback=False` prevents dispatch to a second candidate after primary failure.
3. canonical prompt construction embeds evidence and the post-response provenance boundary;
4. prompt validation rejects the causal contradiction and path-only input before router use;
5. valid receipt plus `BLOCKED_UNQUALIFIABLE` remains unqualified;
6. valid receipt plus substantive `PASS` qualifies;
7. invalid A-08 or report binding cannot qualify;
8. existing retry/fallback behavior remains unchanged for default requests;
9. existing report quarantine remains intact.

Focused model-router/CLI tests, the full non-gateway suite, changed-path Ruff, changed-path Pyright,
`git diff --check`, and clean-worktree verification are required before a local commit. Independent
L14/L17 evidence remains required afterward; implementation tests cannot self-ratify the repair.

