"""Task 4 tests for one-shot Cline transport and discriminative evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from paeos.model_router.types import ModelFamily
from runtime.integrations import cline_worker
from runtime.integrations.cline_worker import (
    ClineWorkerTransport,
    VerificationReceipt,
    run_discriminative_verification,
)
from runtime.worker_adapter import AdapterFailureKind, AdapterFailureReceipt
from runtime.worker_admission import AdmissionError, ProbeContract, RawWorkerRun

OLD_TEXT = "baseline-worker\n"
NEW_TEXT = "admitted-worker\n"
VERIFY = "python3 verify_probe.py"
PROVIDER = "cline-pass"
MODEL = "cline-pass/qwen3.8-max"
SESSION = "session-001"


@pytest.fixture()
def contract(tmp_path: Path) -> ProbeContract:
    return ProbeContract(
        probe_id="probe-001",
        sandbox=tmp_path / "probe" / "sandbox",
        provider_id=PROVIDER,
        model_id=MODEL,
        expected_family=ModelFamily.QWEN,
        artifact_name="artifact.txt",
        initial_bytes=OLD_TEXT.encode(),
        expected_bytes=NEW_TEXT.encode(),
        verification_command=VERIFY,
    )


@pytest.fixture()
def evidence_root(tmp_path: Path) -> Path:
    return tmp_path / "evidence"


@pytest.fixture()
def sandbox(contract: ProbeContract) -> Path:
    contract.sandbox.mkdir(parents=True)
    (contract.sandbox / contract.artifact_name).write_bytes(contract.expected_bytes)
    (contract.sandbox / "verify_probe.py").write_text(
        "import sys\n"
        'actual = open("artifact.txt", "rb").read()\n'
        'print("verified" if actual == b"admitted-worker\\n" else "rejected")\n'
        'sys.exit(0 if actual == b"admitted-worker\\n" else 1)\n'
    )
    return contract.sandbox


def _hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_discriminative_verification_runs_baseline_fail_candidate_pass_mutation_fail_restore_pass(
    contract: ProbeContract,
    sandbox: Path,
) -> None:
    receipt = run_discriminative_verification(contract)

    assert isinstance(receipt, VerificationReceipt)
    assert receipt.baseline_exit_code != 0
    assert receipt.candidate_exit_code == 0
    assert receipt.mutation_exit_code != 0
    assert receipt.restored_exit_code == 0
    assert receipt.baseline_artifact_hash == _hex(contract.initial_bytes)
    assert receipt.candidate_artifact_hash == _hex(contract.expected_bytes)
    assert receipt.mutation_hash == _hex(b"seeded-mutation\n")
    assert receipt.artifact_restored_hash == _hex(contract.expected_bytes)
    assert (contract.sandbox / contract.artifact_name).read_bytes() == contract.expected_bytes


def test_verification_receipt_hashes_stdout_stderr_and_exact_argv(
    contract: ProbeContract,
    sandbox: Path,
) -> None:
    receipt = run_discriminative_verification(contract)

    assert receipt.argv == ("python3", "verify_probe.py")
    assert receipt.argv_hash == _hex(b'["python3","verify_probe.py"]')
    for field in (
        receipt.baseline_stdout_hash,
        receipt.baseline_stderr_hash,
        receipt.candidate_stdout_hash,
        receipt.candidate_stderr_hash,
        receipt.mutation_stdout_hash,
        receipt.mutation_stderr_hash,
        receipt.restored_stdout_hash,
        receipt.restored_stderr_hash,
    ):
        assert len(field) == 64


def test_discriminative_verification_requires_admitted_candidate_bytes(
    contract: ProbeContract,
    sandbox: Path,
) -> None:
    (contract.sandbox / contract.artifact_name).write_bytes(contract.initial_bytes)

    with pytest.raises(AdmissionError, match="candidate artifact"):
        run_discriminative_verification(contract)


def test_discriminative_verification_restores_candidate_after_verifier_error(
    contract: ProbeContract,
    sandbox: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_verifier(
        argv: tuple[str, ...], verifier_sandbox: Path
    ) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(argv, 30)

    monkeypatch.setattr(cline_worker, "_run_verifier", fail_verifier)

    with pytest.raises(subprocess.TimeoutExpired):
        run_discriminative_verification(contract)

    assert (sandbox / contract.artifact_name).read_bytes() == contract.expected_bytes


class FakeClineProcess:
    """Popen-shaped process that emits fixture-owned structured Cline state."""

    def __init__(
        self,
        argv: list[str],
        *,
        stdout: Any,
        stderr: Any,
        env: dict[str, str],
        returncode: int = 0,
        finish_reason: str = "completed",
        run_model: str = MODEL,
        manifest_model: str = MODEL,
        message_model: str = MODEL,
        message_provider: str = PROVIDER,
        extra_manifest: bool = False,
        message_tool_names: tuple[str, ...] = ("editor", "run_commands"),
        message_tool_inputs: tuple[object, ...] | None = None,
        **_kwargs: Any,
    ) -> None:
        self.args = argv
        self.pid = 4242
        self.returncode = returncode
        self._polls = 0
        self.env = env
        sandbox = Path(argv[argv.index("-c") + 1])
        data_dir = Path(argv[argv.index("--data-dir") + 1])
        approval_dir = Path(env["CLINE_TOOL_APPROVAL_DIR"])
        session_dir = data_dir / "sessions" / SESSION
        session_dir.mkdir(parents=True)
        approval_dir.mkdir(parents=True)

        (sandbox / "artifact.txt").write_bytes(NEW_TEXT.encode())
        requests = (
            (
                "call-001",
                "editor",
                {
                    "path": str((sandbox / "artifact.txt").resolve()),
                    "old_text": OLD_TEXT,
                    "new_text": NEW_TEXT,
                },
            ),
            ("call-002", "run_commands", {"commands": [VERIFY]}),
        )
        for call_id, tool_name, tool_input in requests:
            payload = {
                "requestId": call_id,
                "sessionId": SESSION,
                "createdAt": "2026-08-26T10:00:00+00:00",
                "toolCallId": call_id,
                "toolName": tool_name,
                "input": tool_input,
                "iteration": 1,
            }
            (approval_dir / f"{SESSION}.request.{call_id}.json").write_text(json.dumps(payload))

        manifest_path = session_dir / f"{SESSION}.json"
        messages_path = session_dir / f"{SESSION}.messages.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "session_id": SESSION,
                    "source": "cli",
                    "pid": self.pid,
                    "exit_code": returncode,
                    "status": "completed" if returncode == 0 else "failed",
                    "interactive": False,
                    "provider": PROVIDER,
                    "model": manifest_model,
                    "cwd": str(sandbox),
                    "workspace_root": str(sandbox),
                    "enable_tools": True,
                    "enable_spawn": False,
                    "enable_teams": False,
                    "messages_path": str(messages_path),
                }
            )
        )
        if extra_manifest:
            (session_dir / "other.json").write_text("{}")

        tool_uses = [
            {
                "type": "tool_use",
                "id": f"call-00{index}",
                "name": name,
                "input": (
                    requests[index - 1][2]
                    if message_tool_inputs is None
                    else message_tool_inputs[index - 1]
                ),
            }
            for index, name in enumerate(message_tool_names, start=1)
        ]
        messages_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "sessionId": SESSION,
                    "origin": {"source": "cli", "sessionId": SESSION, "version": "3.0.56"},
                    "agent": "lead",
                    "messages": [
                        {
                            "id": "assistant-001",
                            "role": "assistant",
                            "modelInfo": {"provider": message_provider, "id": message_model},
                            "content": tool_uses,
                        }
                    ],
                }
            )
        )

        stdout.write(
            (
                json.dumps(
                    {
                        "type": "run_result",
                        "finishReason": finish_reason,
                        "model": {"provider": PROVIDER, "id": run_model},
                        "usage": {"inputTokens": 10, "outputTokens": 2},
                        "text": "worker prose is not evidence",
                    }
                )
                + "\n"
            ).encode()
        )
        stdout.flush()
        stderr.write(b"fixture-stderr\n")
        stderr.flush()

    def poll(self) -> int | None:
        self._polls += 1
        return None if self._polls == 1 else self.returncode

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


def _patch_popen(
    monkeypatch: pytest.MonkeyPatch,
    **overrides: Any,
) -> list[FakeClineProcess]:
    created: list[FakeClineProcess] = []
    original_popen = subprocess.Popen

    def factory(argv: list[str] | tuple[str, ...], **kwargs: Any) -> Any:
        # subprocess.run() also delegates to subprocess.Popen. Only replace the
        # Cline transport process; discriminative verifier commands must remain
        # real subprocesses.
        if not argv or argv[0] != "/opt/homebrew/bin/cline":
            return original_popen(argv, **kwargs)
        process = FakeClineProcess(argv, **kwargs, **overrides)
        created.append(process)
        return process

    monkeypatch.setattr(
        "runtime.integrations.cline_worker.shutil.which",
        lambda name: "/opt/homebrew/bin/cline" if name == "cline" else None,
    )
    monkeypatch.setattr("runtime.integrations.cline_worker.subprocess.Popen", factory)
    return created


def test_missing_cline_binary_fails_before_request(
    contract: ProbeContract,
    evidence_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("runtime.integrations.cline_worker.shutil.which", lambda _name: None)

    with pytest.raises(FileNotFoundError, match="cline"):
        ClineWorkerTransport().run_diagnostic_probe(contract, evidence_root)

    assert not evidence_root.exists()


def test_transport_captures_structured_receipt_and_exact_invocation(
    contract: ProbeContract,
    evidence_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _patch_popen(monkeypatch)

    run = ClineWorkerTransport(timeout_seconds=300).run_diagnostic_probe(contract, evidence_root)

    assert isinstance(run, RawWorkerRun)
    assert run.probe_id == contract.probe_id
    assert run.receipt.pid == 4242
    assert run.receipt.session_id == SESSION
    assert run.receipt.actual_provider_id == PROVIDER
    assert run.receipt.actual_model_id == MODEL
    assert run.receipt.message_models == (MODEL,)
    assert [decision.tool_name for decision in run.tool_decisions] == ["editor", "run_commands"]
    assert all(decision.approved for decision in run.tool_decisions)
    assert run.verification.candidate_exit_code == 0
    assert run.verification.mutation_exit_code != 0

    argv = created[0].args
    assert argv[:-1] == [
        "/opt/homebrew/bin/cline",
        "-P",
        PROVIDER,
        "-m",
        MODEL,
        "--json",
        "--auto-approve",
        "false",
        "--retries",
        "1",
        "--thinking",
        "medium",
        "-t",
        "300",
        "-c",
        str(contract.sandbox),
        "--data-dir",
        str(evidence_root / "cline-data"),
    ]
    assert "Perform exactly two tool calls" in argv[-1]
    assert created[0].env["CLINE_TOOL_APPROVAL_MODE"] == "desktop"
    assert created[0].env["CLINE_TOOL_APPROVAL_DIR"] == str(evidence_root / "approvals")
    assert created[0].env["CLINE_SANDBOX"] == "1"
    assert (evidence_root / "stdout.raw").stat().st_mode & 0o777 == 0o600
    assert (evidence_root / "stderr.raw").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"returncode": 2}, "CLI exit"),
        ({"finish_reason": "error"}, "finishReason"),
        ({"run_model": "cline-pass/deepseek-v4"}, "model mismatch"),
        ({"manifest_model": "cline-pass/deepseek-v4"}, "model mismatch"),
        ({"message_model": "cline-pass/deepseek-v4"}, "model mismatch"),
        ({"message_provider": "other-provider"}, "provider mismatch"),
        ({"extra_manifest": True}, "exactly one manifest"),
        ({"message_tool_names": ("read_files", "run_commands")}, "tool-use mismatch"),
        (
            {"message_tool_inputs": ({"path": "/wrong"}, {"commands": [VERIFY]})},
            "tool-use mismatch",
        ),
    ],
)
def test_transport_rejects_structural_or_identity_conflicts(
    contract: ProbeContract,
    evidence_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
    reason: str,
) -> None:
    _patch_popen(monkeypatch, **overrides)

    with pytest.raises(AdmissionError, match=reason):
        ClineWorkerTransport().run_diagnostic_probe(contract, evidence_root)


def test_worker_prose_cannot_override_structured_identity(
    contract: ProbeContract,
    evidence_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_popen(monkeypatch)

    run = ClineWorkerTransport().run_diagnostic_probe(contract, evidence_root)

    stdout = (evidence_root / "stdout.raw").read_text()
    assert "worker prose is not evidence" in stdout
    assert run.receipt.actual_model_id == MODEL


def test_legacy_cli_transport_is_mechanically_incapable_of_admission(
    contract: ProbeContract,
    evidence_root: Path,
) -> None:
    transport = ClineWorkerTransport()

    result = transport.run_probe(contract, evidence_root)

    assert transport.admission_capable is False
    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED
    assert not evidence_root.exists()
