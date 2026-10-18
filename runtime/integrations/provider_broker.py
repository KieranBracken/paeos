"""Client for the trusted host-side provider worker supervisor.

The client is deliberately not a launcher. Its parent handoffs are disabled until trusted
disclosure authority is integrated. The installed service, not this caller, constructs the child
environment, filesystem policy, process argv, and Seatbelt profile.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.keystore import load_or_create_signing_key
from kernel.types import Role
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

__all__ = [
    "DEFAULT_LAUNCHER_QUEUE",
    "ConfinedProviderObservation",
    "HostClineCriticTransport",
    "HostConfinedProviderClient",
    "ProviderBrokerError",
    "child_environment_is_clean",
]


class HostClineCriticTransport:
    """One fixed, parent-authenticated Cline/GLM critic capability.

    The bearer is authority to perform one already-selected task, not authority to select a
    provider. Provider authentication remains behind the trusted host supervisor. No reusable
    credential is represented by this object or its child environment.
    """

    provider_id = "cline-pass"
    model_id = "cline-pass/glm-5.3"
    model_family = "glm-5.3"
    allowed_role = Role.CRITIC
    allowed_operation = "critic"
    parent_owns_authentication = True
    allow_fallback = False
    capability_single_use = True
    capability_ttl_s = 45.0
    child_receives_parent_credentials = False
    allowed_environment = (
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "TMPDIR",
        "PAEOS_TASK_BEARER",
        "PAEOS_TASK_BROKER_URL",
    )
    required_observation_fields = frozenset(
        {
            "capability_id",
            "operation",
            "provider_id",
            "model_id",
            "model_family",
            "actual_provider",
            "actual_model",
            "actual_family",
            "fallback_used",
            "lifecycle_state",
            "exit_code",
            "response_content",
            "stdout_sha256",
            "stderr_sha256",
            "stdout_bytes",
            "stderr_bytes",
            "executable",
            "executable_version",
            "environment_fingerprint",
            "argv",
            "profile_sha256",
            "workspace",
            "confinement_canaries",
        }
    )
    rejects_unknown_response_fields = True
    rejects_replay = True
    rejects_expired_capabilities = True
    rejects_provider_failure = True
    rejects_identity_substitution = True
    rejects_hidden_fallback = True

    def __init__(
        self,
        *,
        queue_root: Path = Path("/Users/bob/GitHub/paeos/ops/.trusted-worker/queue"),
        request_signing_key: Any | None = None,
        response_verify_key: VerifyKey | None = None,
        timeout_s: float = 180.0,
    ) -> None:
        if not queue_root.is_absolute() or queue_root.is_symlink():
            raise ProviderBrokerError("trusted launcher queue must be absolute and non-symlinked")
        if isinstance(timeout_s, bool) or not 0 < timeout_s <= 180:
            raise ProviderBrokerError("critic launcher timeout is outside the bounded range")
        self._queue_root = queue_root
        self._request_signing_key = request_signing_key
        self._response_verify_key = response_verify_key
        self._timeout_s = float(timeout_s)
        self.last_observation: dict[str, object] | None = None

    def _authenticate_response(self, raw_response: bytes, request_bytes: bytes) -> dict:
        return _authenticate_provider_response(
            raw_response, request_bytes, self._response_verify_key
        )

    @staticmethod
    def _check_route(role: Role, operation: str) -> None:
        if role is not Role.CRITIC or operation != "critic":
            raise ProviderBrokerError("critic capability route is invalid")

    def issue_task_capability(
        self, *, task_id: str, role: Role, operation: str, now: float | None = None
    ) -> dict[str, object]:
        self._check_route(role, operation)
        if not isinstance(task_id, str) or not task_id.strip() or "\x00" in task_id:
            raise ProviderBrokerError("critic task identity is malformed")
        issued = time.time() if now is None else now
        if isinstance(issued, bool) or not isinstance(issued, (int, float)):
            raise ProviderBrokerError("critic capability time is malformed")
        return {
            "schema": "paeos.trusted-cline-critic-capability/1",
            "operation": operation,
            "capability_id": uuid.uuid4().hex,
            "task_id": task_id,
            "issued_at": float(issued),
            "expires_at": float(issued) + self.capability_ttl_s,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "model_family": self.model_family,
            "role": role.value,
        }

    def redeem_task_capability(
        self,
        *,
        bearer: object,
        task_id: str,
        role: Role,
        operation: str,
        now: float | None = None,
    ) -> str:
        self._check_route(role, operation)
        current = time.time() if now is None else now
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            raise ProviderBrokerError("critic capability time is malformed")
        if not isinstance(bearer, dict) or bearer.get("task_id") != task_id:
            raise ProviderBrokerError("critic capability task identity mismatch")
        if (
            bearer.get("schema") != "paeos.trusted-cline-critic-capability/1"
            or bearer.get("operation") != self.allowed_operation
            or bearer.get("provider_id") != self.provider_id
            or bearer.get("model_id") != self.model_id
            or bearer.get("model_family") != self.model_family
            or bearer.get("role") != self.allowed_role.value
        ):
            raise ProviderBrokerError("critic capability fixed route mismatch")
        issued_at = bearer.get("issued_at")
        expires_at = bearer.get("expires_at")
        if (
            isinstance(issued_at, bool)
            or isinstance(expires_at, bool)
            or not isinstance(issued_at, (int, float))
            or not isinstance(expires_at, (int, float))
            or expires_at <= issued_at
            or expires_at - issued_at > self.capability_ttl_s
            or issued_at > float(current) + 15.0
        ):
            raise ProviderBrokerError("critic capability expiry is malformed")
        if float(current) >= expires_at:
            raise ProviderBrokerError("critic capability is expired")
        capability_id = bearer.get("capability_id")
        if (
            not isinstance(capability_id, str)
            or len(capability_id) != 32
            or any(character not in "0123456789abcdef" for character in capability_id)
        ):
            raise ProviderBrokerError("critic capability identity is malformed")
        return capability_id

    @classmethod
    def validate_supervisor_observation(
        cls, *, observation: object, capability_id: str
    ) -> dict[str, object]:
        if not isinstance(observation, dict) or set(observation) != cls.required_observation_fields:
            raise ProviderBrokerError("critic supervisor observation fields are not exact")
        content = observation.get("response_content")
        argv = observation.get("argv")
        hashes = ("stdout_sha256", "stderr_sha256", "environment_fingerprint", "profile_sha256")
        byte_counts = ("stdout_bytes", "stderr_bytes")
        canaries = observation.get("confinement_canaries")
        workspace = observation.get("workspace")
        if (
            observation.get("capability_id") != capability_id
            or observation.get("operation") != cls.allowed_operation
            or observation.get("provider_id") != cls.provider_id
            or observation.get("model_id") != cls.model_id
            or observation.get("model_family") != cls.model_family
            or observation.get("actual_provider") != cls.provider_id
            or observation.get("actual_model") != cls.model_id
            or observation.get("actual_family") != cls.model_family
            or observation.get("fallback_used") is not False
            or observation.get("lifecycle_state") != "RETURNED"
            or observation.get("exit_code") != 0
            or not isinstance(content, str)
            or not content.strip()
            or len(content.encode("utf-8")) > _MAX_RESPONSE_BYTES
            or not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
            or any(
                not isinstance(observation.get(name), str)
                or len(str(observation[name])) != 64
                or any(c not in "0123456789abcdef" for c in str(observation[name]))
                for name in hashes
            )
            or any(
                isinstance(observation.get(name), bool)
                or not isinstance(observation.get(name), int)
                or int(observation[name]) < 0
                or int(observation[name]) > _MAX_FRAME_BYTES
                for name in byte_counts
            )
            or not isinstance(observation.get("executable"), str)
            or not str(observation["executable"]).startswith("/")
            or not isinstance(observation.get("executable_version"), str)
            or len(str(observation["executable_version"])) != 71
            or not str(observation["executable_version"]).startswith("sha256:")
            or any(c not in "0123456789abcdef" for c in str(observation["executable_version"])[7:])
            or not isinstance(observation.get("workspace"), str)
            or not str(observation["workspace"]).startswith("/")
            or Path(str(workspace)).name != capability_id
            or Path(str(workspace)).is_symlink()
            or argv[:2] != ["/usr/bin/sandbox-exec", "-p"]
            or len(argv) != 6
            or argv[3:] != ["/usr/bin/curl", "--config", str(Path(str(workspace)) / "curl.conf")]
            or observation.get("executable") != "/usr/bin/sandbox-exec"
            or _sha256(str(argv[2]).encode("utf-8")) != observation.get("profile_sha256")
            or not cls._valid_canaries(canaries)
        ):
            raise ProviderBrokerError("critic supervisor observation is unqualified")
        return dict(observation)

    @staticmethod
    def _valid_canaries(value: object) -> bool:
        expected = {
            "parent_secret_or_provider_credential",
            "approved_read",
            "approved_write",
            "forbidden_file_read",
            "forbidden_directory_list",
            "forbidden_write",
            "symlink_escape",
            "traversal_escape",
            "subprocess_inheritance",
        }
        if not isinstance(value, dict) or set(value) != {"results", "process"}:
            return False
        results, process = value.get("results"), value.get("process")
        process_hashes = (
            "stdout_sha256",
            "stderr_sha256",
            "environment_fingerprint",
            "profile_sha256",
        )
        return (
            isinstance(results, dict)
            and set(results) == expected
            and all(result == "PASS" for result in results.values())
            and isinstance(process, dict)
            and set(process)
            == {
                "exit_code",
                "lifecycle_state",
                "stdout_bytes",
                "stdout_sha256",
                "stderr_bytes",
                "stderr_sha256",
                "environment_fingerprint",
                "profile_sha256",
            }
            and process.get("exit_code") == 0
            and process.get("lifecycle_state") == "RETURNED"
            and all(
                isinstance(process.get(name), str)
                and len(process[name]) == 64
                and all(c in "0123456789abcdef" for c in process[name])
                for name in process_hashes
            )
            and all(
                not isinstance(process.get(name), bool)
                and isinstance(process.get(name), int)
                and 0 <= process[name] <= _MAX_FRAME_BYTES
                for name in ("stdout_bytes", "stderr_bytes")
            )
        )

    def run(self, spec: Any) -> Any:
        """Dispatch one signed task-bound request through the trusted parent queue."""
        _require_disclosure_authority()
        if spec.stage != "CRITIQUE":
            raise ProviderBrokerError("critic capability stage is not CRITIQUE")
        _require_response_verifier(self._response_verify_key)
        capability = self.issue_task_capability(
            task_id=spec.task_id, role=Role.CRITIC, operation=self.allowed_operation
        )
        capability.update(
            {
                "goal_id": spec.goal_id,
                "run_id": spec.run_id,
                "stage": spec.stage,
                "prompt": spec.prompt,
            }
        )
        capability_id = self.redeem_task_capability(
            bearer=capability,
            task_id=spec.task_id,
            role=Role.CRITIC,
            operation=self.allowed_operation,
        )
        if len(spec.prompt.encode("utf-8")) > _MAX_PROMPT_BYTES or "\x00" in spec.prompt:
            raise ProviderBrokerError("critic prompt is oversized or malformed")
        key = self._request_signing_key
        if key is None:
            key = self._request_signing_key = load_or_create_signing_key()
        envelope = {
            **capability,
            "signature": key.sign(_canonical_bytes(capability)).signature.hex(),
        }
        payload = _canonical_bytes(envelope)
        self._queue_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        request_path = self._queue_root / f"{capability_id}.request.json"
        response_path = self._queue_root / f"{capability_id}.response.json"
        temporary_path = self._queue_root / f".{capability_id}.request.tmp"
        if len(payload) > _MAX_FRAME_BYTES or any(
            p.exists() for p in (request_path, response_path, temporary_path)
        ):
            raise ProviderBrokerError("critic capability frame or paths are invalid")
        try:
            fd = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                offset = 0
                while offset < len(payload):
                    written = os.write(fd, payload[offset:])
                    if written <= 0:
                        raise ProviderBrokerError("critic queue write made no progress")
                    offset += written
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(temporary_path, request_path)
            deadline = time.monotonic() + self._timeout_s
            while time.monotonic() < deadline:
                if response_path.is_file() and not response_path.is_symlink():
                    raw = response_path.read_bytes()
                    if len(raw) > _MAX_FRAME_BYTES:
                        raise ProviderBrokerError("critic supervisor response is oversized")
                    break
                time.sleep(0.05)
            else:
                request_path.unlink(missing_ok=True)
                raise ProviderBrokerError("critic supervisor response deadline exceeded")
            response = self._authenticate_response(raw, payload)
            response_path.unlink()
            request_path.unlink(missing_ok=True)
        except ProviderBrokerError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderBrokerError("critic supervisor queue failed closed") from exc
        if not isinstance(response, dict) or response.get("capability_id") != capability_id:
            raise ProviderBrokerError("critic supervisor response attribution mismatch")
        if response.get("ok") is not True:
            raise ProviderBrokerError(
                f"critic supervisor rejected capability: {response.get('error_code', 'unknown')}"
            )
        observation = response.get("observation")
        qualified = self.validate_supervisor_observation(
            observation=observation, capability_id=capability_id
        )
        self.last_observation = dict(qualified)
        # Import lazily to avoid the integrations package initialization cycle.
        from runtime.integrations import SessionResult

        return SessionResult(
            transcript=str(qualified["response_content"]),
            lifecycle_state=str(qualified["lifecycle_state"]),
            executable=str(qualified["executable"]),
            executable_version=str(qualified["executable_version"]),
            cwd=str(qualified["workspace"]),
            environment_fingerprint=str(qualified["environment_fingerprint"]),
            exit_code=int(qualified["exit_code"]),
            stdout_sha256=str(qualified["stdout_sha256"]),
            stderr_sha256=str(qualified["stderr_sha256"]),
            stdout_bytes=int(qualified["stdout_bytes"]),
            stderr_bytes=int(qualified["stderr_bytes"]),
            argv=tuple(qualified["argv"]),
            profile_sha256=str(qualified["profile_sha256"]),
            workspace=str(qualified["workspace"]),
            confinement_canaries=dict(qualified["confinement_canaries"]),
            actual_provider=str(qualified["actual_provider"]),
            actual_model=str(qualified["actual_model"]),
            actual_family=str(qualified["actual_family"]),
        )


DEFAULT_LAUNCHER_QUEUE = Path("/Users/bob/GitHub/paeos/ops/.trusted-worker/queue")
_SCHEMA = "paeos.trusted-worker-capability/1"
_OPERATION = "provider_chat"
_PROVIDER = "openrouter"
_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
_FAMILY = "nemotron"
_MAX_PROMPT_BYTES = 4096
_MAX_RESPONSE_BYTES = 256 * 1024
_MAX_FRAME_BYTES = 512 * 1024
_PROVIDER_ENV_NAMES = frozenset(
    {
        "GEMINI_API_KEY",
        "CLINE_API_KEY",
        "NVIDIA_API_KEY",
        "KILO_API_KEY",
        "OPENROUTER_API_KEY",
    }
)


class ProviderBrokerError(RuntimeError):
    """A provider boundary violation or unavailable trusted service."""


def _require_disclosure_authority() -> None:
    """Deny locally until a reviewed trusted disclosure consumer exists."""
    raise ProviderBrokerError("trusted disclosure authority is unavailable")


@dataclass(frozen=True, slots=True)
class ConfinedProviderObservation:
    provider_id: str
    model_id: str
    model_family: str
    actual_model: str
    actual_family: str
    response_content: str
    stdout_sha256: str
    stderr_sha256: str
    stdout_bytes: int
    stderr_bytes: int
    exit_code: int
    lifecycle_state: str
    executable: str
    executable_version: str
    environment_fingerprint: str
    argv: tuple[str, ...]
    profile_sha256: str
    workspace: str
    confinement_canaries: dict[str, object]
    capability_id: str


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_response_verifier(key: VerifyKey | None) -> VerifyKey:
    if not isinstance(key, VerifyKey):
        raise ProviderBrokerError("provider response verification authority is unavailable")
    return key


def _strict_response_json(raw: bytes) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_value):
        raise ValueError("nonfinite JSON value")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def _authenticate_provider_response(
    raw_response: bytes, request_bytes: bytes, verify_key: VerifyKey | None
) -> dict:
    """Authenticate an exact request/reply pair; this does not qualify its observation.

    The caller retains the actual dispatched request bytes. No shared last-request state,
    operational key loader, or new replay ledger is introduced here. Durable attempt
    reconciliation remains the responsibility of the owning execution controller.
    """
    key = _require_response_verifier(verify_key)
    if any(
        type(raw) is not bytes or len(raw) > _MAX_FRAME_BYTES
        for raw in (raw_response, request_bytes)
    ):
        raise ProviderBrokerError("provider response frame is invalid")
    try:
        envelope = _strict_response_json(raw_response)
        if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
            raise ValueError("invalid envelope")
        payload, signature = envelope["payload"], envelope["signature"]
        if not isinstance(payload, dict) or not isinstance(signature, str) or len(signature) != 128:
            raise ValueError("invalid signature encoding")
        key.verify(
            b"PAEOS-PROVIDER-RESPONSE-V1\0" + _canonical_bytes(payload),
            bytes.fromhex(signature),
        )
        # Interpret result and authority bindings only after producer authentication.
        if set(payload) != {"schema", "request_sha256", "response"}:
            raise ValueError("invalid signed payload")
        if payload["schema"] != "paeos.trusted-worker-signed-response/1":
            raise ValueError("invalid signed schema")
        if payload["request_sha256"] != _sha256(request_bytes):
            raise ValueError("request digest mismatch")
        request = _strict_response_json(request_bytes)
        response = payload["response"]
        if not isinstance(request, dict) or not isinstance(response, dict):
            raise ValueError("invalid request or result")
        capability_id = request.get("capability_id")
        if (
            not isinstance(capability_id, str)
            or len(capability_id) != 32
            or any(c not in "0123456789abcdef" for c in capability_id)
            or response.get("capability_id") != capability_id
            or response.get("schema") != "paeos.trusted-worker-service/1"
        ):
            raise ValueError("request attribution mismatch")
        if response.get("ok") is True:
            if set(response) != {"schema", "ok", "capability_id", "observation"}:
                raise ValueError("invalid success fields")
            observation = response["observation"]
            if not isinstance(observation, dict):
                raise ValueError("invalid observation")
            for field in ("provider_id", "model_id", "model_family"):
                if (
                    not isinstance(request.get(field), str)
                    or observation.get(field) != request[field]
                ):
                    raise ValueError("route mismatch")
            for field in ("capability_id", "operation"):
                if field in observation and observation[field] != request.get(field):
                    raise ValueError("observation attribution mismatch")
        elif response.get("ok") is False:
            fields = {"schema", "ok", "capability_id", "error", "error_code"}
            if set(response) not in (fields, fields | {"failure_observation"}):
                raise ValueError("invalid failure fields")
        else:
            raise ValueError("invalid result status")
        return response
    except (ValueError, TypeError, UnicodeError, RecursionError, BadSignatureError):
        raise ProviderBrokerError("provider response authentication or binding failed") from None


def child_environment_is_clean(environment: Mapping[str, str]) -> bool:
    """Return whether an environment contains only the fixed non-secret worker keys."""

    required = {"HOME", "LANG", "LC_ALL", "PATH", "TMPDIR"}
    return (
        set(environment) == required
        and not _PROVIDER_ENV_NAMES.intersection(environment)
        and environment.get("LC_ALL") == "C"
        and environment.get("LANG") == "C.UTF-8"
    )


class HostConfinedProviderClient:
    """The only PAEOS-side capability exposed by the trusted launcher."""

    provider_id = _PROVIDER
    model_id = _MODEL
    model_family = _FAMILY
    allowed_operation = _OPERATION
    allow_fallback = False
    allowed_argv = None
    allowed_environment = None

    def __init__(
        self,
        *,
        socket_path: Path | None = None,
        queue_root: Path = DEFAULT_LAUNCHER_QUEUE,
        signing_key: Any | None = None,
        response_verify_key: VerifyKey | None = None,
        timeout_s: float = 75.0,
    ) -> None:
        if socket_path is not None and (not socket_path.is_absolute() or socket_path.is_symlink()):
            raise ProviderBrokerError("legacy socket parameter is invalid")
        if not queue_root.is_absolute() or queue_root.is_symlink():
            raise ProviderBrokerError("trusted launcher queue must be an absolute non-symlink path")
        if timeout_s <= 0 or timeout_s > 180:
            raise ProviderBrokerError("trusted launcher timeout is outside the bounded range")
        self._signing_key = signing_key
        self._response_verify_key = response_verify_key
        self._queue_root = queue_root
        self._timeout_s = timeout_s

    def _authenticate_response(self, raw_response: bytes, request_bytes: bytes) -> dict:
        return _authenticate_provider_response(
            raw_response, request_bytes, self._response_verify_key
        )

    def _key(self) -> Any:
        if self._signing_key is None:
            self._signing_key = load_or_create_signing_key()
        return self._signing_key

    def _capability(self, prompt: str) -> dict[str, object]:
        _require_disclosure_authority()
        _require_response_verifier(self._response_verify_key)
        if not isinstance(prompt, str) or not prompt.strip():
            raise ProviderBrokerError("provider prompt is empty")
        if len(prompt.encode("utf-8")) > _MAX_PROMPT_BYTES or "\x00" in prompt:
            raise ProviderBrokerError("provider prompt is oversized or contains NUL")
        now = time.time()
        payload: dict[str, object] = {
            "schema": _SCHEMA,
            "operation": _OPERATION,
            "capability_id": uuid.uuid4().hex,
            "issued_at": now,
            "expires_at": now + 45.0,
            "provider_id": _PROVIDER,
            "model_id": _MODEL,
            "model_family": _FAMILY,
            "data_class": "PUBLIC",
            "task_class": "ROUTINE",
            "prompt": prompt,
        }
        signature = self._key().sign(_canonical_bytes(payload)).signature.hex()
        return {**payload, "signature": signature}

    def request(self, prompt: str) -> ConfinedProviderObservation:
        _require_disclosure_authority()
        _require_response_verifier(self._response_verify_key)
        capability = self._capability(prompt)
        frame = (_canonical_bytes(capability)).decode("utf-8")
        if len(frame.encode("utf-8")) > _MAX_FRAME_BYTES:
            raise ProviderBrokerError("capability frame exceeds the bounded IPC size")
        self._queue_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        capability_id = str(capability["capability_id"])
        request_path = self._queue_root / f"{capability_id}.request.json"
        response_path = self._queue_root / f"{capability_id}.response.json"
        temporary_path = self._queue_root / f".{capability_id}.request.tmp"
        if request_path.exists() or response_path.exists() or temporary_path.exists():
            raise ProviderBrokerError("trusted launcher capability paths are not fresh")
        try:
            payload = frame.encode("utf-8")
            fd = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                offset = 0
                while offset < len(payload):
                    written = os.write(fd, payload[offset:])
                    if written <= 0:
                        raise ProviderBrokerError("trusted launcher request write made no progress")
                    offset += written
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(temporary_path, request_path)
            deadline = time.monotonic() + self._timeout_s
            while time.monotonic() < deadline:
                if response_path.is_file() and not response_path.is_symlink():
                    raw_response = response_path.read_bytes()
                    if len(raw_response) > _MAX_FRAME_BYTES:
                        raise ProviderBrokerError(
                            "trusted launcher response exceeds the bounded IPC size"
                        )
                    break
                time.sleep(0.05)
            else:
                request_path.unlink(missing_ok=True)
                raise ProviderBrokerError("trusted launcher response deadline exceeded")
        except ProviderBrokerError:
            raise
        except (OSError, ValueError, TimeoutError) as exc:
            raise ProviderBrokerError("trusted launcher is unavailable") from exc
        response = self._authenticate_response(raw_response, payload)
        try:
            response_path.unlink()
            request_path.unlink(missing_ok=True)
        except OSError:
            raise ProviderBrokerError("authenticated provider response cleanup failed") from None
        if not isinstance(response, dict):
            raise ProviderBrokerError("trusted launcher response envelope is malformed")
        if response.get("capability_id") != capability["capability_id"]:
            raise ProviderBrokerError("trusted launcher capability attribution mismatch")
        if response.get("ok") is not True:
            code = response.get("error_code")
            if not isinstance(code, str) or not code:
                code = "unknown"
            raise ProviderBrokerError(f"trusted launcher rejected the capability: {code}")
        observation = response.get("observation")
        if not isinstance(observation, dict):
            raise ProviderBrokerError("trusted launcher observation is missing")
        return self._validate_observation(observation, str(capability["capability_id"]))

    @staticmethod
    def _validate_observation(
        observation: dict[str, object], capability_id: str
    ) -> ConfinedProviderObservation:
        required = {
            "provider_id",
            "model_id",
            "model_family",
            "actual_model",
            "actual_family",
            "response_content",
            "stdout_sha256",
            "stderr_sha256",
            "stdout_bytes",
            "stderr_bytes",
            "exit_code",
            "lifecycle_state",
            "executable",
            "executable_version",
            "environment_fingerprint",
            "argv",
            "profile_sha256",
            "workspace",
            "confinement_canaries",
        }
        if set(observation) != required:
            raise ProviderBrokerError("trusted launcher observation fields are not exact")
        content = observation["response_content"]
        argv = observation["argv"]
        if (
            observation["provider_id"] != _PROVIDER
            or observation["model_id"] != _MODEL
            or not isinstance(observation["model_family"], str)
            or observation["model_family"].lower() in {"gpt", "unknown"}
            or not isinstance(observation["actual_model"], str)
            or not observation["actual_model"].strip()
            or observation["actual_family"] != observation["model_family"]
            or not isinstance(observation["actual_family"], str)
            or observation["actual_family"].lower() in {"gpt", "unknown"}
            or not isinstance(content, str)
            or not content.strip()
            or len(content.encode("utf-8")) > _MAX_RESPONSE_BYTES
            or observation["exit_code"] != 0
            or observation["lifecycle_state"] != "RETURNED"
            or not isinstance(argv, list)
            or any(not isinstance(item, str) for item in argv)
        ):
            raise ProviderBrokerError(
                "trusted launcher returned an unqualified provider observation"
            )
        typed_ints = ("stdout_bytes", "stderr_bytes", "exit_code")
        if any(
            isinstance(observation[name], bool) or not isinstance(observation[name], int)
            for name in typed_ints
        ):
            raise ProviderBrokerError("trusted launcher byte or exit fields are malformed")
        canaries = observation["confinement_canaries"]
        expected_canaries = {
            "parent_secret_or_provider_credential",
            "approved_read",
            "approved_write",
            "forbidden_file_read",
            "forbidden_directory_list",
            "forbidden_write",
            "symlink_escape",
            "traversal_escape",
            "subprocess_inheritance",
        }
        if not isinstance(canaries, dict) or set(canaries) != {"results", "process"}:
            raise ProviderBrokerError("trusted launcher confinement canaries are missing")
        results = canaries["results"]
        process = canaries["process"]
        if (
            not isinstance(results, dict)
            or set(results) != expected_canaries
            or any(value != "PASS" for value in results.values())
            or not isinstance(process, dict)
            or set(process)
            != {
                "exit_code",
                "lifecycle_state",
                "stdout_bytes",
                "stdout_sha256",
                "stderr_bytes",
                "stderr_sha256",
                "environment_fingerprint",
                "profile_sha256",
            }
            or process.get("exit_code") != 0
            or process.get("lifecycle_state") != "RETURNED"
        ):
            raise ProviderBrokerError("trusted launcher confinement canaries failed")
        return ConfinedProviderObservation(
            provider_id=_PROVIDER,
            model_id=_MODEL,
            model_family=str(observation["model_family"]),
            actual_model=str(observation["actual_model"]),
            actual_family=str(observation["actual_family"]),
            response_content=content,
            stdout_sha256=str(observation["stdout_sha256"]),
            stderr_sha256=str(observation["stderr_sha256"]),
            stdout_bytes=int(observation["stdout_bytes"]),
            stderr_bytes=int(observation["stderr_bytes"]),
            exit_code=0,
            lifecycle_state="RETURNED",
            executable=str(observation["executable"]),
            executable_version=str(observation["executable_version"]),
            environment_fingerprint=str(observation["environment_fingerprint"]),
            argv=tuple(argv),
            profile_sha256=str(observation["profile_sha256"]),
            workspace=str(observation["workspace"]),
            confinement_canaries=dict(canaries),
            capability_id=capability_id,
        )
