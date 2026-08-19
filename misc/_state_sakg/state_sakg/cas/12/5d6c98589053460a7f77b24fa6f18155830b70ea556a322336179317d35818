"""DEBT-0005 tests — the resource-limited sandbox runs commands and reports results."""

from __future__ import annotations

import pytest
from kernel.sandbox import SandboxError, SandboxLimits, run_sandboxed, sandbox_runner


def test_runs_a_command_and_captures_output() -> None:
    result = run_sandboxed("echo hello")
    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert result.timed_out is False


def test_nonzero_exit_is_reported() -> None:
    assert run_sandboxed("false").exit_code == 1


def test_wallclock_timeout() -> None:
    result = run_sandboxed("sleep 5", limits=SandboxLimits(wallclock_s=1))
    assert result.timed_out is True


def test_empty_command_raises() -> None:
    with pytest.raises(SandboxError):
        run_sandboxed("   ")


def test_unlaunchable_command_raises() -> None:
    with pytest.raises(SandboxError):
        run_sandboxed("this_binary_does_not_exist_xyz123")


def test_sandbox_runner_shape() -> None:
    run = sandbox_runner()
    assert run("echo ok") == {"exit_code": 0, "stdout": "ok\n"}


def test_timeout_reported_as_nonzero_by_runner() -> None:
    run = sandbox_runner(SandboxLimits(wallclock_s=1))
    assert run("sleep 5")["exit_code"] == 124  # a timed-out run never looks like success
