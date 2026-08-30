"""Operational CLI tests for one-shot auditor receipt capture."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import ops.auditor_receipt_capture as cli
import pytest
from paeos.model_router.types import ModelFamily, ProviderId

_CANDIDATE = "adf76c61972554f71f2c863b3113f07d19dd1a52"
_EVIDENCE = "e" * 64


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
        f"Audit candidate { _CANDIDATE } with evidence {_EVIDENCE}.", encoding="utf-8"
    )
    receipt_path = tmp_path / "receipt.json"
    report_path = tmp_path / "report.md"
    calls: list[tuple[object, object, object]] = []
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

    def fake_capture(router: object, contract: object, request: object) -> object:
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
