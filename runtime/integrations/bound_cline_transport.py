"""Fail-closed contracts for a state-root-bound Cline worker transport.

Task 1 deliberately contains only pure configuration and path validation. Process
execution and response persistence are added in later plan tasks.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from paeos.model_router.types import ModelFamily

from .bridge_protocol import RequestEnvelope, ResponseEnvelope, validate_request

__all__ = [
    "BoundWorkerConfig",
    "ResponseEnvelope",
    "TransportFailureKind",
    "TransportProtocolError",
    "WorkerToolPolicy",
    "_load_policy",
    "_validate_binding",
    "_validate_paths",
    "_validate_policy",
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
