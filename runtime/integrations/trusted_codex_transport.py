"""PAEOS client for the trusted host-side Codex Builder supervisor.

This module is a narrow transport adapter, not a launcher.  It cannot select a command, model,
environment, filesystem root, or fallback.  It signs task metadata, waits for the supervisor's
signed observation, and converts that observation into the existing ``SessionResult`` seam.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import stat
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager, suppress
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from runtime.autonomy.admission_authority import BINDINGS, AdmissionAuthority, canonical
from runtime.autonomy.admission_send_fence import (
    AdmissionSendFence,
    SendOperation,
    SendOutcome,
    SendSettlementError,
)
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
_ROUTE_ID = "trusted-codex-worker/v1"
_ROUTE_DIGEST = hashlib.sha256(_ROUTE_ID.encode("ascii")).hexdigest()
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
_TOOL_QUEUE_LIMIT = 270336
_TOOL_WIRE_LIMIT = 196608
_TOOL_CONTEXT_FIELDS = frozenset(
    (
        "bindings",
        "base_grant_id",
        "base_grant_digest",
        "tool_grant_id",
        "tool_grant_digest",
        "admission_ref",
        "admission_epoch",
        "policy_id",
        "policy_revision",
        "policy_digest",
        "signed_v2_manifest_sha256",
        "derivative_rule_id",
    )
)


def _tool_json(raw: bytes, limit: int) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        raise ValueError("bounded parent-tool encoding required")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate parent-tool field")
            result[key] = value
        return result

    value = json.loads(raw.decode("ascii"), object_pairs_hook=unique)
    if type(value) is not dict or canonical(value) != raw:
        raise ValueError("noncanonical parent-tool encoding")
    return value


def _tool_decode(value: object, limit: int) -> bytes:
    if type(value) is not str or len(value) > 4 * ((limit + 2) // 3):
        raise ValueError("bounded parent-tool bytes required")
    raw = base64.b64decode(value, validate=True)
    if not 0 < len(raw) <= limit or base64.b64encode(raw).decode("ascii") != value:
        raise ValueError("noncanonical parent-tool bytes")
    return raw


@contextmanager
def _tool_queue_directory(root: Path):
    if not root.is_absolute():
        raise ValueError("absolute parent-tool directory required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in root.parts[1:]:
            if part in {"", ".", ".."}:
                raise ValueError("unsafe parent-tool directory")
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd
            )
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _tool_queue_read(directory: int, name: str) -> bytes | None:
    try:
        fd = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory
        )
    except FileNotFoundError:
        return None
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or not 0 < before.st_size <= _TOOL_QUEUE_LIMIT
        ):
            raise ValueError("parent-tool queue input is not bounded regular bytes")
        raw = bytearray()
        while len(raw) <= _TOOL_QUEUE_LIMIT:
            block = os.read(fd, min(65536, _TOOL_QUEUE_LIMIT + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        after = os.fstat(fd)
        if len(raw) != before.st_size or (
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("parent-tool queue input changed during read")
        return bytes(raw)
    finally:
        os.close(fd)


def _tool_queue_publish(directory: int, name: str, raw: bytes) -> None:
    temporary = ".parent-tool-" + uuid.uuid4().hex + ".tmp"
    fd = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=directory,
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        os.unlink(temporary, dir_fd=directory)
        os.fsync(directory)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temporary, dir_fd=directory)


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
        type(exit_code) is not int
        or (
            exit_code < 0
            and (
                -exit_code not in signal.valid_signals()
                or value["lifecycle_state"] not in {"FAILED", "TIMED_OUT"}
            )
        )
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
        admission_send_fence: AdmissionSendFence | None = None,
        admission_ref: str | None = None,
        expected_admission_epoch: int | None = None,
        parent_tool_authority: AdmissionAuthority | None = None,
        parent_tool_binding: bytes | None = None,
        parent_tool_ack_issuer_id: str | None = None,
        parent_tool_ack_signer: Callable[[bytes], bytes] | None = None,
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
        if admission_send_fence is None:
            if admission_ref is not None or expected_admission_epoch is not None:
                raise TrustedCodexTransportError(
                    "admission identity cannot be configured without the trusted send fence"
                )
        elif (
            not isinstance(admission_send_fence, AdmissionSendFence)
            or not isinstance(admission_ref, str)
            or not admission_ref
            or type(expected_admission_epoch) is not int
            or expected_admission_epoch < 1
        ):
            raise TrustedCodexTransportError("trusted admission send-fence binding is incomplete")
        self.queue_root = queue_root
        self.workspace_root = workspace_root.resolve()
        self.evidence_root = evidence_root
        self._request_signing_key = request_signing_key
        self._response_verify_key = response_verify_key
        self._timeout_s = timeout_s
        self._admission_send_fence = admission_send_fence
        self._admission_ref = admission_ref
        self._expected_admission_epoch = expected_admission_epoch
        self.last_request_sha256: str | None = None
        self.last_response_sha256: str | None = None
        self.last_observation: dict[str, object] | None = None
        self._parent_tool_authority = parent_tool_authority
        self._parent_tool_binding = parent_tool_binding
        self._parent_tool_ack_issuer_id = parent_tool_ack_issuer_id
        self._parent_tool_ack_signer = parent_tool_ack_signer
        supplied = (
            parent_tool_authority,
            parent_tool_binding,
            parent_tool_ack_issuer_id,
            parent_tool_ack_signer,
        )
        if any(value is not None for value in supplied):
            try:
                if (
                    any(value is None for value in supplied)
                    or type(parent_tool_authority) is not AdmissionAuthority
                    or not callable(parent_tool_ack_signer)
                    or admission_send_fence is None
                    or admission_send_fence._authority is not parent_tool_authority
                    or admission_send_fence._ledger is not parent_tool_authority.ledger
                ):
                    raise ValueError("concrete parent-tool binding is unavailable")
                binding = self._parent_binding()
                identities = [
                    i
                    for i in parent_tool_authority.trust.identities
                    if i.identity_id == parent_tool_ack_issuer_id
                ]
                if (
                    len(identities) != 1
                    or identities[0].public_key
                    in (
                        bytes(response_verify_key),
                        bytes(request_signing_key.verify_key),
                        *(i.public_key for i in parent_tool_authority.trust.roots),
                    )
                    or binding["parent_identity_sha256"] != _sha256(bytes(response_verify_key))
                ):
                    raise ValueError("parent-tool signer separation is unavailable")
            except (ValueError, TypeError, AttributeError, UnicodeError) as exc:
                raise TrustedCodexTransportError("parent-tool configuration is incomplete") from exc

    def _parent_binding(self) -> dict:
        value = _tool_json(self._parent_tool_binding, 32768)
        if (
            set(value)
            != {"context", "parent_identity_sha256", "parent_boot_id", "parent_process_id"}
            or type(value["context"]) is not dict
            or set(value["context"]) != _TOOL_CONTEXT_FIELDS
            or type(value["context"]["bindings"]) is not dict
            or set(value["context"]["bindings"]) != set(BINDINGS)
        ):
            raise ValueError("exact parent-tool binding required")
        for name in ("parent_boot_id", "parent_process_id"):
            text = value[name]
            if type(text) is not str or not 0 < len(text.encode("utf-8")) <= 128 or "\0" in text:
                raise ValueError("parent-tool process binding required")
        return value

    def _parent_launch_fields(self, spec: SessionSpec) -> dict:
        if self._parent_tool_authority is None:
            return {}
        context = self._parent_binding()["context"]
        expected = dict(
            goal_id=spec.goal_id,
            task_id=spec.task_id,
            run_id=spec.run_id,
            stage=spec.stage,
            role="BUILDER",
            workspace_id=spec.workspace.name,
            route_id=_ROUTE_ID,
            route_digest=_ROUTE_DIGEST,
        )
        if (
            context["admission_ref"] != self._admission_ref
            or type(context["admission_epoch"]) is not int
            or context["admission_epoch"] != self._expected_admission_epoch
            or any(context["bindings"][k] != v for k, v in expected.items())
        ):
            raise TrustedCodexTransportError("parent-tool awaited session binding differs")
        return dict(
            operation_kind="WORKER_LAUNCH",
            frame_ordinal=0,
            **{
                k: context["bindings"][k]
                for k in ("session_id", "contract_digest", "scope_digest", "root_allocation_id")
            },
        )

    def _poll_parent_tool_queue(self, request_id: str, spec: SessionSpec, *, deadline: float):
        try:
            if (
                type(request_id) is not str
                or len(request_id) != 32
                or any(c not in "0123456789abcdef" for c in request_id)
                or time.monotonic() >= deadline
            ):
                raise ValueError("parent-tool wait is unavailable")
            with _tool_queue_directory(self.queue_root) as directory:

                def event(phase):
                    raw = _tool_queue_read(
                        directory, f"{request_id}.parent-tool.{phase.lower()}.json"
                    )
                    if raw is None:
                        return None
                    wrapper = _tool_json(raw, _TOOL_QUEUE_LIMIT)
                    if (
                        set(wrapper) != {"schema", "request_id", "phase", "envelope_b64"}
                        or wrapper["schema"] != "paeos.parent-tool-queue-event/1"
                        or wrapper["request_id"] != request_id
                        or wrapper["phase"] != phase
                    ):
                        raise ValueError("parent-tool event correlation differs")
                    return _tool_decode(
                        wrapper["envelope_b64"], 32768 if phase == "CLAIM" else _TOOL_WIRE_LIMIT
                    )

                claim_raw, outcome_raw = event("CLAIM"), event("OUTCOME")
                authority = self._parent_tool_authority
                if authority is None:
                    if claim_raw is not None or outcome_raw is not None:
                        raise ValueError("parent-tool authority unavailable")
                    return None
                self._parent_launch_fields(spec)
                binding = self._parent_binding()
                context = binding["context"]
                if not _is_sha256(self.last_request_sha256):
                    raise ValueError("actual awaited launch digest unavailable")
                rows = authority.ledger.read()
                authority.ledger.verify_chain()
                launches = [
                    r.event.payload
                    for r in rows
                    if r.domain_tag == authority.domain_tag
                    and r.event.kind == "ADMISSION_SEND_CLAIMED"
                    and r.event.payload.get("request_id") == request_id
                ]
                if len(launches) != 1:
                    raise ValueError("canonical awaited launch missing")
                launch = launches[0]
                expected = dict(
                    context["bindings"],
                    admission_ref=context["admission_ref"],
                    admission_epoch=context["admission_epoch"],
                    operation_kind="WORKER_LAUNCH",
                    frame_ordinal=0,
                    frame_digest=self.last_request_sha256,
                    policy_id=context["policy_id"],
                    policy_revision=context["policy_revision"],
                    policy_digest=context["policy_digest"],
                )
                if any(
                    type(launch.get(k)) is not type(v) or launch.get(k) != v
                    for k, v in expected.items()
                ) or any(
                    r.event.kind == "ADMISSION_SEND_SETTLED"
                    and r.event.payload.get("lease_id") == launch["lease_id"]
                    for r in rows
                ):
                    raise ValueError("canonical launch binding differs or is settled")
                operation_id = _sha256(
                    canonical(
                        dict(
                            root_allocation_id=context["bindings"]["root_allocation_id"],
                            operation_kind="PARENT_TOOL_READ",
                            ordinal=0,
                        )
                    )
                )
                exists = any(
                    r.event.kind == "PARENT_TOOL_READ_CLAIMED"
                    and r.domain_tag == authority.domain_tag
                    and r.event.payload.get("operation_id") == operation_id
                    for r in rows
                )
                if not exists and claim_raw is None:
                    if outcome_raw is not None:
                        raise ValueError("parent-tool outcome precedes claim")
                    return None
                if exists:
                    view = authority.read_parent_tool_operation(operation_id)
                    if claim_raw is not None and claim_raw != view.request_bytes:
                        raise ValueError("conflicting parent-tool request")
                    claim_raw = view.request_bytes
                claim = _tool_json(claim_raw, 32768)["body"]
                if (
                    type(claim) is not dict
                    or claim.get("purpose") != "PARENT_TOOL_CLAIM_REQUEST"
                    or claim.get("request_id") != request_id
                    or claim.get("context") != context
                    or claim.get("operation_id") != operation_id
                    or any(
                        claim.get(k) != binding[k]
                        for k in ("parent_identity_sha256", "parent_boot_id", "parent_process_id")
                    )
                ):
                    raise ValueError("parent-tool signed request binding differs")
                if not exists:
                    authority.claim_parent_tool_read(claim_raw)
                view = authority.read_parent_tool_operation(operation_id)

                def commit_ack(phase, observation):
                    if time.monotonic() >= deadline:
                        raise ValueError("parent-tool wait expired")
                    name = f"{request_id}.parent-tool.{phase.lower()}-ack.json"
                    stored = _tool_queue_read(directory, name)
                    if stored is not None:
                        wrapper = _tool_json(stored, _TOOL_QUEUE_LIMIT)
                        if (
                            set(wrapper) != {"schema", "request_id", "phase", "ack_b64"}
                            or wrapper["schema"] != "paeos.parent-tool-queue-ack/1"
                            or wrapper["request_id"] != request_id
                            or wrapper["phase"] != phase
                        ):
                            raise ValueError("parent-tool ACK correlation differs")
                        ack = _tool_decode(wrapper["ack_b64"], _TOOL_WIRE_LIMIT)
                    else:
                        ack = authority.issue_parent_tool_commit_ack(
                            operation_id,
                            phase,
                            issuer_id=self._parent_tool_ack_issuer_id,
                            signer=self._parent_tool_ack_signer,
                        )
                    ack_body = _tool_json(ack, _TOOL_WIRE_LIMIT)["body"]
                    if type(ack_body) is not dict or ack_body.get("phase") != phase:
                        raise ValueError("parent-tool ACK phase differs")
                    authority.verify_parent_tool_commit_ack(
                        ack,
                        expected_request_bytes=claim_raw,
                        expected_observation_bytes=observation,
                    )
                    if time.monotonic() >= deadline:
                        raise ValueError("parent-tool wait expired before ACK publication")
                    if stored is None:
                        _tool_queue_publish(
                            directory,
                            name,
                            canonical(
                                dict(
                                    schema="paeos.parent-tool-queue-ack/1",
                                    request_id=request_id,
                                    phase=phase,
                                    ack_b64=base64.b64encode(ack).decode("ascii"),
                                )
                            ),
                        )

                if view.outcome == "UNRESOLVED":
                    commit_ack("CLAIM", None)
                if outcome_raw is not None:
                    if view.observation_bytes is None:
                        authority.record_parent_tool_observation(outcome_raw)
                    elif view.observation_bytes != outcome_raw:
                        raise ValueError("conflicting parent-tool outcome")
                    view = authority.read_parent_tool_operation(operation_id)
                if view.outcome == "RETURNED":
                    commit_ack("OUTCOME", view.observation_bytes)
                elif view.outcome != "UNRESOLVED":
                    raise ValueError("parent-tool outcome is not returned")
                return view.outcome
        except TrustedCodexTransportError:
            raise
        except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
            raise TrustedCodexTransportError("parent-tool queue exchange refused") from exc

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
        # No environment/default path activates this boundary. Production composition still
        # supplies no fence until its admission owner and policy verifier are integrated.
        fence = self._admission_send_fence
        admission_ref = self._admission_ref
        expected_epoch = self._expected_admission_epoch
        if fence is None or admission_ref is None or expected_epoch is None:
            raise TrustedTransportFailure(
                "disclosure_authority_unavailable",
                "trusted disclosure authority is unavailable",
            )
        try:
            fence.preflight(admission_ref, expected_epoch)
        except Exception as exc:
            raise TrustedTransportFailure(
                "disclosure_authority_unavailable",
                "current admission and disclosure policy are unavailable",
            ) from exc

        parent_launch = self._parent_launch_fields(spec)
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
        operation = SendOperation(
            admission_ref=admission_ref,
            expected_epoch=expected_epoch,
            task_id=spec.task_id,
            goal_id=spec.goal_id,
            run_id=spec.run_id,
            stage=spec.stage,
            role="BUILDER",
            workspace_id=spec.workspace.name,
            route_id=_ROUTE_ID,
            route_digest=_ROUTE_DIGEST,
            request_id=request_id,
            frame=encoded,
            **parent_launch,
        )
        try:
            lease = fence.acquire_send_lease(operation)
        except Exception as exc:
            raise TrustedTransportFailure(
                "disclosure_authority_unavailable",
                "current admission refused the exact outbound frame",
            ) from exc
        settled = False
        try:
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
                    tool_state = self._poll_parent_tool_queue(request_id, spec, deadline=deadline)
                    if response_path.is_file() and not response_path.is_symlink():
                        if tool_state == "UNRESOLVED":
                            raise TrustedCodexTransportError("parent-tool operation is unresolved")
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
                        result = self._validate_response(response, request_id=request_id, spec=spec)
                        fence.finish_send_lease(
                            lease,
                            SendOutcome.RETURNED,
                            outcome_ref=self.last_response_sha256,
                        )
                        settled = True
                        return result
                    time.sleep(0.05)
                request_path.unlink(missing_ok=True)
                raise TrustedCodexTransportError("trusted supervisor response deadline exceeded")
            except TrustedCodexTransportError:
                raise
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise TrustedCodexTransportError(
                    "trusted supervisor is unavailable or malformed"
                ) from exc
        finally:
            if not settled:
                with suppress(SendSettlementError):
                    fence.finish_send_lease(lease, SendOutcome.UNKNOWN)

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
