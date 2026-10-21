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
