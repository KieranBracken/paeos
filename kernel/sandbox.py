"""Sandboxed execution — resource-limited command runs (DEBT-0005 / 7.5 §T2 EXEC).

The court (B1.E) re-runs *agent-produced* commands to verify evidence (T2). Those commands are
untrusted, so they must run under limits. This module runs a command with **OS resource limits**
(CPU time, address space, file size, open files — `setrlimit`), a **wallclock timeout**, a **scoped
working directory**, and a **minimal environment**. Limits are applied best-effort per-platform (a
limit a platform rejects is skipped, not fatal), so it works on macOS and Linux CI alike.

Scope (honest boundary): this is the *portable resource* sandbox. Container-grade **filesystem
namespacing and network isolation** need containers/namespaces (docker, root) unavailable in this
environment; the `Sandbox` seam lets a container adapter drop in for production deploys. DEBT-0005
is thereby repaid for resource/DoS protection; container isolation remains a deploy-env task.
"""

from __future__ import annotations

import contextlib
import enum
import resource
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kernel.ledger import JsonValue

__all__ = [
    "FactKind",
    "RunFact",
    "SandboxError",
    "SandboxLimits",
    "SandboxResult",
    "allowlisted_path",
    "run_sandboxed",
    "sandbox_runner",
]

_MB = 1024 * 1024


class SandboxError(Exception):
    """The command could not be launched (empty/unresolvable), distinct from a nonzero exit."""


class FactKind(enum.StrEnum):
    """Typed run-report fact kinds (conservative reporting: mechanism-authored facts only).

    Worker-emitted stdout/stderr text is opaque payload — it is never parsed as, or
    laundered into, any of these facts.
    """

    REFUSAL = "REFUSAL"
    CAP_FIRED = "CAP_FIRED"
    TRUNCATION = "TRUNCATION"
    CLEANUP_ERROR = "CLEANUP_ERROR"
    ENFORCEMENT_FAILURE = "ENFORCEMENT_FAILURE"
    COMPLETION = "COMPLETION"


@dataclass(frozen=True, slots=True)
class RunFact:
    """A single mechanism-observed fact about a confined run.

    `os_fact` carries only mechanism-observed evidence (signal name, errno class,
    observed-vs-expected digest, observed byte count vs cap, ESRCH confirmation) —
    never free-text interpretation of worker output.
    """

    kind: FactKind
    dimension: str | None
    mechanism_id: str | None
    os_fact: str


def allowlisted_path() -> str:
    """The minimal PATH the sandbox permits for kernel-side executable resolution."""
    home_cargo = str(Path.home() / ".cargo" / "bin")
    home_local = str(Path.home() / ".local" / "bin")
    return f"{home_cargo}:{home_local}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    """Resource caps for a sandboxed run."""

    cpu_seconds: int = 10
    memory_bytes: int = 1024 * _MB
    file_size_bytes: int = 64 * _MB
    open_files: int = 256
    wallclock_s: int = 30


@dataclass(frozen=True, slots=True)
class SandboxResult:
    exit_code: int
    stdout: str
    timed_out: bool
    # Conservative-report extensions (backward compatible defaults; the legacy
    # court reproduce seam keeps constructing three-argument results):
    stderr: str = ""
    facts: tuple[RunFact, ...] = ()


def _apply_limits(limits: SandboxLimits) -> Callable[[], None]:
    def _preexec() -> None:  # runs in the child, before exec (POSIX)
        for res, soft in (
            (resource.RLIMIT_CPU, limits.cpu_seconds),
            (resource.RLIMIT_AS, limits.memory_bytes),
            (resource.RLIMIT_FSIZE, limits.file_size_bytes),
            (resource.RLIMIT_NOFILE, limits.open_files),
        ):
            # best-effort: a platform that rejects a limit skips it rather than crashing
            with contextlib.suppress(ValueError, OSError):
                resource.setrlimit(res, (soft, soft))

    return _preexec


def run_sandboxed(
    command: str,
    *,
    limits: SandboxLimits | None = None,
    cwd: str | Path | None = None,
) -> SandboxResult:
    """Run `command` (shell-free, `shlex`-split) under resource limits + a wallclock timeout, in a
    minimal environment. Returns exit code + stdout; a timeout yields `timed_out=True`."""
    lim = limits if limits is not None else SandboxLimits()
    args = shlex.split(command)
    if not args:
        raise SandboxError("empty command")
    env = {"PATH": allowlisted_path(), "LC_ALL": "C"}

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=lim.wallclock_s,
            check=False,
            preexec_fn=_apply_limits(lim),
            cwd=str(cwd) if cwd is not None else None,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(exit_code=-1, stdout="", timed_out=True)
    except (FileNotFoundError, OSError) as exc:
        raise SandboxError(f"could not launch {args[0]!r}: {exc}") from exc
    return SandboxResult(exit_code=proc.returncode, stdout=proc.stdout, timed_out=False)


def sandbox_runner(
    limits: SandboxLimits | None = None,
) -> Callable[[str], dict[str, JsonValue]]:
    """A `reproduce` runner (command → {exit_code, stdout}) backed by the sandbox. A timed-out run
    reports a nonzero exit so evidence claiming success is not reproduced."""

    def _run(command: str) -> dict[str, JsonValue]:
        result = run_sandboxed(command, limits=limits)
        exit_code = 124 if result.timed_out else result.exit_code  # 124 = conventional timeout code
        return {"exit_code": exit_code, "stdout": result.stdout}

    return _run
