"""Strict provider-neutral envelopes for headless supervisor adapters.

Model-authored response bytes are data only.  The locally trusted transport observation is kept
outside those bytes and is cross-checked by admission before a coordinator can consume a response.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

from kernel.types import ArtifactRef, Hash
from paeos.model_router.types import ModelFamily

from runtime.integrations.bridge_protocol import Disposition, ProtocolViolation, canonical_json

SCHEMA_VERSION = "paeos-supervisor-v1"
MAX_ENVELOPE_BYTES = 1_048_576
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")
_VALUE = re.compile(r"^[A-Za-z0-9_./:@+-]{1,200}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


class SupervisorTier(StrEnum):
    ARCHITECT = "ARCHITECT"
    DEGRADED_TRACE_A = "DEGRADED_TRACE_A"
    WORKER_ONLY = "WORKER_ONLY"
    QUARANTINED = "QUARANTINED"


def _text(value: object, field: str, *, allow_slash: bool = False) -> str:
    pattern = _VALUE if allow_slash else _IDENTIFIER
    if not isinstance(value, str) or not value or pattern.fullmatch(value) is None:
        raise ProtocolViolation(f"invalid supervisor protocol field: {field}")
    return value


def _hash(value: object, field: str) -> Hash:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ProtocolViolation(f"{field} must be a lowercase SHA-256 digest")
    return value


def _mapping(value: Mapping[str, int]) -> Mapping[str, int]:
    copied = dict(value)
    if any(
        not isinstance(key, str) or not isinstance(item, int) or item < 0
        for key, item in copied.items()
    ):
        raise ProtocolViolation("usage must map string names to non-negative integers")
    return MappingProxyType(copied)


@dataclass(frozen=True, slots=True)
class SupervisorRequest:
    request_id: str
    transaction_key: str
    nonce: str
    checkpoint_hash: Hash
    policy_hash: Hash
    task_class: str
    prompt_hash: Hash
    context_manifest_hash: Hash
    allowed_dispositions: tuple[Disposition, ...]

    def __post_init__(self) -> None:
        for field in ("request_id", "transaction_key", "nonce", "task_class"):
            _text(getattr(self, field), field)
        for field in ("checkpoint_hash", "policy_hash", "prompt_hash", "context_manifest_hash"):
            _hash(getattr(self, field), field)
        if not self.allowed_dispositions or any(
            not isinstance(item, Disposition) for item in self.allowed_dispositions
        ):
            raise ProtocolViolation("allowed_dispositions must contain Disposition values")
        if len(set(self.allowed_dispositions)) != len(self.allowed_dispositions):
            raise ProtocolViolation("allowed_dispositions must not contain duplicates")


@dataclass(frozen=True, slots=True)
class TransportObservation:
    provider: str
    actual_model_id: str
    model_family: ModelFamily
    adapter_id: str
    adapter_version: str
    provider_request_id: str
    observed_at: str
    usage: Mapping[str, int]

    def __post_init__(self) -> None:
        for field in (
            "provider",
            "adapter_id",
            "adapter_version",
            "provider_request_id",
            "observed_at",
        ):
            _text(getattr(self, field), field, allow_slash=field == "observed_at")
        _text(self.actual_model_id, "actual_model_id", allow_slash=True)
        _text(self.actual_model_id, "actual_model_id", allow_slash=True)
        if not isinstance(self.model_family, ModelFamily):
            raise ProtocolViolation("model_family must be a ModelFamily")
        object.__setattr__(self, "usage", _mapping(self.usage))


@dataclass(frozen=True, slots=True)
class SupervisorResponse:
    request_id: str
    transaction_key: str
    nonce: str
    checkpoint_hash: Hash
    disposition: Disposition
    artifact_refs: tuple[ArtifactRef, ...]
    rationale_ref: Hash

    def __post_init__(self) -> None:
        for field in ("request_id", "transaction_key", "nonce"):
            _text(getattr(self, field), field)
        _hash(self.checkpoint_hash, "checkpoint_hash")
        _hash(self.rationale_ref, "rationale_ref")
        if not isinstance(self.disposition, Disposition):
            raise ProtocolViolation("disposition must be a Disposition")
        if any(not isinstance(ref, ArtifactRef) for ref in self.artifact_refs):
            raise ProtocolViolation("artifact_refs must contain ArtifactRef values")
        for ref in self.artifact_refs:
            _hash(ref.hash, "artifact_ref.hash")
            _text(ref.type, "artifact_ref.type", allow_slash=True)


@dataclass(frozen=True, slots=True)
class AdapterResult:
    response_bytes: bytes
    observation: TransportObservation

    def __post_init__(self) -> None:
        if not isinstance(self.response_bytes, bytes) or not self.response_bytes:
            raise ProtocolViolation("response_bytes must be non-empty bytes")
        if len(self.response_bytes) > MAX_ENVELOPE_BYTES:
            raise ProtocolViolation("response exceeds supervisor envelope size limit")
        if not isinstance(self.observation, TransportObservation):
            raise ProtocolViolation("observation must be a TransportObservation")


class SupervisorAdapter(Protocol):
    def invoke(self, request: SupervisorRequest, context: bytes) -> AdapterResult: ...


def _payload(value: object, *, kind: str) -> bytes:
    raw = (canonical_json(value) + "\n").encode("utf-8")
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise ProtocolViolation(f"{kind} exceeds supervisor envelope size limit")
    return raw


def encode_request(request: SupervisorRequest) -> bytes:
    return _payload(
        {
            "schema_version": SCHEMA_VERSION,
            "request_id": request.request_id,
            "transaction_key": request.transaction_key,
            "nonce": request.nonce,
            "checkpoint_hash": request.checkpoint_hash,
            "policy_hash": request.policy_hash,
            "task_class": request.task_class,
            "prompt_hash": request.prompt_hash,
            "context_manifest_hash": request.context_manifest_hash,
            "allowed_dispositions": list(request.allowed_dispositions),
        },
        kind="request",
    )


def encode_response(response: SupervisorResponse) -> bytes:
    return _payload(
        {
            "schema_version": SCHEMA_VERSION,
            "request_id": response.request_id,
            "transaction_key": response.transaction_key,
            "nonce": response.nonce,
            "checkpoint_hash": response.checkpoint_hash,
            "disposition": response.disposition,
            "artifact_refs": [
                {"hash": ref.hash, "type": ref.type} for ref in response.artifact_refs
            ],
            "rationale_ref": response.rationale_ref,
        },
        kind="response",
    )


def _decode(raw: bytes, *, kind: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ENVELOPE_BYTES:
        raise ProtocolViolation(f"{kind} bytes are empty or oversized")
    try:
        text = raw.decode("utf-8")
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolViolation(f"{kind} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict) or set(value) != fields:
        raise ProtocolViolation(f"{kind} contains unknown or missing fields")
    if canonical_json(value).encode("utf-8") + b"\n" != raw:
        raise ProtocolViolation(f"{kind} is not canonical JSON")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ProtocolViolation(f"unsupported {kind} schema_version")
    return value


def decode_request(raw: bytes) -> SupervisorRequest:
    value = _decode(
        raw,
        kind="request",
        fields={
            "schema_version",
            "request_id",
            "transaction_key",
            "nonce",
            "checkpoint_hash",
            "policy_hash",
            "task_class",
            "prompt_hash",
            "context_manifest_hash",
            "allowed_dispositions",
        },
    )
    allowed = value["allowed_dispositions"]
    if not isinstance(allowed, list):
        raise ProtocolViolation("allowed_dispositions must be a JSON array")
    try:
        dispositions = tuple(Disposition(item) for item in allowed)
    except (TypeError, ValueError) as exc:
        raise ProtocolViolation("allowed_dispositions contains an unknown value") from exc
    return SupervisorRequest(
        request_id=value["request_id"],
        transaction_key=value["transaction_key"],
        nonce=value["nonce"],
        checkpoint_hash=value["checkpoint_hash"],
        policy_hash=value["policy_hash"],
        task_class=value["task_class"],
        prompt_hash=value["prompt_hash"],
        context_manifest_hash=value["context_manifest_hash"],
        allowed_dispositions=dispositions,
    )


def decode_response(raw: bytes) -> SupervisorResponse:
    value = _decode(
        raw,
        kind="response",
        fields={
            "schema_version",
            "request_id",
            "transaction_key",
            "nonce",
            "checkpoint_hash",
            "disposition",
            "artifact_refs",
            "rationale_ref",
        },
    )
    try:
        disposition = Disposition(value["disposition"])
    except (TypeError, ValueError) as exc:
        raise ProtocolViolation("response disposition is invalid") from exc
    refs = value["artifact_refs"]
    if not isinstance(refs, list):
        raise ProtocolViolation("artifact_refs must be a JSON array")
    try:
        artifact_refs = tuple(ArtifactRef(hash=item["hash"], type=item["type"]) for item in refs)
    except (KeyError, TypeError) as exc:
        raise ProtocolViolation("artifact_refs contains an invalid entry") from exc
    return SupervisorResponse(
        request_id=value["request_id"],
        transaction_key=value["transaction_key"],
        nonce=value["nonce"],
        checkpoint_hash=value["checkpoint_hash"],
        disposition=disposition,
        artifact_refs=artifact_refs,
        rationale_ref=value["rationale_ref"],
    )


def validate_response(request: SupervisorRequest, response: SupervisorResponse) -> None:
    """Enforce correlation and disposition policy before coordinator consumption."""

    if (
        request.request_id != response.request_id
        or request.transaction_key != response.transaction_key
        or request.nonce != response.nonce
        or request.checkpoint_hash != response.checkpoint_hash
    ):
        raise ProtocolViolation("supervisor response correlation does not match request")
    if response.disposition not in request.allowed_dispositions:
        raise ProtocolViolation("response disposition is outside the request allow-list")
