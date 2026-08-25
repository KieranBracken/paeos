"""Immutable protocol envelopes and write-once storage for the PAEOS bridge."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import cast

SCHEMA_VERSION = "paeos-bridge-v2"

_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]+")
_HEX_HASH = re.compile(r"[0-9a-f]{64}")
_UNKNOWN_MODEL_VALUES = frozenset({"unknown", "none", "null", "unavailable"})


class ProtocolViolation(RuntimeError):
    """Raised when bridge protocol data fails closed validation."""


class Disposition(StrEnum):
    CONTINUE = "CONTINUE"
    REMAND = "REMAND"
    HALT = "HALT"
    NEEDS_FOUNDER = "NEEDS_FOUNDER"


class TransactionState(StrEnum):
    NEW = "NEW"
    PREPARED = "PREPARED"
    CLAIMED = "CLAIMED"
    RESPONDED = "RESPONDED"
    CONSUMED = "CONSUMED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True, slots=True)
class BridgePaths:
    state_root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_root", self.state_root.resolve())

    @property
    def bridge_root(self) -> Path:
        return self.state_root / "bridge"

    @property
    def requests(self) -> Path:
        return self.bridge_root / "requests"

    @property
    def responses(self) -> Path:
        return self.bridge_root / "responses"

    @property
    def quarantine(self) -> Path:
        return self.bridge_root / "quarantine"

    @property
    def transactions(self) -> Path:
        return self.bridge_root / "transactions"

    def ensure(self) -> None:
        for path in (
            self.requests,
            self.responses,
            self.quarantine,
            self.transactions,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class RequestEnvelope:
    schema_version: str
    request_id: str
    transaction_key: str
    created_at: str
    expires_at: str
    goal_id: str
    run_id: str
    stage_id: str
    role: str
    workspace_root: str
    worker_transport_id: str
    worker_session_id: str
    worker_pid: int
    worker_tty: str | None
    worker_model_provider: str
    worker_model_id: str
    worker_model_family: str
    semantic_hash: str
    evidence_manifest_hash: str
    payload_hash: str
    allowed_dispositions: tuple[Disposition, ...]


@dataclass(frozen=True, slots=True)
class ResponseEnvelope:
    schema_version: str
    request_id: str
    transaction_key: str
    run_id: str
    stage_id: str
    payload_hash: str
    lease_owner: str
    overseer_model_provider: str
    overseer_model_id: str
    overseer_model_family: str
    disposition: Disposition
    response_text: str
    response_hash: str
    source_task_id: str
    completed_at: str


def _normalize(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _normalize(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _normalize(item) for key, item in mapping.items()}
    if isinstance(value, tuple):
        sequence = cast(tuple[object, ...], value)
        return [_normalize(item) for item in sequence]
    if isinstance(value, list):
        sequence = cast(list[object], value)
        return [_normalize(item) for item in sequence]
    return value


def canonical_json(value: object) -> str:
    try:
        return json.dumps(
            _normalize(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolViolation(f"value is not canonically serializable: {exc}") from exc


def content_hash(value: str | bytes | Mapping[str, object]) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    elif isinstance(value, Mapping):
        payload = canonical_json(value).encode("utf-8")
    else:
        raise ProtocolViolation("content_hash accepts only text, bytes, or a mapping")
    return hashlib.sha256(payload).hexdigest()


def transaction_key(
    *,
    request_id: str,
    run_id: str,
    stage_id: str,
    semantic_hash: str,
    evidence_manifest_hash: str,
    payload_hash: str,
) -> str:
    identity = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "run_id": run_id,
        "stage_id": stage_id,
        "semantic_hash": semantic_hash,
        "evidence_manifest_hash": evidence_manifest_hash,
        "payload_hash": payload_hash,
    }
    return hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()


def _validate_identifier(value: object, field_name: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ProtocolViolation(f"{field_name} must be a slash-free protocol identifier")


def _validate_hash(value: object, field_name: str) -> None:
    if not isinstance(value, str) or _HEX_HASH.fullmatch(value) is None:
        raise ProtocolViolation(f"{field_name} must be a lowercase 64-character hex digest")


def _validate_model_identity(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolViolation(f"{field_name} must be a non-empty string")
    if value.strip().lower() in _UNKNOWN_MODEL_VALUES:
        raise ProtocolViolation(f"{field_name} must be attributable, not a placeholder")


def _parse_aware_timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ProtocolViolation(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProtocolViolation(f"{field_name} must be valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProtocolViolation(f"{field_name} must be timezone-aware")
    return parsed


def validate_request(request: RequestEnvelope) -> None:
    if request.schema_version != SCHEMA_VERSION:
        raise ProtocolViolation("unsupported request schema_version")

    for field_name, value in (
        ("request_id", request.request_id),
        ("goal_id", request.goal_id),
        ("run_id", request.run_id),
        ("stage_id", request.stage_id),
        ("role", request.role),
        ("worker_transport_id", request.worker_transport_id),
        ("worker_session_id", request.worker_session_id),
    ):
        _validate_identifier(value, field_name)

    for field_name, value in (
        ("transaction_key", request.transaction_key),
        ("semantic_hash", request.semantic_hash),
        ("evidence_manifest_hash", request.evidence_manifest_hash),
        ("payload_hash", request.payload_hash),
    ):
        _validate_hash(value, field_name)

    created_at = _parse_aware_timestamp(request.created_at, "created_at")
    expires_at = _parse_aware_timestamp(request.expires_at, "expires_at")
    if expires_at <= created_at:
        raise ProtocolViolation("expires_at must be later than created_at")

    if not isinstance(request.workspace_root, str):
        raise ProtocolViolation("workspace_root must be a string")
    if not Path(request.workspace_root).is_absolute():
        raise ProtocolViolation("workspace_root must be absolute")

    if (
        isinstance(request.worker_pid, bool)
        or not isinstance(request.worker_pid, int)
        or request.worker_pid <= 0
    ):
        raise ProtocolViolation("worker_pid must be a positive integer")

    for field_name, value in (
        ("worker_model_provider", request.worker_model_provider),
        ("worker_model_id", request.worker_model_id),
        ("worker_model_family", request.worker_model_family),
    ):
        _validate_model_identity(value, field_name)

    if request.worker_tty is None:
        if not request.worker_transport_id.startswith("headless:"):
            raise ProtocolViolation("worker_tty may be null only for a headless transport")
    elif not isinstance(request.worker_tty, str) or not request.worker_tty.strip():
        raise ProtocolViolation("worker_tty must be non-empty when present")

    allowed = request.allowed_dispositions
    if not isinstance(allowed, tuple) or not allowed:
        raise ProtocolViolation("allowed_dispositions must be a non-empty tuple")
    if any(not isinstance(item, Disposition) for item in allowed):
        raise ProtocolViolation("allowed_dispositions must contain only Disposition values")
    if len(set(allowed)) != len(allowed):
        raise ProtocolViolation("allowed_dispositions must not contain duplicates")


def validate_response(response: ResponseEnvelope) -> None:
    if response.schema_version != SCHEMA_VERSION:
        raise ProtocolViolation("unsupported response schema_version")

    for field_name, value in (
        ("request_id", response.request_id),
        ("run_id", response.run_id),
        ("stage_id", response.stage_id),
        ("lease_owner", response.lease_owner),
        ("source_task_id", response.source_task_id),
    ):
        _validate_identifier(value, field_name)

    for field_name, value in (
        ("transaction_key", response.transaction_key),
        ("payload_hash", response.payload_hash),
        ("response_hash", response.response_hash),
    ):
        _validate_hash(value, field_name)

    for field_name, value in (
        ("overseer_model_provider", response.overseer_model_provider),
        ("overseer_model_id", response.overseer_model_id),
        ("overseer_model_family", response.overseer_model_family),
    ):
        _validate_model_identity(value, field_name)

    if not isinstance(response.disposition, Disposition):
        raise ProtocolViolation("disposition must be a Disposition value")
    if response.response_hash != content_hash(response.response_text):
        raise ProtocolViolation("response_hash does not match response_text")
    _parse_aware_timestamp(response.completed_at, "completed_at")


def write_once_bytes(path: Path, payload: bytes) -> None:
    target = Path(path)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temp_path, target)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temp_path)


def write_once_json(path: Path, value: object) -> None:
    payload = (canonical_json(value) + "\n").encode("utf-8")
    write_once_bytes(path, payload)


def load_json(path: Path) -> dict[str, object]:
    source = Path(path)
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolViolation(f"{source} is not valid UTF-8") from exc
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolViolation(f"{source} contains malformed JSON") from exc
    if not isinstance(parsed, dict):
        raise ProtocolViolation(f"{source} must contain a JSON object")
    return cast(dict[str, object], parsed)