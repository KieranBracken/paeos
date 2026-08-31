# PAEOS Two-Phase Auditor Adjudication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one-shot L14/L17 audits self-contained, causally valid, and qualified only by the
conjunction of a substantive PASS report and a post-response A-08 physical receipt.

**Architecture:** Add typed per-request retry/fallback policy to the existing PAEOS router, build
and validate one canonical substantive-audit prompt, then combine report and receipt results in a
typed fail-closed adjudication object. Defaults preserve all non-audit routing behavior.

**Tech Stack:** Python 3.12+, frozen dataclasses, enums, pytest, Ruff, Pyright, canonical SHA-256
evidence.

**Spec:** `docs/superpowers/specs/2026-08-31-paeos-two-phase-auditor-adjudication.md`

## Global Constraints

- Work only in `/private/tmp/paeos-control-plane-recovery-s1-clean-recovered`.
- Use RED-GREEN TDD for every behavior change and retain exact command output.
- PAEOS remains the single router policy authority; do not dispatch transport directly.
- No provider call, credential read, fallback, retry, Court change, gate seal, push, or promotion.
- Existing reports and receipts remain immutable and are never upgraded retroactively.

---

### Task 1: Enforce Typed No-Retry and No-Fallback Requests

**Files:**
- Modify: `paeos/model_router/types.py`
- Modify: `paeos/model_router/router.py`
- Modify: `paeos/model_router/auditor_receipt.py`
- Test: `tests/model_router/test_routing_policy.py`
- Test: `tests/model_router/test_auditor_receipt.py`

**Interfaces:**
- Produces: `RetryPolicy.NONE`, `RetryPolicy.SINGLE_RATE_LIMIT`.
- Produces: `TaskRequest.retry_policy` and `TaskRequest.allow_fallback` with compatible defaults.
- Consumed by: `ModelRouter.route()`, `_dispatch_with_single_retry()`, and request fingerprints.

- [ ] **Step 1: Write failing router behavior tests**

```python
def test_no_retry_policy_stops_after_first_short_429(mock_router):
    router, transport = mock_router
    transport.responses[(ProviderId.GOOGLE, "gemini-3.6-flash")] = [
        NormalizedError(
            error_type=NormalizedErrorType.RATE_LIMITED,
            message="short 429",
            provider_id=ProviderId.GOOGLE,
            model_id="gemini-3.6-flash",
            http_status=429,
            retry_after=0.05,
        ),
        RouterResponse(
            content="second call must never happen",
            model_id="gemini-3.6-flash",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
        ),
    ]
    request = TaskRequest(
        messages=[{"role": "user", "content": "one shot"}],
        logical_model=LogicalModel.PAEOS_STRONG,
        data_class=DataClass.PUBLIC,
    )
    request.retry_policy = "none"  # desired API value; current router ignores it
    request.allow_fallback = False
    with pytest.raises(NormalizedError):
        router.route(request)
    assert transport.call_history == [(ProviderId.GOOGLE, "gemini-3.6-flash")]

def test_no_fallback_stops_after_first_candidate_failure(mock_router):
    router, transport = mock_router
    transport.responses[(ProviderId.GOOGLE, "gemini-3.6-flash")] = NormalizedError(
        error_type=NormalizedErrorType.RATE_LIMITED,
        message="no fallback",
        provider_id=ProviderId.GOOGLE,
        model_id="gemini-3.6-flash",
        http_status=429,
        retry_after=30.0,
    )
    request = TaskRequest(
        messages=[{"role": "user", "content": "one route"}],
        logical_model=LogicalModel.PAEOS_STRONG,
        data_class=DataClass.PUBLIC,
    )
    request.allow_fallback = False
    with pytest.raises(NormalizedError):
        router.route(request)
    assert len(transport.call_history) == 1
```

- [ ] **Step 2: Run RED tests**

Run: `/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/model_router/test_routing_policy.py -k 'no_retry or no_fallback'`

Expected: test failures because the current router retries or falls back despite the requested
one-shot attributes. After GREEN, replace the literal with `RetryPolicy.NONE` without changing the
behavioral assertion.

- [ ] **Step 3: Implement the minimal typed routing controls**

Add the enum and compatible request defaults. Truncate the candidate chain when fallback is false;
skip the short-429 retry when retry policy is `NONE`. Add both values to `_request_payload()`.

- [ ] **Step 4: Run GREEN and compatibility tests**

Run: `/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/model_router/test_routing_policy.py tests/model_router/test_auditor_receipt.py`

Expected: all collected tests pass, including the existing default retry/fallback tests.

- [ ] **Step 5: Commit**

Commit message: `feat(router): enforce one-shot request policy`

### Task 2: Build and Validate Canonical Substantive Audit Prompts

**Files:**
- Create: `paeos/model_router/audit_prompt.py`
- Modify: `paeos/model_router/__init__.py`
- Create: `tests/model_router/test_audit_prompt.py`

**Interfaces:**
- Produces: `build_substantive_audit_prompt(candidate_sha, evidence_sha256, evidence_content,
  worker_counts, court_counts) -> str`.
- Produces: `validate_substantive_audit_prompt(content, candidate_sha, evidence_sha256) -> None`.
- Consumed by: Task 4 capture CLI integration.

- [ ] **Step 1: Write failing prompt behavior tests**

```python
def test_builder_embeds_evidence_and_separates_post_response_provenance():
    from paeos.model_router.audit_prompt import (
        build_substantive_audit_prompt,
        validate_substantive_audit_prompt,
    )
    prompt = build_substantive_audit_prompt(
        candidate_sha="a" * 40,
        evidence_sha256="e" * 64,
        evidence_content="sealed diff bytes",
        worker_counts=(0, 1, 0),
        court_counts=(0, 0, 0),
    )
    assert "sealed diff bytes" in prompt
    validate_substantive_audit_prompt(prompt, "a" * 40, "e" * 64)

def test_validator_rejects_path_only_or_self_referential_prompt():
    from paeos.model_router.audit_prompt import validate_substantive_audit_prompt
    with pytest.raises(AuditorPromptError):
        validate_substantive_audit_prompt(
            "review /private/tmp/bundle; receipt required",
            "a" * 40,
            "e" * 64,
        )
```

- [ ] **Step 2: Run RED tests**

Run: `/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/model_router/test_audit_prompt.py`

Expected: the tests fail inside their bodies with `ModuleNotFoundError` because the module does not
exist; pytest still collects and reports the intended missing behavior.

- [ ] **Step 3: Implement the pure builder and fail-closed validator**

Use exact phase markers, exact counts, a non-empty delimited evidence section, and the existing
three report statuses. Do not read files, credentials, or routes in this module.

- [ ] **Step 4: Run GREEN, Ruff, and Pyright**

Run the focused pytest file, Ruff on the new module/test, and Pyright on the same paths.

- [ ] **Step 5: Commit**

Commit message: `feat(audit): define substantive review prompt`

### Task 3: Add Conjunctive Report/Receipt Adjudication

**Files:**
- Modify: `paeos/model_router/auditor_receipt.py`
- Modify: `paeos/model_router/__init__.py`
- Test: `tests/model_router/test_auditor_receipt.py`

**Interfaces:**
- Produces: `AuditorReportStatus`.
- Produces: `AuditorArtifactAdjudication(report_status, a08_verdict, qualified)`.
- Produces: `adjudicate_auditor_artifact_pair(receipt_path, report_path, contract, catalog) ->
  AuditorArtifactAdjudication`.

- [ ] **Step 1: Write failing conjunctive behavior tests**

```python
def _bound_report(contract, status):
    return (
        f"Candidate SHA: {contract.candidate_sha256}\n"
        f"Evidence Bundle SHA-256: {contract.evidence_bundle_sha256}\n"
        "Worker: Admitted: 0 | Rejected: 1 | Remediated: 0\n"
        "Court: Sealed: 0 | Remanded: 0 | Remediated: 0\n"
        f"L14_STATUS: {status}\n"
    )

def test_valid_receipt_does_not_upgrade_blocked_report(tmp_path):
    request = _request()
    contract = _contract(
        request,
        expected_worker_counts=(0, 1, 0),
        expected_court_counts=(0, 0, 0),
    )
    report = _bound_report(contract, "BLOCKED_UNQUALIFIABLE")
    receipt = capture_auditor_receipt(
        FakeRouter(_response(request), _catalog()), contract, request
    )
    report_path = persist_auditor_report(report, tmp_path / "report.md")
    receipt_path = persist_auditor_receipt(
        bind_auditor_report(receipt, report), tmp_path / "receipt.json"
    )
    result = adjudicate_auditor_artifact_pair(
        receipt_path, report_path, contract, _catalog()
    )
    assert result.report_status is AuditorReportStatus.BLOCKED_UNQUALIFIABLE
    assert result.a08_verdict == "PASS"
    assert result.qualified is False

def test_substantive_pass_and_valid_a08_pair_qualify(tmp_path):
    request = _request()
    contract = _contract(request)
    report = _bound_report(contract, "PASS")
    receipt = capture_auditor_receipt(
        FakeRouter(_response(request), _catalog()), contract, request
    )
    report_path = persist_auditor_report(report, tmp_path / "report.md")
    receipt_path = persist_auditor_receipt(
        bind_auditor_report(receipt, report), tmp_path / "receipt.json"
    )
    result = adjudicate_auditor_artifact_pair(
        receipt_path, report_path, contract, _catalog()
    )
    assert result.qualified is True
```

- [ ] **Step 2: Run RED tests**

Run the two exact pytest node IDs and confirm missing-symbol failures.

- [ ] **Step 3: Implement minimal status parsing and adjudication**

Reuse existing report/pair validators. Do not add Court, seal, promotion, or mutation methods.

- [ ] **Step 4: Run GREEN plus receipt mutation tests**

Run the full auditor-receipt test module and confirm tampered pairs still fail closed.

- [ ] **Step 5: Commit**

Commit message: `feat(audit): combine report and physical receipt`

### Task 4: Integrate the One-Shot CLI and Record the Recovery Checkpoint

**Files:**
- Modify: `ops/auditor_receipt_capture.py`
- Modify: `tests/ops/test_auditor_receipt_capture.py`
- Modify: `docs/superpowers/specs/2026-08-30-paeos-auditor-physical-receipt-capture.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `operations/CURRENT_STATE.md`
- Modify: `MessyChangesNeedsReview.md`
- Create: `reviews/tasks/PAEOS_TWO_PHASE_AUDITOR_ADJUDICATION_review.md`

**Interfaces:**
- CLI validates the prompt before `ModelRouter()` construction.
- CLI requests `RetryPolicy.NONE` and `allow_fallback=False`.
- CLI output adds `report_status` and `qualified` without changing receipt schema.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_invalid_phase_prompt_fails_before_router_construction(tmp_path, monkeypatch):
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("review /private/tmp/bundle", encoding="utf-8")
    constructed = False

    def forbidden_router():
        nonlocal constructed
        constructed = True
        pytest.fail("router constructed")

    monkeypatch.setattr(cli, "ModelRouter", forbidden_router)
    assert cli.run(
        [
            "--audit-id", "audit-1",
            "--candidate-sha", _CANDIDATE,
            "--evidence-sha", _EVIDENCE,
            "--prompt-file", str(prompt_path),
            "--report-path", str(tmp_path / "report.md"),
            "--receipt-path", str(tmp_path / "receipt.json"),
        ]
    ) == 2
    assert constructed is False

# In test_run_uses_router_capture_and_emits_only_receipt_metadata, replace the
# prompt fixture with this canonical prompt and add the adjudication fake.
prompt_path.write_text(
    build_substantive_audit_prompt(
        candidate_sha=_CANDIDATE,
        evidence_sha256=_EVIDENCE,
        evidence_content="sealed evidence",
        worker_counts=(0, 1, 0),
        court_counts=(0, 0, 0),
    ),
    encoding="utf-8",
)
monkeypatch.setattr(
    cli,
    "adjudicate_auditor_artifact_pair",
    lambda receipt_path, report_path, contract, catalog: AuditorArtifactAdjudication(
        report_status=AuditorReportStatus.BLOCKED_UNQUALIFIABLE,
        a08_verdict="PASS",
        qualified=False,
    ),
)

# After the existing cli.run assertion, add these behavioral assertions.
request = calls[0][2]
assert request.retry_policy is RetryPolicy.NONE
assert request.allow_fallback is False
assert json.loads(capsys.readouterr().out)["qualified"] is False
```

- [ ] **Step 2: Run RED tests and verify the intended failures**

Run: `/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/ops/test_auditor_receipt_capture.py`

- [ ] **Step 3: Implement minimal CLI integration and spec amendment**

Keep rejection quarantine behavior unchanged. Update the Task 9A spec to state the two phases and
router-native one-shot policy.

- [ ] **Step 4: Run full verification**

Run focused tests; full non-gateway pytest; changed-path Ruff; changed-path Pyright;
`git diff --check`; and `git status --short`. Preserve exact counts and inherited static debt.

- [ ] **Step 5: Record L17 review and checkpoint**

The review must attempt to falsify all ten protocol dimensions and must state that a fresh physical
non-GLM audit is still required. Do not change `12/48`, worker counts, Court counts, or debt status.

- [ ] **Step 6: Commit**

Commit message: `fix(audit): separate substantive and physical gates`
