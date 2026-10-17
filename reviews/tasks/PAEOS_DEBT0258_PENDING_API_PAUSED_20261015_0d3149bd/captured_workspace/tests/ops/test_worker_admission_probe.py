"""Tests for the one-shot worker admission probe CLI utility (Task 4).

Plan: 2026-08-26-paeos-cline-worker-admission.md, lines 627-651.
Tests argument validation and safety constraints without launching Cline.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from paeos.model_router.types import ModelFamily
from runtime.worker_admission import (
    AdmissionError,
    PhysicalModelReceipt,
    RawWorkerRun,
    ToolDecisionRecord,
    VerificationReceipt,
)

from ops import worker_admission_probe

HEX = "a" * 64


def _admitted_run() -> RawWorkerRun:
    receipt = PhysicalModelReceipt(
        transport_id="headless:cline-cli:binary-hash",
        session_id="session-001",
        pid=4242,
        configured_provider_id="cline-pass",
        configured_model_id="cline-pass/qwen3.8-max",
        actual_provider_id="cline-pass",
        actual_model_id="cline-pass/qwen3.8-max",
        actual_family=ModelFamily.QWEN,
        manifest_provider_id="cline-pass",
        manifest_model_id="cline-pass/qwen3.8-max",
        message_models=("cline-pass/qwen3.8-max",),
        argv_hash=HEX,
        stdout_hash=HEX,
        stderr_hash=HEX,
        manifest_hash=HEX,
        messages_hash=HEX,
    )
    verification = VerificationReceipt(
        argv=("python3", "verify_probe.py"),
        argv_hash=HEX,
        baseline_artifact_hash=HEX,
        baseline_exit_code=1,
        baseline_stdout_hash=HEX,
        baseline_stderr_hash=HEX,
        candidate_artifact_hash=HEX,
        candidate_exit_code=0,
        candidate_stdout_hash=HEX,
        candidate_stderr_hash=HEX,
        mutation_hash=HEX,
        mutation_exit_code=1,
        mutation_stdout_hash=HEX,
        mutation_stderr_hash=HEX,
        artifact_restored_hash=HEX,
        restored_exit_code=0,
        restored_stdout_hash=HEX,
        restored_stderr_hash=HEX,
    )
    return RawWorkerRun(
        probe_id="test-probe",
        receipt=receipt,
        tool_decisions=(
            ToolDecisionRecord("editor", True, ""),
            ToolDecisionRecord("run_commands", True, ""),
        ),
        artifact_name="artifact.txt",
        artifact_hash=HEX,
        artifact_size=16,
        verification=verification,
    )


def _sdk_args(tmp_path: Path) -> list[str]:
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    qualification = tmp_path / "qualification.json"
    qualification.write_text(
        json.dumps(
            {
                "schema": "paeos.cline-sdk-qualification/1",
                "cline_version": "3.0.60",
                "sdk_version": "0.0.81",
                "core_version": "0.0.81",
                "node_version": "24.1.0",
                "node_executable": "/usr/bin/node",
                "node_sha256": "a" * 64,
                "package_root": str(tmp_path),
                "sdk_entrypoint": "/usr/bin/node",
                "core_entrypoint": "/usr/bin/node",
                "files": [],
                "required_symbols": [],
                "record_sha256": "b" * 64,
            }
        )
    )
    return [
        "--transport",
        "cline-sdk",
        "--qualification-record",
        str(qualification),
        "--profile-root",
        str(profile),
        "--profile-uuid",
        "12345678-1234-5678-1234-567812345678",
        "--auth-epoch",
        "1",
        "--node-executable",
        "/usr/bin/node",
    ]


def _run_probe_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the probe CLI utility and return the result."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ops.worker_admission_probe",
            "--transport",
            "cline-cli-diagnostic",
            *args,
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[2],
        timeout=10,
    )


def test_refuses_state_root_inside_git_worktree() -> None:
    """State root inside the Git worktree should be refused."""
    result = _run_probe_cli(
        "--state-root",
        str(Path(__file__).parents[2] / "state"),
        "--probe-id",
        "test-probe",
        "--provider",
        "cline-pass",
        "--model",
        "cline-pass/qwen3.8-max",
        "--expected-family",
        "qwen",
        "--timeout-seconds",
        "300",
        "--transport",
        "cline-cli-diagnostic",
    )
    assert result.returncode != 0
    assert "worktree" in result.stderr.lower() or "inside" in result.stderr.lower()


def test_refuses_existing_probe_id(tmp_path: Path) -> None:
    """Existing probe ID directory should be refused."""
    state_root = tmp_path / "runtime"
    probe_dir = state_root / "worker-admission" / "existing-probe"
    probe_dir.mkdir(parents=True)

    result = _run_probe_cli(
        "--state-root",
        str(state_root),
        "--probe-id",
        "existing-probe",
        "--provider",
        "cline-pass",
        "--model",
        "cline-pass/qwen3.8-max",
        "--expected-family",
        "qwen",
    )
    assert result.returncode != 0
    assert "exist" in result.stderr.lower()


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--state-root", "relative"), "absolute"),
        (("--probe-id", "../escape"), "probe"),
        (("--expected-family", "unknown"), "family"),
        (("--timeout-seconds", "0"), "timeout"),
    ],
)
def test_refuses_unsafe_or_unknown_arguments(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    args: tuple[str, str],
    message: str,
) -> None:
    argv = [
        "--state-root",
        str(tmp_path / "state"),
        "--probe-id",
        "test-probe",
        "--provider",
        "cline-pass",
        "--model",
        "cline-pass/qwen3.8-max",
        "--expected-family",
        "qwen",
        "--timeout-seconds",
        "300",
        "--transport",
        "cline-cli-diagnostic",
    ]
    option = argv.index(args[0])
    argv[option + 1] = args[1]

    assert worker_admission_probe.main(argv) == 2
    assert message in capsys.readouterr().err.lower()


def test_one_shot_success_writes_atomic_hash_only_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[object, Path]] = []
    run = _admitted_run()

    class FakeTransport:
        def __init__(self, config: object) -> None:
            assert config is not None

        def run_probe(self, contract: object) -> RawWorkerRun:
            calls.append((contract, tmp_path / "state" / "worker-admission" / "test-probe"))
            return run

    monkeypatch.setattr(worker_admission_probe, "ClineSdkAdmissionAdapter", FakeTransport)
    state_root = tmp_path / "state"
    code = worker_admission_probe.main(
        [
            "--state-root",
            str(state_root),
            "--probe-id",
            "test-probe",
            "--provider",
            "cline-pass",
            "--model",
            "cline-pass/qwen3.8-max",
            "--expected-family",
            "qwen",
            "--timeout-seconds",
            "17",
            *_sdk_args(tmp_path),
        ]
    )

    assert code == 0
    assert len(calls) == 1
    evidence_dir = state_root / "worker-admission" / "test-probe"
    result_path = evidence_dir / "admission-result.json"
    payload = __import__("json").loads(result_path.read_text())
    assert payload["verdict"] == "ADMITTED"
    assert payload["reason_codes"] == []
    assert payload["receipt_hash"] == run.receipt.receipt_hash
    assert payload["evidence"]["stdout_hash"] == HEX
    assert payload["evidence"]["verification"]["mutation_hash"] == HEX
    assert "text" not in str(payload).lower()
    assert not list(evidence_dir.glob("*.tmp"))
    assert evidence_dir.stat().st_mode & 0o777 == 0o700
    output = capsys.readouterr()
    assert output.err == ""
    assert set(line.split("=", 1)[0] for line in output.out.splitlines()) == {
        "probe_id",
        "verdict",
        "provider",
        "model",
        "family",
        "receipt_hash",
        "evidence_dir",
        "worker_counts",
        "court_counts",
    }


def test_one_shot_admission_failure_is_stable_and_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = 0

    class RejectingTransport:
        def __init__(self, config: object) -> None:
            pass

        def run_probe(self, contract: object) -> RawWorkerRun:
            nonlocal calls
            calls += 1
            raise AdmissionError("raw model output must not be printed")

    monkeypatch.setattr(worker_admission_probe, "ClineSdkAdmissionAdapter", RejectingTransport)
    state_root = tmp_path / "state"
    code = worker_admission_probe.main(
        [
            "--state-root",
            str(state_root),
            "--probe-id",
            "test-probe",
            "--provider",
            "cline-pass",
            "--model",
            "cline-pass/qwen3.8-max",
            "--expected-family",
            "qwen",
            *_sdk_args(tmp_path),
        ]
    )

    assert code == 1
    assert calls == 1
    result = (state_root / "worker-admission/test-probe/admission-result.json").read_text()
    assert '"reason_codes":["ADMISSION_REJECTED"]' in result
    output = capsys.readouterr()
    assert "raw model output" not in output.out + output.err
