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
import hashlib
import json
import resource
import shlex
import subprocess
import time
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
    "canonical_command",
    "run_sandboxed",
    "run_sandboxed_argv",
    "sandbox_runner",
    "structured_sandbox_runner",
]

_MB = 1024 * 1024
_FORBIDDEN_COMMAND_BYTES = frozenset(";&|<>`$")
_FORBIDDEN_EXECUTABLES = frozenset({"sh", "bash", "zsh", "fish", "env", "exec", "cd"})


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
    argv: tuple[str, ...] = ()
    executable: str = ""
    executable_version: str = ""
    cwd: str = ""
    environment_fingerprint: str = ""
    duration_ms: int = 0


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_argv(argv: tuple[str, ...], *, structured: bool) -> None:
    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise SandboxError("argv must be a non-empty tuple of non-empty strings")
    if not structured:
        return
    if any(any(character in _FORBIDDEN_COMMAND_BYTES for character in item) for item in argv):
        raise SandboxError("shell expansion is forbidden in structured argv")
    if Path(argv[0]).name in _FORBIDDEN_EXECUTABLES or "-c" in argv:
        raise SandboxError("shell and nested interpreter commands are forbidden")


def _validate_environment(environment: dict[str, str]) -> None:
    if any(key not in {"PATH", "LC_ALL"} for key in environment):
        raise SandboxError("structured command environment contains unsupported variables")
    if "PATH" in environment and environment["PATH"] != allowlisted_path():
        raise SandboxError("structured command PATH is not the kernel allowlist")
    if "LC_ALL" in environment and environment["LC_ALL"] != "C":
        raise SandboxError("structured command locale is not canonical")


def canonical_command(argv: tuple[str, ...], *, environment: dict[str, str] | None = None) -> str:
    """Encode one replayable command without shell syntax or host-specific cwd."""

    _validate_argv(argv, structured=True)
    if environment is not None:
        _validate_environment(environment)
    payload = {
        "argv": list(argv),
        "cwd": ".",
        "environment": environment if environment is not None else {"LC_ALL": "C"},
        "schema": "paeos.structured-command/1",
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _resolve_executable(argv0: str, env: dict[str, str]) -> Path:
    candidate = Path(argv0)
    if not candidate.is_absolute():
        for directory in env.get("PATH", allowlisted_path()).split(":"):
            path = Path(directory) / argv0
            if path.is_file() and path.stat().st_mode & 0o111:
                candidate = path
                break
        else:
            raise SandboxError(f"could not resolve executable {argv0!r}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise SandboxError(f"could not resolve executable {argv0!r}") from exc
    if not resolved.is_file() or not resolved.stat().st_mode & 0o111:
        raise SandboxError(f"executable {argv0!r} is not executable")
    return resolved


def _structured_command(command: str) -> tuple[tuple[str, ...], dict[str, str]] | None:
    try:
        value = json.loads(command)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    if value.get("schema") != "paeos.structured-command/1":
        raise SandboxError("structured command schema is invalid")
    if value.get("cwd") != ".":
        raise SandboxError("structured command cwd must be relative to the verifier workspace")
    argv = value.get("argv")
    environment = value.get("environment")
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(item, str) or not item for item in argv)
        or not isinstance(environment, dict)
        or any(not isinstance(key, str) or not isinstance(item, str) for key, item in environment.items())
    ):
        raise SandboxError("structured command fields are invalid")
    parsed_argv = tuple(argv)
    parsed_environment = dict(environment)
    _validate_argv(parsed_argv, structured=True)
    _validate_environment(parsed_environment)
    return parsed_argv, parsed_environment


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
    parsed = _structured_command(command)
    if parsed is None:
        args = tuple(shlex.split(command))
        env = {"PATH": allowlisted_path(), "LC_ALL": "C"}
    else:
        args, env = parsed
        env.setdefault("PATH", allowlisted_path())
        env.setdefault("LC_ALL", "C")
    return run_sandboxed_argv(
        args,
        limits=limits,
        cwd=cwd,
        environment=env,
        _legacy_command=parsed is None,
    )


def run_sandboxed_argv(
    argv: tuple[str, ...],
    *,
    limits: SandboxLimits | None = None,
    cwd: str | Path | None = None,
    environment: dict[str, str] | None = None,
    _legacy_command: bool = False,
) -> SandboxResult:
    """Execute explicit argv with captured streams and toolchain identity."""

    lim = limits if limits is not None else SandboxLimits()
    args = tuple(argv)
    _validate_argv(args, structured=not _legacy_command)
    env = dict(environment) if environment is not None else {"PATH": allowlisted_path(), "LC_ALL": "C"}
    env.setdefault("PATH", allowlisted_path())
    env.setdefault("LC_ALL", "C")
    executable = _resolve_executable(args[0], env)
    executable_version = "sha256:" + _sha(executable.read_bytes())
    actual_cwd = Path(cwd) if cwd is not None else Path.cwd()
    if not actual_cwd.is_absolute() or not actual_cwd.is_dir() or actual_cwd.is_symlink():
        raise SandboxError("cwd must be an absolute non-symlink directory")
    environment_fingerprint = _sha(
        json.dumps(dict(sorted(env.items())), sort_keys=True, separators=(",", ":")).encode()
    )
    started = time.monotonic()

    try:
        proc = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            timeout=lim.wallclock_s,
            check=False,
            preexec_fn=_apply_limits(lim),
            cwd=str(actual_cwd),
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return SandboxResult(
            exit_code=-1,
            stdout=stdout,
            timed_out=True,
            stderr=stderr,
            argv=args,
            executable=str(executable),
            executable_version=executable_version,
            cwd=str(actual_cwd),
            environment_fingerprint=environment_fingerprint,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except (FileNotFoundError, OSError) as exc:
        raise SandboxError(f"could not launch {args[0]!r}: {exc}") from exc
    return SandboxResult(
        exit_code=proc.returncode,
        stdout=proc.stdout,
        timed_out=False,
        stderr=proc.stderr,
        argv=args,
        executable=str(executable),
        executable_version=executable_version,
        cwd=str(actual_cwd),
        environment_fingerprint=environment_fingerprint,
        duration_ms=int((time.monotonic() - started) * 1000),
    )


def _is_structured_command(command: str) -> bool:
    try:
        value = json.loads(command)
    except (TypeError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and value.get("schema") == "paeos.structured-command/1"


def _physical_result(result: SandboxResult) -> dict[str, JsonValue]:
    """Return only verifier-owned, hash-based fields for a structured command."""

    return {
        "exit_code": 124 if result.timed_out else result.exit_code,
        "stdout_sha256": _sha(result.stdout.encode()),
        "stderr_sha256": _sha(result.stderr.encode()),
        "argv": list(result.argv),
        "executable": result.executable,
        "executable_version": result.executable_version,
        # Structured commands bind cwd logically to the verifier workspace.  The physical host
        # path is intentionally not part of the evidence identity, otherwise Builder and Court
        # could never reproduce the same command in two isolated workspaces.
        "cwd": ".",
        "environment_fingerprint": result.environment_fingerprint,
    }


def sandbox_runner(
    limits: SandboxLimits | None = None,
) -> Callable[[str], dict[str, JsonValue]]:
    """A `reproduce` runner (command → {exit_code, stdout}) backed by the sandbox. A timed-out run
    reports a nonzero exit so evidence claiming success is not reproduced."""

    def _run(command: str) -> dict[str, JsonValue]:
        result = run_sandboxed(command, limits=limits)
        if _is_structured_command(command):
            return _physical_result(result)
        exit_code = 124 if result.timed_out else result.exit_code  # 124 = conventional timeout code
        return {"exit_code": exit_code, "stdout": result.stdout}

    return _run


def structured_sandbox_runner(
    limits: SandboxLimits | None = None,
) -> Callable[[str], dict[str, JsonValue]]:
    """Return a hash-only runner for canonical commands and physical observations."""

    def _run(command: str) -> dict[str, JsonValue]:
        result = run_sandboxed(command, limits=limits)
        return _physical_result(result)

    return _run
