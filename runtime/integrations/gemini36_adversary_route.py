"""Role-scoped parent-owned Google Gemini 3.6 adversary route."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from kernel.types import Role, StageId
from runtime.integrations.provider_broker import HostClineCriticTransport

PROVIDER = "google"
MODEL = "gemini-3.6-flash"
FAMILY = "gemini"
OPERATION = "adversarial_review"
CAPABILITY_SCHEMA = "paeos.trusted-gemini36-adversary-capability/1"
OBSERVATION_SCHEMA = "paeos.parent-google-gemini36-adversary-observation/1"
SERVICE_SCHEMA = "paeos.trusted-worker-service/1"
PROVIDER_FAILURE_SCHEMA = "paeos.provider-failure-observation/1"
BROKER_URL = "parent-owned:google-gemini36-adversary"
TRUSTED_QUEUE = Path("/Users/bob/GitHub/paeos/ops/.trusted-worker/queue")
CAPABILITY_TTL_S = 45.0
MAX_ID_BYTES = 1024
MAX_PROMPT_BYTES = 128 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
MAX_FRAME_BYTES = 512 * 1024
HEX = frozenset("0123456789abcdef")
ERROR_CODE_ALPHABET = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_:-")
FAILURE_TYPES = frozenset(
    {
        "CONTEXT_EXCEEDED", "RATE_LIMITED", "QUOTA_EXHAUSTED", "AUTH_FAILED",
        "PROVIDER_UNAVAILABLE", "BAD_REQUEST", "CONTENT_POLICY", "TIMEOUT",
        "MODEL_UNAVAILABLE", "UNKNOWN",
    }
)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hex(value: object, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(c in HEX for c in value)


def _text(value: object, maximum: int) -> bool:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        return False
    try:
        return len(value.encode("utf-8")) <= maximum
    except UnicodeEncodeError:
        return False


@dataclass(frozen=True, slots=True)
class Gemini36AdversaryResult:
    stage: str
    role: Role
    tools_used: bool
    production_writes: bool
    fallback_used: bool
    supervisor: str
    confined: bool
    a08_builder_family: str
    a08_adversary_family: str
    transcript: str
    environment_fingerprint: str = ""
    lifecycle_state: str = "RETURNED"
    exit_code: int = 0
    failure_code: str | None = None
    stderr: bytes = b""


class Gemini36AdversaryRouteError(RuntimeError):
    def __init__(self, code: str, message: str, *, failure_observation: Mapping[str, object] | None = None, error_code: str | None = None) -> None:
        self.code = code
        self.message = message
        self.failure_observation = dict(failure_observation) if failure_observation is not None else None
        self.diagnostic = self.failure_observation
        self.error_code = error_code
        super().__init__(f"{code}: {message}")


class Gemini36AdversaryRoute:
    provider_id = PROVIDER
    model_id = MODEL
    model_family = FAMILY
    allowed_role = Role.ADVERSARY
    allowed_operation = OPERATION
    parent_owns_authentication = True
    child_receives_parent_credentials = False
    requires_trusted_parent_confinement = True
    allows_tools = False
    allows_writes = False
    allow_fallback = False
    broker_url = BROKER_URL
    capability_ttl_s = CAPABILITY_TTL_S
    _capability_fields = frozenset({
        "schema", "capability_id", "task_id", "goal_id", "run_id", "stage", "role", "operation",
        "provider_id", "model_id", "model_family", "prompt", "read_only", "allow_tools",
        "allow_fallback", "require_confinement", "builder_family", "adversary_family", "issued_at",
        "expires_at", "signature",
    })
    _observation_fields = frozenset({
        "schema", "capability_id", "task_id", "goal_id", "run_id", "stage", "role", "operation",
        "provider_id", "model_id", "model_family", "actual_provider", "actual_model", "actual_family",
        "tools_used", "production_writes", "fallback_used", "trusted_parent_confinement",
        "response_content", "request_sha256", "response_sha256",
    })

    def __init__(self, *, request_signing_key: Any, parent_exchange: Callable[..., object] | None = None, builder_family: str = "gpt", now: Callable[[], float] = time.time, timeout_s: float = 180.0) -> None:
        if request_signing_key is None or not callable(getattr(request_signing_key, "sign", None)):
            self._fail("invalid_configuration", "parent-owned signing key is unavailable")
        if not callable(parent_exchange) or not callable(now):
            self._fail("invalid_configuration", "parent exchange or clock is unavailable")
        if not _text(builder_family, MAX_ID_BYTES) or builder_family == FAMILY:
            self._fail("invalid_configuration", "Builder and adversary families are not independent")
        if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or not math.isfinite(float(timeout_s)) or not 0 < float(timeout_s) <= 180.0:
            self._fail("invalid_configuration", "parent exchange timeout is invalid")
        self.builder_family = builder_family
        self._signer = request_signing_key
        self._parent_exchange = parent_exchange
        self._clock = now
        self._timeout_s = float(timeout_s)
        self._redeemed: set[str] = set()
        self.last_observation: dict[str, object] | None = None

    @staticmethod
    def _fail(code: str, message: str) -> NoReturn:
        raise Gemini36AdversaryRouteError(code, message)

    @staticmethod
    def _value(spec: object, name: str) -> object:
        if isinstance(spec, Mapping):
            if name not in spec:
                raise Gemini36AdversaryRouteError("malformed_spec", "task specification is incomplete")
            return spec[name]
        try:
            return getattr(spec, name)
        except AttributeError as exc:
            raise Gemini36AdversaryRouteError("malformed_spec", "task specification is incomplete") from exc

    def issue_task_capability(self, task_id: str, goal_id: str, run_id: str, stage: str, role: Role, operation: str, prompt: str, builder_family: str | None = None, tools: None = None, allow_writes: bool = False, allow_fallback: bool = False, require_confinement: bool = True, now: float | None = None) -> dict[str, object]:
        if role is not Role.ADVERSARY or operation != OPERATION or stage != StageId.ADVERSARIAL_REVIEW.name:
            self._fail("route_mismatch", "only Role.ADVERSARY at ADVERSARIAL_REVIEW is authorized")
        if tools is not None or allow_writes is not False or allow_fallback is not False or require_confinement is not True:
            self._fail("authority_mismatch", "tools, writes, fallback, or unconstrained execution is forbidden")
        selected_family = self.builder_family if builder_family is None else builder_family
        for name, value in (("task_id", task_id), ("goal_id", goal_id), ("run_id", run_id), ("stage", stage), ("builder_family", selected_family)):
            if not _text(value, MAX_ID_BYTES):
                self._fail("malformed_identity", f"{name} is malformed")
        if selected_family == FAMILY:
            self._fail("independence_mismatch", "Builder and adversary families must be heterogeneous")
        if not _text(prompt, MAX_PROMPT_BYTES) or "context/" not in prompt:
            self._fail("malformed_prompt", "adversary prompt must name the sealed context bundle")
        issued = self._clock() if now is None else now
        if isinstance(issued, bool) or not isinstance(issued, (int, float)) or not math.isfinite(float(issued)):
            self._fail("malformed_time", "capability time is malformed")
        claims: dict[str, object] = {
            "schema": CAPABILITY_SCHEMA, "capability_id": uuid.uuid4().hex, "task_id": task_id,
            "goal_id": goal_id, "run_id": run_id, "stage": stage, "role": Role.ADVERSARY.name,
            "operation": OPERATION, "provider_id": PROVIDER, "model_id": MODEL, "model_family": FAMILY,
            "prompt": prompt, "read_only": True, "allow_tools": False, "allow_fallback": False,
            "require_confinement": True, "builder_family": selected_family, "adversary_family": FAMILY,
            "issued_at": float(issued), "expires_at": float(issued) + self.capability_ttl_s,
        }
        try:
            signature = self._signer.sign(_canonical(claims)).signature.hex()
        except Exception as exc:
            raise Gemini36AdversaryRouteError("signing_failed", "parent signing failed") from exc
        if not _hex(signature, 128):
            self._fail("signing_failed", "parent signer returned malformed data")
        return {**claims, "signature": signature}

    def redeem_task_capability(self, *, bearer: object, task_id: str, goal_id: str, run_id: str, stage: str, role: Role, operation: str, now: float | None = None) -> str:
        if not isinstance(bearer, dict) or set(bearer) != self._capability_fields:
            self._fail("malformed_capability", "capability fields are not exact")
        exact = {"task_id": task_id, "goal_id": goal_id, "run_id": run_id, "stage": stage, "role": Role.ADVERSARY.name, "operation": OPERATION, "provider_id": PROVIDER, "model_id": MODEL, "model_family": FAMILY, "adversary_family": FAMILY, "read_only": True, "allow_tools": False, "allow_fallback": False, "require_confinement": True}
        if role is not Role.ADVERSARY or operation != OPERATION or any(bearer.get(key) != value for key, value in exact.items()):
            self._fail("route_mismatch", "signed task or route identity mismatched")
        for name in ("task_id", "goal_id", "run_id", "stage", "builder_family"):
            if not _text(bearer.get(name), MAX_ID_BYTES):
                self._fail("malformed_capability", "capability identity is malformed")
        if bearer.get("builder_family") == FAMILY or not _text(bearer.get("prompt"), MAX_PROMPT_BYTES) or "context/" not in str(bearer.get("prompt")):
            self._fail("independence_mismatch", "adversary capability context or family basis is invalid")
        capability_id = bearer.get("capability_id")
        issued, expires = bearer.get("issued_at"), bearer.get("expires_at")
        current = self._clock() if now is None else now
        if not _hex(capability_id, 32) or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in (issued, expires, current)) or expires <= issued or expires - issued > self.capability_ttl_s or issued > current + 15:
            self._fail("malformed_capability", "capability identity or lifetime is malformed")
        if current >= expires:
            self._fail("expired_capability", "capability is stale")
        if capability_id in self._redeemed:
            self._fail("replayed_capability", "capability was already redeemed")
        signature = bearer.get("signature")
        if not _hex(signature, 128):
            self._fail("invalid_signature", "capability signature is malformed")
        claims = dict(bearer)
        del claims["signature"]
        try:
            self._signer.verify_key.verify(_canonical(claims), bytes.fromhex(signature))
        except Exception as exc:
            raise Gemini36AdversaryRouteError("invalid_signature", "capability signature verification failed") from exc
        self._redeemed.add(capability_id)
        return capability_id

    def child_environment(self, bearer: Mapping[str, object]) -> dict[str, str]:
        capability_id = bearer.get("capability_id")
        if not _hex(capability_id, 32):
            self._fail("malformed_capability", "capability identity is malformed")
        return {"HOME": "/nonexistent/paeos-gemini36-adversary", "LANG": "C.UTF-8", "LC_ALL": "C", "PATH": "/usr/bin:/bin", "TMPDIR": "/nonexistent/paeos-gemini36-adversary/tmp", "PAEOS_TASK_BEARER": str(capability_id), "PAEOS_TASK_BROKER_URL": BROKER_URL}

    @classmethod
    def validate_observation(cls, *, observation: object, capability: Mapping[str, object]) -> dict[str, object]:
        if set(capability) != cls._capability_fields or capability.get("schema") != CAPABILITY_SCHEMA:
            cls._fail("malformed_capability", "observation capability fields are not exact")
        if not isinstance(observation, dict) or set(observation) != cls._observation_fields:
            cls._fail("malformed_observation", "observation fields are not exact")
        content = observation.get("response_content")
        verdicts = [line.strip() for line in str(content).splitlines() if line.strip() in {"VERDICT: PASS", "VERDICT: BLOCK"}] if isinstance(content, str) else []
        exact = {"schema": OBSERVATION_SCHEMA, "capability_id": capability.get("capability_id"), "task_id": capability.get("task_id"), "goal_id": capability.get("goal_id"), "run_id": capability.get("run_id"), "stage": capability.get("stage"), "role": Role.ADVERSARY.name, "operation": OPERATION, "provider_id": PROVIDER, "model_id": MODEL, "model_family": FAMILY, "actual_provider": PROVIDER, "actual_model": MODEL, "actual_family": FAMILY, "tools_used": False, "production_writes": False, "fallback_used": False, "trusted_parent_confinement": True}
        if observation.get("schema") != OBSERVATION_SCHEMA or any(observation.get(key) != value for key, value in exact.items()) or not _text(content, MAX_RESPONSE_BYTES) or observation.get("request_sha256") != _sha256(_canonical(dict(capability))) or observation.get("response_sha256") != _sha256(content.encode("utf-8")) or len(verdicts) != 1:
            cls._fail("unqualified_observation", "observation identity, hash, confinement, or verdict is invalid")
        return dict(observation)

    @classmethod
    def reject_provider_failure(cls, value: object, *, error_code: str | None = None) -> NoReturn:
        fields = {"schema", "provider_id", "model_id", "error_type", "http_status", "retry_after", "response_bytes", "response_sha256", "raw_response_persisted"}
        if not isinstance(value, dict) or set(value) != fields or value.get("schema") != PROVIDER_FAILURE_SCHEMA or value.get("provider_id") != PROVIDER or value.get("model_id") != MODEL or value.get("error_type") not in FAILURE_TYPES or value.get("raw_response_persisted") is not False:
            cls._fail("malformed_failure", "provider failure metadata is invalid")
        raise Gemini36AdversaryRouteError("provider_failure", "trusted Google Gemini provider request failed", failure_observation=value, error_code=error_code)

    def run(self, spec: object) -> Gemini36AdversaryResult:
        values = {name: self._value(spec, name) for name in ("task_id", "goal_id", "run_id", "stage", "role", "operation", "prompt")}
        builder_family = self._value(spec, "builder_family") if (isinstance(spec, Mapping) and "builder_family" in spec) or hasattr(spec, "builder_family") else self.builder_family
        capability = self.issue_task_capability(**values, builder_family=builder_family)  # type: ignore[arg-type]
        self.redeem_task_capability(bearer=capability, task_id=values["task_id"], goal_id=values["goal_id"], run_id=values["run_id"], stage=values["stage"], role=values["role"], operation=values["operation"])  # type: ignore[arg-type]
        try:
            observation = self._parent_exchange(request=capability, environment=self.child_environment(capability), timeout_s=self._timeout_s)
        except Gemini36AdversaryRouteError:
            raise
        except Exception as exc:
            raise Gemini36AdversaryRouteError("parent_exchange_failed", "parent-owned Gemini exchange failed closed") from exc
        validated = self.validate_observation(observation=observation, capability=capability)
        self.last_observation = validated
        content = str(validated["response_content"])
        return Gemini36AdversaryResult(stage=str(validated["stage"]), role=Role.ADVERSARY, tools_used=False, production_writes=False, fallback_used=False, supervisor="parent-owned", confined=True, a08_builder_family=str(capability["builder_family"]), a08_adversary_family=FAMILY, transcript=content, environment_fingerprint=_sha256(_canonical(self.child_environment(capability))))


def parent_gemini36_adversary_exchange(*, request: object, environment: Mapping[str, str], timeout_s: float) -> dict[str, object]:
    if not isinstance(request, dict) or set(request) != Gemini36AdversaryRoute._capability_fields:
        raise Gemini36AdversaryRouteError("malformed_request", "signed adversary capability fields are not exact")
    if request.get("schema") != CAPABILITY_SCHEMA or request.get("operation") != OPERATION or request.get("role") != Role.ADVERSARY.name or request.get("provider_id") != PROVIDER or request.get("model_id") != MODEL or request.get("model_family") != FAMILY or request.get("adversary_family") != FAMILY or request.get("builder_family") == FAMILY or request.get("read_only") is not True or request.get("allow_tools") is not False or request.get("allow_fallback") is not False or request.get("require_confinement") is not True:
        raise Gemini36AdversaryRouteError("malformed_request", "signed adversary capability attribution is invalid")
    capability_id = request.get("capability_id")
    if not _hex(capability_id, 32) or not _hex(request.get("signature"), 128):
        raise Gemini36AdversaryRouteError("malformed_request", "signed adversary capability identity is invalid")
    for field in ("task_id", "goal_id", "run_id", "stage", "builder_family", "prompt"):
        if not _text(request.get(field), MAX_PROMPT_BYTES):
            raise Gemini36AdversaryRouteError("malformed_request", "signed adversary capability content is invalid")
    expected = {"HOME": "/nonexistent/paeos-gemini36-adversary", "LANG": "C.UTF-8", "LC_ALL": "C", "PATH": "/usr/bin:/bin", "TMPDIR": "/nonexistent/paeos-gemini36-adversary/tmp", "PAEOS_TASK_BEARER": str(capability_id), "PAEOS_TASK_BROKER_URL": BROKER_URL}
    if not isinstance(environment, Mapping) or dict(environment) != expected:
        raise Gemini36AdversaryRouteError("invalid_environment", "task environment or identity is not exact")
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or not math.isfinite(float(timeout_s)) or not 0 < float(timeout_s) <= 180.0:
        raise Gemini36AdversaryRouteError("invalid_timeout", "response deadline is invalid")
    payload = _canonical(request)
    if len(payload) > MAX_FRAME_BYTES:
        raise Gemini36AdversaryRouteError("oversized_request", "signed capability frame is oversized")
    issued, expires, now = request.get("issued_at"), request.get("expires_at"), time.time()
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in (issued, expires, now)) or expires <= issued or expires - issued > CAPABILITY_TTL_S or issued > now + 15.0 or expires <= now:
        raise Gemini36AdversaryRouteError("expired_request", "signed capability lifetime is invalid")
    request_path = TRUSTED_QUEUE / f"{capability_id}.request.json"
    response_path = TRUSTED_QUEUE / f"{capability_id}.response.json"
    temporary_path = TRUSTED_QUEUE / f".{capability_id}.request.tmp"
    owned_request = owned_tmp = observed = False
    try:
        queue_stat = os.lstat(TRUSTED_QUEUE)
        if stat.S_ISLNK(queue_stat.st_mode) or not stat.S_ISDIR(queue_stat.st_mode):
            raise Gemini36AdversaryRouteError("supervisor_unavailable", "trusted supervisor queue is unavailable")
        if any(os.path.lexists(path) for path in (request_path, response_path, temporary_path)):
            raise Gemini36AdversaryRouteError("stale_queue_path", "capability queue paths are not fresh")
        fd = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        owned_tmp = True
        try:
            offset = 0
            while offset < len(payload):
                count = os.write(fd, payload[offset:])
                if count <= 0:
                    raise Gemini36AdversaryRouteError("queue_write_failed", "capability write made no progress")
                offset += count
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary_path, request_path)
        owned_tmp, owned_request = False, True
        raw: bytes | None = None
        deadline = time.monotonic() + float(timeout_s)
        while time.monotonic() < deadline:
            if os.path.lexists(response_path):
                observed = True
                fd = os.open(response_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                try:
                    if not stat.S_ISREG(os.fstat(fd).st_mode):
                        raise Gemini36AdversaryRouteError("invalid_response", "supervisor response is not a regular file")
                    raw = os.read(fd, MAX_FRAME_BYTES + 1)
                finally:
                    os.close(fd)
                break
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        if raw is None or len(raw) > MAX_FRAME_BYTES:
            raise Gemini36AdversaryRouteError("response_timeout", "trusted supervisor response deadline exceeded")
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gemini36AdversaryRouteError("malformed_response", "trusted supervisor response is malformed") from exc
        if not isinstance(response, dict):
            raise Gemini36AdversaryRouteError("rejected_response", "trusted supervisor response failed attribution")
        if response.get("ok") is False:
            code = response.get("error_code")
            if response.get("schema") != SERVICE_SCHEMA or response.get("capability_id") != capability_id or not isinstance(code, str) or not code or any(char not in ERROR_CODE_ALPHABET for char in code):
                raise Gemini36AdversaryRouteError("rejected_response", "trusted supervisor failure failed attribution")
            Gemini36AdversaryRoute.reject_provider_failure(response.get("failure_observation"), error_code=code)
        if set(response) != {"schema", "ok", "capability_id", "observation"} or response.get("schema") != SERVICE_SCHEMA or response.get("ok") is not True or response.get("capability_id") != capability_id:
            raise Gemini36AdversaryRouteError("rejected_response", "trusted supervisor response failed attribution")
        return response["observation"]
    except Gemini36AdversaryRouteError:
        raise
    except OSError as exc:
        raise Gemini36AdversaryRouteError("supervisor_unavailable", "trusted supervisor queue failed closed") from exc
    finally:
        for path, owned in ((response_path, observed), (request_path, owned_request), (temporary_path, owned_tmp)):
            if owned:
                try:
                    if os.path.lexists(path) and not path.is_symlink():
                        path.unlink()
                except OSError:
                    pass


class HostGemini36AdversaryTransport(HostClineCriticTransport):
    provider_id = PROVIDER
    model_id = MODEL
    model_family = FAMILY
    allowed_role = Role.ADVERSARY
    allowed_operation = OPERATION
    parent_owns_authentication = True
    child_receives_parent_credentials = False
    allows_tools = False
    allows_production_writes = False
    allow_fallback = False
    contacts_cline = False

    def __init__(self, *, request_signing_key: Any, parent_exchange: Callable[..., object] = parent_gemini36_adversary_exchange, builder_family: str = "gpt", timeout_s: float = 180.0) -> None:
        if not _text(builder_family, MAX_ID_BYTES) or builder_family == FAMILY:
            raise Gemini36AdversaryRouteError("invalid_configuration", "Builder and adversary families are not independent")
        self._route = Gemini36AdversaryRoute(request_signing_key=request_signing_key, parent_exchange=parent_exchange, builder_family=builder_family, timeout_s=timeout_s)
        self.builder_family = builder_family
        self.last_observation: dict[str, object] | None = None

    def run(self, spec: object) -> object:
        result = self._route.run(spec)
        self.last_observation = self._route.last_observation
        return result
