"""Bounded, observable execution for provider-backed worker processes.

This module is deliberately narrower than the PAEOS scheduler: it owns process launch and
observation only.  It never decides a lifecycle layer, creates Court evidence, or promotes an
artifact.  Every invocation has a durable state record and a finite start/execution deadline.
"""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import signal
import subprocess
import threading
import time
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

__all__ = [
    "ProcessLifecycleState",
    "ProcessObservation",
    "ProcessSupervisorError",
    "run_bounded_process",
]


class ProcessSupervisorError(ValueError):
    """A process configuration or persistence invariant failed before execution."""


class ProcessLifecycleState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    TIMED_OUT = "TIMED_OUT"
    FAILED = "FAILED"
    RETURNED = "RETURNED"


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    """Physical process observation; stdout/stderr are captured bytes, never caller claims."""

    argv: tuple[str, ...]
    executable: str
    executable_version: str
    cwd: str
    environment_fingerprint: str
    stdout: bytes
    stderr: bytes
    exit_code: int | None
    duration_ms: int
    lifecycle_state: ProcessLifecycleState


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _environment_fingerprint(environment: Mapping[str, str]) -> str:
    if any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in environment.items()
    ):
        raise ProcessSupervisorError("environment must contain only string keys and values")
    return _sha(_canonical(dict(sorted(environment.items()))))


def _resolve_executable(argv0: str, environment: Mapping[str, str]) -> Path:
    path = Path(argv0)
    if not path.is_absolute():
        search_path = environment.get("PATH", os.defpath)
        for directory in search_path.split(os.pathsep):
            candidate = Path(directory) / argv0
            if candidate.is_file() and os.access(candidate, os.X_OK):
                path = candidate
                break
        else:
            raise ProcessSupervisorError("executable must resolve to an absolute file")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ProcessSupervisorError("executable is unavailable") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ProcessSupervisorError("executable is not an executable regular file")
    return resolved


def _executable_version(path: Path) -> str:
    """Use an immutable binary digest as the version identity without launching a probe."""

    try:
        return "sha256:" + _sha(path.read_bytes())
    except OSError as exc:
        raise ProcessSupervisorError("executable identity cannot be measured") from exc


def _write_state(path: Path, state: dict[str, object]) -> None:
    path = Path(path)
    if not path.is_absolute():
        raise ProcessSupervisorError("lifecycle state path must be absolute")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = _canonical(state)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise ProcessSupervisorError("lifecycle state write made no progress")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _terminate(process: subprocess.Popen[bytes]) -> None:
    """Cancel the process group with bounded waits; never call communicate()."""

    with suppress(ProcessLookupError, OSError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=0.5)
        return
    except subprocess.TimeoutExpired:
        pass
    with suppress(ProcessLookupError, OSError):
        os.killpg(process.pid, signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired, OSError):
        process.wait(timeout=0.5)


def run_bounded_process(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    start_timeout_s: float,
    execution_timeout_s: float,
    state_path: Path,
) -> ProcessObservation:
    """Run one explicit process with bounded startup/execution and durable lifecycle state."""

    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ProcessSupervisorError("argv must be a non-empty tuple of non-empty strings")
    if not cwd.is_absolute() or not cwd.is_dir() or cwd.is_symlink():
        raise ProcessSupervisorError("cwd must be an absolute non-symlink directory")
    if start_timeout_s <= 0 or execution_timeout_s <= 0:
        raise ProcessSupervisorError("process deadlines must be positive")
    executable = _resolve_executable(argv[0], environment)
    executable_version = _executable_version(executable)
    env = dict(environment)
    environment_fingerprint = _environment_fingerprint(env)
    started_at = time.monotonic()
    state: dict[str, object] = {
        "schema": "paeos.process-lifecycle/1",
        "argv": list(argv),
        "executable": str(executable),
        "executable_version": executable_version,
        "cwd": str(cwd),
        "environment_fingerprint": environment_fingerprint,
        "pid": None,
        "events": [],
        "terminal_state": ProcessLifecycleState.NOT_STARTED.value,
        "exit_code": None,
        "stdout_sha256": _sha(b""),
        "stderr_sha256": _sha(b""),
    }

    def record(event_state: ProcessLifecycleState, *, reason: str, pid: int | None = None) -> None:
        events = state["events"]
        assert isinstance(events, list)
        events.append(
            {
                "state": event_state.value,
                "reason": reason,
                "elapsed_ms": int((time.monotonic() - started_at) * 1000),
            }
        )
        state["terminal_state"] = event_state.value
        if pid is not None:
            state["pid"] = pid
        _write_state(state_path, state)

    record(ProcessLifecycleState.NOT_STARTED, reason="invocation accepted")
    launch_finished = threading.Event()
    launch_result: dict[str, object] = {}

    def launch() -> None:
        try:
            launch_result["process"] = subprocess.Popen(
                list(argv),
                cwd=str(cwd),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                bufsize=0,
            )
        except (OSError, ValueError) as exc:
            launch_result["error"] = exc
        finally:
            launch_finished.set()

    threading.Thread(target=launch, name="paeos-provider-launch", daemon=True).start()
    if not launch_finished.wait(timeout=start_timeout_s):
        record(ProcessLifecycleState.TIMED_OUT, reason="launch acknowledgement deadline exceeded")

        def terminate_late_launch() -> None:
            launch_finished.wait()
            late_process = launch_result.get("process")
            if late_process is not None and hasattr(late_process, "pid"):
                _terminate(late_process)  # type: ignore[arg-type]

        threading.Thread(
            target=terminate_late_launch, name="paeos-late-launch-cleanup", daemon=True
        ).start()
        return ProcessObservation(
            argv=argv,
            executable=str(executable),
            executable_version=executable_version,
            cwd=str(cwd),
            environment_fingerprint=environment_fingerprint,
            stdout=b"",
            stderr=b"",
            exit_code=None,
            duration_ms=int((time.monotonic() - started_at) * 1000),
            lifecycle_state=ProcessLifecycleState.TIMED_OUT,
        )
    launch_error = launch_result.get("error")
    if launch_error is not None:
        record(ProcessLifecycleState.FAILED, reason="launch failed")
        assert isinstance(launch_error, (OSError, ValueError))
        raise ProcessSupervisorError("provider process failed to launch") from launch_error
    process_value = launch_result.get("process")
    if not isinstance(process_value, subprocess.Popen):
        record(ProcessLifecycleState.FAILED, reason="launch returned no process")
        raise ProcessSupervisorError("provider process failed to launch")
    process = process_value
    record(ProcessLifecycleState.STARTED, reason="launch acknowledged", pid=process.pid)

    assert process.stdout is not None and process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    stdout = bytearray()
    stderr = bytearray()
    execution_deadline = time.monotonic() + execution_timeout_s
    terminal: ProcessLifecycleState | None = None
    state["heartbeat_count"] = 0
    state["stdout_bytes"] = 0
    state["stderr_bytes"] = 0
    record(
        ProcessLifecycleState.RUNNING,
        reason="launch acknowledged; execution observation active",
        pid=process.pid,
    )
    try:
        while selector.get_map() or process.poll() is None:
            now = time.monotonic()
            deadline = execution_deadline
            if now >= deadline:
                _terminate(process)
                terminal = ProcessLifecycleState.TIMED_OUT
                record(terminal, reason="execution deadline exceeded", pid=process.pid)
                break
            events = (
                selector.select(timeout=min(0.5, max(0.0, deadline - now)))
                if selector.get_map()
                else []
            )
            if not events:
                state["heartbeat_count"] = int(state["heartbeat_count"]) + 1
                state["last_heartbeat_elapsed_ms"] = int((time.monotonic() - started_at) * 1000)
                _write_state(state_path, state)
                continue
            for key, _mask in events:
                try:
                    chunk = os.read(key.fileobj.fileno(), 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    with suppress(KeyError):
                        selector.unregister(key.fileobj)
                    continue
                if key.data == "stdout":
                    stdout.extend(chunk)
                    state["stdout_bytes"] = len(stdout)
                else:
                    stderr.extend(chunk)
                    state["stderr_bytes"] = len(stderr)
                state["heartbeat_count"] = int(state["heartbeat_count"]) + 1
                state["last_heartbeat_elapsed_ms"] = int((time.monotonic() - started_at) * 1000)
                state["stdout_sha256"] = _sha(bytes(stdout))
                state["stderr_sha256"] = _sha(bytes(stderr))
                _write_state(state_path, state)
        if terminal is None:
            exit_code = process.poll()
            if exit_code is None:
                _terminate(process)
                terminal = ProcessLifecycleState.TIMED_OUT
            else:
                terminal = (
                    ProcessLifecycleState.RETURNED
                    if exit_code == 0
                    else ProcessLifecycleState.FAILED
                )
            record(terminal, reason="process exited", pid=process.pid)
    finally:
        with suppress(Exception):
            selector.close()
        with suppress(OSError):
            process.stdout.close()
        with suppress(OSError):
            process.stderr.close()

    exit_code = process.poll()
    state["exit_code"] = exit_code
    state["stdout_sha256"] = _sha(bytes(stdout))
    state["stderr_sha256"] = _sha(bytes(stderr))
    _write_state(state_path, state)
    assert terminal is not None
    return ProcessObservation(
        argv=argv,
        executable=str(executable),
        executable_version=executable_version,
        cwd=str(cwd),
        environment_fingerprint=environment_fingerprint,
        stdout=bytes(stdout),
        stderr=bytes(stderr),
        exit_code=exit_code,
        duration_ms=int((time.monotonic() - started_at) * 1000),
        lifecycle_state=terminal,
    )
