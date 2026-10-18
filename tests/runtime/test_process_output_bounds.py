"""Synthetic process-boundary checks; no providers or host credentials."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import sys
import time
import tracemalloc
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace

import pytest
from runtime.integrations import process_supervisor
from runtime.integrations.process_supervisor import ProcessLifecycleState, run_bounded_process

CAP = 1024 * 1024  # Frozen response-envelope-derived operating limit, not the implementation value.


def _run(tmp_path: Path, code: str, deadline: float = 8.0):
    return run_bounded_process(
        (sys.executable, "-I", "-B", "-S", "-c", code),
        cwd=tmp_path,
        environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        start_timeout_s=1.0,
        execution_timeout_s=deadline,
        state_path=tmp_path / "process.json",
    )


def _emitter(streams: tuple[int, ...], size: int) -> str:
    return f"""
import os, threading
def emit(fd):
    value = (b'x' if fd == 1 else b'y') * {size}
    while value:
        value = value[os.write(fd, value):]
threads = [threading.Thread(target=emit, args=(fd,)) for fd in {streams!r}]
for thread in threads: thread.start()
for thread in threads: thread.join()
"""


@pytest.mark.parametrize("streams", [(1,), (2,), (1, 2)])
def test_overflow_retains_bounded_prefix_and_cannot_report_success(tmp_path, streams):
    observation = _run(tmp_path, _emitter(streams, CAP + 65536))
    assert observation.lifecycle_state is ProcessLifecycleState.FAILED
    assert len(observation.stdout) <= CAP
    assert len(observation.stderr) <= CAP
    state = json.loads((tmp_path / "process.json").read_text())
    assert state["terminal_state"] == "FAILED"
    assert state["output_limit_bytes"] == CAP
    assert state["capture_complete"] is False
    assert state["output_overflow_streams"]
    assert state["exit_code"] == observation.exit_code
    for name, captured in (("stdout", observation.stdout), ("stderr", observation.stderr)):
        assert state[name + "_bytes"] == len(captured)
        assert state[name + "_sha256"] == hashlib.sha256(captured).hexdigest()
        observed = state[name + "_observed_bytes"]
        assert len(captured) <= observed <= CAP + 65536
        assert state[name + "_truncated"] is (observed > len(captured))
        if name in state["output_overflow_streams"]:
            assert len(captured) == CAP
            assert state[name + "_truncated"]
    assert "output limit exceeded" in state["events"][-1]["reason"]


def test_exact_limit_is_complete_and_hashing_processes_each_captured_byte_once(
    tmp_path, monkeypatch
):
    hashed_stream_bytes = 0
    original_sha256 = hashlib.sha256

    class TrackedSha256:
        def __init__(self, value=b""):
            self.digest = original_sha256()
            self.update(value)

        def update(self, value):
            nonlocal hashed_stream_bytes
            if value[:1] in (b"x", b"y"):
                hashed_stream_bytes += len(value)
            self.digest.update(value)

        def hexdigest(self):
            return self.digest.hexdigest()

    monkeypatch.setattr(process_supervisor, "hashlib", SimpleNamespace(sha256=TrackedSha256))
    observation = _run(tmp_path, _emitter((1, 2), CAP))
    assert observation.lifecycle_state is ProcessLifecycleState.RETURNED
    assert observation.exit_code == 0
    assert len(observation.stdout) == len(observation.stderr) == CAP
    assert hashed_stream_bytes == 2 * CAP
    state = json.loads((tmp_path / "process.json").read_text())
    assert state["capture_complete"] is True
    assert state["output_overflow_streams"] == []
    assert state["stdout_truncated"] is state["stderr_truncated"] is False
    assert state["stdout_sha256"] == original_sha256(b"x" * CAP).hexdigest()
    assert state["stderr_sha256"] == original_sha256(b"y" * CAP).hexdigest()


def test_simultaneous_large_writers_keep_capture_allocations_bounded(tmp_path):
    tracemalloc.start()
    try:
        observation = _run(tmp_path, _emitter((1, 2), 4 * CAP))
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert observation.lifecycle_state is ProcessLifecycleState.FAILED
    assert len(observation.stdout) <= CAP
    assert len(observation.stderr) <= CAP
    # Allows bytearray-to-bytes copies plus chunks and bookkeeping; independent of child volume.
    assert peak < 8 * CAP, f"supervisor capture allocation peak: {peak}"


def test_overflow_is_failure_even_if_child_has_already_exited_zero(tmp_path, monkeypatch):
    terminate = process_supervisor._terminate
    exit_before_termination = []

    def await_zero_exit(process):
        # A controlled race: output is finite and the final write fits the kernel pipe.
        exit_before_termination.append(process.wait(timeout=2))
        terminate(process)

    monkeypatch.setattr(process_supervisor, "_terminate", await_zero_exit)
    observation = _run(tmp_path, _emitter((1,), CAP + 1))
    assert exit_before_termination == [0]
    assert observation.exit_code == 0
    assert observation.lifecycle_state is ProcessLifecycleState.FAILED
    assert json.loads((tmp_path / "process.json").read_text())["capture_complete"] is False


def test_overflow_kills_term_ignoring_descendant_after_leader_exit(tmp_path):
    child = (
        "import os,signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "Path('child-ready').write_text(str(os.getpid())); time.sleep(10)"
    )
    code = f"""
import os, subprocess, sys, time
from pathlib import Path
subprocess.Popen([sys.executable, '-I', '-B', '-S', '-c', {child!r}])
while not Path('child-ready').exists(): time.sleep(0.01)
value = b'x' * {CAP + 1}
while value: value = value[os.write(1, value):]
time.sleep(10)
"""
    child_pid = None
    try:
        observation = _run(tmp_path, code, deadline=3.0)
        child_pid = int((tmp_path / "child-ready").read_text())
        assert observation.lifecycle_state is ProcessLifecycleState.FAILED
        deadline = time.monotonic() + 1.0
        alive = True
        while time.monotonic() < deadline:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                alive = False
                break
            time.sleep(0.02)
        assert not alive, "synthetic descendant survived overflow"
    finally:
        if child_pid is None and (tmp_path / "child-ready").exists():
            child_pid = int((tmp_path / "child-ready").read_text())
        if child_pid is not None:
            with suppress(ProcessLookupError):
                os.kill(child_pid, signal.SIGKILL)


def test_read_failure_is_incomplete_and_remains_a_valid_failure_observation(tmp_path, monkeypatch):
    from ops.trusted_codex_worker_supervisor import _observation_facts
    from runtime.integrations.trusted_codex_transport import _validate_failure_observation

    class FailingRead:
        def __getattr__(self, name):
            return getattr(os, name)

        def read(self, _fd, _size):
            raise OSError("synthetic pipe read failure")

    # Inject only the collector's read failure; real launch, group termination and state writes run.
    monkeypatch.setattr(process_supervisor, "os", FailingRead())
    observation = _run(tmp_path, "import os,time; os.write(1,b'x'); time.sleep(2)")
    assert observation.lifecycle_state is ProcessLifecycleState.FAILED
    state = json.loads((tmp_path / "process.json").read_text())
    assert state["capture_complete"] is False
    assert state["output_overflow_streams"] == []
    assert state["events"][-1]["reason"] == "output read failed"
    facts = _observation_facts(observation)
    assert _validate_failure_observation(facts) == facts


def test_signal_termination_cannot_be_reported_as_returned():
    from runtime.integrations.trusted_codex_transport import (
        TrustedCodexTransportError,
        _validate_failure_observation,
    )

    with pytest.raises(TrustedCodexTransportError, match="exit code"):
        _validate_failure_observation(
            {
                "lifecycle_state": "RETURNED",
                "exit_code": -int(signal.SIGTERM),
                "stdout_bytes": 0,
                "stdout_sha256": hashlib.sha256(b"").hexdigest(),
                "stderr_bytes": 0,
                "stderr_sha256": hashlib.sha256(b"").hexdigest(),
            }
        )


@pytest.mark.parametrize("value", [-1_000_000, -int(signal.NSIG), True, 1.5])
def test_failure_observation_rejects_invalid_signal_or_exit_code(value):
    from runtime.integrations.trusted_codex_transport import (
        TrustedCodexTransportError,
        _validate_failure_observation,
    )

    with pytest.raises(TrustedCodexTransportError, match="exit code"):
        _validate_failure_observation(
            {
                "lifecycle_state": "FAILED",
                "exit_code": value,
                "stdout_bytes": 0,
                "stdout_sha256": hashlib.sha256(b"").hexdigest(),
                "stderr_bytes": 0,
                "stderr_sha256": hashlib.sha256(b"").hexdigest(),
            }
        )
