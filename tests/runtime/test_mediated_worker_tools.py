from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from runtime.integrations.mediated_worker_tools import (
    MediatedWorkerError,
    MediatedWorkerTools,
    WorkerToolScope,
)


def _scope(workspace: Path) -> WorkerToolScope:
    return WorkerToolScope(
        workspace=workspace,
        artifacts={"sample": "src/sample.txt"},
        patch_targets={"sample": "src/sample.txt"},
        tests={"unit": (sys.executable, "-c", "print('TEST_OK')")},
    )


def _sample_workspace(root: Path) -> Path:
    workspace = root / "workspace"
    source = workspace / "src" / "sample.txt"
    source.parent.mkdir(parents=True)
    source.write_text("before\n", encoding="utf-8")
    return workspace


def test_tool_inventory_is_only_parent_mediated_and_has_closed_schemas(tmp_path: Path) -> None:
    tools = MediatedWorkerTools(_scope(_sample_workspace(tmp_path)))
    definitions = tools.list_tools()

    assert {item["name"] for item in definitions} == {
        "read_artifact",
        "propose_patch",
        "run_test",
    }
    annotations = {item["name"]: item.get("annotations") for item in definitions}
    assert annotations == {
        "read_artifact": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "propose_patch": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "run_test": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    }
    for item in definitions:
        schema = item["inputSchema"]
        assert schema["additionalProperties"] is False
        assert not {"command", "argv", "cwd", "workspace", "sandbox", "receipt_key"} & set(
            schema["properties"]
        )


def test_scope_serialization_rejects_sandbox_command_and_caller_receipt_key(
    tmp_path: Path,
) -> None:
    scope = _scope(_sample_workspace(tmp_path))
    encoded = json.loads(scope.to_json())
    assert set(encoded) == {"schema", "workspace", "artifacts", "patch_targets", "tests"}

    for forbidden in ("sandbox", "command", "receipt_key", "environment"):
        forged = dict(encoded)
        forged[forbidden] = "caller-controlled"
        with pytest.raises(MediatedWorkerError):
            WorkerToolScope.from_mapping(forged)


def test_read_artifact_uses_parent_id_and_denies_path_arguments(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    tools = MediatedWorkerTools(_scope(workspace))

    result = tools.invoke("read_artifact", {"artifact_id": "sample"})
    assert result["text"] == "before\n"
    assert result["sha256"] == hashlib.sha256(b"before\n").hexdigest()
    with pytest.raises(MediatedWorkerError, match="arguments"):
        tools.invoke("read_artifact", {"artifact_id": "sample", "path": "../../etc/passwd"})
    with pytest.raises(MediatedWorkerError):
        tools.invoke("read_artifact", {"artifact_id": "../../etc/passwd"})


def test_read_artifact_rejects_symlinked_target_and_outside_sentinel(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE_SENTINEL", encoding="utf-8")
    target = workspace / "src" / "sample.txt"
    target.unlink()
    target.symlink_to(outside)

    with pytest.raises(MediatedWorkerError):
        MediatedWorkerTools(_scope(workspace)).invoke("read_artifact", {"artifact_id": "sample"})
    assert outside.read_text(encoding="utf-8") == "OUTSIDE_SENTINEL"


def test_propose_patch_applies_only_exact_parent_bound_target(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    tools = MediatedWorkerTools(_scope(workspace))
    expected = hashlib.sha256(b"before\n").hexdigest()
    unified_diff = "--- a/src/sample.txt\n+++ b/src/sample.txt\n@@ -1 +1 @@\n-before\n+after\n"

    result = tools.invoke(
        "propose_patch",
        {"patch_id": "sample", "expected_sha256": expected, "unified_diff": unified_diff},
    )
    assert result["applied"] is True
    assert result["sha256"] == hashlib.sha256(b"after\n").hexdigest()
    assert (workspace / "src" / "sample.txt").read_text(encoding="utf-8") == "after\n"


@pytest.mark.parametrize(
    "patch_id, expected_sha256, unified_diff",
    [
        (
            "sample",
            "0" * 64,
            "--- a/src/sample.txt\n+++ b/src/sample.txt\n@@ -1 +1 @@\n-before\n+after\n",
        ),
        (
            "../../outside.txt",
            "0" * 64,
            "--- a/src/sample.txt\n+++ b/src/sample.txt\n@@ -1 +1 @@\n-before\n+after\n",
        ),
        (
            "sample",
            hashlib.sha256(b"before\n").hexdigest(),
            "--- a/../../outside.txt\n+++ b/../../outside.txt\n@@ -1 +1 @@\n-before\n+after\n",
        ),
    ],
)
def test_propose_patch_rejects_stale_or_unbound_patch(
    tmp_path: Path, patch_id: str, expected_sha256: str, unified_diff: str
) -> None:
    workspace = _sample_workspace(tmp_path)
    tools = MediatedWorkerTools(_scope(workspace))
    with pytest.raises(MediatedWorkerError):
        tools.invoke(
            "propose_patch",
            {
                "patch_id": patch_id,
                "expected_sha256": expected_sha256,
                "unified_diff": unified_diff,
            },
        )
    assert (workspace / "src" / "sample.txt").read_text(encoding="utf-8") == "before\n"
    assert not (tmp_path / "outside.txt").exists()


def test_run_test_accepts_only_parent_named_test_and_fixed_argv(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    tools = MediatedWorkerTools(_scope(workspace))

    result = tools.invoke("run_test", {"test_id": "unit"})
    assert result["exit_code"] == 0
    assert result["stdout"] == "TEST_OK\n"
    with pytest.raises(MediatedWorkerError):
        tools.invoke("run_test", {"test_id": "unit", "command": "touch escaped"})
    with pytest.raises(MediatedWorkerError):
        tools.invoke("run_test", {"test_id": "arbitrary"})


def test_run_test_child_inherits_seatbelt_write_denial(tmp_path: Path) -> None:
    import uuid

    workspace = _sample_workspace(tmp_path)
    outside = Path("/private/tmp") / f"paeos-run-test-escape-{uuid.uuid4().hex}"
    script = (
        "from pathlib import Path\n"
        f"path = Path({str(outside)!r})\n"
        "try:\n"
        "    path.write_text('unexpected', encoding='utf-8')\n"
        "except OSError:\n"
        "    print('DENIED')\n"
        "else:\n"
        "    path.unlink(missing_ok=True)\n"
        "    print('WRITTEN')\n"
    )
    scope = WorkerToolScope(
        workspace=workspace,
        artifacts={},
        patch_targets={},
        tests={"outside-write": (sys.executable, "-c", script)},
    )

    result = MediatedWorkerTools(scope).invoke("run_test", {"test_id": "outside-write"})

    assert result["exit_code"] == 0
    assert result["stdout"] == "DENIED\n"


def test_unknown_or_shell_tool_calls_fail_closed(tmp_path: Path) -> None:
    tools = MediatedWorkerTools(_scope(_sample_workspace(tmp_path)))
    for name, arguments in (
        ("shell", {"command": "touch escaped"}),
        ("exec_command", {"cmd": "touch escaped"}),
        ("apply_patch", {"patch": "unbounded"}),
    ):
        with pytest.raises(MediatedWorkerError):
            tools.invoke(name, arguments)


def test_stdio_mcp_server_reports_exact_tool_inventory(tmp_path: Path) -> None:
    import base64
    import subprocess

    workspace = _sample_workspace(tmp_path)
    scope = _scope(workspace)
    env = {
        "PATH": os.defpath,
        "PAEOS_TASK_SCOPE_B64": base64.b64encode(scope.to_json().encode()).decode(),
    }
    server = Path(__file__).parents[2] / "runtime/integrations/mediated_worker_tools.py"
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    proc = subprocess.run(
        [sys.executable, str(server), "--stdio"],
        input="".join(json.dumps(item) + "\n" for item in requests),
        text=True,
        capture_output=True,
        env=env,
        cwd=workspace,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    responses = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert responses[0]["result"]["serverInfo"]["name"] == "paeos-mediated-worker"
    assert {item["name"] for item in responses[1]["result"]["tools"]} == {
        "read_artifact",
        "propose_patch",
        "run_test",
    }


@pytest.mark.parametrize("operation", ["read", "patch"])
def test_conf01_fifo_without_writer_is_rejected_before_blocking(
    tmp_path: Path, operation: str
) -> None:
    import contextlib
    import signal
    import subprocess

    workspace = _sample_workspace(tmp_path)
    leaf = workspace / "src/sample.txt"
    leaf.unlink()
    os.mkfifo(leaf)
    module_path = Path(__file__).parents[2] / "runtime/integrations/mediated_worker_tools.py"
    script = """
import importlib.util
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("fifo_subject", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
scope = module.WorkerToolScope(Path(sys.argv[2]), {}, {}, {})
tools = module.MediatedWorkerTools(scope)
try:
    if sys.argv[3] == "read":
        tools._read_relative("src/sample.txt")
    else:
        tools._atomic_replace("src/sample.txt", b"before\\n", b"after\\n")
except module.MediatedWorkerError as exc:
    assert "bounded regular file" in str(exc), str(exc)
    print("REJECTED_NONREGULAR")
else:
    raise AssertionError("FIFO accepted")
"""
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", script, str(module_path), str(workspace), operation],
        cwd=workspace,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    blocked = False
    try:
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            blocked = True
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=2)
    finally:
        if process.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
    assert not blocked, f"{operation} blocked in FIFO open before file-type rejection"
    assert process.returncode == 0, stderr.decode()
    assert stdout == b"REJECTED_NONREGULAR\n"
    assert leaf.is_fifo()
    assert not list(leaf.parent.glob(".*.tmp"))


@pytest.mark.parametrize("newline", [False, True])
def test_conf02_rpc_input_reads_are_bounded_before_tool_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, newline: bool
) -> None:
    import io

    import runtime.integrations.mediated_worker_tools as mediator

    limit = 128
    monkeypatch.setattr(mediator, "MAX_RPC_LINE_BYTES", limit)

    class ObservedInput(io.BytesIO):
        def __init__(self, payload: bytes) -> None:
            super().__init__(payload)
            self.requests: list[int] = []
            self.unbounded_iterations = 0

        def __next__(self) -> bytes:
            self.unbounded_iterations += 1
            return super().__next__()

        def readline(self, size: int = -1) -> bytes:
            self.requests.append(size)
            return super().readline(size)

    source = ObservedInput(b" " * (limit * 4) + (b"\n" if newline else b""))
    target = io.BytesIO()
    calls: list[object] = []
    tools = MediatedWorkerTools(_scope(_sample_workspace(tmp_path)))
    monkeypatch.setattr(tools, "invoke", lambda *args: calls.append(args))
    assert mediator.serve_stdio(tools, stdin=source, stdout=target) == 2
    assert calls == []
    assert source.unbounded_iterations == 0, "RPC source used unbounded full-line iteration"
    assert source.requests == [limit + 1]
    assert source.tell() == limit + 1, "oversized input was drained or fully buffered"
    assert target.getvalue() == b""


@pytest.mark.parametrize("ending", [b"", b"\n"])
def test_conf02_small_rpc_terminal_line_and_empty_eof_remain_compatible(
    tmp_path: Path, ending: bytes
) -> None:
    import io

    import runtime.integrations.mediated_worker_tools as mediator

    tools = MediatedWorkerTools(_scope(_sample_workspace(tmp_path)))
    target = io.BytesIO()
    request = b'{"jsonrpc":"2.0","id":7,"method":"ping"}'
    assert mediator.serve_stdio(tools, stdin=io.BytesIO(request + ending), stdout=target) == 0
    assert json.loads(target.getvalue()) == {"jsonrpc": "2.0", "id": 7, "result": {}}
    empty_target = io.BytesIO()
    assert mediator.serve_stdio(tools, stdin=io.BytesIO(), stdout=empty_target) == 0
    assert empty_target.getvalue() == b""


@pytest.mark.parametrize("mode", ["timeout", "overflow"])
def test_conf03_exited_leader_descendant_is_killed_before_tool_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    import contextlib
    import signal
    import subprocess
    import time

    import runtime.integrations.mediated_worker_tools as mediator

    workspace = _sample_workspace(tmp_path)
    identity_path = workspace / "owned-descendant.json"
    script = """
import json
import os
from pathlib import Path
import signal
import sys
import time
leader = os.getpid()
if os.fork():
    os._exit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
deadline = time.monotonic() + 2
while os.getppid() == leader and time.monotonic() < deadline:
    time.sleep(0.005)
assert os.getppid() != leader
Path(sys.argv[1]).write_text(json.dumps({"pid": os.getpid(), "pgid": os.getpgrp(),
                                      "leader": leader, "leader_exited": True}))
if sys.argv[2] == "overflow":
    os.write(1, b"x" * 65536)
# This owned fixture holds stderr open until death and ignores TERM.
while True:
    time.sleep(10)
"""
    scope = WorkerToolScope(
        workspace=workspace,
        artifacts={},
        patch_targets={},
        tests={"owned": (sys.executable, "-B", "-c", script, str(identity_path), mode)},
    )
    monkeypatch.setattr(mediator, "TEST_TIMEOUT_SECONDS", 0.8)
    monkeypatch.setattr(mediator, "MAX_TEST_OUTPUT_BYTES", 32)
    original_popen = subprocess.Popen
    owned: list[tuple[subprocess.Popen, int]] = []

    def observe_owned_process(*args: object, **kwargs: object) -> subprocess.Popen:
        process = original_popen(*args, **kwargs)
        assert process.stderr is not None
        # Retaining a read descriptor lets EOF distinguish death from a live
        # descendant even if the OS has not yet reaped its terminated PID.
        owned.append((process, os.dup(process.stderr.fileno())))
        return process

    monkeypatch.setattr(mediator.subprocess, "Popen", observe_owned_process)

    def deadline_expired(signum: int, frame: object) -> None:
        raise RuntimeError("owned process-group regression exceeded hard harness deadline")

    previous_handler = signal.signal(signal.SIGALRM, deadline_expired)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 8)
    try:
        result = MediatedWorkerTools(scope).invoke("run_test", {"test_id": "owned"})
        assert len(owned) == 1
        process, stderr_fd = owned[0]
        identity = json.loads(identity_path.read_text())
        assert identity["leader_exited"] is True
        assert identity["pgid"] == identity["leader"] == process.pid
        assert identity["pid"] != process.pid
        assert process.poll() == 0
        assert result["timed_out"] is (mode == "timeout")
        assert result["output_limit_exceeded"] is (mode == "overflow")
        assert len(result["stdout"].encode()) <= 32
        os.set_blocking(stderr_fd, False)
        gone = False
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            try:
                assert os.read(stderr_fd, 1) == b""
                gone = True
                break
            except BlockingIOError:
                time.sleep(0.01)
        assert gone, "owned descendant survived tool timeout/overflow after leader exit"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        for process, stderr_fd in owned:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
            os.close(stderr_fd)
