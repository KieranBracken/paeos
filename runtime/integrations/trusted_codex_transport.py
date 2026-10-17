"""PAEOS client for the trusted host-side Codex Builder supervisor.

This module is a narrow transport adapter, not a launcher.  It cannot select a command, model,
environment, filesystem root, or fallback.  It signs task metadata, waits for the supervisor's
signed observation, and converts that observation into the existing ``SessionResult`` seam.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from runtime.builder_transport import REQUIRED_CANARIES, REQUIRED_LIFECYCLE
from runtime.integrations import SessionResult, SessionSpec, TrustedTransportFailure
from runtime.integrations.task_scoped_responses_broker import MAX_TASK_REQUESTS

__all__ = [
    "DEFAULT_BUILDER_TRANSPORT_QUALIFICATION",
    "DEFAULT_BUILDER_TRANSPORT_VERIFY_KEY",
    "DEFAULT_CODEX_QUEUE",
    "DEFAULT_CODEX_REQUEST_KEY",
    "DEFAULT_CODEX_RESPONSE_VERIFY_KEY",
    "DEFAULT_CODEX_WORKSPACE_ROOT",
    "HostCodexWorkerTransport",
    "TrustedCodexTransportError",
]

DEFAULT_CODEX_QUEUE = Path("/Users/bob/GitHub/paeos/ops/.trusted-codex-worker/queue")
DEFAULT_CODEX_WORKSPACE_ROOT = Path("/Users/bob/GitHub/paeos/ops/.trusted-codex-worker/workspaces")
DEFAULT_CODEX_REQUEST_KEY = Path("/Users/bob/GitHub/paeos/ops/.trusted-codex-worker/request.key")
DEFAULT_CODEX_RESPONSE_VERIFY_KEY = Path(
    "/Users/bob/GitHub/paeos/ops/.trusted-codex-worker/response-verify.key"
)
DEFAULT_BUILDER_TRANSPORT_QUALIFICATION = Path(
    "/Users/bob/GitHub/paeos/ops/.trusted-codex-worker/qualification.json"
)
DEFAULT_BUILDER_TRANSPORT_VERIFY_KEY = Path(
    "/Users/bob/GitHub/paeos/ops/.trusted-codex-worker/qualification-verify.key"
)
DEFAULT_RESPONSE_TIMEOUT_S = 630.0
MAX_RESPONSE_TIMEOUT_S = 660.0
_SCHEMA = "paeos.trusted-codex-worker-service/1"
_CAPABILITY_SCHEMA = "paeos.trusted-codex-launch/1"
_MAX_FRAME_BYTES = 2 * 1024 * 1024
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_CAPABILITY_TTL_SECONDS = 90.0
_FAILURE_ERROR = "trusted Codex launch rejected or failed closed"
_FAILURE_CODES = frozenset(
    {
        "path_failure",
        "executable_failure",
        "broker_failure",
        "state_failure",
        "protocol_failure",
        "identity_failure",
        "confinement_failure",
        "capability_failure",
        "workspace_failure",
        "codex_home_failure",
        "environment_failure",
        "replay_failure",
        "provider_execution_failure",
        "liveness_failure",
        "supervisor_failure",
    }
)
_FAILURE_OBSERVATION_FIELDS = frozenset(
    {
        "lifecycle_state",
        "exit_code",
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
        "stderr_sha256",
    }
)
_FAILURE_LIFECYCLE_STATES = frozenset({"RETURNED", "FAILED", "TIMED_OUT"})


class TrustedCodexTransportError(TrustedTransportFailure):
    """The trusted supervisor is absent or returned an unqualified observation."""

    def __init__(self, message: str) -> None:
        super().__init__("transport_protocol_failure", message)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_failure_observation(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _FAILURE_OBSERVATION_FIELDS:
        raise TrustedCodexTransportError(
            "trusted supervisor failure observation fields are not exact"
        )
    if value["lifecycle_state"] not in _FAILURE_LIFECYCLE_STATES:
        raise TrustedCodexTransportError("trusted supervisor failure lifecycle is invalid")
    exit_code = value["exit_code"]
    if exit_code is not None and (
        not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code < 0
    ):
        raise TrustedCodexTransportError("trusted supervisor failure exit code is invalid")
    for field in ("stdout_bytes", "stderr_bytes"):
        count = value[field]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise TrustedCodexTransportError("trusted supervisor failure byte count is invalid")
    for field in ("stdout_sha256", "stderr_sha256"):
        if not _is_sha256(value[field]):
            raise TrustedCodexTransportError("trusted supervisor failure hash is invalid")
    return dict(value)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_atomic(path: Path, payload: bytes) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise TrustedCodexTransportError("trusted supervisor queue path is unsafe")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise TrustedCodexTransportError(
                    "trusted supervisor request write made no progress"
                )
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)


def _write_receipt_once(path: Path, payload: bytes) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise TrustedCodexTransportError("trusted supervisor receipt path is unsafe")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise TrustedCodexTransportError("trusted supervisor receipt already exists") from exc
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise TrustedCodexTransportError(
                    "trusted supervisor receipt write made no progress"
                )
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class HostCodexWorkerTransport:
    """Signed queue client for one fixed, host-supervised Codex Builder route."""

    provider_id = "codex"
    model_id = "gpt-5.6-sol"
    model_family = "gpt"
    allow_fallback = False
    manual_chat_bridge = False

    def __init__(
        self,
        *,
        queue_root: Path = DEFAULT_CODEX_QUEUE,
        workspace_root: Path,
        request_signing_key: SigningKey,
        response_verify_key: VerifyKey,
        timeout_s: float = DEFAULT_RESPONSE_TIMEOUT_S,
        evidence_root: Path | None = None,
    ) -> None:
        if not queue_root.is_absolute() or queue_root.is_symlink():
            raise TrustedCodexTransportError(
                "trusted supervisor queue must be absolute and non-symlinked"
            )
        if not workspace_root.is_absolute() or workspace_root.is_symlink():
            raise TrustedCodexTransportError("trusted supervisor workspace root is unsafe")
        if timeout_s <= 0 or timeout_s > MAX_RESPONSE_TIMEOUT_S:
            raise TrustedCodexTransportError(
                "trusted supervisor timeout is outside the bounded range"
            )
        if evidence_root is not None and (
            not evidence_root.is_absolute() or evidence_root.is_symlink()
        ):
            raise TrustedCodexTransportError("trusted supervisor evidence root is unsafe")
        self.queue_root = queue_root
        self.workspace_root = workspace_root.resolve()
        self.evidence_root = evidence_root
        self._request_signing_key = request_signing_key
        self._response_verify_key = response_verify_key
        self._timeout_s = timeout_s
        self.last_request_sha256: str | None = None
        self.last_response_sha256: str | None = None
        self.last_observation: dict[str, object] | None = None

    def _workspace_is_approved(self, workspace: Path) -> bool:
        if not workspace.is_absolute() or workspace.is_symlink() or not workspace.is_dir():
            return False
        try:
            resolved = workspace.resolve(strict=True)
        except OSError:
            return False
        return resolved == workspace and resolved.parent == self.workspace_root

    def _request_payload(self, spec: SessionSpec) -> dict[str, object]:
        if not self._workspace_is_approved(spec.workspace):
            raise TrustedCodexTransportError(
                "session workspace is outside the fixed supervisor root"
            )
        if not all(
            isinstance(value, str) and value
            for value in (spec.task_id, spec.goal_id, spec.run_id, spec.stage)
        ):
            raise TrustedCodexTransportError("session identity is incomplete")
        if "\x00" in spec.prompt or not spec.prompt.strip():
            raise TrustedCodexTransportError("session prompt is malformed")
        issued = time.time()
        return {
            "schema": _CAPABILITY_SCHEMA,
            "request_id": uuid.uuid4().hex,
            "task_id": spec.task_id,
            "goal_id": spec.goal_id,
            "run_id": spec.run_id,
            "stage": spec.stage,
            "workspace_id": spec.workspace.name,
            "prompt": spec.prompt,
            "issued_at": issued,
            "expires_at": issued + _CAPABILITY_TTL_SECONDS,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "family": self.model_family,
            "fallback_used": False,
            "manual_chat_bridge": False,
        }

    def run(self, spec: SessionSpec) -> SessionResult:
        request = self._request_payload(spec)
        request_id = request["request_id"]
        assert isinstance(request_id, str)
        request_path = self.queue_root / f"{request_id}.request.json"
        response_path = self.queue_root / f"{request_id}.response.json"
        if request_path.exists() or response_path.exists():
            raise TrustedCodexTransportError("trusted supervisor request identity is not fresh")
        envelope = {
            **request,
            "signature": self._request_signing_key.sign(_canonical_bytes(request)).signature.hex(),
        }
        encoded = _canonical_bytes(envelope)
        if len(encoded) > _MAX_FRAME_BYTES:
            raise TrustedCodexTransportError("trusted supervisor request exceeds bounded size")
        self.last_request_sha256 = _sha256(encoded)
        try:
            if self.evidence_root is not None:
                try:
                    evidence_root = self.evidence_root.resolve(strict=True)
                except OSError as exc:
                    raise TrustedCodexTransportError(
                        "trusted supervisor evidence root is unavailable"
                    ) from exc
                if (
                    self.evidence_root.is_symlink()
                    or not self.evidence_root.is_dir()
                    or evidence_root != self.evidence_root
                    or self.evidence_root.parent != spec.workspace
                    or not evidence_root.is_relative_to(spec.workspace)
                ):
                    raise TrustedCodexTransportError(
                        "trusted supervisor evidence root is outside the workspace"
                    )
                _write_receipt_once(self.evidence_root / "request-envelope.json", encoded)
            _write_atomic(request_path, encoded)
            deadline = time.monotonic() + self._timeout_s
            while time.monotonic() < deadline:
                if response_path.is_file() and not response_path.is_symlink():
                    raw = response_path.read_bytes()
                    if self.evidence_root is not None:
                        _write_receipt_once(self.evidence_root / "response-envelope.json", raw)
                    response_path.unlink()
                    request_path.unlink(missing_ok=True)
                    if len(raw) > _MAX_RESPONSE_BYTES:
                        raise TrustedCodexTransportError(
                            "trusted supervisor response exceeds bounded size"
                        )
                    self.last_response_sha256 = _sha256(raw)
                    response = json.loads(raw.decode("utf-8"))
                    return self._validate_response(response, request_id=request_id, spec=spec)
                time.sleep(0.05)
            request_path.unlink(missing_ok=True)
            raise TrustedCodexTransportError("trusted supervisor response deadline exceeded")
        except TrustedCodexTransportError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise TrustedCodexTransportError(
                "trusted supervisor is unavailable or malformed"
            ) from exc

    def _validate_response(
        self,
        response: object,
        *,
        request_id: str,
        spec: SessionSpec,
    ) -> SessionResult:
        if not isinstance(response, dict) or set(response) != {"payload", "signature"}:
            raise TrustedCodexTransportError("trusted supervisor response envelope is not exact")
        payload = response.get("payload")
        signature = response.get("signature")
        if not isinstance(payload, dict) or not isinstance(signature, str) or len(signature) != 128:
            raise TrustedCodexTransportError("trusted supervisor response signature is malformed")
        try:
            self._response_verify_key.verify(_canonical_bytes(payload), bytes.fromhex(signature))
        except (BadSignatureError, ValueError) as exc:
            raise TrustedCodexTransportError(
                "trusted supervisor response signature is invalid"
            ) from exc
        if payload.get("schema") != _SCHEMA or payload.get("request_id") != request_id:
            raise TrustedCodexTransportError("trusted supervisor response fields are not exact")
        if payload.get("ok") is False:
            allowed = {"schema", "ok", "request_id", "error_code", "error"}
            if set(payload) not in (allowed, allowed | {"failure_observation"}):
                raise TrustedCodexTransportError("trusted supervisor failure fields are not exact")
            error_code = payload.get("error_code")
            if error_code not in _FAILURE_CODES or payload.get("error") != _FAILURE_ERROR:
                raise TrustedCodexTransportError(
                    "trusted supervisor failure classification is invalid"
                )
            failure_observation = _validate_failure_observation(payload.get("failure_observation"))
            lifecycle_state = (
                str(failure_observation["lifecycle_state"])
                if failure_observation is not None
                else "STRUCTURED_FAILURE"
            )
            exit_code = failure_observation["exit_code"] if failure_observation is not None else 1
            self.last_observation = failure_observation
            return SessionResult(
                transcript=f"trusted_worker_failure:{error_code}",
                stderr=b"",
                lifecycle_state=lifecycle_state,
                cwd=str(spec.workspace),
                environment_fingerprint="",
                exit_code=exit_code if isinstance(exit_code, int) else 1,
                failure_code=str(error_code),
            )
        if (
            set(payload) != {"schema", "ok", "request_id", "observation"}
            or payload.get("ok") is not True
        ):
            raise TrustedCodexTransportError("trusted supervisor rejected the launch")
        observation = payload.get("observation")
        if not isinstance(observation, dict):
            raise TrustedCodexTransportError("trusted supervisor observation is missing")
        required = {
            "provider_id",
            "model_id",
            "family",
            "request_id",
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "workspace_id",
            "workspace",
            "transcript",
            "stdout_sha256",
            "stderr_sha256",
            "stdout_bytes",
            "stderr_bytes",
            "exit_code",
            "process_state",
            "lifecycle",
            "heartbeat_count",
            "executable",
            "executable_version",
            "environment_fingerprint",
            "profile_sha256",
            "supervisor_identity_sha256",
            "broker_evidence_sha256",
            "broker_request_count",
            "artifact_sha256",
            "boot_id",
            "canaries",
            "fallback_used",
            "manual_chat_bridge",
        }
        if set(observation) != required:
            raise TrustedCodexTransportError("trusted supervisor observation fields are not exact")
        transcript = observation["transcript"]
        canaries = observation["canaries"]
        if (
            observation["provider_id"] != self.provider_id
            or observation["model_id"] != self.model_id
            or observation["family"] != self.model_family
            or observation["request_id"] != request_id
            or observation["task_id"] != spec.task_id
            or observation["goal_id"] != spec.goal_id
            or observation["run_id"] != spec.run_id
            or observation["stage"] != spec.stage
            or observation["workspace_id"] != spec.workspace.name
            or observation["workspace"] != str(spec.workspace)
            or not isinstance(transcript, str)
            or not transcript.strip()
            or observation["stdout_sha256"] != _sha256(transcript.encode("utf-8"))
            or observation["stdout_bytes"] != len(transcript.encode("utf-8"))
            or observation["exit_code"] != 0
            or observation["process_state"] != "RETURNED"
            or observation["lifecycle"] != list(REQUIRED_LIFECYCLE)
            or not isinstance(observation["heartbeat_count"], int)
            or observation["heartbeat_count"] < 1
            or not isinstance(observation["broker_request_count"], int)
            or not 1 <= observation["broker_request_count"] <= MAX_TASK_REQUESTS
            or not isinstance(canaries, dict)
            or any(
                canaries.get(key) != "PASS"
                for key in REQUIRED_CANARIES
                if key != "supervisor_restart_no_fallback"
            )
            or observation["fallback_used"] is not False
            or observation["manual_chat_bridge"] is not False
            or observation["supervisor_identity_sha256"]
            != _sha256(bytes(self._response_verify_key))
        ):
            raise TrustedCodexTransportError(
                "trusted supervisor returned an unqualified observation"
            )
        if observation["canaries"].get("supervisor_restart_no_fallback") == "UNPROVEN":
            raise TrustedCodexTransportError("supervisor restart qualification is pending")
        if not isinstance(observation["boot_id"], str) or not observation["boot_id"]:
            raise TrustedCodexTransportError("trusted supervisor boot identity is missing")
        for field in (
            "stdout_sha256",
            "stderr_sha256",
            "environment_fingerprint",
            "profile_sha256",
            "broker_evidence_sha256",
            "supervisor_identity_sha256",
            "artifact_sha256",
        ):
            value = observation[field]
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise TrustedCodexTransportError(
                    f"trusted supervisor observation hash is invalid: {field}"
                )
        for field in ("stdout_bytes", "stderr_bytes", "exit_code", "heartbeat_count"):
            value = observation[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise TrustedCodexTransportError(
                    f"trusted supervisor observation integer is invalid: {field}"
                )
        self.last_observation = dict(observation)
        return SessionResult(
            transcript=transcript,
            stderr=b"",
            lifecycle_state="RETURNED",
            executable=str(observation["executable"]),
            executable_version=str(observation["executable_version"]),
            cwd=str(spec.workspace),
            environment_fingerprint=str(observation["environment_fingerprint"]),
            exit_code=0,
        )
