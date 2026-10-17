"""Characterization tests for shell-free Codex/Antigravity supervisor wrappers."""

import hashlib
from pathlib import Path

import pytest
from kernel.types import ArtifactRef
from paeos.model_router.types import ModelFamily
from runtime.integrations.bridge_protocol import Disposition, ProtocolViolation
from runtime.supervisors.antigravity import AntigravitySupervisorAdapter
from runtime.supervisors.codex import CodexSupervisorAdapter
from runtime.supervisors.headless import (
    HeadlessResult,
    SupervisorAdapterError,
)
from runtime.supervisors.protocol import (
    SupervisorRequest,
    SupervisorResponse,
    encode_response,
)


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _request() -> SupervisorRequest:
    return SupervisorRequest(
        request_id="request-1",
        transaction_key="tx-1",
        nonce="nonce-1",
        checkpoint_hash=_hash("checkpoint"),
        policy_hash=_hash("policy"),
        task_class="ARCHITECTURE",
        prompt_hash=_hash("prompt"),
        context_manifest_hash=_hash("context"),
        allowed_dispositions=(Disposition.CONTINUE,),
    )


def _stdout() -> bytes:
    return encode_response(
        SupervisorResponse(
            request_id="request-1",
            transaction_key="tx-1",
            nonce="nonce-1",
            checkpoint_hash=_hash("checkpoint"),
            disposition=Disposition.CONTINUE,
            artifact_refs=(ArtifactRef(hash=_hash("artifact"), type="spec"),),
            rationale_ref=_hash("rationale"),
        )
    )


class FakeRunner:
    def __init__(self, result: HeadlessResult | Exception):
        self.result = result
        self.calls = []

    def run(self, invocation):
        self.calls.append(invocation)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _adapter(tmp_path: Path, runner: FakeRunner, cls=CodexSupervisorAdapter):
    executable = tmp_path / "supervisor"
    executable.write_bytes(b"pinned executable")
    return cls(
        runner=runner,
        executable=executable,
        executable_sha256=hashlib.sha256(b"pinned executable").hexdigest(),
        cwd=tmp_path,
        environment_keys=("PATH", "PAEOS_GATEWAY_KEY"),
        timeout_seconds=7.0,
    )


def _result(stdout: bytes | None = None, returncode: int = 0) -> HeadlessResult:
    return HeadlessResult(
        returncode=returncode,
        stdout=stdout or _stdout(),
        stderr=b"",
        provider="future-provider",
        actual_model_id="future/model-v1",
        model_family=ModelFamily.GLM,
        provider_request_id="provider-request-1",
        observed_at="2026-08-30T00:00:00+00:00",
        usage={"prompt_tokens": 3},
    )


def test_adapter_uses_fixed_shell_free_invocation_and_captures_observation(tmp_path: Path) -> None:
    runner = FakeRunner(_result())
    adapter = _adapter(tmp_path, runner)
    result = adapter.invoke(_request(), b"opaque context")
    invocation = runner.calls[0]
    assert invocation.argv == ("--headless-supervisor", "--json", str(tmp_path / "supervisor"))
    assert invocation.cwd == tmp_path
    assert invocation.stdin.startswith(b"{\"allowed_dispositions\":[\"CONTINUE\"]")
    assert invocation.timeout_seconds == 7.0
    assert invocation.environment_keys == ("PATH", "PAEOS_GATEWAY_KEY")
    assert result.observation.actual_model_id == "future/model-v1"
    assert result.observation.model_family is ModelFamily.GLM


def test_codex_and_antigravity_have_distinct_adapter_identity(tmp_path: Path) -> None:
    codex_runner = FakeRunner(_result())
    antigravity_runner = FakeRunner(_result())
    codex = _adapter(tmp_path, codex_runner, CodexSupervisorAdapter)
    antigravity = _adapter(tmp_path, antigravity_runner, AntigravitySupervisorAdapter)
    assert codex.invoke(_request(), b"").observation.adapter_id == "codex-headless"
    assert antigravity.invoke(_request(), b"").observation.adapter_id == "antigravity-headless"


def test_missing_or_drifted_binary_fails_before_runner(tmp_path: Path) -> None:
    runner = FakeRunner(_result())
    executable = tmp_path / "supervisor"
    executable.write_bytes(b"changed")
    adapter = CodexSupervisorAdapter(
        runner=runner,
        executable=executable,
        executable_sha256=_hash("original"),
        cwd=tmp_path,
    )
    with pytest.raises(SupervisorAdapterError, match="hash mismatch"):
        adapter.invoke(_request(), b"")
    assert runner.calls == []


def test_runner_failure_and_timeout_are_preserved_without_fallback(tmp_path: Path) -> None:
    failed = FakeRunner(_result(returncode=9))
    with pytest.raises(SupervisorAdapterError, match="returncode 9"):
        _adapter(tmp_path, failed).invoke(_request(), b"")
    assert len(failed.calls) == 1

    timed_out = FakeRunner(TimeoutError("deadline"))
    with pytest.raises(TimeoutError, match="deadline"):
        _adapter(tmp_path, timed_out).invoke(_request(), b"")
    assert len(timed_out.calls) == 1


def test_context_and_environment_boundaries_fail_closed(tmp_path: Path) -> None:
    runner = FakeRunner(_result())
    adapter = _adapter(tmp_path, runner)
    with pytest.raises(ProtocolViolation, match="environment_keys"):
        _adapter(tmp_path, runner).__class__(
            runner=runner,
            executable=tmp_path / "supervisor",
            executable_sha256=_hash("x"),
            cwd=tmp_path,
            environment_keys=("SECRET=value",),
        )
    with pytest.raises(ProtocolViolation, match="exceed envelope"):
        adapter.invoke(_request(), b"x" * 1_048_576)
