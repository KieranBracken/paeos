"""RED tests for the bound Cline transport contract."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from paeos.model_router.types import ModelFamily
from runtime.integrations.bound_cline_transport import (
    BoundWorkerConfig,
    TransportFailureKind,
    TransportProtocolError,
    WorkerDispatchFailure,
    WorkerDispatchSuccess,
    _validate_binding,
    _validate_paths,
    dispatch_once,
)
from runtime.integrations.bridge_protocol import Disposition, RequestEnvelope

_FAKE_HOST = r"""
import json
import struct
import sys
import time

def read_frame():
    header = sys.stdin.buffer.read(4)
    if len(header) != 4:
        raise SystemExit(3)
    size = struct.unpack(">I", header)[0]
    payload = sys.stdin.buffer.read(size)
    if len(payload) != size:
        raise SystemExit(3)
    return json.loads(payload)

def emit(invocation_id, sequence, message_type, payload, session_id=None):
    message = {
        "invocation_id": invocation_id,
        "payload": payload,
        "protocol_version": "paeos-worker-admission/1",
        "sequence": sequence,
        "type": message_type,
    }
    if session_id is not None:
        message["session_id"] = session_id
    encoded = json.dumps(message, sort_keys=True, separators=(",", ":")).encode()
    sys.stdout.buffer.write(struct.pack(">I", len(encoded)) + encoded)
    sys.stdout.buffer.flush()

start = read_frame()
invocation_id = start["invocation_id"]
session_id = start["payload"]["session_id"]
prompt = start["payload"]["prompt"]
workspace = start["payload"]["cwd"]
if "partial_frame" in prompt:
    sys.stdout.buffer.write(struct.pack(">I", 100) + b"partial")
    sys.stdout.buffer.flush()
    time.sleep(10)
    raise SystemExit(0)
if "unknown_event" in prompt:
    emit(invocation_id, 0, "not_a_host_event", {})
    raise SystemExit(0)
if "out_of_order" in prompt:
    emit(invocation_id, 1, "hello", {})
    raise SystemExit(0)
emit(invocation_id, 0, "hello", {"host": "fake"})
emit(invocation_id, 1, "session_created", {}, session_id)

def attempt(sequence, turn, correlation):
    emit(invocation_id, sequence, "provider_attempt_started", {
        "attempt_ordinal": 1,
        "correlation_id": correlation,
        "turn_id": turn,
    }, session_id)
    emit(invocation_id, sequence + 1, "provider_attempt_finished", {
        "attempt_ordinal": 1,
        "correlation_id": correlation,
        "status_class": "2xx",
        "turn_id": turn,
    }, session_id)

if "duplicate_attempt" in prompt:
    attempt(2, "turn-1", "a1")
    attempt(4, "turn-1", "a2")
    raise SystemExit(0)

attempt(2, "turn-1", "a1")
if "unknown_tool" in prompt:
    tool = "read_files"
    tool_input = {"path": "artifact.txt"}
elif "command_mismatch" in prompt:
    tool = "run_commands"
    tool_input = {"command": "cd /tmp && pytest"}
else:
    tool = "editor"
    tool_input = {"path": workspace + "/artifact.txt", "old_text": "initial", "new_text": "updated"}
emit(
    invocation_id,
    4,
    "tool_request",
    {"call_id": "c1", "input": tool_input, "tool_name": tool},
    session_id,
)
read_frame()

if "success" in prompt:
    attempt(5, "turn-2", "a2")
    emit(
        invocation_id,
        7,
        "tool_request",
        {"call_id": "c2", "input": {"command": "true"}, "tool_name": "run_commands"},
        session_id,
    )
    read_frame()
terminal_sequence = 8 if "success" in prompt else 5
emit(invocation_id, terminal_sequence, "terminal", {"result": {"status": "ok"}}, session_id)
if "post_terminal" in prompt:
    emit(invocation_id, terminal_sequence + 1, "hello", {"host": "fake"})
if "nonzero_exit" in prompt:
    raise SystemExit(7)
"""


def _request(tmp_path: Path, *, workspace: Path | None = None) -> RequestEnvelope:
    sandbox = workspace or (tmp_path / "sandbox")
    sandbox.mkdir(parents=True, exist_ok=True)
    return RequestEnvelope(
        schema_version="paeos-bridge-v2",
        request_id="request-1",
        transaction_key="a" * 64,
        created_at="2026-08-31T00:00:00Z",
        expires_at="2026-08-31T01:00:00Z",
        goal_id="goal-1",
        run_id="run-1",
        stage_id="L12",
        role="BUILDER",
        workspace_root=str(sandbox),
        worker_transport_id="headless:bound-cline",
        worker_session_id="session-1",
        worker_pid=1,
        worker_tty=None,
        worker_model_provider="cline-pass",
        worker_model_id="z-ai/glm-5.3-flash",
        worker_model_family=ModelFamily.GLM.value,
        semantic_hash="b" * 64,
        evidence_manifest_hash="c" * 64,
        payload_hash="d" * 64,
        allowed_dispositions=(Disposition.CONTINUE, Disposition.REMAND),
    )


def _config(tmp_path: Path, *, branch_name: str = "codex/recovery") -> BoundWorkerConfig:
    state_root = tmp_path / "state"
    worktree = tmp_path / "worktree"
    package = tmp_path / "package"
    state_root.mkdir()
    worktree.mkdir()
    package.mkdir()
    files = {}
    for name in ("node", "host.mjs", "sdk.mjs", "core.mjs", "qualification.json"):
        path = package / name
        path.write_text("synthetic", encoding="utf-8")
        files[name] = path
    policy = state_root / "policy.json"
    policy.write_text("{}", encoding="utf-8")
    return BoundWorkerConfig(
        state_root=state_root,
        recovery_worktree=worktree,
        branch_name=branch_name,
        candidate_head="e" * 40,
        node_executable=files["node"],
        host_module=files["host.mjs"],
        sdk_entrypoint=files["sdk.mjs"],
        core_entrypoint=files["core.mjs"],
        qualification_record=files["qualification.json"],
        policy_path=policy,
        policy_sha256="f" * 64,
        provider_id="cline-pass",
        model_id="z-ai/glm-5.3-flash",
        model_family=ModelFamily.GLM,
        session_id="session-1",
    )


def test_valid_request_and_config_pass_binding(tmp_path: Path) -> None:
    config = _config(tmp_path)
    request = _request(tmp_path, workspace=config.recovery_worktree / "sandbox")
    _validate_binding(request, config)


def test_main_branch_is_rejected_before_process_launch(tmp_path: Path) -> None:
    config = _config(tmp_path, branch_name="main")
    request = _request(tmp_path, workspace=config.recovery_worktree / "sandbox")
    with pytest.raises(TransportProtocolError, match="main/trunk"):
        _validate_binding(request, config)


def test_workspace_outside_recovery_worktree_is_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path)
    request = _request(tmp_path, workspace=tmp_path / "outside")
    with pytest.raises(TransportProtocolError, match="worktree"):
        _validate_binding(request, config)


def test_symlinked_host_and_prompt_are_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path)
    link = config.host_module.with_name("host-link.mjs")
    link.symlink_to(config.host_module)
    prompt = config.recovery_worktree / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")
    request = _request(tmp_path, workspace=config.recovery_worktree / "sandbox")
    with pytest.raises(TransportProtocolError, match="symlink"):
        _validate_paths(request, config, prompt_path=prompt, host_path=link)


def _dispatch_fixture(tmp_path: Path, mode: str) -> tuple[Path, Path, BoundWorkerConfig]:
    config = _config(tmp_path)
    host = config.host_module
    host.write_text(_FAKE_HOST, encoding="utf-8")
    host.chmod(0o700)
    config = replace(config, node_executable=Path(sys.executable), host_module=host)
    workspace = config.recovery_worktree / "sandbox"
    request = _request(tmp_path, workspace=workspace)
    request_path = config.state_root / "request.json"
    request_path.write_text(canonical_request(request), encoding="utf-8")
    prompt_path = config.state_root / "prompt.md"
    prompt_path.write_text(mode, encoding="utf-8")
    policy = {
        "allowed_tools": ["editor", "run_commands"],
        "artifact_path": "artifact.txt",
        "request_payload_hash": request.payload_hash,
        "verification_command": "true",
        "write_scopes": ["artifact.txt"],
    }
    policy_bytes = (json.dumps(policy, sort_keys=True, separators=(",", ":")) + "\n").encode()
    config.policy_path.write_bytes(policy_bytes)
    config = replace(config, policy_sha256=hashlib.sha256(policy_bytes).hexdigest())
    (workspace / "artifact.txt").write_text("initial", encoding="utf-8")
    return request_path, prompt_path, config


def canonical_request(request: RequestEnvelope) -> str:
    from runtime.integrations.bridge_protocol import canonical_json

    return canonical_json(request) + "\n"


def test_dispatch_executes_only_preapproved_editor_and_exact_command(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "success")
    result = dispatch_once(request_path, prompt_path, config)
    assert isinstance(result, WorkerDispatchSuccess)
    assert (config.recovery_worktree / "sandbox" / "artifact.txt").read_text() == "updated"
    assert len(result.tool_decisions) == 2


def test_unknown_tool_is_rejected_before_execution(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "unknown_tool")
    result = dispatch_once(request_path, prompt_path, config)
    assert isinstance(result, WorkerDispatchFailure)
    assert result.failure.kind is TransportFailureKind.TOOL_DENIED


def test_extra_cd_or_separator_is_rejected(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "command_mismatch")
    result = dispatch_once(request_path, prompt_path, config)
    assert isinstance(result, WorkerDispatchFailure)
    assert result.failure.kind is TransportFailureKind.COMMAND_MISMATCH


def test_second_provider_attempt_in_one_turn_is_rejected(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "duplicate_attempt")
    result = dispatch_once(request_path, prompt_path, config)
    assert isinstance(result, WorkerDispatchFailure)
    assert result.failure.kind is TransportFailureKind.PROVIDER_ATTEMPT_OVERFLOW


def test_partial_frame_honors_deadline_and_is_not_success(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "partial_frame")
    result = dispatch_once(request_path, prompt_path, replace(config, timeout_seconds=0.1))
    assert isinstance(result, WorkerDispatchFailure)
    assert result.failure.kind is TransportFailureKind.TIMEOUT


def test_post_terminal_frame_is_rejected(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "post_terminal")
    result = dispatch_once(request_path, prompt_path, config)
    assert isinstance(result, WorkerDispatchFailure)
    assert result.failure.kind is TransportFailureKind.PROTOCOL_VIOLATION


def test_request_path_escape_is_rejected(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "success")
    escaped_request = tmp_path / "request-outside.json"
    escaped_request.write_bytes(request_path.read_bytes())
    result = dispatch_once(escaped_request, prompt_path, config)
    assert isinstance(result, WorkerDispatchFailure)
    assert result.failure.kind is TransportFailureKind.PATH_ESCAPE


def test_unknown_event_is_rejected(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "unknown_event")
    result = dispatch_once(request_path, prompt_path, config)
    assert isinstance(result, WorkerDispatchFailure)
    assert result.failure.kind is TransportFailureKind.PROTOCOL_VIOLATION


def test_out_of_order_event_is_rejected(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "out_of_order")
    result = dispatch_once(request_path, prompt_path, config)
    assert isinstance(result, WorkerDispatchFailure)
    assert result.failure.kind is TransportFailureKind.PROTOCOL_VIOLATION


def test_nonzero_worker_exit_is_not_success(tmp_path: Path) -> None:
    request_path, prompt_path, config = _dispatch_fixture(tmp_path, "nonzero_exit")
    result = dispatch_once(request_path, prompt_path, config)
    assert isinstance(result, WorkerDispatchFailure)
    assert result.failure.kind is TransportFailureKind.PROCESS_FAILED
