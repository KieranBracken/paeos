"""Synthetic regression for the retired Task 02 Codex entrypoint."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
APPROVED_SCRIPT_BODY = (
    b"#!/usr/bin/env bash\n"
    b"set -euo pipefail\n"
    b"\n"
    b"printf '%s\\n' 'Task 02 Codex execution is retired; provider and fallback execution are disabled.' >&2\n"
    b"exit 1\n"
)
REFUSAL = "Task 02 Codex execution is retired; provider and fallback execution are disabled."


def _fixed_script_path() -> Path:
    return REPOSITORY_ROOT / "ops" / "run_task02_codex.sh"


def _require_exact_retired_script(script_path: Path) -> None:
    if script_path != _fixed_script_path():
        raise RuntimeError("Task 02 test target is not the fixed repository entrypoint")
    if script_path.is_symlink() or not script_path.is_file():
        raise RuntimeError("Task 02 test target is not a regular repository file")
    if script_path.read_bytes() != APPROVED_SCRIPT_BODY:
        raise RuntimeError("Task 02 test target differs from the exact retired refusal body")


def test_task02_script_refuses_without_invoking_provider_or_fallback(tmp_path: Path) -> None:
    script_path = _fixed_script_path()
    _require_exact_retired_script(script_path)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "client-calls.txt"

    for name in ("codex", "fallback"):
        executable = fake_bin / name
        executable.write_text(
            f"#!/bin/sh\nprintf '%s\\n' '{name}' >> \"$PAEOS_TASK02_CALL_LOG\"\nexit 0\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)

    date = fake_bin / "date"
    date.write_text("#!/bin/sh\nprintf '%s\\n' '2026-10-19T00:00:00Z'\n", encoding="utf-8")
    date.chmod(0o755)

    result = subprocess.run(
        ["/bin/bash", str(script_path)],
        cwd=tmp_path,
        env={
            "HOME": str(tmp_path),
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": str(fake_bin),
            "PAEOS_TASK02_CALL_LOG": str(calls),
            "TMPDIR": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    observed_calls = calls.read_text(encoding="utf-8") if calls.exists() else "<none>"
    assert result.returncode == 1, (
        f"expected fixed refusal, got {result.returncode}; fake calls: {observed_calls}"
    )
    assert result.stdout == ""
    assert result.stderr == REFUSAL + "\n"
    assert not calls.exists(), f"fake provider/fallback invoked: {observed_calls}"


def test_unapproved_script_path_is_rejected_without_execution(tmp_path: Path) -> None:
    marker = tmp_path / "unsafe-script-was-run"
    unapproved = tmp_path / "caller-selected.sh"
    unapproved.write_text(f"#!/bin/sh\nprintf '%s\\n' ran > '{marker}'\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="fixed repository entrypoint"):
        _require_exact_retired_script(unapproved)

    assert not marker.exists()


def test_caller_environment_cannot_redirect_script_or_prompt_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PAEOS_TASK02_SCRIPT", str(tmp_path / "caller-selected.sh"))
    monkeypatch.setenv("PAEOS_TASK02_PROMPT_FILE", str(tmp_path / "caller-selected-prompt.txt"))
    monkeypatch.setenv("PROMPT_FILE", str(tmp_path / "caller-selected-prompt.txt"))

    fixed_path = _fixed_script_path()
    expected_path = Path(__file__).resolve().parents[2] / "ops" / "run_task02_codex.sh"
    assert fixed_path == expected_path
    _require_exact_retired_script(fixed_path)
