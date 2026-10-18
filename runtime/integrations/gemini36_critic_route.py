"""Bounded parent-owned Google Gemini 3.6 Flash CRITIC capability.

The child side of this route receives only a signed, single-use task capability.
Provider credentials and provider I/O remain in the trusted parent, and every
successful observation must attest the exact selected and observed identity.
"""

from __future__ import annotations

import hashlib
import json
import math
import socket
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, NoReturn, Protocol

from kernel.types import Role

from runtime.integrations.provider_broker import HostClineCriticTransport

CAPABILITY_SCHEMA = "paeos.trusted-gemini36-critic-capability/1"
OBSERVATION_SCHEMA = "paeos.parent-google-gemini36-critic-observation/1"
FAILURE_SCHEMA = "paeos.provider-failure-observation/1"
PROVIDER, MODEL, FAMILY = "google", "gemini-3.6-flash", "gemini"
_HEX = frozenset("0123456789abcdef")
_ERROR_CODE_ALPHABET = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_:-")
_ERROR_TYPES = frozenset(
    {
        "AUTH_FAILED",
        "BAD_REQUEST",
        "CONTENT_POLICY",
        "CONTEXT_EXCEEDED",
        "MODEL_UNAVAILABLE",
        "PROVIDER_UNAVAILABLE",
        "QUOTA_EXHAUSTED",
        "RATE_LIMITED",
        "TIMEOUT",
        "UNKNOWN",
    }
)


class _SigningKey(Protocol):
    """Structural type for the parent-owned signing authority."""

    verify_key: Any

    def sign(self, message: bytes) -> Any:
        """Sign one canonical capability payload."""


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def _hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in _HEX for character in value)
    )


def _text(value: object, maximum_bytes: int) -> bool:
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        return False
    try:
        return len(value.encode("utf-8")) <= maximum_bytes
    except UnicodeEncodeError:
        return False


def _optional_http_status(value: object) -> bool:
    return value is None or (
        isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599
    )


def _optional_nonnegative_integer(value: object) -> bool:
    return value is None or (
        isinstance(value, int) and not isinstance(value, bool) and value >= 0
    )


def _optional_nonnegative_number(value: object) -> bool:
    return value is None or (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )


def _optional_sha256(value: object) -> bool:
    return value is None or _hex(value, 64)


@dataclass(frozen=True, slots=True)
class Gemini36CriticRouteRegistration:
    """Role-scoped route registration with no lifecycle-stage admission policy."""

    provider_id: str = PROVIDER
    model_id: str = MODEL
    model_family: str = FAMILY
    roles: frozenset[Role] = frozenset({Role.CRITIC})
    lifecycle_stages: None = None


GEMINI36_CRITIC_ROUTE = Gemini36CriticRouteRegistration()
GEMINI36_CRITIC_CANDIDATE = GEMINI36_CRITIC_ROUTE


def register_candidate(registry: object) -> Gemini36CriticRouteRegistration:
    """Register the candidate without granting admission to any lifecycle stage."""

    register = getattr(registry, "register_candidate", None)
    if not callable(register):
        raise TypeError("registry does not provide register_candidate")
    register(GEMINI36_CRITIC_CANDIDATE)
    return GEMINI36_CRITIC_CANDIDATE


@dataclass(frozen=True, slots=True)
class Gemini36CriticResult:
    stage: str
    role: Role
    tools_used: bool
    production_writes: bool
    fallback_used: bool
    supervisor: str
    confined: bool
    a08_builder_family: str
    a08_critic_family: str


class Gemini36CriticRouteError(RuntimeError):
    """Machine-classifiable failure that never embeds provider response content."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        failure_observation: Mapping[str, object] | None = None,
        error_code: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.error_code = error_code
        self.failure_observation = (
            dict(failure_observation) if failure_observation is not None else None
        )
        self.diagnostic = self.failure_observation
        super().__init__(f"{code}: {message}")


class Gemini36CriticCapabilityAdapter(HostClineCriticTransport):
    """Issue and redeem one exact parent-signed Gemini 3.6 critic capability."""

    provider_id = PROVIDER
    model_id = MODEL
    model_family = FAMILY
    allowed_role = Role.CRITIC
    allowed_operation = "critic"
    parent_owns_authentication = True
    parent_owned = True
    requires_trusted_parent_confinement = True
    allows_tools = False
    allows_writes = False
    allow_fallback = False
    child_receives_parent_credentials = False
    contacts_cline = False
    capability_ttl_s = 45.0
    broker_url = "parent-owned:google-gemini36-critic"
    registration = GEMINI36_CRITIC_ROUTE
    _fields = frozenset(
        {
            "schema",
            "capability_id",
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "role",
            "operation",
            "provider_id",
            "model_id",
            "model_family",
            "prompt",
            "read_only",
            "allow_tools",
            "allow_fallback",
            "require_confinement",
            "builder_family",
            "critic_family",
            "issued_at",
            "expires_at",
            "signature",
        }
    )
    _obs = frozenset(
        {
            "schema",
            "capability_id",
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "role",
            "operation",
            "provider_id",
            "model_id",
            "model_family",
            "actual_provider",
            "actual_model",
            "actual_family",
            "tools_used",
            "production_writes",
            "fallback_used",
            "trusted_parent_confinement",
            "response_content",
            "request_sha256",
            "response_sha256",
        }
    )

    def __init__(
        self,
        *,
        request_signing_key: _SigningKey,
        parent_exchange: Callable[..., object] | None = None,
        now: Callable[[], float] = time.time,
        timeout_s: float = 180.0,
    ) -> None:
        if (
            not callable(getattr(request_signing_key, "sign", None))
            or not callable(now)
            or not callable(parent_exchange)
        ):
            raise Gemini36CriticRouteError(
                "invalid_configuration", "parent authority is unavailable"
            )
        if (
            isinstance(timeout_s, bool)
            or not isinstance(timeout_s, (int, float))
            or not 0 < timeout_s <= 180
        ):
            raise Gemini36CriticRouteError(
                "invalid_configuration", "timeout is invalid"
            )
        self._signer = request_signing_key
        self._exchange = parent_exchange
        self._clock = now
        self._timeout = float(timeout_s)
        self._redeemed: set[str] = set()
        self.last_observation: dict[str, object] | None = None

    @staticmethod
    def _fail(code: str, message: str) -> NoReturn:
        raise Gemini36CriticRouteError(code, message)

    def issue_task_capability(
        self,
        task_id: str,
        goal_id: str,
        run_id: str,
        stage: str,
        role: Role,
        operation: str,
        prompt: str,
        builder_family: str,
        tools: None = None,
        allow_writes: bool = False,
        allow_fallback: bool = False,
        require_confinement: bool = True,
        now: float | None = None,
    ) -> dict[str, object]:
        """Create a short-lived capability bound to the exact critic task and route."""

        if role is not Role.CRITIC or operation != "critic":
            self._fail(
                "route_mismatch", "only Role.CRITIC critic operation is authorized"
            )
        if (
            tools is not None
            or allow_writes is not False
            or allow_fallback is not False
            or require_confinement is not True
        ):
            self._fail("authority_mismatch", "bounded policy required")
        for name, value in (
            ("task", task_id),
            ("goal", goal_id),
            ("run", run_id),
            ("stage", stage),
            ("builder", builder_family),
        ):
            if not _text(value, 1024):
                self._fail("malformed_identity", f"{name} is malformed")
        if builder_family == FAMILY or not _text(prompt, 16384):
            self._fail("a08_mismatch", "critic independence or prompt is invalid")
        issued = self._clock() if now is None else now
        if (
            isinstance(issued, bool)
            or not isinstance(issued, (int, float))
            or not math.isfinite(issued)
        ):
            self._fail("malformed_time", "time is malformed")
        claims = {
            "schema": CAPABILITY_SCHEMA,
            "capability_id": uuid.uuid4().hex,
            "task_id": task_id,
            "goal_id": goal_id,
            "run_id": run_id,
            "stage": stage,
            "role": "CRITIC",
            "operation": "critic",
            "provider_id": PROVIDER,
            "model_id": MODEL,
            "model_family": FAMILY,
            "prompt": prompt,
            "read_only": True,
            "allow_tools": False,
            "allow_fallback": False,
            "require_confinement": True,
            "builder_family": builder_family,
            "critic_family": FAMILY,
            "issued_at": float(issued),
            "expires_at": float(issued) + 45.0,
        }
        try:
            signature = self._signer.sign(_canonical(claims)).signature.hex()
        except Exception as exc:
            raise Gemini36CriticRouteError(
                "signing_failed", "parent signing failed"
            ) from exc
        if not _hex(signature, 128):
            self._fail("signing_failed", "signature malformed")
        return {**claims, "signature": signature}

    def redeem_task_capability(
        self,
        *,
        bearer: object,
        task_id: str,
        goal_id: str,
        run_id: str,
        stage: str,
        role: Role,
        operation: str,
        now: float | None = None,
    ) -> str:
        """Validate and consume one capability exactly once."""

        if role is not Role.CRITIC or operation != "critic":
            self._fail(
                "route_mismatch", "only Role.CRITIC critic operation is authorized"
            )
        if not isinstance(bearer, dict) or set(bearer) != self._fields:
            self._fail("malformed_capability", "fields are not exact")
        exact = {
            "schema": CAPABILITY_SCHEMA,
            "task_id": task_id,
            "goal_id": goal_id,
            "run_id": run_id,
            "stage": stage,
            "role": "CRITIC",
            "operation": "critic",
            "provider_id": PROVIDER,
            "model_id": MODEL,
            "model_family": FAMILY,
            "read_only": True,
            "allow_tools": False,
            "allow_fallback": False,
            "require_confinement": True,
            "critic_family": FAMILY,
        }
        if any(bearer.get(k) != v for k, v in exact.items()):
            self._fail("route_mismatch", "route identity mismatched")
        current = self._clock() if now is None else now
        issued = bearer.get("issued_at")
        expires = bearer.get("expires_at")
        cid = bearer.get("capability_id")
        if (
            not _hex(cid, 32)
            or not all(
                isinstance(x, (int, float))
                and not isinstance(x, bool)
                and math.isfinite(x)
                for x in (issued, expires, current)
            )
            or expires <= issued
            or expires - issued > 45
            or issued > current + 15
        ):
            self._fail("malformed_capability", "lifetime malformed")
        if current >= expires:
            self._fail("expired_capability", "capability is stale")
        if cid in self._redeemed:
            self._fail("replayed_capability", "capability was already redeemed")
        sig = bearer.get("signature")
        claims = dict(bearer)
        claims.pop("signature", None)
        try:
            self._signer.verify_key.verify(
                _canonical(claims), bytes.fromhex(sig) if _hex(sig, 128) else b""
            )
        except Exception as exc:
            raise Gemini36CriticRouteError(
                "invalid_signature", "signature verification failed"
            ) from exc
        self._redeemed.add(cid)
        return cid

    def child_environment(self, bearer: Mapping[str, object]) -> dict[str, str]:
        """Return the complete non-secret child environment."""

        cid = bearer.get("capability_id")
        if not _hex(cid, 32):
            self._fail("malformed_capability", "identity malformed")
        return {
            "HOME": "/nonexistent/paeos-gemini36-critic",
            "LANG": "C.UTF-8",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
            "TMPDIR": "/nonexistent/paeos-gemini36-critic/tmp",
            "PAEOS_TASK_BEARER": cid,
            "PAEOS_TASK_BROKER_URL": self.broker_url,
        }

    @classmethod
    def validate_observation(
        cls,
        *,
        observation: object,
        capability: Mapping[str, object],
    ) -> dict[str, object]:
        """Validate exact route identity, confinement facts, and content hashes."""

        if not isinstance(observation, dict) or set(observation) != cls._obs:
            cls._fail("malformed_observation", "fields are not exact")
        exact = {
            "schema": OBSERVATION_SCHEMA,
            "capability_id": capability.get("capability_id"),
            "task_id": capability.get("task_id"),
            "goal_id": capability.get("goal_id"),
            "run_id": capability.get("run_id"),
            "stage": capability.get("stage"),
            "role": "CRITIC",
            "operation": "critic",
            "provider_id": PROVIDER,
            "model_id": MODEL,
            "model_family": FAMILY,
            "actual_provider": PROVIDER,
            "actual_model": MODEL,
            "actual_family": FAMILY,
            "tools_used": False,
            "production_writes": False,
            "fallback_used": False,
            "trusted_parent_confinement": True,
        }
        content = observation.get("response_content")
        if (
            any(observation.get(k) != v for k, v in exact.items())
            or not _text(content, 262144)
            or observation.get("request_sha256")
            != hashlib.sha256(_canonical(dict(capability))).hexdigest()
            or observation.get("response_sha256")
            != hashlib.sha256(content.encode("utf-8")).hexdigest()
        ):
            cls._fail(
                "unqualified_observation",
                "observation identity or confinement is invalid",
            )
        return dict(observation)

    @staticmethod
    def _spec_value(spec: object, name: str) -> object:
        if isinstance(spec, Mapping):
            if name not in spec:
                raise Gemini36CriticRouteError(
                    "malformed_spec", "task specification is incomplete"
                )
            return spec[name]
        try:
            return getattr(spec, name)
        except AttributeError as exc:
            raise Gemini36CriticRouteError(
                "malformed_spec", "task specification is incomplete"
            ) from exc

    def run(self, spec: object) -> Gemini36CriticResult:
        """Execute one signed CRITIC exchange through the trusted parent."""

        names = (
            "task_id",
            "goal_id",
            "run_id",
            "stage",
            "role",
            "operation",
            "prompt",
            "builder_family",
        )
        values = {name: self._spec_value(spec, name) for name in names}
        cap = self.issue_task_capability(**values)
        self.redeem_task_capability(
            bearer=cap,
            **{
                k: values[k]
                for k in ("task_id", "goal_id", "run_id", "stage", "role", "operation")
            },
        )
        try:
            observation = self._exchange(
                request=cap,
                environment=self.child_environment(cap),
                timeout_s=self._timeout,
            )
        except Gemini36CriticRouteError:
            raise
        except Exception as exc:
            raise Gemini36CriticRouteError(
                "parent_exchange_failed", "parent exchange failed closed"
            ) from exc
        observation = self.validate_observation(
            observation=observation, capability=cap
        )
        self.last_observation = observation
        return Gemini36CriticResult(
            str(observation["stage"]),
            Role.CRITIC,
            False,
            False,
            False,
            "parent-owned",
            True,
            str(cap["builder_family"]),
            FAMILY,
        )


Gemini36CriticRoute = Gemini36CriticCapabilityAdapter


def parent_gemini36_exchange(
    *, request: object, environment: Mapping[str, str], timeout_s: float
) -> dict[str, object]:
    """Send the signed grant to the local service; never contact Google here."""
    if (
        not isinstance(request, dict)
        or set(request) != Gemini36CriticCapabilityAdapter._fields
    ):
        raise Gemini36CriticRouteError(
            "malformed_request", "signed capability fields are not exact"
        )
    expected = Gemini36CriticCapabilityAdapter.child_environment.__get__(
        object.__new__(Gemini36CriticCapabilityAdapter)
    )(request)
    if dict(environment) != expected:
        raise Gemini36CriticRouteError(
            "invalid_environment", "child environment is not exact"
        )
    raw = _canonical(request)
    try:
        for attempt in range(3):
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
                    channel.settimeout(float(timeout_s))
                    channel.connect(
                        "/Users/bob/GitHub/paeos/ops/.trusted-worker/launcher.sock"
                    )
                    channel.sendall(raw)
                    channel.shutdown(socket.SHUT_WR)
                    chunks: list[bytes] = []
                    total = 0
                    while True:
                        chunk = channel.recv(65536)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > 524288:
                            raise Gemini36CriticRouteError(
                                "oversized_response", "service response is oversized"
                            )
                        chunks.append(chunk)
                break
            except ConnectionRefusedError:
                if attempt == 2:
                    raise
                time.sleep(0.05)
        try:
            response = json.loads(b"".join(chunks))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gemini36CriticRouteError(
                "supervisor_malformed_response",
                "trusted service response is malformed",
            ) from exc
    except Gemini36CriticRouteError:
        raise
    except ConnectionResetError as exc:
        raise Gemini36CriticRouteError(
            "supervisor_connection_reset",
            "trusted service connection was reset",
        ) from exc
    except TimeoutError as exc:
        raise Gemini36CriticRouteError(
            "supervisor_timeout",
            "trusted service response deadline exceeded",
        ) from exc
    except ConnectionRefusedError as exc:
        raise Gemini36CriticRouteError(
            "supervisor_connection_refused",
            "trusted service connection was refused",
        ) from exc
    except OSError as exc:
        raise Gemini36CriticRouteError(
            "supervisor_socket_error",
            "trusted service socket failed closed",
        ) from exc
    cid = request["capability_id"]
    if (
        not isinstance(response, dict)
        or response.get("schema") != "paeos.trusted-worker-service/1"
        or response.get("capability_id") != cid
    ):
        raise Gemini36CriticRouteError(
            "rejected_response", "service attribution failed"
        )
    if response.get("ok") is True and set(response) == {
        "schema",
        "ok",
        "capability_id",
        "observation",
    }:
        return response["observation"]
    failure = response.get("failure_observation")
    error_code = response.get("error_code")
    allowed = {
        "schema",
        "provider_id",
        "model_id",
        "error_type",
        "http_status",
        "retry_after",
        "response_bytes",
        "response_sha256",
        "raw_response_persisted",
    }
    if (
        set(response)
        != {
            "schema",
            "ok",
            "capability_id",
            "error",
            "error_code",
            "failure_observation",
        }
        or response.get("ok") is not False
        or response.get("error")
        != "provider capability rejected or execution failed closed"
        or not isinstance(error_code, str)
        or not 1 <= len(error_code) <= 80
        or any(character not in _ERROR_CODE_ALPHABET for character in error_code)
        or not isinstance(failure, dict)
        or set(failure) != allowed
        or failure.get("schema") != FAILURE_SCHEMA
        or failure.get("provider_id") != PROVIDER
        or failure.get("model_id") != MODEL
        or failure.get("error_type") not in _ERROR_TYPES
        or not _optional_http_status(failure.get("http_status"))
        or not _optional_nonnegative_number(failure.get("retry_after"))
        or not _optional_nonnegative_integer(failure.get("response_bytes"))
        or not _optional_sha256(failure.get("response_sha256"))
        or (failure.get("response_bytes") is None)
        != (failure.get("response_sha256") is None)
        or failure.get("raw_response_persisted") is not False
    ):
        raise Gemini36CriticRouteError(
            "rejected_response", "service failure attribution failed"
        )
    raise Gemini36CriticRouteError(
        "provider_failure",
        "trusted Google Gemini provider request failed",
        failure_observation=failure,
        error_code=error_code,
    )


class HostGemini36CriticTransport(HostClineCriticTransport):
    """Runtime transport facade for the exact qualified Gemini 3.6 route."""

    provider_id = PROVIDER
    model_id = MODEL
    model_family = FAMILY
    contacts_cline = False

    def __init__(
        self,
        *,
        request_signing_key: _SigningKey,
        parent_exchange: Callable[..., object],
        builder_family: str = "gpt-5.6",
        timeout_s: float = 180.0,
    ) -> None:
        self.builder_family = builder_family
        self._adapter = Gemini36CriticRoute(
            request_signing_key=request_signing_key,
            parent_exchange=parent_exchange,
            timeout_s=timeout_s,
        )

    def run(self, spec: object) -> Any:
        """Run one critic task and expose only its validated response content."""

        from runtime.integrations import SessionResult

        package = {
            "task_id": spec.task_id,
            "goal_id": spec.goal_id,
            "run_id": spec.run_id,
            "stage": spec.stage,
            "role": Role.CRITIC,
            "operation": "critic",
            "prompt": spec.prompt,
            "builder_family": self.builder_family,
        }
        self._adapter.run(package)
        observation = self._adapter.last_observation
        if observation is None:
            raise Gemini36CriticRouteError(
                "missing_observation", "validated parent observation is unavailable"
            )
        return SessionResult(
            transcript=observation["response_content"],
            lifecycle_state="RETURNED",
            exit_code=0,
            actual_provider=PROVIDER,
            actual_model=MODEL,
            actual_family=FAMILY,
        )
