"""Operational CLI tests for one-shot auditor receipt capture."""

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import ops.auditor_receipt_capture as cli
import pytest
from paeos.model_router.audit_prompt import build_substantive_audit_prompt
from paeos.model_router.auditor_receipt import (
    AUDITOR_RECEIPT_SCHEMA,
    AuditorArtifactAdjudication,
    AuditorReportStatus,
    PhysicalAuditorReceipt,
    load_auditor_receipt,
)
from paeos.model_router.types import ModelFamily, ProviderId, RetryPolicy, TaskRequest

_CANDIDATE = "adf76c61972554f71f2c863b3113f07d19dd1a52"
_EVIDENCE = "e" * 64


def _physical_receipt() -> PhysicalAuditorReceipt:
    return PhysicalAuditorReceipt(
        schema=AUDITOR_RECEIPT_SCHEMA,
        audit_id="audit-1",
        invocation_id="audit-1:invocation",
        session_id="audit-1-session",
        candidate_sha256=_CANDIDATE,
        evidence_bundle_sha256=_EVIDENCE,
        review_scope_sha256="a" * 64,
        builder_provider="cline-pass",
        builder_model_id="z-ai/glm-5.3-flash",
        builder_family=ModelFamily.GLM,
        configured_provider_id=ProviderId.GOOGLE,
        configured_model_id="gemini-3.6-flash",
        actual_provider_id=ProviderId.GOOGLE,
        actual_model_id="gemini-3.6-flash",
        actual_family=ModelFamily.GEMINI,
        transport_id="paeos-model-router:google:gemini-3.6-flash:test",
        provider_attempt_count=1,
        fallback_chain=("google:gemini-3.6-flash",),
        transport_request_sha256="b" * 64,
        transport_response_sha256="c" * 64,
        transcript_sha256="d" * 64,
        captured_at_unix=1_788_132_345.0,
        a08_verdict="PASS",
    )


def test_parse_args_rejects_noncanonical_hashes() -> None:
    with pytest.raises(SystemExit):
        cli._parse_args(
            [
                "--audit-id",
                "audit-1",
                "--candidate-sha",
                "A" * 40,
                "--evidence-sha",
                _EVIDENCE,
                "--prompt-file",
                "/tmp/prompt.md",
                "--report-path",
                "/tmp/report.md",
                "--receipt-path",
                "/tmp/receipt.json",
            ]
        )


def test_run_uses_router_capture_and_emits_only_receipt_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt_path = tmp_path / "prompt.md"
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
    receipt_path = tmp_path / "receipt.json"
    report_path = tmp_path / "report.md"
    calls: list[tuple[object, object, TaskRequest]] = []
    receipt = SimpleNamespace(
        receipt_sha256="r" * 64,
        actual_provider_id=ProviderId.GOOGLE,
        actual_model_id="gemini-3.6-flash",
        actual_family=ModelFamily.GEMINI,
        provider_attempt_count=1,
    )
    bound_receipt = SimpleNamespace(
        receipt_sha256="b" * 64,
        actual_provider_id=ProviderId.GOOGLE,
        actual_model_id="gemini-3.6-flash",
        actual_family=ModelFamily.GEMINI,
        provider_attempt_count=1,
    )

    report = (
        f"Candidate SHA: {_CANDIDATE}\n"
        f"Evidence Bundle SHA-256: {_EVIDENCE}\n"
        "Worker: Admitted: 0 | Rejected: 1 | Remediated: 0\n"
        "Court: Sealed: 0 | Remanded: 0 | Remediated: 0\n"
        "`L14_STATUS`: **PASS**\n"
        "Findings: independent findings\n"
    )
    interaction = SimpleNamespace(receipt=receipt, response_content=report)

    def fake_capture(router: object, contract: object, request: TaskRequest) -> object:
        calls.append((router, contract, request))
        return interaction

    def fake_persist(value: object, path: Path) -> Path:
        assert value is bound_receipt
        path.write_text("{}\n", encoding="utf-8")
        return path

    def fake_persist_report(content: str, path: Path) -> Path:
        assert content == report
        path.write_text(content, encoding="utf-8")
        return path

    def fake_bind(value: object, content: str) -> object:
        assert value is receipt
        assert content == report
        return bound_receipt

    def fake_validate(
        value: object, contract: object, catalog: object, *, require_report_binding: bool
    ) -> object:
        assert value is bound_receipt
        assert require_report_binding is True
        return SimpleNamespace(passed=True)

    router = SimpleNamespace(catalog=object())
    monkeypatch.setattr(cli, "ModelRouter", lambda: router)
    monkeypatch.setattr(cli, "capture_auditor_interaction", fake_capture)
    monkeypatch.setattr(cli, "bind_auditor_report", fake_bind)
    monkeypatch.setattr(cli, "validate_auditor_receipt", fake_validate)
    monkeypatch.setattr(
        cli,
        "adjudicate_auditor_artifact_pair",
        lambda receipt_path, report_path, contract, catalog: AuditorArtifactAdjudication(
            report_status=AuditorReportStatus.BLOCKED_UNQUALIFIABLE,
            a08_verdict="PASS",
            qualified=False,
        ),
    )
    monkeypatch.setattr(cli, "persist_auditor_report", fake_persist_report)
    monkeypatch.setattr(cli, "persist_auditor_receipt", fake_persist)

    assert (
        cli.run(
            [
                "--audit-id",
                "audit-1",
                "--candidate-sha",
                _CANDIDATE,
                "--evidence-sha",
                _EVIDENCE,
                "--prompt-file",
                str(prompt_path),
                "--report-path",
                str(report_path),
                "--receipt-path",
                str(receipt_path),
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    assert "gemini-3.6-flash" in output.out
    assert str(report_path) in output.out
    assert "audit result" not in output.out
    assert output.err == ""
    assert len(calls) == 1
    request = calls[0][2]
    assert request.retry_policy is RetryPolicy.NONE
    assert request.allow_fallback is False
    assert request.max_tokens == 512
    system_content = request.messages[0]["content"]
    assert "first six non-blank lines" in system_content
    assert "Do not emit a preamble" in system_content
    assert json.loads(output.out)["qualified"] is False


def test_invalid_phase_prompt_fails_before_router_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("review /private/tmp/bundle; receipt required", encoding="utf-8")
    constructed = False

    def forbidden_router() -> object:
        nonlocal constructed
        constructed = True
        pytest.fail("router constructed")

    monkeypatch.setattr(cli, "ModelRouter", forbidden_router)

    assert (
        cli.run(
            [
                "--audit-id",
                "audit-1",
                "--candidate-sha",
                _CANDIDATE,
                "--evidence-sha",
                _EVIDENCE,
                "--prompt-file",
                str(prompt_path),
                "--report-path",
                str(tmp_path / "report.md"),
                "--receipt-path",
                str(tmp_path / "receipt.json"),
            ]
        )
        == 2
    )
    assert constructed is False


def test_run_rejects_prompt_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("prompt", encoding="utf-8")
    link = tmp_path / "prompt.md"
    link.symlink_to(target)

    assert (
        cli.run(
            [
                "--audit-id",
                "audit-1",
                "--candidate-sha",
                _CANDIDATE,
                "--evidence-sha",
                _EVIDENCE,
                "--prompt-file",
                str(link),
                "--report-path",
                str(tmp_path / "report.md"),
                "--receipt-path",
                str(tmp_path / "receipt.json"),
            ]
        )
        == 2
    )


def test_run_quarantines_invalid_provider_report_with_exact_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt_path = tmp_path / "prompt.md"
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
    report_path = tmp_path / "report.md"
    receipt_path = tmp_path / "receipt.json"
    rejected_report_path = tmp_path / "report.md.rejected"
    rejected_receipt_path = tmp_path / "receipt.json.rejected"
    rejection_path = tmp_path / "receipt.json.rejection.json"
    invalid_report = (
        f"Candidate SHA: {_CANDIDATE}\n"
        f"Evidence Bundle SHA-256: {_EVIDENCE}\n"
        "Worker: Admitted: 1 | Rejected: 0 | Remediated: 0\n"
        "Court: Sealed: 0 | Remanded: 0 | Remediated: 0\n"
        "L14_STATUS: PASS\n"
    )
    receipt = _physical_receipt()
    interaction = SimpleNamespace(receipt=receipt, response_content=invalid_report)
    monkeypatch.setattr(cli, "ModelRouter", lambda: SimpleNamespace(catalog=object()))
    monkeypatch.setattr(
        cli, "capture_auditor_interaction", lambda router, contract, request: interaction
    )

    assert (
        cli.run(
            [
                "--audit-id",
                "audit-1",
                "--candidate-sha",
                _CANDIDATE,
                "--evidence-sha",
                _EVIDENCE,
                "--prompt-file",
                str(prompt_path),
                "--report-path",
                str(report_path),
                "--receipt-path",
                str(receipt_path),
            ]
        )
        == 2
    )

    assert not report_path.exists()
    assert not receipt_path.exists()
    assert rejected_report_path.read_text(encoding="utf-8") == invalid_report
    assert load_auditor_receipt(rejected_receipt_path) == receipt
    rejection = json.loads(rejection_path.read_text(encoding="utf-8"))
    assert rejection == {
        "audit_id": "audit-1",
        "candidate_sha256": _CANDIDATE,
        "evidence_bundle_sha256": _EVIDENCE,
        "reason": "worker accounting mismatch",
        "receipt_path": str(rejected_receipt_path),
        "receipt_sha256": receipt.receipt_sha256,
        "report_path": str(rejected_report_path),
        "report_sha256": hashlib.sha256(invalid_report.encode("utf-8")).hexdigest(),
        "schema": "paeos.auditor-rejection/1",
    }
    assert stat.S_IMODE(rejected_report_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(rejected_receipt_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(rejection_path.stat().st_mode) == 0o600
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "AUDITOR_RECEIPT_REJECTED:worker accounting mismatch\n"
