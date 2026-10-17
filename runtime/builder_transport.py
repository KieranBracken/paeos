"""Cryptographically verified readiness gate for the production Codex Builder transport.

``BuilderTransportReadiness`` does not trust a model statement or a configuration flag.  It accepts
only a signed, hash-bound qualification record produced by the trusted supervisor's physical
qualification harness.  The record is deliberately narrower than P1: it proves the minimum
launch, progress, response, terminal, and confinement conjunction needed before a Trace-B mission
may enter L12.
"""

from __future__ import annotations

import json
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

__all__ = [
    "REQUIRED_CANARIES",
    "REQUIRED_LIFECYCLE",
    "BuilderTransportNotReady",
    "BuilderTransportQualification",
    "BuilderTransportReadiness",
    "canonical_qualification_bytes",
]

SCHEMA = "paeos-builder-transport-qualification/1"
REQUIRED_LIFECYCLE = ("STARTING", "RUNNING", "PROGRESS", "COMPLETED")
REQUIRED_CANARIES = frozenset(
    {
        "approved_read",
        "approved_write",
        "forbidden_read_denied",
        "forbidden_write_denied",
        "parent_secret_invisible",
        "provider_credential_absent",
        "symlink_escape_denied",
        "traversal_escape_denied",
        "child_subprocess_confined",
        "broker_capability_task_scoped",
        "supervisor_restart_no_fallback",
    }
)
_HASH_FIELDS = frozenset(
    {
        "supervisor_identity_sha256",
        "request_sha256",
        "response_sha256",
        "artifact_sha256",
        "evidence_sha256",
    }
)
_PAYLOAD_FIELDS = frozenset(
    {
        "schema",
        "qualification_scope",
        "qualification_id",
        *_HASH_FIELDS,
        "provider",
        "model",
        "family",
        "observed_at",
        "expires_at",
        "lifecycle",
        "canaries",
        "fallback_used",
        "manual_chat_bridge",
    }
)


class BuilderTransportNotReady(RuntimeError):
    """The physical qualification proof is absent, stale, forged, or incomplete."""


@dataclass(frozen=True, slots=True)
class BuilderTransportQualification:
    qualification_scope: str
    qualification_id: str
    supervisor_identity_sha256: str
    request_sha256: str
    response_sha256: str
    artifact_sha256: str
    evidence_sha256: str
    provider: str
    model: str
    family: str
    observed_at: int
    expires_at: int
    lifecycle: tuple[str, ...]
    canaries: tuple[str, ...]
    fallback_used: bool
    manual_chat_bridge: bool


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def canonical_qualification_bytes(payload: Mapping[str, object]) -> bytes:
    if set(payload) != _PAYLOAD_FIELDS:
        raise BuilderTransportNotReady("qualification payload fields are not exact")
    return _canonical(dict(payload))


def _strict_json(raw: bytes) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise BuilderTransportNotReady("qualification contains a duplicate JSON field")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuilderTransportNotReady("qualification is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise BuilderTransportNotReady("qualification root is not an object")
    return value


def _hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and value == value.casefold() and all(
        character in "0123456789abcdef" for character in value
    )


class BuilderTransportReadiness:
    """Verify one signed physical qualification record at the production composition root."""

    def __init__(
        self,
        qualification_path: Path,
        verify_key: VerifyKey,
        *,
        clock: Callable[[], int] | None = None,
        max_age_s: int = 86_400,
    ) -> None:
        self._path = qualification_path
        self._verify_key = verify_key
        self._clock = clock or (lambda: int(time.time()))
        self._max_age_s = max_age_s

    def require(self) -> BuilderTransportQualification:
        path = self._path
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise BuilderTransportNotReady("qualification file is unavailable")
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & 0o077:
                raise BuilderTransportNotReady("qualification file permissions are too broad")
            document = _strict_json(path.read_bytes())
        except OSError as exc:
            raise BuilderTransportNotReady("qualification file cannot be read") from exc
        if set(document) != {"payload", "signature"} or not isinstance(document.get("payload"), dict):
            raise BuilderTransportNotReady("qualification envelope is not exact")
        payload = document["payload"]
        assert isinstance(payload, dict)
        try:
            signed = canonical_qualification_bytes(payload)
            signature = document["signature"]
            if not isinstance(signature, str) or len(signature) != 128:
                raise BuilderTransportNotReady("qualification signature is malformed")
            self._verify_key.verify(signed, bytes.fromhex(signature))
        except (BadSignatureError, ValueError) as exc:
            raise BuilderTransportNotReady("qualification signature is invalid") from exc
        qualification = self._validate_payload(payload)
        now = self._clock()
        if qualification.observed_at > now + 5:
            raise BuilderTransportNotReady("qualification timestamp is in the future")
        if qualification.expires_at <= now or qualification.expires_at - qualification.observed_at > self._max_age_s:
            raise BuilderTransportNotReady("qualification is expired or stale")
        if now - qualification.observed_at > self._max_age_s:
            raise BuilderTransportNotReady("qualification is stale")
        return qualification

    @staticmethod
    def _validate_payload(payload: Mapping[str, object]) -> BuilderTransportQualification:
        if payload.get("schema") != SCHEMA:
            raise BuilderTransportNotReady("qualification schema is unsupported")
        if payload.get("qualification_scope") != "standalone-provider-probe":
            raise BuilderTransportNotReady("qualification scope is not a standalone provider probe")
        for field in _HASH_FIELDS:
            if not _hash(payload.get(field)):
                raise BuilderTransportNotReady(f"qualification hash is invalid: {field}")
        for field in ("qualification_id", "provider", "model", "family"):
            if not isinstance(payload.get(field), str) or not payload[field]:
                raise BuilderTransportNotReady(f"qualification identity is invalid: {field}")
        if payload["provider"] != "codex" or payload["model"] != "gpt-5.6-sol" or payload["family"] != "gpt":
            raise BuilderTransportNotReady("qualification is not the admitted Codex Builder route")
        times = (payload.get("observed_at"), payload.get("expires_at"))
        if any(not isinstance(value, int) or isinstance(value, bool) for value in times):
            raise BuilderTransportNotReady("qualification timestamps are invalid")
        lifecycle = payload.get("lifecycle")
        canaries = payload.get("canaries")
        if not isinstance(lifecycle, list) or tuple(lifecycle) != REQUIRED_LIFECYCLE:
            raise BuilderTransportNotReady("qualification liveness sequence is incomplete")
        if not isinstance(canaries, list) or not REQUIRED_CANARIES.issubset(canaries):
            raise BuilderTransportNotReady("qualification confinement canaries are incomplete")
        if not isinstance(payload.get("fallback_used"), bool) or payload["fallback_used"]:
            raise BuilderTransportNotReady("qualification used a fallback")
        if not isinstance(payload.get("manual_chat_bridge"), bool) or payload["manual_chat_bridge"]:
            raise BuilderTransportNotReady("qualification depends on manual ChatBridge")
        return BuilderTransportQualification(
            qualification_scope=payload["qualification_scope"],  # type: ignore[arg-type]
            qualification_id=payload["qualification_id"],  # type: ignore[arg-type]
            supervisor_identity_sha256=payload["supervisor_identity_sha256"],  # type: ignore[arg-type]
            request_sha256=payload["request_sha256"],  # type: ignore[arg-type]
            response_sha256=payload["response_sha256"],  # type: ignore[arg-type]
            artifact_sha256=payload["artifact_sha256"],  # type: ignore[arg-type]
            evidence_sha256=payload["evidence_sha256"],  # type: ignore[arg-type]
            provider=payload["provider"],  # type: ignore[arg-type]
            model=payload["model"],  # type: ignore[arg-type]
            family=payload["family"],  # type: ignore[arg-type]
            observed_at=payload["observed_at"],  # type: ignore[arg-type]
            expires_at=payload["expires_at"],  # type: ignore[arg-type]
            lifecycle=tuple(lifecycle),
            canaries=tuple(sorted(canaries)),
            fallback_used=payload["fallback_used"],  # type: ignore[arg-type]
            manual_chat_bridge=payload["manual_chat_bridge"],  # type: ignore[arg-type]
        )
