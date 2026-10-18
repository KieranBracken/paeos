"""Antigravity callable paths deny locally until trusted disclosure authority exists."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from runtime.integrations import SessionSpec, TrustedTransportFailure
from runtime.integrations import antigravity as antigravity

_PROMPT_MARKER = "SYNTHETIC_ANTIGRAVITY_PROMPT_MUST_NOT_BE_ECHOED"


class _PromptAccessBomb:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.timeout_s = 1

    @property
    def prompt(self) -> str:
        raise AssertionError("prompt was inspected before local denial")


class _ConfigAccessBomb:
    def exists(self) -> bool:
        raise AssertionError("MCP configuration was inspected before local denial")

    def read_text(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("MCP configuration was read before local denial")


class _Opaque:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"object attribute {name!r} was inspected before local denial")


def _deny_without_sensitive_echo(invoke: Callable[[], object]) -> None:
    with pytest.raises(TrustedTransportFailure) as raised:
        invoke()
    assert raised.value.code == "disclosure_authority_unavailable"
    assert _PROMPT_MARKER not in str(raised.value)


def test_cli_invoker_denies_before_prompt_access_or_bootstrap_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writes: list[str] = []
    launches: list[str] = []
    monkeypatch.setattr(
        antigravity.Path,
        "write_text",
        lambda _path, *_args, **_kwargs: writes.append("bootstrap"),
    )
    monkeypatch.setattr(
        antigravity.subprocess,
        "run",
        lambda *_args, **_kwargs: launches.append("subprocess"),
    )
    spec = _PromptAccessBomb(tmp_path)
    invoker = antigravity.antigravity_cli_invoker(_Opaque())

    _deny_without_sensitive_echo(lambda: invoker(spec))

    assert writes == []
    assert launches == []


def test_cli_invoker_denies_before_mcp_config_read_or_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writes: list[str] = []
    launches: list[str] = []
    monkeypatch.setattr(
        antigravity.Path,
        "write_text",
        lambda _path, *_args, **_kwargs: writes.append("bootstrap"),
    )
    monkeypatch.setattr(
        antigravity.subprocess,
        "run",
        lambda *_args, **_kwargs: launches.append("subprocess"),
    )
    spec = SessionSpec(
        workspace=tmp_path,
        prompt=_PROMPT_MARKER,
        allowed_tools=(),
        read_scopes=(),
        timeout_s=1,
    )
    invoker = antigravity.antigravity_cli_invoker(_Opaque(), mcp_config_path=_ConfigAccessBomb())

    _deny_without_sensitive_echo(lambda: invoker(spec))

    assert writes == []
    assert launches == []


def test_runtime_denies_before_workspace_or_context_setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    effects: list[str] = []
    monkeypatch.setattr(
        antigravity.tempfile,
        "mkdtemp",
        lambda *_args, **_kwargs: effects.append("workspace"),
    )
    monkeypatch.setattr(
        antigravity,
        "_seed_workspace",
        lambda *_args, **_kwargs: effects.append("seed_workspace"),
    )
    monkeypatch.setattr(
        antigravity,
        "_seed_constitution",
        lambda *_args, **_kwargs: effects.append("seed_constitution"),
    )
    monkeypatch.setattr(
        antigravity,
        "_materialize_context",
        lambda *_args, **_kwargs: effects.append("materialize_context"),
    )
    runtime = antigravity.AntigravityRuntime(workspace_root=tmp_path)

    _deny_without_sensitive_echo(lambda: runtime.run(_Opaque()))

    assert effects == []
