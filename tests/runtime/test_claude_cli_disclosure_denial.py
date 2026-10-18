"""Claude CLI disclosure defaults to local denial until trusted authority is integrated."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from kernel.capability import CapabilityBroker
from kernel.types import Role, StageId
from nacl.signing import SigningKey
from runtime.integrations import ClaudeCodeRuntime, SessionSpec, TrustedTransportFailure
from runtime.task_package import Budget, Permissions, TaskPackage, TaskStatus

_SYNTHETIC_PROMPT = "SYNTHETIC_SECRET_MARKER_MUST_NOT_BE_ECHOED"


def _package() -> TaskPackage:
    broker = CapabilityBroker(SigningKey.generate())
    capability = broker.mint(
        goal_id="synthetic-goal",
        run_id="synthetic-run",
        stage=StageId.IMPLEMENT,
        role=Role.BUILDER,
        session="synthetic-session",
        operations=("mcp:artifacts",),
        issued_seq=0,
        expires_seq=10,
    )
    return TaskPackage(
        task_id="synthetic-task",
        goal_id="synthetic-goal",
        run_id="synthetic-run",
        stage=StageId.IMPLEMENT,
        role=Role.BUILDER,
        objective="synthetic objective",
        capability=capability,
        permissions=Permissions(("runtime/",), ("runtime/",), ("artifacts",)),
        required_evidence=(),
        context_refs=(),
        budget=Budget(100, 30, 0),
    )


def _launch_attempt_spies(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    import runtime.integrations as integ

    calls: list[str] = []

    def _prepare(*args: object, **kwargs: object) -> tuple[object, dict[str, str], None]:
        calls.append("prepare_provider_launch")
        return args[0], {}, None

    def _run(*args: object, **kwargs: object) -> object:
        calls.append("run_bounded_process")
        raise AssertionError("provider process boundary was reached")

    def _popen(*args: object, **kwargs: object) -> object:
        calls.append("subprocess.Popen")
        raise AssertionError("a subprocess was attempted")

    monkeypatch.setattr(integ, "prepare_provider_launch", _prepare, raising=False)
    monkeypatch.setattr(integ, "run_bounded_process", _run, raising=False)
    monkeypatch.setattr(subprocess, "Popen", _popen)
    return calls


def _assert_denied_without_launch(
    monkeypatch: pytest.MonkeyPatch, invoke: Callable[[], object]
) -> None:
    calls = _launch_attempt_spies(monkeypatch)
    with pytest.raises(TrustedTransportFailure) as raised:
        invoke()
    assert raised.value.code == "disclosure_authority_unavailable"
    assert _SYNTHETIC_PROMPT not in str(raised.value)
    assert calls == []


def _spec(tmp_path: Path) -> SessionSpec:
    return SessionSpec(
        workspace=tmp_path,
        prompt=_SYNTHETIC_PROMPT,
        allowed_tools=("Read", "Write"),
        read_scopes=("runtime/",),
        timeout_s=30,
        task_id="synthetic-task",
        goal_id="synthetic-goal",
        run_id="synthetic-run",
        stage="IMPLEMENT",
    )


def test_public_claude_cli_invoker_denies_locally_without_echo(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from runtime.integrations import claude_cli_invoker

    invoker = claude_cli_invoker(_package(), mcp_config_path=tmp_path / "synthetic-mcp.json")
    _assert_denied_without_launch(monkeypatch, lambda: invoker(_spec(tmp_path)))


def test_direct_bounded_session_helper_denies_locally_without_echo(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from runtime.integrations import _bounded_session_result

    _assert_denied_without_launch(
        monkeypatch,
        lambda: _bounded_session_result(
            _spec(tmp_path),
            ["claude", "-p", _SYNTHETIC_PROMPT],
            provider="claude",
        ),
    )


def test_runtime_records_bounded_denial_without_writes(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    calls = _launch_attempt_spies(monkeypatch)
    package = replace(_package(), objective=_SYNTHETIC_PROMPT)

    result = ClaudeCodeRuntime(workspace_root=tmp_path).run(package)

    assert result.status is TaskStatus.FAILED
    assert result.failure_code == "disclosure_authority_unavailable"
    assert result.trace == b"trusted_transport_failure:disclosure_authority_unavailable"
    assert _SYNTHETIC_PROMPT.encode() not in result.trace
    assert result.writes == ()
    assert calls == []
