"""Deterministic host-side supervisor for the PAEOS Codex Builder.

The supervisor is infrastructure, not an agent.  It accepts only a signed task request, derives
the workspace and every launch property from its fixed policy, applies the OS boundary before the
Codex process starts, and returns a signed observation.  It has no caller-selected argv,
environment, filesystem roots, sandbox profile, provider, model, or fallback path.

This service is intentionally separate from ``trusted_worker_launcher_service.py``.  That older
service is a different fixed OpenRouter capability and is not repurposed for the Codex Builder.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import time
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey
from runtime.builder_transport import REQUIRED_CANARIES, REQUIRED_LIFECYCLE
from runtime.integrations.process_supervisor import (
    ProcessLifecycleState,
    ProcessObservation,
    ProcessSupervisorError,
    run_bounded_process,
)
from runtime.integrations.task_scoped_responses_broker import (
    MAX_TASK_REQUESTS,
    ParentOwnedResponsesBroker,
)
from runtime.integrations.worker_confinement import (
    WorkerConfinementError,
    build_provider_environment,
    policy_for_worker,
)
from runtime.planner_transport import PLANNER_STAGES, contract_markers_for

__all__ = [
    "CAPABILITY_SCHEMA",
    "MODEL_ID",
    "PLANNER_CAPABILITY_SCHEMA",
    "PLANNER_MODEL_ID",
    "PROVIDER_ID",
    "SERVICE_SCHEMA",
    "TrustedCodexWorkerSupervisor",
    "_canonical_bytes",
    "main",
    "serve",
    "verify_bundle_manifest",
]

SERVICE_SCHEMA = "paeos.trusted-codex-worker-service/1"
CAPABILITY_SCHEMA = "paeos.trusted-codex-launch/1"
PLANNER_CAPABILITY_SCHEMA = "paeos.trusted-codex-planner-launch/1"
PROVIDER_ID = "codex"
MODEL_ID = "gpt-5.6-sol"
PLANNER_MODEL_ID = "gpt-5.6-luna"
FAMILY = "gpt"
CODEX_EXECUTABLE = Path("/opt/homebrew/bin/codex")
CODEX_INSTALL_ROOT = Path("/opt/homebrew/Caskroom/codex")
CANARY_EXECUTABLE = Path("/bin/sh")
MAX_PROMPT_BYTES = 64 * 1024
MAX_FRAME_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
CAPABILITY_TTL_SECONDS = 90.0
# The old fixed 300-second window terminated live Builder sessions after the provider had already
# returned HTTP 200.  Keep the supervisor deadline finite while allowing a bounded P1 stage to
# finish its authenticated, confined exchange.
BUILDER_EXECUTION_TIMEOUT_S = 600.0
CAPABILITY_ID_RE = re.compile(r"^[0-9a-f]{32}$")
REQUEST_ID_RE = CAPABILITY_ID_RE
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

_REQUEST_FIELDS = frozenset(
    {
        "schema",
        "request_id",
        "task_id",
        "goal_id",
        "run_id",
        "stage",
        "workspace_id",
        "prompt",
        "issued_at",
        "expires_at",
        "provider_id",
        "model_id",
        "family",
        "fallback_used",
        "manual_chat_bridge",
    }
)

_QUALIFICATION_TASK_PREFIX = "t-builder-transport-qualification-"
_QUALIFICATION_GOAL_PREFIX = "g-builder-transport-qualification-"
_QUALIFICATION_RUN_PREFIX = "r-builder-transport-qualification-"
_QUALIFICATION_NONCE_RE = re.compile(r"^[0-9a-f]{32}$")
_PLANNER_QUALIFICATION_IDENTITY = (
    "t-luna-planner-qualification",
    "g-luna-planner-qualification",
    "r-luna-planner-qualification",
)


def _qualification_nonce(
    task_id: object, goal_id: object, run_id: object, stage: object
) -> str | None:
    """Return the shared fresh nonce only for the exact bootstrap identity tuple."""

    if stage != "IMPLEMENT" or not all(
        isinstance(item, str) for item in (task_id, goal_id, run_id)
    ):
        return None
    if not task_id.startswith(_QUALIFICATION_TASK_PREFIX):
        return None
    nonce = task_id.removeprefix(_QUALIFICATION_TASK_PREFIX)
    if (
        _QUALIFICATION_NONCE_RE.fullmatch(nonce) is None
        or goal_id != _QUALIFICATION_GOAL_PREFIX + nonce
        or run_id != _QUALIFICATION_RUN_PREFIX + nonce
    ):
        return None
    return nonce


class SupervisorFailure(RuntimeError):
    """A bounded, content-free supervisor failure classification."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        observation: dict[str, object] | None = None,
        failure_boundary: str | None = None,
    ):
        self.code = code
        self.observation = observation
        self.failure_boundary = failure_boundary
        super().__init__(message)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_path(path: Path, *, label: str, must_exist: bool = False) -> Path:
    if not path.is_absolute() or path.is_symlink() or ".." in path.parts:
        raise SupervisorFailure("path_failure", f"{label} is not absolute and canonical")
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as exc:
        raise SupervisorFailure("path_failure", f"{label} is unavailable") from exc
    if resolved != path:
        raise SupervisorFailure("path_failure", f"{label} crosses a symlink")
    return resolved


def _fixed_codex_executable() -> Path:
    """Resolve the fixed Homebrew launcher only within the pinned Codex install root."""

    launcher = CODEX_EXECUTABLE
    install_root = CODEX_INSTALL_ROOT
    if (
        not launcher.is_absolute()
        or ".." in launcher.parts
        or not install_root.is_absolute()
        or ".." in install_root.parts
        or install_root.is_symlink()
    ):
        raise SupervisorFailure("executable_failure", "fixed Codex executable path is unsafe")
    try:
        canonical_root = install_root.resolve(strict=True)
        executable = launcher.resolve(strict=True)
    except OSError as exc:
        raise SupervisorFailure(
            "executable_failure", "fixed Codex executable is unavailable"
        ) from exc
    if canonical_root != install_root or executable.is_symlink() or not executable.is_file():
        raise SupervisorFailure("executable_failure", "fixed Codex executable is unavailable")
    try:
        executable.relative_to(canonical_root)
    except ValueError as exc:
        raise SupervisorFailure(
            "executable_failure", "fixed Codex executable escaped the pinned install root"
        ) from exc
    if (
        executable.name != "codex"
        or executable.parent.name != "bin"
        or not os.access(executable, os.X_OK)
    ):
        raise SupervisorFailure("executable_failure", "fixed Codex executable is unavailable")
    return executable


def _codex_argv(
    executable: Path,
    *,
    prompt: str,
    workspace: Path,
    broker_base_url: str,
    model_id: str = MODEL_ID,
) -> tuple[str, ...]:
    """Build the fixed custom-provider invocation without embedding broker credentials."""

    if not broker_base_url.startswith("http://127.0.0.1:") or not broker_base_url.endswith("/v1"):
        raise SupervisorFailure("broker_failure", "task broker URL is not fixed to loopback")
    if model_id not in {MODEL_ID, PLANNER_MODEL_ID}:
        raise SupervisorFailure(
            "capability_failure", "Codex model is not an authorized fixed route"
        )
    return (
        str(executable),
        "exec",
        prompt,
        "-m",
        model_id,
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "-C",
        str(workspace),
        "-c",
        'model_provider="paeos_broker"',
        "-c",
        'model_providers.paeos_broker.name="PAEOS Broker"',
        "-c",
        f'model_providers.paeos_broker.base_url="{broker_base_url}"',
        "-c",
        'model_providers.paeos_broker.env_key="PAEOS_TASK_BROKER_TOKEN"',
        "-c",
        'model_providers.paeos_broker.wire_api="responses"',
        "-c",
        "model_providers.paeos_broker.request_max_retries=0",
        "-c",
        "model_providers.paeos_broker.stream_max_retries=0",
        "-c",
        "model_providers.paeos_broker.requires_openai_auth=false",
    )


def _write_atomic(path: Path, payload: bytes) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise SupervisorFailure("state_failure", "supervisor state path is unsafe")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise SupervisorFailure("state_failure", "supervisor state write made no progress")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _strict_json(raw: bytes) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise SupervisorFailure("protocol_failure", "duplicate JSON field")
            result[key] = value
        return result

    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupervisorFailure("protocol_failure", "request is not strict UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise SupervisorFailure("protocol_failure", "request is not a JSON object")
    return document


def _hex_key(path: Path, *, label: str, private: bool = False) -> bytes:
    path = _safe_path(path, label=label, must_exist=True)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        raw = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise SupervisorFailure("identity_failure", f"{label} cannot be read") from exc
    if (mode & 0o077 if private else mode & 0o022) or len(raw) != 64:
        raise SupervisorFailure("identity_failure", f"{label} permissions or length are invalid")
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise SupervisorFailure("identity_failure", f"{label} is not hexadecimal") from exc


def _observation_facts(observation: ProcessObservation) -> dict[str, object]:
    return {
        "lifecycle_state": observation.lifecycle_state.value,
        "exit_code": observation.exit_code,
        "stdout_bytes": len(observation.stdout),
        "stdout_sha256": _sha256(observation.stdout),
        "stderr_bytes": len(observation.stderr),
        "stderr_sha256": _sha256(observation.stderr),
    }


def _failure_lifecycle_state(observation: dict[str, object] | None) -> str:
    if observation is not None and observation.get("lifecycle_state") == "TIMED_OUT":
        return "TIMED_OUT"
    return "STRUCTURED_FAILURE"


def _workspace_tree_sha256(root: Path) -> str:
    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SupervisorFailure("confinement_failure", "worker workspace contains a symlink")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if not relative or relative.startswith("../"):
            raise SupervisorFailure("confinement_failure", "worker workspace path escaped root")
        entries.append((relative, _sha256(path.read_bytes())))
    return _sha256(_canonical_bytes(entries))


def verify_bundle_manifest(bundle_root: Path, manifest_path: Path) -> None:
    """Verify the immutable supervisor bundle before launchd accepts requests."""

    bundle_root = _safe_path(bundle_root, label="supervisor bundle", must_exist=True)
    manifest_path = _safe_path(manifest_path, label="supervisor bundle manifest", must_exist=True)
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupervisorFailure(
            "identity_failure", "supervisor bundle manifest is unreadable"
        ) from exc
    if not isinstance(document, dict) or document.get("schema") != "paeos.trusted-codex-bundle/1":
        raise SupervisorFailure("identity_failure", "supervisor bundle manifest schema is invalid")
    files = document.get("files")
    if not isinstance(files, dict) or not files:
        raise SupervisorFailure("identity_failure", "supervisor bundle manifest files are missing")
    expected_paths: set[Path] = set()
    for relative, expected in files.items():
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(expected, str)
            or len(expected) != 64
        ):
            raise SupervisorFailure(
                "identity_failure", "supervisor bundle manifest entry is malformed"
            )
        candidate = _safe_path(
            bundle_root / relative, label="supervisor bundle file", must_exist=True
        )
        if not candidate.is_file() or _sha256(candidate.read_bytes()) != expected:
            raise SupervisorFailure(
                "identity_failure", "supervisor bundle manifest verification failed"
            )
        expected_paths.add(candidate)
    actual_paths = {
        path for path in bundle_root.rglob("*") if path.is_file() and not path.is_symlink()
    }
    if actual_paths != expected_paths:
        raise SupervisorFailure("identity_failure", "supervisor bundle contains unmanifested files")


def _canary_program() -> str:
    """Return the supervisor-authored confinement discriminator executed in the child boundary."""

    # Use the macOS base-system shell.  /usr/bin/python3 is an Xcode developer-tools shim on
    # machines without the CLT package and can terminate before executing the discriminator.
    return """\
set -u
read_path=$1
write_path=$2
forbidden=$3
forbidden_write=$4
symlink=$5
traversal=$6
traversal_target=$7
provider_auth=$8
failed=0
pass() { printf '%s=PASS\\n' "$1"; }
fail() { printf '%s=FAIL\\n' "$1"; failed=1; }

if [ -z "${PAEOS_SYNTHETIC_PARENT_SECRET+x}" ]; then pass parent_secret_invisible; else fail parent_secret_invisible; fi
if /usr/bin/env | /usr/bin/grep -Eq '(^|_)(OPENAI_API_KEY|[A-Z0-9_]+_API_KEY)='; then
    fail provider_credential_absent
elif /bin/cat "$provider_auth" >/dev/null 2>&1; then
    fail provider_credential_absent
else
    pass provider_credential_absent
fi
if IFS= read -r value < "$read_path" && [ "$value" = PAEOS_APPROVED_READ ]; then pass approved_read; else fail approved_read; fi
if IFS= read -r _value < "$forbidden" 2>/dev/null; then fail forbidden_read_denied; else pass forbidden_read_denied; fi
if printf forbidden > "$forbidden_write" 2>/dev/null; then fail forbidden_write_denied; else pass forbidden_write_denied; fi
if printf 'PAEOS_APPROVED_WRITE\\n' > "$write_path" && IFS= read -r value < "$write_path" && [ "$value" = PAEOS_APPROVED_WRITE ]; then pass approved_write; else fail approved_write; fi
if IFS= read -r _value < "$symlink" 2>/dev/null; then fail symlink_escape_denied; else pass symlink_escape_denied; fi
if printf traversal > "$traversal" 2>/dev/null; then fail traversal_escape_denied; else pass traversal_escape_denied; fi
if /bin/cat "$forbidden" >/dev/null 2>&1 || [ -e "$traversal_target" ]; then fail child_subprocess_confined; else pass child_subprocess_confined; fi
exit "$failed"
"""


class TrustedCodexWorkerSupervisor:
    """Single-purpose host supervisor for signed Codex Builder launches."""

    def __init__(
        self,
        *,
        queue_root: Path,
        state_root: Path,
        workspace_root: Path,
        codex_home: Path,
        request_verify_key_path: Path,
        response_signing_key: SigningKey | None = None,
        response_signing_key_path: Path | None = None,
        qualification_path: Path | None = None,
        planner_qualification_path: Path | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.queue_root = _safe_path(queue_root, label="queue root")
        self.state_root = _safe_path(state_root, label="state root")
        self.workspace_root = _safe_path(workspace_root, label="workspace root")
        self.codex_home = _safe_path(codex_home, label="Codex runtime home", must_exist=True)
        self.request_verify_key_path = _safe_path(
            request_verify_key_path, label="request verification key", must_exist=True
        )
        self.qualification_path = (
            _safe_path(qualification_path, label="Builder transport qualification")
            if qualification_path is not None
            else None
        )
        self.planner_qualification_path = (
            _safe_path(planner_qualification_path, label="Luna planner qualification")
            if planner_qualification_path is not None
            else None
        )
        self.queue_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for directory in (self.queue_root, self.state_root, self.workspace_root, self.codex_home):
            os.chmod(directory, 0o700)
        request_key = _hex_key(self.request_verify_key_path, label="request verification key")
        try:
            self._request_verify_key = VerifyKey(request_key)
        except ValueError as exc:
            raise SupervisorFailure(
                "identity_failure", "request verification key is malformed"
            ) from exc
        if response_signing_key is not None and response_signing_key_path is not None:
            raise SupervisorFailure(
                "identity_failure", "response signing key sources are ambiguous"
            )
        if response_signing_key is None:
            if response_signing_key_path is None:
                raise SupervisorFailure("identity_failure", "response signing key is unavailable")
            raw = _hex_key(response_signing_key_path, label="response signing key", private=True)
            try:
                response_signing_key = SigningKey(raw)
            except ValueError as exc:
                raise SupervisorFailure(
                    "identity_failure", "response signing key is malformed"
                ) from exc
        self._response_signing_key = response_signing_key
        self._clock = clock or time.time
        self._boot_id = uuid.uuid4().hex
        self._previous_boot_verified = self._verify_previous_identity()
        self._write_identity()

    @property
    def supervisor_identity_sha256(self) -> str:
        return _sha256(bytes(self._response_signing_key.verify_key))

    def _write_identity(self) -> None:
        identity = {
            "schema": SERVICE_SCHEMA,
            "supervisor_identity_sha256": self.supervisor_identity_sha256,
            "provider_id": PROVIDER_ID,
            "model_id": MODEL_ID,
            "family": FAMILY,
            "codex_executable": str(CODEX_EXECUTABLE),
            "workspace_root": str(self.workspace_root),
            "boot_id": self._boot_id,
        }
        envelope = {
            **identity,
            "signature": self._response_signing_key.sign(
                _canonical_bytes(identity)
            ).signature.hex(),
        }
        _write_atomic(self.state_root / "identity.json", _canonical_bytes(envelope))

    def _verify_previous_identity(self) -> bool:
        identity_path = self.state_root / "identity.json"
        if identity_path.is_symlink() or not identity_path.is_file():
            return False
        try:
            document = _strict_json(identity_path.read_bytes())
            signature = document.pop("signature")
            previous_boot = document.get("boot_id")
            if (
                not isinstance(signature, str)
                or not isinstance(previous_boot, str)
                or previous_boot == self._boot_id
                or document.get("schema") != SERVICE_SCHEMA
                or document.get("supervisor_identity_sha256") != self.supervisor_identity_sha256
                or document.get("provider_id") != PROVIDER_ID
                or document.get("model_id") != MODEL_ID
                or document.get("family") != FAMILY
            ):
                return False
            self._response_signing_key.verify_key.verify(
                _canonical_bytes(document), bytes.fromhex(signature)
            )
            return True
        except (OSError, SupervisorFailure, BadSignatureError, ValueError, KeyError, TypeError):
            return False

    def _validate_route_request(
        self,
        document: Mapping[str, object],
        *,
        schema: str,
        model_id: str,
        allowed_stages: frozenset[str] | None = None,
    ) -> tuple[dict[str, object], str]:
        if not isinstance(document, dict):
            raise SupervisorFailure("protocol_failure", "launch request is not an object")
        candidate = dict(document)
        signature = candidate.pop("signature", None)
        if not isinstance(signature, str) or len(signature) != 128:
            raise SupervisorFailure("protocol_failure", "launch request signature is malformed")
        try:
            signature_bytes = bytes.fromhex(signature)
            self._request_verify_key.verify(_canonical_bytes(candidate), signature_bytes)
        except (ValueError, BadSignatureError) as exc:
            raise SupervisorFailure(
                "protocol_failure", "launch request signature is invalid"
            ) from exc
        if set(candidate) != _REQUEST_FIELDS:
            raise SupervisorFailure("protocol_failure", "launch request fields are not exact")
        if candidate.get("schema") != schema:
            raise SupervisorFailure("protocol_failure", "launch request schema is unsupported")
        request_id = candidate.get("request_id")
        if not isinstance(request_id, str) or REQUEST_ID_RE.fullmatch(request_id) is None:
            raise SupervisorFailure("protocol_failure", "launch request identity is malformed")
        for field in ("task_id", "goal_id", "run_id", "stage"):
            value = candidate.get(field)
            if not isinstance(value, str) or IDENTIFIER_RE.fullmatch(value) is None:
                raise SupervisorFailure("protocol_failure", f"launch request {field} is malformed")
        workspace_id = candidate.get("workspace_id")
        if not isinstance(workspace_id, str) or WORKSPACE_ID_RE.fullmatch(workspace_id) is None:
            raise SupervisorFailure("protocol_failure", "launch workspace identity is malformed")
        prompt = candidate.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or "\x00" in prompt:
            raise SupervisorFailure("protocol_failure", "launch prompt is malformed")
        if len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise SupervisorFailure("protocol_failure", "launch prompt exceeds bounded size")
        if allowed_stages is not None and candidate["stage"] not in allowed_stages:
            raise SupervisorFailure("capability_failure", "planner stage is not permitted for Luna")
        issued = candidate.get("issued_at")
        expires = candidate.get("expires_at")
        if (
            isinstance(issued, bool)
            or isinstance(expires, bool)
            or not isinstance(issued, (int, float))
            or not isinstance(expires, (int, float))
            or expires <= issued
            or expires - issued > CAPABILITY_TTL_SECONDS
            or issued > self._clock() + 15.0
            or expires < self._clock()
        ):
            raise SupervisorFailure(
                "capability_failure", "launch capability is expired or outside its bounded lifetime"
            )
        if (
            candidate.get("provider_id") != PROVIDER_ID
            or candidate.get("model_id") != model_id
            or candidate.get("family") != FAMILY
            or candidate.get("fallback_used") is not False
            or candidate.get("manual_chat_bridge") is not False
        ):
            raise SupervisorFailure(
                "capability_failure", "launch route or fallback policy is invalid"
            )
        return candidate, request_id

    def _validate_request(self, document: Mapping[str, object]) -> tuple[dict[str, object], str]:
        """Validate the unchanged fixed Sol Builder capability."""

        return self._validate_route_request(
            document,
            schema=CAPABILITY_SCHEMA,
            model_id=MODEL_ID,
        )

    def _validate_planner_request(
        self, document: Mapping[str, object]
    ) -> tuple[dict[str, object], str]:
        """Validate the distinct fixed Luna planner capability."""

        return self._validate_route_request(
            document,
            schema=PLANNER_CAPABILITY_SCHEMA,
            model_id=PLANNER_MODEL_ID,
            allowed_stages=frozenset(PLANNER_STAGES),
        )

    def _workspace_for(self, request: Mapping[str, object]) -> Path:
        workspace_id = request.get("workspace_id")
        if not isinstance(workspace_id, str) or WORKSPACE_ID_RE.fullmatch(workspace_id) is None:
            raise SupervisorFailure("workspace_failure", "workspace identity is malformed")
        workspace = self.workspace_root / workspace_id
        if (
            workspace.parent != self.workspace_root
            or workspace.is_symlink()
            or not workspace.is_dir()
        ):
            raise SupervisorFailure("workspace_failure", "approved worker workspace is unavailable")
        try:
            resolved = workspace.resolve(strict=True)
        except OSError as exc:
            raise SupervisorFailure(
                "workspace_failure", "approved worker workspace is unavailable"
            ) from exc
        if resolved != workspace or not resolved.is_relative_to(self.workspace_root):
            raise SupervisorFailure("workspace_failure", "worker workspace crosses a symlink")
        return resolved

    def _validate_codex_home(self) -> None:
        auth = self.codex_home / "auth.json"
        if auth.is_symlink() or not auth.is_file():
            raise SupervisorFailure(
                "codex_home_failure", "dedicated Codex auth state is unavailable"
            )
        try:
            if stat.S_IMODE(auth.stat().st_mode) & 0o077:
                raise SupervisorFailure(
                    "codex_home_failure", "dedicated Codex auth state permissions are too broad"
                )
        except OSError as exc:
            raise SupervisorFailure(
                "codex_home_failure", "dedicated Codex auth state cannot be inspected"
            ) from exc

    def _policy(
        self,
        workspace: Path,
        *,
        loopback_port: int,
        broker_token: str,
    ) -> tuple[Any, dict[str, str], Path]:
        codex_executable = _fixed_codex_executable()
        runtime_home = workspace / ".paeos-codex-runtime"
        temp_root = workspace / ".paeos-codex-tmp"
        policy = policy_for_worker(
            workspace=workspace,
            read_roots=(workspace,),
            write_roots=(workspace,),
            runtime_home=runtime_home,
            temp_root=temp_root,
            loopback_port=loopback_port,
            preference_domains=("com.openai.codex", "kCFPreferencesAnyApplication"),
            read_probe_paths=(Path("/etc/codex/requirements.toml"),),
        )
        environment = build_provider_environment(
            {},
            runtime_home=runtime_home,
            temp_root=temp_root,
            task_environment={"PAEOS_TASK_BROKER_TOKEN": broker_token},
        )
        environment["CODEX_HOME"] = str(runtime_home)
        if (
            any(name.endswith("_API_KEY") for name in environment)
            or "OPENAI_API_KEY" in environment
        ):
            raise SupervisorFailure(
                "environment_failure", "provider credential entered child environment"
            )
        if set(environment) != {
            "HOME",
            "LANG",
            "LC_ALL",
            "PATH",
            "TMPDIR",
            "CODEX_HOME",
            "PAEOS_TASK_BROKER_TOKEN",
        }:
            raise SupervisorFailure(
                "environment_failure", "child environment is not the fixed allow-list"
            )
        return policy, environment, codex_executable

    def _run_canaries(
        self, workspace: Path, policy: Any, environment: Mapping[str, str], state_dir: Path
    ) -> dict[str, str]:
        forbidden_root = workspace.parent / f".paeos-forbidden-{state_dir.parent.name}"
        if forbidden_root.exists() or forbidden_root.is_symlink():
            raise SupervisorFailure("confinement_failure", "forbidden canary root is not fresh")
        forbidden_root.mkdir(mode=0o700, parents=True)
        forbidden_file = forbidden_root / "secret.txt"
        forbidden_file.write_bytes(b"PAEOS_FORBIDDEN_CANARY_SECRET")
        forbidden_file.chmod(0o600)
        canary_root = workspace / ".paeos-supervisor-canary"
        canary_root.mkdir(mode=0o700, exist_ok=False)
        approved_read = canary_root / "approved-read.txt"
        approved_read.write_text("PAEOS_APPROVED_READ\n", encoding="utf-8")
        approved_write = canary_root / "approved-write.txt"
        forbidden_write = forbidden_root / "forbidden-write.txt"
        symlink_escape = canary_root / "symlink-escape.txt"
        symlink_escape.symlink_to(forbidden_file)
        traversal_escape = workspace / ".." / forbidden_root.name / "traversal-write.txt"
        traversal_target = forbidden_root / "traversal-write.txt"
        code = _canary_program()
        argv = (
            str(CANARY_EXECUTABLE),
            "-c",
            code,
            "paeos-confinement-canary",
            str(approved_read),
            str(approved_write),
            str(forbidden_file),
            str(forbidden_write),
            str(symlink_escape),
            str(traversal_escape),
            str(traversal_target),
            str(self.codex_home / "auth.json"),
        )
        bound = policy.wrap_argv(argv)
        try:
            observation = run_bounded_process(
                bound,
                cwd=workspace,
                environment=environment,
                start_timeout_s=5.0,
                execution_timeout_s=20.0,
                state_path=state_dir / "canary-process.json",
            )
            try:
                text = observation.stdout.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SupervisorFailure(
                    "confinement_failure", "canary output is not UTF-8"
                ) from exc
            results: dict[str, str] = {}
            for line in text.splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                results[key] = value
            expected = {
                "approved_read",
                "approved_write",
                "forbidden_read_denied",
                "forbidden_write_denied",
                "parent_secret_invisible",
                "provider_credential_absent",
                "symlink_escape_denied",
                "traversal_escape_denied",
                "child_subprocess_confined",
            }
            if (
                observation.lifecycle_state is not ProcessLifecycleState.RETURNED
                or observation.exit_code != 0
                or set(results) != expected
                or any(value != "PASS" for value in results.values())
            ):
                raise SupervisorFailure(
                    "confinement_failure",
                    "confinement canary failed",
                    observation=_observation_facts(observation),
                )
            return results
        finally:
            for path in (canary_root, forbidden_root):
                if path.is_symlink():
                    raise SupervisorFailure(
                        "confinement_failure", "canary cleanup encountered a symlink"
                    )
                if path.exists():
                    shutil.rmtree(path)
                if path.exists():
                    raise SupervisorFailure(
                        "confinement_failure", "canary cleanup did not complete"
                    )

    def _run_request(
        self,
        request: dict[str, object],
        request_id: str,
        *,
        model_id: str = MODEL_ID,
    ) -> dict[str, object]:
        if model_id not in {MODEL_ID, PLANNER_MODEL_ID}:
            raise SupervisorFailure(
                "capability_failure", "Codex model is not an authorized fixed route"
            )
        workspace = self._workspace_for(request)
        request_state = self.state_root / request_id
        if request_state.exists() or request_state.is_symlink():
            raise SupervisorFailure("replay_failure", "launch request identity was already used")
        request_state.mkdir(mode=0o700)
        try:
            self._claim_qualification_identity(request, request_id)
            self._validate_codex_home()
            _write_atomic(request_state / "request.json", _canonical_bytes(request))
            _write_atomic(
                request_state / "lifecycle.json",
                _canonical_bytes(
                    {"request_id": request_id, "state": "STARTING", "observed_at": self._clock()}
                ),
            )
            with ParentOwnedResponsesBroker(
                auth_path=self.codex_home / "auth.json", model_id=model_id
            ) as broker:
                policy, environment, codex_executable = self._policy(
                    workspace,
                    loopback_port=broker.loopback_port,
                    broker_token=broker.task_token,
                )
                canary_state = request_state / "canary"
                canary_state.mkdir(mode=0o700)
                canaries = self._run_canaries(workspace, policy, environment, canary_state)
                prompt = request["prompt"]
                assert isinstance(prompt, str)
                argv = _codex_argv(
                    codex_executable,
                    prompt=prompt,
                    workspace=workspace,
                    broker_base_url=broker.base_url,
                    model_id=model_id,
                )
                bound = policy.wrap_argv(argv)
                process = run_bounded_process(
                    bound,
                    cwd=workspace,
                    environment=environment,
                    start_timeout_s=30.0,
                    execution_timeout_s=BUILDER_EXECUTION_TIMEOUT_S,
                    state_path=request_state / "process.json",
                )
                broker_evidence = broker.evidence()
                _write_atomic(
                    request_state / "broker-evidence.json",
                    _canonical_bytes(broker_evidence),
                )
            if (
                broker_evidence.get("binding") != "127.0.0.1"
                or broker_evidence.get("model_id") != model_id
                or broker_evidence.get("transport_outcome") != "response_received"
                or not isinstance(broker_evidence.get("upstream_status"), int)
                or not isinstance(broker_evidence.get("request_count"), int)
                or not 1 <= broker_evidence["request_count"] <= MAX_TASK_REQUESTS
                or broker_evidence.get("local_rejection_count") != 0
                or broker_evidence.get("local_error_class") is not None
                or any(
                    not isinstance(broker_evidence.get(field), str)
                    or len(broker_evidence[field]) != 64
                    for field in ("request_sha256", "response_sha256")
                )
            ):
                raise SupervisorFailure("broker_failure", "task broker evidence is incomplete")
            canaries["broker_capability_task_scoped"] = "PASS"
            broker_evidence_sha256 = _sha256(_canonical_bytes(broker_evidence))
            process_facts = _observation_facts(process)
            if (
                process.lifecycle_state is not ProcessLifecycleState.RETURNED
                or process.exit_code != 0
                or not process.stdout.strip()
            ):
                raise SupervisorFailure(
                    "provider_execution_failure",
                    "Codex Builder did not return a bounded response",
                    observation=process_facts,
                    failure_boundary="post_response_process",
                )
            try:
                transcript = process.stdout.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SupervisorFailure(
                    "provider_execution_failure",
                    "Codex Builder response is not UTF-8",
                    observation=process_facts,
                ) from exc
            process_record = _strict_json((request_state / "process.json").read_bytes())
            heartbeat_count = process_record.get("heartbeat_count", 0)
            if not isinstance(heartbeat_count, int) or heartbeat_count < 1:
                raise SupervisorFailure(
                    "liveness_failure",
                    "Codex Builder emitted no observed heartbeat or progress",
                    observation=process_facts,
                )
            lifecycle = ["STARTING", "RUNNING", "PROGRESS", "COMPLETED"]
            observation = {
                "provider_id": PROVIDER_ID,
                "model_id": model_id,
                "family": FAMILY,
                "request_id": request_id,
                "task_id": request["task_id"],
                "goal_id": request["goal_id"],
                "run_id": request["run_id"],
                "stage": request["stage"],
                "workspace_id": request["workspace_id"],
                "workspace": str(workspace),
                "transcript": transcript,
                "stdout_sha256": _sha256(process.stdout),
                "stderr_sha256": _sha256(process.stderr),
                "stdout_bytes": len(process.stdout),
                "stderr_bytes": len(process.stderr),
                "exit_code": process.exit_code,
                "process_state": process.lifecycle_state.value,
                "lifecycle": lifecycle,
                "heartbeat_count": heartbeat_count,
                "executable": process.executable,
                "executable_version": process.executable_version,
                "environment_fingerprint": process.environment_fingerprint,
                "profile_sha256": _sha256(policy.seatbelt_profile.encode("utf-8")),
                "broker_evidence_sha256": broker_evidence_sha256,
                "broker_request_count": broker_evidence["request_count"],
                "supervisor_identity_sha256": self.supervisor_identity_sha256,
                "boot_id": self._boot_id,
                "artifact_sha256": _workspace_tree_sha256(workspace),
                "canaries": {
                    **canaries,
                    "supervisor_restart_no_fallback": (
                        "PASS" if self._previous_boot_verified else "UNPROVEN"
                    ),
                },
                "fallback_used": False,
                "manual_chat_bridge": False,
            }
        except SupervisorFailure as exc:
            observation = exc.observation
            failure_state = _failure_lifecycle_state(observation)
            _write_atomic(
                request_state / "lifecycle.json",
                _canonical_bytes(
                    {
                        "request_id": request_id,
                        "state": failure_state,
                        "error_code": exc.code,
                        "observation": observation,
                        "observed_at": self._clock(),
                        **(
                            {"failure_boundary": exc.failure_boundary}
                            if exc.failure_boundary is not None
                            else {}
                        ),
                    }
                ),
            )
            raise
        except (
            OSError,
            ProcessSupervisorError,
            WorkerConfinementError,
            ValueError,
            TypeError,
        ) as exc:
            _write_atomic(
                request_state / "lifecycle.json",
                _canonical_bytes(
                    {
                        "request_id": request_id,
                        "state": "STRUCTURED_FAILURE",
                        "error_code": "supervisor_failure",
                        "observed_at": self._clock(),
                    }
                ),
            )
            raise SupervisorFailure(
                "supervisor_failure", "trusted Codex launch failed closed"
            ) from exc
        except Exception as exc:
            _write_atomic(
                request_state / "lifecycle.json",
                _canonical_bytes(
                    {
                        "request_id": request_id,
                        "state": "STRUCTURED_FAILURE",
                        "error_code": "supervisor_failure",
                        "observed_at": self._clock(),
                    }
                ),
            )
            raise SupervisorFailure(
                "supervisor_failure", "trusted Codex launch failed closed"
            ) from exc
        _write_atomic(
            request_state / "lifecycle.json",
            _canonical_bytes(
                {
                    "request_id": request_id,
                    "state": "COMPLETED",
                    "heartbeat_count": heartbeat_count,
                    "response_sha256": observation["stdout_sha256"],
                    "artifact_sha256": observation["artifact_sha256"],
                    "observed_at": self._clock(),
                }
            ),
        )
        return observation

    def _signed_response(self, payload: dict[str, object]) -> bytes:
        envelope = {
            "payload": payload,
            "signature": self._response_signing_key.sign(_canonical_bytes(payload)).signature.hex(),
        }
        return _canonical_bytes(envelope)

    def _claim_qualification_identity(
        self, request: Mapping[str, object], request_id: str
    ) -> str | None:
        nonce = _qualification_nonce(
            request.get("task_id"),
            request.get("goal_id"),
            request.get("run_id"),
            request.get("stage"),
        )
        if nonce is None:
            return None
        if REQUEST_ID_RE.fullmatch(request_id) is None:
            raise SupervisorFailure(
                "protocol_failure", "qualification request identity is malformed"
            )
        claim_root = self.state_root / "qualification-identities"
        claim_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if (
            claim_root.is_symlink()
            or not claim_root.is_dir()
            or stat.S_IMODE(claim_root.stat().st_mode) & 0o077
        ):
            raise SupervisorFailure("state_failure", "qualification identity state is unsafe")
        claim_path = claim_root / f"{nonce}.json"
        document = {
            "schema": "paeos.builder-transport-qualification-claim/1",
            "nonce": nonce,
            "task_id": request["task_id"],
            "goal_id": request["goal_id"],
            "run_id": request["run_id"],
            "stage": request["stage"],
            "request_id": request_id,
        }
        encoded = _canonical_bytes(document)
        try:
            descriptor = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise SupervisorFailure(
                "replay_failure", "qualification run identity was already used"
            ) from exc
        try:
            offset = 0
            while offset < len(encoded):
                written = os.write(descriptor, encoded[offset:])
                if written <= 0:
                    raise SupervisorFailure(
                        "state_failure", "qualification claim write made no progress"
                    )
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(claim_root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return nonce

    def _qualification_identity_is_claimed(self, observation: Mapping[str, object]) -> bool:
        nonce = _qualification_nonce(
            observation.get("task_id"),
            observation.get("goal_id"),
            observation.get("run_id"),
            observation.get("stage"),
        )
        request_id = observation.get("request_id")
        if nonce is None or not isinstance(request_id, str):
            return False
        claim_path = self.state_root / "qualification-identities" / f"{nonce}.json"
        if (
            claim_path.is_symlink()
            or not claim_path.is_file()
            or stat.S_IMODE(claim_path.stat().st_mode) & 0o077
        ):
            return False
        try:
            claim = _strict_json(claim_path.read_bytes())
        except (OSError, SupervisorFailure):
            return False
        expected = {
            "schema": "paeos.builder-transport-qualification-claim/1",
            "nonce": nonce,
            "task_id": observation.get("task_id"),
            "goal_id": observation.get("goal_id"),
            "run_id": observation.get("run_id"),
            "stage": observation.get("stage"),
            "request_id": request_id,
        }
        return claim == expected

    def _write_qualification(
        self,
        observation: Mapping[str, object],
        *,
        request_sha256: str,
        response_sha256: str,
    ) -> None:
        if self.qualification_path is None:
            return
        if not self._qualification_identity_is_claimed(observation):
            return
        canaries = observation.get("canaries")
        broker_request_count = observation.get("broker_request_count")
        if (
            not isinstance(canaries, dict)
            or not REQUIRED_CANARIES.issubset(canaries)
            or any(canaries.get(key) != "PASS" for key in REQUIRED_CANARIES)
            or observation.get("lifecycle") != list(REQUIRED_LIFECYCLE)
            or not isinstance(broker_request_count, int)
            or isinstance(broker_request_count, bool)
            or broker_request_count != 1
        ):
            return
        evidence = {
            "request_sha256": request_sha256,
            "observation": {
                key: value for key, value in observation.items() if key != "transcript"
            },
        }
        evidence_sha256 = _sha256(_canonical_bytes(evidence))
        payload: dict[str, object] = {
            "schema": "paeos-builder-transport-qualification/1",
            "qualification_scope": "standalone-provider-probe",
            "qualification_id": "btq-" + uuid.uuid4().hex,
            "supervisor_identity_sha256": self.supervisor_identity_sha256,
            "request_sha256": request_sha256,
            "response_sha256": response_sha256,
            "artifact_sha256": observation["artifact_sha256"],
            "evidence_sha256": evidence_sha256,
            "provider": PROVIDER_ID,
            "model": MODEL_ID,
            "family": FAMILY,
            "observed_at": int(self._clock()),
            "expires_at": int(self._clock()) + 86_400,
            "lifecycle": ["STARTING", "RUNNING", "PROGRESS", "COMPLETED"],
            "canaries": sorted(canaries),
            "fallback_used": False,
            "manual_chat_bridge": False,
        }
        envelope = {
            "payload": payload,
            "signature": self._response_signing_key.sign(_canonical_bytes(payload)).signature.hex(),
        }
        _write_atomic(self.qualification_path, _canonical_bytes(envelope))

    def _write_planner_qualification(
        self,
        observation: Mapping[str, object],
        *,
        request_sha256: str,
        response_sha256: str,
    ) -> None:
        """Accumulate supervisor-signed, stage-specific Luna transport observations."""

        if self.planner_qualification_path is None:
            return
        identity = tuple(observation.get(field) for field in ("task_id", "goal_id", "run_id"))
        stage = observation.get("stage")
        if identity != _PLANNER_QUALIFICATION_IDENTITY or stage not in PLANNER_STAGES:
            return
        canaries = observation.get("canaries")
        if (
            not isinstance(canaries, dict)
            or any(value != "PASS" for value in canaries.values())
            or observation.get("lifecycle") != ["STARTING", "RUNNING", "PROGRESS", "COMPLETED"]
        ):
            return
        transcript = observation.get("transcript")
        if not isinstance(transcript, str):
            return
        contract_markers = contract_markers_for(str(stage), transcript)
        if not all(contract_markers.values()):
            return
        evidence = {
            "request_sha256": request_sha256,
            "response_sha256": response_sha256,
            "observation": {
                key: value for key, value in observation.items() if key != "transcript"
            },
        }
        binding = {
            "request_sha256": request_sha256,
            "response_sha256": response_sha256,
            "artifact_sha256": str(observation["artifact_sha256"]),
            "evidence_sha256": _sha256(_canonical_bytes(evidence)),
            "contract_markers": contract_markers,
        }
        qualified_stages = {str(stage)}
        probe_bindings: dict[str, dict[str, object]] = {str(stage): binding}
        qualification_id = "ptq-" + uuid.uuid4().hex
        previous_observed_at = 0
        path = self.planner_qualification_path
        if path.exists() or path.is_symlink():
            try:
                previous_document = _strict_json(path.read_bytes())
                previous_signature = previous_document.pop("signature")
                previous_payload = previous_document.get("payload")
                if (
                    set(previous_document) != {"payload"}
                    or not isinstance(previous_signature, str)
                    or not isinstance(previous_payload, dict)
                ):
                    raise ValueError("planner qualification envelope is not exact")
                self._response_signing_key.verify_key.verify(
                    _canonical_bytes(previous_payload), bytes.fromhex(previous_signature)
                )
                from runtime.planner_transport import PlannerTransportReadiness

                previous = PlannerTransportReadiness._validate_payload(previous_payload)
                if previous.supervisor_identity_sha256 != self.supervisor_identity_sha256:
                    raise ValueError("planner qualification supervisor identity changed")
                qualification_id = previous.qualification_id
                previous_observed_at = previous.observed_at
                qualified_stages.update(previous.qualified_stages)
                probe_bindings.update(previous.probe_bindings)
            except (OSError, BadSignatureError, ValueError, TypeError, KeyError) as exc:
                raise SupervisorFailure(
                    "identity_failure", "planner qualification record is invalid"
                ) from exc
        payload: dict[str, object] = {
            "schema": "paeos-planner-transport-qualification/2",
            "qualification_scope": "standalone-planner-probe",
            "qualification_id": qualification_id,
            "supervisor_identity_sha256": self.supervisor_identity_sha256,
            "provider": PROVIDER_ID,
            "model": PLANNER_MODEL_ID,
            "family": FAMILY,
            "observed_at": max(int(self._clock()), previous_observed_at),
            "expires_at": max(int(self._clock()), previous_observed_at) + 86_400,
            "lifecycle": ["STARTING", "RUNNING", "PROGRESS", "COMPLETED"],
            "canaries": sorted(canaries),
            "qualified_stages": sorted(qualified_stages),
            "probe_bindings": dict(sorted(probe_bindings.items())),
            "fallback_used": False,
            "manual_chat_bridge": False,
        }
        envelope = {
            "payload": payload,
            "signature": self._response_signing_key.sign(_canonical_bytes(payload)).signature.hex(),
        }
        _write_atomic(path, _canonical_bytes(envelope))

    def handle(self, raw: bytes) -> bytes:
        request_id: str | None = None
        request_sha256 = _sha256(raw)
        try:
            document = _strict_json(raw)
            possible = document.get("request_id")
            request_id = possible if isinstance(possible, str) else None
            if document.get("schema") == PLANNER_CAPABILITY_SCHEMA:
                request, request_id = self._validate_planner_request(document)
                route_model = PLANNER_MODEL_ID
            else:
                request, request_id = self._validate_request(document)
                route_model = MODEL_ID
            observation = self._run_request(request, request_id, model_id=route_model)
            payload: dict[str, object] = {
                "schema": SERVICE_SCHEMA,
                "ok": True,
                "request_id": request_id,
                "observation": observation,
            }
        except SupervisorFailure as exc:
            payload = {
                "schema": SERVICE_SCHEMA,
                "ok": False,
                "request_id": request_id,
                "error_code": exc.code,
                "error": "trusted Codex launch rejected or failed closed",
            }
            if exc.observation is not None:
                payload["failure_observation"] = exc.observation
        except (OSError, ProcessSupervisorError, WorkerConfinementError, ValueError, TypeError):
            payload = {
                "schema": SERVICE_SCHEMA,
                "ok": False,
                "request_id": request_id,
                "error_code": "supervisor_failure",
                "error": "trusted Codex launch rejected or failed closed",
            }
        response = self._signed_response(payload)
        if payload.get("ok") is True:
            observation = payload.get("observation")
            if isinstance(observation, dict):
                try:
                    self._write_qualification(
                        observation,
                        request_sha256=request_sha256,
                        response_sha256=_sha256(response),
                    )
                    self._write_planner_qualification(
                        observation,
                        request_sha256=request_sha256,
                        response_sha256=_sha256(response),
                    )
                except (OSError, SupervisorFailure, ValueError, TypeError):
                    # The launch response remains signed and bounded, but the readiness artifact
                    # is intentionally absent when its durable write cannot be completed.
                    return response
        return response

    def process_queue(self) -> None:
        for request_path in sorted(self.queue_root.glob("*.request.json")):
            if request_path.is_symlink() or not request_path.is_file():
                continue
            request_id = request_path.name[: -len(".request.json")]
            if REQUEST_ID_RE.fullmatch(request_id) is None:
                continue
            phase = "read"
            raw = b""
            try:
                raw = request_path.read_bytes()
                if len(raw) > MAX_FRAME_BYTES:
                    raise SupervisorFailure(
                        "protocol_failure", "launch request exceeds bounded size"
                    )
                phase = "handle"
                response = self.handle(raw)
                if len(response) > MAX_RESPONSE_BYTES:
                    raise SupervisorFailure(
                        "protocol_failure", "launch response exceeds bounded size"
                    )
                response_path = self.queue_root / f"{request_id}.response.json"
                if response_path.exists() or response_path.is_symlink():
                    raise SupervisorFailure("protocol_failure", "launch response path is not fresh")
                phase = "publish_response"
                _write_atomic(response_path, response)
                phase = "remove_request"
                request_path.unlink()
            except Exception as exc:
                # Quarantine a malformed/unprocessable request for forensic inspection.  It is
                # never treated as a successful launch and cannot be retried under the same name.
                # Persist only bounded classes, never exception text or provider output; silent
                # queue loss would strand an otherwise durable lifecycle outcome.
                failure_path = self.state_root / "queue-failures" / f"{request_id}.json"
                failure = {
                    "schema": "paeos.trusted-codex-queue-failure/1",
                    "request_id": request_id,
                    "request_sha256": _sha256(raw) if raw else None,
                    "state": "QUARANTINED",
                    "phase": phase,
                    "error_class": type(exc).__name__,
                    "error_code": exc.code if isinstance(exc, SupervisorFailure) else None,
                    "observed_at": self._clock(),
                }
                with contextlib.suppress(Exception):
                    _write_atomic(failure_path, _canonical_bytes(failure))
                quarantine = self.state_root / "quarantine"
                quarantine.mkdir(mode=0o700, parents=True, exist_ok=True)
                target = quarantine / request_path.name
                if not target.exists() and not target.is_symlink():
                    with contextlib.suppress(OSError):
                        os.replace(request_path, target)
                continue


def serve(service: TrustedCodexWorkerSupervisor) -> None:
    while True:
        service.process_queue()
        time.sleep(0.1)


def main() -> int:
    parser = argparse.ArgumentParser(description="PAEOS trusted Codex Builder supervisor")
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--bundle-manifest", type=Path, required=True)
    parser.add_argument("--queue-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--request-verify-key", type=Path, required=True)
    parser.add_argument("--response-signing-key", type=Path, required=True)
    parser.add_argument("--qualification-path", type=Path, required=True)
    parser.add_argument("--planner-qualification-path", type=Path, required=False)
    args = parser.parse_args()
    verify_bundle_manifest(args.bundle_root, args.bundle_manifest)
    service = TrustedCodexWorkerSupervisor(
        queue_root=args.queue_root,
        state_root=args.state_root,
        workspace_root=args.workspace_root,
        codex_home=args.codex_home,
        request_verify_key_path=args.request_verify_key,
        response_signing_key_path=args.response_signing_key,
        qualification_path=args.qualification_path,
        planner_qualification_path=args.planner_qualification_path,
    )
    serve(service)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
