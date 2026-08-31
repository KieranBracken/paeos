"""Fail-closed state-root-bound Cline worker transport.

The dispatcher is deliberately run-once: it validates an immutable request and policy,
starts one framed host process, and returns typed data. It does not create Court or
lifecycle authority and never retries a provider or worker command.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import select
import shlex
import signal
import subprocess
import time
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, cast

from paeos.model_router.types import ModelFamily

from .bridge_protocol import (
    SCHEMA_VERSION,
    BridgePaths,
    Disposition,
    RequestEnvelope,
    ResponseEnvelope,
    canonical_json,
    load_json,
    validate_request,
    validate_response,
    write_once_bytes,
)
from .cline_sdk_protocol import (
    MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    HostEventMachine,
    ProtocolError,
    encode_frame,
)

__all__ = [
    "BoundWorkerConfig",
    "HandoffRecord",
    "QuarantineRecord",
    "ResponseEnvelope",
    "SideEffectCertainty",
    "TransportFailure",
    "TransportFailureKind",
    "TransportProtocolError",
    "WorkerDispatchFailure",
    "WorkerDispatchResult",
    "WorkerDispatchSuccess",
    "WorkerToolPolicy",
    "_load_policy",
    "_persist_handoff_once",
    "_persist_response_once",
    "_quarantine_failure_once",
    "_validate_binding",
    "_validate_paths",
    "_validate_policy",
    "dispatch_once",
]

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_UNKNOWN = frozenset({"", "unknown", "none", "null", "unavailable"})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_COMMAND = re.compile(r"(?:^|\s)(?:cd|exec|env)(?:\s|$)|[;&|<>`$]")


class TransportProtocolError(ValueError):
    """A request/configuration violation detected before worker launch."""


class TransportFailureKind(StrEnum):
    REQUEST_BINDING = "REQUEST_BINDING"
    PATH_ESCAPE = "PATH_ESCAPE"
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    LEASE_UNAVAILABLE = "LEASE_UNAVAILABLE"
    QUALIFICATION_DRIFT = "QUALIFICATION_DRIFT"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    PROTOCOL_VIOLATION = "PROTOCOL_VIOLATION"
    TOOL_DENIED = "TOOL_DENIED"
    COMMAND_MISMATCH = "COMMAND_MISMATCH"
    PROVIDER_ATTEMPT_OVERFLOW = "PROVIDER_ATTEMPT_OVERFLOW"
    TIMEOUT = "TIMEOUT"
    PROCESS_FAILED = "PROCESS_FAILED"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
    RESPONSE_BINDING = "RESPONSE_BINDING"


class SideEffectCertainty(StrEnum):
    NOT_DISPATCHED = "NOT_DISPATCHED"
    PROVIDER_ACCEPTED = "PROVIDER_ACCEPTED"
    TOOL_EFFECT_POSSIBLE = "TOOL_EFFECT_POSSIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class BoundWorkerConfig:
    """Public, non-secret launch tuple for one bound worker invocation."""

    state_root: Path
    recovery_worktree: Path
    branch_name: str
    candidate_head: str
    node_executable: Path
    host_module: Path
    sdk_entrypoint: Path
    core_entrypoint: Path
    qualification_record: Path
    policy_path: Path
    policy_sha256: str
    provider_id: str
    model_id: str
    model_family: ModelFamily
    session_id: str
    timeout_seconds: float = 300.0
    max_declared_model_turns: int = 2


@dataclass(frozen=True, slots=True)
class WorkerToolPolicy:
    """Canonical, immutable tool policy bound to one request payload."""

    request_payload_hash: str
    allowed_tools: tuple[str, ...]
    write_scopes: tuple[str, ...]
    verification_command: str | None
    artifact_path: str | None


@dataclass(frozen=True, slots=True)
class TransportFailure:
    """Content-free failure metadata produced by one worker invocation."""

    kind: TransportFailureKind
    request_id: str
    transaction_key: str
    message: str
    side_effect_certainty: SideEffectCertainty
    stdout_hash: str
    stderr_hash: str
    exit_code: int | None


@dataclass(frozen=True, slots=True)
class HandoffRecord:
    """Secret-blind continuity record for the next overseer."""

    request_id: str
    transaction_key: str
    candidate_head: str
    branch_name: str
    session_id: str
    provider_id: str
    model_id: str
    model_family: str
    policy_sha256: str
    stdout_hash: str
    stderr_hash: str
    next_action: str


@dataclass(frozen=True, slots=True)
class QuarantineRecord:
    request_id: str
    transaction_key: str
    failure_kind: TransportFailureKind
    failure_hash: str
    path: Path


@dataclass(frozen=True, slots=True)
class WorkerDispatchSuccess:
    request_id: str
    transaction_key: str
    terminal_payload: dict[str, object]
    tool_decisions: tuple[dict[str, object], ...]
    stdout_hash: str
    stderr_hash: str
    exit_code: int
    response: ResponseEnvelope | None = None
    handoff: HandoffRecord | None = None


@dataclass(frozen=True, slots=True)
class WorkerDispatchFailure:
    request_id: str
    transaction_key: str
    failure: TransportFailure
    quarantine: QuarantineRecord | None = None
    handoff: HandoffRecord | None = None


WorkerDispatchResult = WorkerDispatchSuccess | WorkerDispatchFailure


def _absolute(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise TransportProtocolError(f"{label} must be absolute")
    return path


def _regular_non_symlink(path: Path, label: str) -> Path:
    _absolute(path, label)
    if path.is_symlink():
        raise TransportProtocolError(f"{label} must not be a symlink")
    if not path.exists() or not path.is_file():
        raise TransportProtocolError(f"{label} must be an existing regular file")
    return path


def _directory(path: Path, label: str) -> Path:
    _absolute(path, label)
    if path.is_symlink():
        raise TransportProtocolError(f"{label} must not be a symlink")
    if not path.exists() or not path.is_dir():
        raise TransportProtocolError(f"{label} must be an existing directory")
    return path


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _attributable(value: str, label: str) -> None:
    if not isinstance(value, str) or value.strip().lower() in _UNKNOWN:
        raise TransportProtocolError(f"{label} must be attributable")


def _canonical_policy_bytes(policy: WorkerToolPolicy) -> bytes:
    payload = {
        "allowed_tools": list(policy.allowed_tools),
        "artifact_path": policy.artifact_path,
        "request_payload_hash": policy.request_payload_hash,
        "verification_command": policy.verification_command,
        "write_scopes": list(policy.write_scopes),
    }
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _load_policy(path: Path) -> WorkerToolPolicy:
    """Load and validate one canonical policy sidecar without executing it."""

    _regular_non_symlink(path, "policy_path")
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportProtocolError("policy is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise TransportProtocolError("policy must be a JSON object")
    expected = {
        "allowed_tools",
        "artifact_path",
        "request_payload_hash",
        "verification_command",
        "write_scopes",
    }
    if set(parsed) != expected:
        raise TransportProtocolError("policy schema mismatch")
    allowed = parsed["allowed_tools"]
    scopes = parsed["write_scopes"]
    if (
        not isinstance(allowed, list)
        or not allowed
        or any(not isinstance(item, str) for item in allowed)
        or len(set(allowed)) != len(allowed)
        or any(item not in {"editor", "run_commands"} for item in allowed)
    ):
        raise TransportProtocolError("policy contains an unknown or duplicate tool")
    if (
        not isinstance(scopes, list)
        or not scopes
        or any(
            not isinstance(item, str)
            or not item.strip()
            or Path(item).is_absolute()
            or ".." in Path(item).parts
            for item in scopes
        )
        or len(set(scopes)) != len(scopes)
    ):
        raise TransportProtocolError("policy write scopes are invalid")
    command = parsed["verification_command"]
    if command is not None and (
        not isinstance(command, str) or not command.strip() or _FORBIDDEN_COMMAND.search(command)
    ):
        raise TransportProtocolError("policy verification command is invalid")
    artifact = parsed["artifact_path"]
    if artifact is not None and (
        not isinstance(artifact, str)
        or not artifact.strip()
        or Path(artifact).is_absolute()
        or ".." in Path(artifact).parts
    ):
        raise TransportProtocolError("policy artifact path is invalid")
    return WorkerToolPolicy(
        request_payload_hash=parsed["request_payload_hash"],
        allowed_tools=tuple(allowed),
        write_scopes=tuple(scopes),
        verification_command=command,
        artifact_path=artifact,
    )


def _validate_policy(
    policy: WorkerToolPolicy,
    request: RequestEnvelope,
    config: BoundWorkerConfig,
) -> None:
    _validate_binding(request, config)
    if not _HEX64.fullmatch(policy.request_payload_hash):
        raise TransportProtocolError("policy payload hash is invalid")
    if policy.request_payload_hash != request.payload_hash:
        raise TransportProtocolError("policy payload hash does not match request")
    try:
        policy_hash = hashlib.sha256(_canonical_policy_bytes(policy)).hexdigest()
        file_hash = hashlib.sha256(config.policy_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise TransportProtocolError("policy cannot be read") from exc
    if file_hash != policy_hash or config.policy_sha256 != file_hash:
        raise TransportProtocolError("policy hash mismatch")
    if "run_commands" in policy.allowed_tools and not policy.verification_command:
        raise TransportProtocolError("run_commands requires a verification command")
    if policy.artifact_path is not None and not any(
        policy.artifact_path == scope or policy.artifact_path.startswith(scope.rstrip("/") + "/")
        for scope in policy.write_scopes
    ):
        raise TransportProtocolError("policy artifact path is outside write scopes")


def _validate_binding(request: RequestEnvelope, config: BoundWorkerConfig) -> None:
    """Validate immutable request identity before any process can be launched."""

    try:
        validate_request(request)
    except Exception as exc:
        raise TransportProtocolError(str(exc)) from exc

    state_root = _directory(config.state_root, "state_root")
    worktree = _directory(config.recovery_worktree, "recovery_worktree")
    if config.branch_name in {"main", "trunk"}:
        raise TransportProtocolError("main/trunk branches are forbidden")
    if not config.branch_name.startswith("codex/"):
        raise TransportProtocolError("recovery branch must use the codex/ namespace")
    if not _HEX40.fullmatch(config.candidate_head):
        raise TransportProtocolError("candidate_head must be a 40-character lowercase SHA")
    if config.timeout_seconds <= 0 or config.max_declared_model_turns <= 0:
        raise TransportProtocolError("timeout and model-turn limits must be positive")

    _attributable(config.provider_id, "provider_id")
    _attributable(config.model_id, "model_id")
    if config.model_family is ModelFamily.UNKNOWN:
        raise TransportProtocolError("model_family must be attributable")
    if request.worker_transport_id != "headless:bound-cline":
        raise TransportProtocolError("request is not bound to headless:bound-cline")
    if request.worker_session_id != config.session_id:
        raise TransportProtocolError("worker session does not match configuration")
    if request.worker_model_provider != config.provider_id:
        raise TransportProtocolError("provider does not match configuration")
    if request.worker_model_id != config.model_id:
        raise TransportProtocolError("model does not match configuration")
    if request.worker_model_family != config.model_family.value:
        raise TransportProtocolError("model family does not match configuration")

    workspace = Path(request.workspace_root)
    _directory(workspace, "request workspace")
    if not _within(workspace, worktree):
        raise TransportProtocolError("request workspace is outside recovery worktree")
    if _within(workspace, state_root):
        raise TransportProtocolError("request workspace must be separate from state_root")


def _validate_paths(
    request: RequestEnvelope,
    config: BoundWorkerConfig,
    *,
    prompt_path: Path,
    host_path: Path | None = None,
    sdk_path: Path | None = None,
    core_path: Path | None = None,
    qualification_path: Path | None = None,
) -> None:
    """Validate all launch files without following symlinks or reading secrets."""

    _validate_binding(request, config)
    _regular_non_symlink(prompt_path, "prompt_path")
    host = _regular_non_symlink(host_path or config.host_module, "host_module")
    sdk = _regular_non_symlink(sdk_path or config.sdk_entrypoint, "sdk_entrypoint")
    core = _regular_non_symlink(core_path or config.core_entrypoint, "core_entrypoint")
    qualification = _regular_non_symlink(
        qualification_path or config.qualification_record,
        "qualification_record",
    )

    package_root = qualification.parent.resolve(strict=True)
    for label, path in (("host_module", host), ("sdk_entrypoint", sdk), ("core_entrypoint", core)):
        if not _within(path, package_root):
            raise TransportProtocolError(f"{label} is outside qualification package")

    prompt = Path(prompt_path)
    worktree = config.recovery_worktree
    if not (_within(prompt, config.state_root) or _within(prompt, worktree)):
        raise TransportProtocolError("prompt_path is outside state root and recovery worktree")


def _request_from_mapping(raw: Mapping[str, object]) -> RequestEnvelope:
    """Decode one exact request envelope without accepting extension fields."""

    fields = {
        "schema_version",
        "request_id",
        "transaction_key",
        "created_at",
        "expires_at",
        "goal_id",
        "run_id",
        "stage_id",
        "role",
        "workspace_root",
        "worker_transport_id",
        "worker_session_id",
        "worker_pid",
        "worker_tty",
        "worker_model_provider",
        "worker_model_id",
        "worker_model_family",
        "semantic_hash",
        "evidence_manifest_hash",
        "payload_hash",
        "allowed_dispositions",
    }
    if set(raw) != fields:
        raise TransportProtocolError("request schema mismatch")
    dispositions = raw["allowed_dispositions"]
    if not isinstance(dispositions, list):
        raise TransportProtocolError("request dispositions must be a list")
    worker_pid = raw["worker_pid"]
    if isinstance(worker_pid, bool) or not isinstance(worker_pid, int):
        raise TransportProtocolError("request worker_pid must be an integer")
    try:
        allowed = tuple(Disposition(str(item)) for item in dispositions)
    except ValueError as exc:
        raise TransportProtocolError("request disposition is invalid") from exc
    try:
        request = RequestEnvelope(
            schema_version=str(raw["schema_version"]),
            request_id=str(raw["request_id"]),
            transaction_key=str(raw["transaction_key"]),
            created_at=str(raw["created_at"]),
            expires_at=str(raw["expires_at"]),
            goal_id=str(raw["goal_id"]),
            run_id=str(raw["run_id"]),
            stage_id=str(raw["stage_id"]),
            role=str(raw["role"]),
            workspace_root=str(raw["workspace_root"]),
            worker_transport_id=str(raw["worker_transport_id"]),
            worker_session_id=str(raw["worker_session_id"]),
            worker_pid=worker_pid,
            worker_tty=raw["worker_tty"] if raw["worker_tty"] is None else str(raw["worker_tty"]),
            worker_model_provider=str(raw["worker_model_provider"]),
            worker_model_id=str(raw["worker_model_id"]),
            worker_model_family=str(raw["worker_model_family"]),
            semantic_hash=str(raw["semantic_hash"]),
            evidence_manifest_hash=str(raw["evidence_manifest_hash"]),
            payload_hash=str(raw["payload_hash"]),
            allowed_dispositions=allowed,
        )
    except (TypeError, ValueError) as exc:
        raise TransportProtocolError("request field types are invalid") from exc
    try:
        validate_request(request)
    except Exception as exc:
        raise TransportProtocolError(str(exc)) from exc
    return request


def _load_request(path: Path) -> RequestEnvelope:
    _regular_non_symlink(path, "request_path")
    try:
        raw_bytes = path.read_bytes()
        if raw_bytes != (canonical_json(json.loads(raw_bytes.decode("utf-8"))) + "\n").encode():
            raise TransportProtocolError("request is not canonical JSON")
        return _request_from_mapping(load_json(path))
    except TransportProtocolError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportProtocolError("request is not valid canonical JSON") from exc


def _scope_relative(path: Path, workspace: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(workspace.resolve(strict=True)).as_posix()
    except (OSError, ValueError) as exc:
        raise TransportProtocolError("tool path is outside request workspace") from exc


def _scope_allows(relative: str, policy: WorkerToolPolicy) -> bool:
    return any(
        relative == scope or relative.startswith(scope.rstrip("/") + "/")
        for scope in policy.write_scopes
    )


def _execute_approved_tool(
    *,
    request: RequestEnvelope,
    policy: WorkerToolPolicy,
    tool_name: str,
    tool_input: object,
) -> dict[str, object]:
    if tool_name not in policy.allowed_tools:
        raise TransportProtocolError("unauthorized tool")
    workspace = Path(request.workspace_root).resolve(strict=True)
    if not isinstance(tool_input, dict):
        raise TransportProtocolError("tool input must be an object")
    if tool_name == "editor":
        path_value = tool_input.get("path")
        new_text = tool_input.get("new_text")
        if not isinstance(path_value, str) or not isinstance(new_text, str):
            raise TransportProtocolError("editor input is malformed")
        path = Path(path_value)
        if path.is_symlink():
            raise TransportProtocolError("editor path is a symlink")
        if not path.is_absolute():
            path = workspace / path
        path = path.resolve(strict=False)
        relative = _scope_relative(path, workspace)
        if not _scope_allows(relative, policy) or (
            policy.artifact_path is not None and relative != policy.artifact_path
        ):
            raise TransportProtocolError("editor path is outside write scopes")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")
        return {"bytes_written": len(new_text.encode("utf-8")), "path": relative}
    if tool_name == "run_commands":
        command = tool_input.get("command")
        if not isinstance(command, str) or command != policy.verification_command:
            raise TransportProtocolError("command does not match immutable policy")
        try:
            argv = shlex.split(command, posix=True)
        except ValueError as exc:
            raise TransportProtocolError("command is not safely tokenized") from exc
        if not argv:
            raise TransportProtocolError("command is empty")
        completed = subprocess.run(
            argv,
            cwd=workspace,
            env={"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"},
            shell=False,
            capture_output=True,
            check=False,
            timeout=30,
        )
        return {
            "exit_code": completed.returncode,
            "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        }
    raise TransportProtocolError("unsupported tool")


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _failure(
    request: RequestEnvelope,
    kind: TransportFailureKind,
    message: str,
    stdout: bytes,
    stderr: bytes,
    *,
    exit_code: int | None = None,
    certainty: SideEffectCertainty = SideEffectCertainty.NOT_DISPATCHED,
) -> WorkerDispatchFailure:
    return WorkerDispatchFailure(
        request_id=request.request_id,
        transaction_key=request.transaction_key,
        failure=TransportFailure(
            kind=kind,
            request_id=request.request_id,
            transaction_key=request.transaction_key,
            message=message,
            side_effect_certainty=certainty,
            stdout_hash=_hash_bytes(stdout),
            stderr_hash=_hash_bytes(stderr),
            exit_code=exit_code,
        ),
    )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_component(value: str) -> str:
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]+", value) else "unknown"


def _persist_response_once(paths: BridgePaths, response: ResponseEnvelope) -> Path:
    """Persist one validated response create-only and reject conflicting bytes."""

    try:
        validate_response(response)
    except Exception as exc:
        raise TransportProtocolError(f"response validation failed: {exc}") from exc
    paths.ensure()
    target = paths.responses / f"{_safe_component(response.request_id)}.json"
    payload = (canonical_json(response) + "\n").encode("utf-8")
    try:
        write_once_bytes(target, payload)
    except FileExistsError:
        try:
            existing = target.read_bytes()
        except OSError as exc:
            raise TransportProtocolError("existing response cannot be read") from exc
        if existing != payload:
            raise TransportProtocolError("duplicate response has different content") from None
    _fsync_directory(paths.responses)
    return target


def _quarantine_failure_once(
    paths: BridgePaths,
    failure: TransportFailure,
) -> QuarantineRecord:
    """Persist only typed, hash-based failure metadata; never worker prose."""

    paths.ensure()
    metadata = {
        "schema_version": "paeos-bound-cline-quarantine/1",
        "request_id": _safe_component(failure.request_id),
        "transaction_key": failure.transaction_key,
        "failure_kind": failure.kind.value,
        "side_effect_certainty": failure.side_effect_certainty.value,
        "stdout_hash": failure.stdout_hash,
        "stderr_hash": failure.stderr_hash,
        "exit_code": failure.exit_code,
    }
    failure_hash = _hash_bytes((canonical_json(metadata) + "\n").encode("utf-8"))
    target = paths.quarantine / f"{_safe_component(failure.request_id)}--{failure_hash}.json"
    payload = (canonical_json({**metadata, "failure_hash": failure_hash}) + "\n").encode("utf-8")
    try:
        write_once_bytes(target, payload)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise TransportProtocolError("quarantine record collision") from None
    _fsync_directory(paths.quarantine)
    return QuarantineRecord(
        request_id=failure.request_id,
        transaction_key=failure.transaction_key,
        failure_kind=failure.kind,
        failure_hash=failure_hash,
        path=target,
    )


def _persist_handoff_once(paths: BridgePaths, handoff: HandoffRecord) -> Path:
    """Persist a secret-blind, create-only continuity handoff."""

    paths.ensure()
    target = paths.transactions / f"{_safe_component(handoff.request_id)}.handoff.json"
    payload = (canonical_json(asdict(handoff)) + "\n").encode("utf-8")
    try:
        write_once_bytes(target, payload)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise TransportProtocolError("handoff collision with different content") from None
    _fsync_directory(paths.transactions)
    return target


def _send_cancel(stream: BinaryIO, invocation_id: str, session_id: str, sequence: int) -> None:
    with suppress(BrokenPipeError, OSError):
        stream.write(
            encode_frame(
                {
                    "invocation_id": invocation_id,
                    "payload": {},
                    "protocol_version": PROTOCOL_VERSION,
                    "sequence": sequence,
                    "session_id": session_id,
                    "type": "cancel",
                }
            )
        )
        stream.flush()


def _stop_process(
    process: subprocess.Popen[bytes], *, invocation_id: str, session_id: str, sequence: int
) -> bytes:
    if process.stdin is not None:
        _send_cancel(cast(BinaryIO, process.stdin), invocation_id, session_id, sequence)
    try:
        process.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=1)
    if process.stderr is None:
        return b""
    return process.stderr.read()


def _read_frame_until(stream: BinaryIO, deadline: float) -> dict[str, object]:
    """Read one frame while applying the invocation deadline to every byte read."""

    def read_exact(size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([stream], [], [], remaining)[0]:
                raise TimeoutError("worker frame read deadline exceeded")
            chunk = stream.read(size - len(data))
            if not chunk:
                raise ProtocolError("truncated frame")
            data.extend(chunk)
        return bytes(data)

    header = read_exact(4)
    length = int.from_bytes(header, "big")
    if length <= 0 or length > MAX_FRAME_BYTES:
        raise ProtocolError("frame size invalid")
    payload = read_exact(length)
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid JSON frame") from exc
    if not isinstance(value, dict) or encode_frame(value)[4:] != payload:
        raise ProtocolError("non-canonical frame")
    return cast(dict[str, object], value)


def _run_host_once(
    request: RequestEnvelope,
    prompt: str,
    policy: WorkerToolPolicy,
    config: BoundWorkerConfig,
) -> WorkerDispatchResult:
    """Run one host process and enforce its complete framed event lifecycle."""

    argv = [str(config.node_executable), str(config.host_module)]
    start = {
        "invocation_id": request.request_id,
        "payload": {
            "backend_mode": "local",
            "core_entrypoint": str(config.core_entrypoint),
            "core_sha256": _hash_bytes(config.core_entrypoint.read_bytes()),
            "cwd": request.workspace_root,
            "max_declared_model_turns": config.max_declared_model_turns,
            "model_id": config.model_id,
            "prompt": prompt,
            "provider_id": config.provider_id,
            "sdk_entrypoint": str(config.sdk_entrypoint),
            "sdk_sha256": _hash_bytes(config.sdk_entrypoint.read_bytes()),
            "session_id": config.session_id,
        },
        "protocol_version": PROTOCOL_VERSION,
        "sequence": 0,
        "type": "start",
    }
    try:
        process = subprocess.Popen(
            argv,
            cwd=request.workspace_root,
            env={
                "CLINE_DATA_DIR": str(config.state_root),
                "LANG": "C.UTF-8",
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
            },
            shell=False,
            start_new_session=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
    except OSError as exc:
        return _failure(request, TransportFailureKind.PROCESS_FAILED, str(exc), b"", b"")
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(encode_frame(start))
    process.stdin.flush()

    machine = HostEventMachine(request.request_id)
    raw_stdout = bytearray()
    decisions: list[dict[str, object]] = []
    attempts: dict[str, int] = {}
    command_sequence = 1
    terminal_payload: dict[str, object] | None = None
    deadline = time.monotonic() + config.timeout_seconds
    try:
        while not machine.terminal:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                stderr = _stop_process(
                    process,
                    invocation_id=request.request_id,
                    session_id=config.session_id,
                    sequence=command_sequence,
                )
                return _failure(
                    request,
                    TransportFailureKind.TIMEOUT,
                    "worker deadline exceeded",
                    bytes(raw_stdout),
                    stderr,
                    certainty=SideEffectCertainty.UNKNOWN,
                )
            event = _read_frame_until(cast(BinaryIO, process.stdout), deadline)
            raw_stdout.extend(encode_frame(event))
            machine.accept(event)
            event_type = event["type"]
            payload = event["payload"]
            assert isinstance(payload, dict)
            if event_type == "provider_attempt_started":
                turn_id = payload.get("turn_id")
                if not isinstance(turn_id, str):
                    raise TransportProtocolError("provider attempt turn is missing")
                attempts[turn_id] = attempts.get(turn_id, 0) + 1
                if attempts[turn_id] > 1:
                    stderr = _stop_process(
                        process,
                        invocation_id=request.request_id,
                        session_id=config.session_id,
                        sequence=command_sequence,
                    )
                    return _failure(
                        request,
                        TransportFailureKind.PROVIDER_ATTEMPT_OVERFLOW,
                        "more than one provider attempt in a model turn",
                        bytes(raw_stdout),
                        stderr,
                        certainty=SideEffectCertainty.PROVIDER_ACCEPTED,
                    )
            elif event_type == "tool_request":
                tool_name = payload.get("tool_name")
                tool_input = payload.get("input")
                decision: dict[str, object] = {
                    "approved": False,
                    "call_id": payload.get("call_id"),
                    "tool_name": tool_name,
                }
                try:
                    if not isinstance(tool_name, str) or tool_name not in policy.allowed_tools:
                        raise TransportProtocolError("unauthorized tool")
                    result = _execute_approved_tool(
                        request=request, policy=policy, tool_name=tool_name, tool_input=tool_input
                    )
                    decision.update({"approved": True, "result": result})
                except (OSError, subprocess.SubprocessError, TransportProtocolError) as exc:
                    kind = (
                        TransportFailureKind.COMMAND_MISMATCH
                        if tool_name == "run_commands"
                        else TransportFailureKind.TOOL_DENIED
                    )
                    stderr = _stop_process(
                        process,
                        invocation_id=request.request_id,
                        session_id=config.session_id,
                        sequence=command_sequence,
                    )
                    return _failure(
                        request,
                        kind,
                        str(exc),
                        bytes(raw_stdout),
                        stderr,
                        certainty=SideEffectCertainty.TOOL_EFFECT_POSSIBLE,
                    )
                decisions.append(decision)
                response = {
                    "invocation_id": request.request_id,
                    "payload": {
                        "approved": True,
                        "call_id": payload.get("call_id"),
                        "result": decision["result"],
                    },
                    "protocol_version": PROTOCOL_VERSION,
                    "sequence": command_sequence,
                    "session_id": config.session_id,
                    "type": "tool_response",
                }
                command_sequence += 1
                process.stdin.write(encode_frame(response))
                process.stdin.flush()
            elif event_type == "terminal":
                terminal_payload = payload
            elif event_type in {"failure", "cancelled"}:
                stderr = _stop_process(
                    process,
                    invocation_id=request.request_id,
                    session_id=config.session_id,
                    sequence=command_sequence,
                )
                return _failure(
                    request,
                    TransportFailureKind.PROCESS_FAILED,
                    f"worker emitted {event_type}",
                    bytes(raw_stdout),
                    stderr,
                    certainty=SideEffectCertainty.UNKNOWN,
                )
    except (ProtocolError, TransportProtocolError, OSError, TimeoutError, ValueError) as exc:
        stderr = _stop_process(
            process,
            invocation_id=request.request_id,
            session_id=config.session_id,
            sequence=command_sequence,
        )
        kind = (
            TransportFailureKind.TIMEOUT
            if isinstance(exc, TimeoutError)
            else TransportFailureKind.PROTOCOL_VIOLATION
            if isinstance(exc, (ProtocolError, ValueError))
            else TransportFailureKind.PROCESS_FAILED
        )
        return _failure(
            request,
            kind,
            str(exc),
            bytes(raw_stdout),
            stderr,
            certainty=SideEffectCertainty.UNKNOWN,
        )

    if process.stdout is not None and select.select([process.stdout], [], [], 0)[0]:
        trailing = process.stdout.read(1)
        if trailing:
            stderr = _stop_process(
                process,
                invocation_id=request.request_id,
                session_id=config.session_id,
                sequence=command_sequence,
            )
            return _failure(
                request,
                TransportFailureKind.PROTOCOL_VIOLATION,
                "post-terminal frame emitted",
                bytes(raw_stdout) + trailing,
                stderr,
                certainty=SideEffectCertainty.UNKNOWN,
            )
    try:
        process.stdin.close()
        process.wait(timeout=max(0.1, deadline - time.monotonic()))
    except (OSError, subprocess.TimeoutExpired) as exc:
        stderr = _stop_process(
            process,
            invocation_id=request.request_id,
            session_id=config.session_id,
            sequence=command_sequence,
        )
        return _failure(
            request,
            TransportFailureKind.TIMEOUT,
            str(exc),
            bytes(raw_stdout),
            stderr,
            certainty=SideEffectCertainty.UNKNOWN,
        )
    stderr = process.stderr.read() if process.stderr is not None else b""
    if process.returncode != 0 or terminal_payload is None:
        return _failure(
            request,
            TransportFailureKind.PROCESS_FAILED,
            "worker exited without a confirmed terminal response",
            bytes(raw_stdout),
            stderr,
            exit_code=process.returncode,
            certainty=SideEffectCertainty.UNKNOWN,
        )
    return WorkerDispatchSuccess(
        request_id=request.request_id,
        transaction_key=request.transaction_key,
        terminal_payload=terminal_payload,
        tool_decisions=tuple(decisions),
        stdout_hash=_hash_bytes(bytes(raw_stdout)),
        stderr_hash=_hash_bytes(stderr),
        exit_code=process.returncode,
    )


def dispatch_once(
    request_path: Path, prompt_path: Path, config: BoundWorkerConfig
) -> WorkerDispatchResult:
    """Validate and dispatch one request, never retrying or falling back."""

    request: RequestEnvelope | None = None
    try:
        request_path = Path(request_path)
        prompt_path = Path(prompt_path)
        _directory(config.state_root, "state_root")
        _validate_paths(
            request_from_path := _load_request(request_path), config, prompt_path=prompt_path
        )
        request = request_from_path
        if not _within(request_path, config.state_root):
            raise TransportProtocolError("request_path is outside state_root")
        if not _within(config.policy_path, config.state_root):
            raise TransportProtocolError("policy_path is outside state_root")
        policy = _load_policy(config.policy_path)
        _validate_policy(policy, request, config)
        prompt = prompt_path.read_text(encoding="utf-8")
        return _run_host_once(request, prompt, policy, config)
    except (TransportProtocolError, OSError, UnicodeDecodeError) as exc:
        if request is None:
            request = RequestEnvelope(
                schema_version=SCHEMA_VERSION,
                request_id="unknown",
                transaction_key="0" * 64,
                created_at="1970-01-01T00:00:00Z",
                expires_at="1970-01-01T00:00:01Z",
                goal_id="unknown",
                run_id="unknown",
                stage_id="unknown",
                role="unknown",
                workspace_root=str(config.recovery_worktree),
                worker_transport_id="headless:bound-cline",
                worker_session_id=config.session_id,
                worker_pid=1,
                worker_tty=None,
                worker_model_provider=config.provider_id,
                worker_model_id=config.model_id,
                worker_model_family=config.model_family.value,
                semantic_hash="0" * 64,
                evidence_manifest_hash="0" * 64,
                payload_hash="0" * 64,
                allowed_dispositions=(Disposition.HALT,),
            )
        return _failure(request, TransportFailureKind.REQUEST_BINDING, str(exc), b"", b"")
