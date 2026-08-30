"""Candidate-bound physical receipts for heterogeneous Layer 14 audits.

The router remains responsible for policy, provider selection, retries, and fallback.  This
module only captures and validates the completed transport result; it never dispatches a second
request or stores prompt/response content.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from paeos.model_router.a08_enforcer import (
    A08EnforcementResult,
    A08Enforcer,
    derive_family_from_actual_model,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.types import (
    DataClass,
    LogicalModel,
    ModelFamily,
    ProviderId,
    RouterResponse,
    TaskClass,
    TaskRequest,
)

AUDITOR_RECEIPT_SCHEMA = "paeos.auditor-physical-receipt/1"
_MAX_RECEIPT_BYTES = 1_048_576
_L14_STATUS_RE = re.compile(
    r"^\s*`?L14_STATUS`?\s*:\s*(?:\*\*)?"
    r"(PASS|REMAND_WITH_AMENDMENTS|BLOCKED_UNQUALIFIABLE)"
    r"(?:\*\*)?\s*$",
    re.MULTILINE,
)
_L14_INVARIANT_RE = re.compile(r"^\s*INVARIANT:\s*\S", re.MULTILINE)
_L14_REPRODUCTION_RE = re.compile(r"^\s*REPRODUCTION:\s*\S", re.MULTILINE)


class AuditorReceiptError(ValueError):
    """Raised when an auditor receipt cannot be proven and must fail closed."""


class _RouterLike(Protocol):
    catalog: ModelCatalog

    def route(self, request: TaskRequest) -> RouterResponse:
        ...


def _json_default(value: object) -> object:
    if isinstance(value, (DataClass, LogicalModel, ModelFamily, ProviderId, TaskClass)):
        return value.value
    raise TypeError(f"unsupported value for canonical JSON: {type(value).__name__}")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_json_default,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_hex(value: object, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(
        character in "0123456789abcdef" for character in value
    )


def _request_payload(request: TaskRequest) -> dict[str, object]:
    """Return the content-free identity fields used by the transport request fingerprint."""

    return {
        "messages": request.messages,
        "task_class": request.task_class.value,
        "data_class": request.data_class.value,
        "logical_model": request.logical_model.value if request.logical_model else None,
        "explicit_model": request.explicit_model,
        "builder_family": request.builder_family.value if request.builder_family else None,
        "require_tools": request.require_tools,
        "require_json": request.require_json,
        "tools": request.tools,
        "tool_choice": request.tool_choice,
        "stream": request.stream,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
    }


def request_fingerprint(request: TaskRequest) -> str:
    """Hash the exact audit request without persisting its content."""

    return _sha256(_canonical_bytes(_request_payload(request)))


def _tool_calls_fingerprint(tool_calls: object) -> str | None:
    if tool_calls is None:
        return None
    return _sha256(_canonical_bytes(tool_calls))


def _response_payload(response: RouterResponse) -> dict[str, object]:
    """Return only non-secret response identity and content digests."""

    return {
        "content_sha256": _sha256(response.content.encode("utf-8")),
        "model_id": response.model_id,
        "provider_id": response.provider_id.value,
        "family": response.family.value,
        "actual_model": response.actual_model,
        "actual_family": response.actual_family.value if response.actual_family else None,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "total_tokens": response.total_tokens,
        "attempts": response.attempts,
        "fallback_chain": list(response.fallback_chain),
        "tool_calls_sha256": _tool_calls_fingerprint(response.tool_calls),
        "finish_reason": response.finish_reason,
    }


def response_fingerprint(response: RouterResponse) -> str:
    """Hash the machine-captured response identity without storing provider content."""

    return _sha256(_canonical_bytes(_response_payload(response)))


@dataclass(frozen=True, slots=True)
class AuditorReceiptContract:
    """The immutable candidate and builder context an L14 receipt must bind."""

    audit_id: str
    candidate_sha256: str
    evidence_bundle_sha256: str
    review_scope_sha256: str
    builder_provider: str
    builder_model_id: str
    builder_family: ModelFamily


@dataclass(frozen=True, slots=True)
class PhysicalAuditorReceipt:
    """A content-free, machine-captured physical auditor identity receipt."""

    schema: str
    audit_id: str
    invocation_id: str
    session_id: str
    candidate_sha256: str
    evidence_bundle_sha256: str
    review_scope_sha256: str
    builder_provider: str
    builder_model_id: str
    builder_family: ModelFamily
    configured_provider_id: ProviderId
    configured_model_id: str
    actual_provider_id: ProviderId
    actual_model_id: str
    actual_family: ModelFamily
    transport_id: str
    provider_attempt_count: int
    fallback_chain: tuple[str, ...]
    transport_request_sha256: str
    transport_response_sha256: str
    transcript_sha256: str
    captured_at_unix: float
    a08_verdict: str

    @property
    def receipt_sha256(self) -> str:
        return _sha256(_canonical_bytes(self.to_dict(include_hash=False)))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "a08_verdict": self.a08_verdict,
            "actual_family": self.actual_family.value,
            "actual_model_id": self.actual_model_id,
            "actual_provider_id": self.actual_provider_id.value,
            "audit_id": self.audit_id,
            "builder_family": self.builder_family.value,
            "builder_model_id": self.builder_model_id,
            "builder_provider": self.builder_provider,
            "candidate_sha256": self.candidate_sha256,
            "captured_at_unix": self.captured_at_unix,
            "configured_model_id": self.configured_model_id,
            "configured_provider_id": self.configured_provider_id.value,
            "evidence_bundle_sha256": self.evidence_bundle_sha256,
            "fallback_chain": list(self.fallback_chain),
            "invocation_id": self.invocation_id,
            "provider_attempt_count": self.provider_attempt_count,
            "receipt_schema": self.schema,
            "review_scope_sha256": self.review_scope_sha256,
            "session_id": self.session_id,
            "transport_id": self.transport_id,
            "transport_request_sha256": self.transport_request_sha256,
            "transport_response_sha256": self.transport_response_sha256,
            "transcript_sha256": self.transcript_sha256,
        }
        if include_hash:
            payload["receipt_sha256"] = self.receipt_sha256
        return payload


@dataclass(frozen=True, slots=True)
class AuditorCaptureResult:
    """The receipt plus the one response body that produced the audit findings."""

    receipt: PhysicalAuditorReceipt
    response_content: str


def _validate_contract(contract: AuditorReceiptContract) -> None:
    if not contract.audit_id or any(character.isspace() for character in contract.audit_id):
        raise AuditorReceiptError("audit identity missing or contains whitespace")
    if not _is_hex(contract.candidate_sha256, 40):
        raise AuditorReceiptError("candidate commit SHA is invalid")
    for field_name, value in (
        ("evidence bundle", contract.evidence_bundle_sha256),
        ("review scope", contract.review_scope_sha256),
    ):
        if not _is_hex(value, 64):
            raise AuditorReceiptError(f"{field_name} SHA-256 is invalid")
    if not contract.builder_provider or not contract.builder_model_id:
        raise AuditorReceiptError("builder identity is incomplete")
    if contract.builder_family is ModelFamily.UNKNOWN:
        raise AuditorReceiptError("builder family is unknown")


def _require_hex(value: object, label: str) -> None:
    if not _is_hex(value, 64):
        raise AuditorReceiptError(f"{label} SHA-256 is invalid")


def validate_auditor_receipt(
    receipt: PhysicalAuditorReceipt,
    contract: AuditorReceiptContract,
    catalog: ModelCatalog,
) -> A08EnforcementResult:
    """Validate every binding and return the physical A-08 result; fail closed on any mismatch."""

    _validate_contract(contract)
    if receipt.schema != AUDITOR_RECEIPT_SCHEMA:
        raise AuditorReceiptError("receipt schema is not qualified")
    if receipt.audit_id != contract.audit_id:
        raise AuditorReceiptError("audit identity mismatch")
    if receipt.candidate_sha256 != contract.candidate_sha256:
        raise AuditorReceiptError("candidate identity mismatch")
    if receipt.evidence_bundle_sha256 != contract.evidence_bundle_sha256:
        raise AuditorReceiptError("evidence bundle identity mismatch")
    if receipt.review_scope_sha256 != contract.review_scope_sha256:
        raise AuditorReceiptError("review scope identity mismatch")
    if (
        receipt.builder_provider != contract.builder_provider
        or receipt.builder_model_id != contract.builder_model_id
        or receipt.builder_family is not contract.builder_family
    ):
        raise AuditorReceiptError("builder identity mismatch")
    if not receipt.invocation_id or not receipt.session_id or not receipt.transport_id:
        raise AuditorReceiptError("physical invocation identity is incomplete")
    if receipt.actual_provider_id is not receipt.configured_provider_id:
        raise AuditorReceiptError("actual provider differs from configured provider")
    if not receipt.configured_model_id or not receipt.actual_model_id:
        raise AuditorReceiptError("auditor model identity is incomplete")
    if receipt.actual_family is ModelFamily.UNKNOWN:
        raise AuditorReceiptError("unknown auditor family")
    derived_family = derive_family_from_actual_model(receipt.actual_model_id, catalog)
    if derived_family is not receipt.actual_family:
        raise AuditorReceiptError(
            "auditor family mismatch: "
            f"derived {derived_family.value} != receipt {receipt.actual_family.value}"
        )
    if receipt.provider_attempt_count != 1:
        raise AuditorReceiptError("receipt requires exactly one provider attempt")
    if len(receipt.fallback_chain) != 1:
        raise AuditorReceiptError("receipt cannot contain fallback candidates")
    expected_route = f"{receipt.configured_provider_id.value}:{receipt.configured_model_id}"
    if receipt.fallback_chain[0] != expected_route:
        raise AuditorReceiptError("fallback telemetry does not identify configured route")
    for field_name, value in (
        ("review scope", receipt.review_scope_sha256),
        ("transport request", receipt.transport_request_sha256),
        ("transport response", receipt.transport_response_sha256),
        ("transcript", receipt.transcript_sha256),
    ):
        _require_hex(value, field_name)
    if receipt.a08_verdict != "PASS":
        raise AuditorReceiptError(f"receipt A-08 disposition is {receipt.a08_verdict}")
    expected_hash = receipt.receipt_sha256
    if not _is_hex(expected_hash, 64):
        raise AuditorReceiptError("receipt hash could not be computed")

    result = A08Enforcer(catalog).enforce(
        builder_provider=receipt.builder_provider,
        builder_model_id=receipt.builder_model_id,
        builder_family=receipt.builder_family,
        auditor_provider=receipt.actual_provider_id.value,
        auditor_model_id=receipt.actual_model_id,
        auditor_family=receipt.actual_family,
    )
    if not result.passed:
        raise AuditorReceiptError(f"auditor A-08 disposition is {result.verdict.value}")
    return result


def capture_auditor_interaction(
    router: _RouterLike,
    contract: AuditorReceiptContract,
    request: TaskRequest,
) -> AuditorCaptureResult:
    """Capture one completed router response and retain its report for separate evidence storage."""

    _validate_contract(contract)
    if request.task_class is not TaskClass.AUDIT:
        raise AuditorReceiptError("auditor receipt requires AUDIT task class")
    if request.logical_model is not LogicalModel.PAEOS_AUDIT:
        raise AuditorReceiptError("auditor receipt requires paeos-audit logical model")
    if request.builder_family is not contract.builder_family:
        raise AuditorReceiptError("request builder family does not match receipt contract")
    request_bytes = _canonical_bytes(_request_payload(request))
    request_text = request_bytes.decode("utf-8")
    if (
        contract.candidate_sha256 not in request_text
        or contract.evidence_bundle_sha256 not in request_text
    ):
        raise AuditorReceiptError("audit request does not bind candidate and evidence")
    request_hash = request_fingerprint(request)
    if request_hash != contract.review_scope_sha256:
        raise AuditorReceiptError("request fingerprint does not match review scope")

    response = router.route(request)
    if not isinstance(response, RouterResponse):
        raise AuditorReceiptError("router returned no physical response")
    if response.transport_request_sha256 != request_hash:
        raise AuditorReceiptError("transport request fingerprint mismatch")
    if response.transport_response_sha256 != response_fingerprint(response):
        raise AuditorReceiptError("transport response fingerprint mismatch")
    if not response.content.strip():
        raise AuditorReceiptError("audit response is empty")
    if response.actual_model is None or not response.actual_model:
        raise AuditorReceiptError("physical auditor model is missing")
    derived_family = derive_family_from_actual_model(response.actual_model, router.catalog)
    if derived_family is ModelFamily.UNKNOWN:
        raise AuditorReceiptError("unknown auditor family")
    if response.actual_family is not None and response.actual_family is not derived_family:
        raise AuditorReceiptError(
            "transport auditor family does not match the returned physical model"
        )
    actual_family = derived_family
    if response.attempts != 1 or len(response.fallback_chain) != 1:
        raise AuditorReceiptError("receipt requires exactly one provider attempt and no fallback")

    response_hash = response.transport_response_sha256
    assert response_hash is not None
    transcript_hash = _sha256(
        _canonical_bytes({"request": request_hash, "response": response_hash})
    )
    a08_result = A08Enforcer(router.catalog).enforce(
        builder_provider=contract.builder_provider,
        builder_model_id=contract.builder_model_id,
        builder_family=contract.builder_family,
        auditor_provider=response.provider_id.value,
        auditor_model_id=response.actual_model,
        auditor_family=actual_family,
    )
    if not a08_result.passed:
        raise AuditorReceiptError(f"auditor A-08 disposition is {a08_result.verdict.value}")

    receipt = PhysicalAuditorReceipt(
        schema=AUDITOR_RECEIPT_SCHEMA,
        audit_id=contract.audit_id,
        invocation_id=f"{contract.audit_id}:{uuid.uuid4().hex}",
        session_id=f"{contract.audit_id}-session-{uuid.uuid4().hex}",
        candidate_sha256=contract.candidate_sha256,
        evidence_bundle_sha256=contract.evidence_bundle_sha256,
        review_scope_sha256=request_hash,
        builder_provider=contract.builder_provider,
        builder_model_id=contract.builder_model_id,
        builder_family=contract.builder_family,
        configured_provider_id=response.provider_id,
        configured_model_id=response.model_id,
        actual_provider_id=response.provider_id,
        actual_model_id=response.actual_model,
        actual_family=actual_family,
        transport_id=(
            f"paeos-model-router:{response.provider_id.value}:{response.model_id}:{response_hash[:16]}"
        ),
        provider_attempt_count=response.attempts,
        fallback_chain=tuple(response.fallback_chain),
        transport_request_sha256=request_hash,
        transport_response_sha256=response_hash,
        transcript_sha256=transcript_hash,
        captured_at_unix=time.time(),
        a08_verdict=a08_result.verdict.value,
    )
    validate_auditor_receipt(receipt, contract, router.catalog)
    return AuditorCaptureResult(receipt=receipt, response_content=response.content)


def capture_auditor_receipt(
    router: _RouterLike,
    contract: AuditorReceiptContract,
    request: TaskRequest,
) -> PhysicalAuditorReceipt:
    """Capture one completed router response and return only its physical receipt."""

    return capture_auditor_interaction(router, contract, request).receipt


def validate_auditor_report(content: str, contract: AuditorReceiptContract) -> None:
    """Reject an unbound or vacuous L14 report before it becomes evidence."""

    _validate_contract(contract)
    if not content.strip():
        raise AuditorReceiptError("audit report is empty")
    if contract.candidate_sha256 not in content:
        raise AuditorReceiptError("audit report does not bind candidate")
    if contract.evidence_bundle_sha256 not in content:
        raise AuditorReceiptError("audit report does not bind evidence bundle")
    statuses = _L14_STATUS_RE.findall(content)
    if len(statuses) != 1:
        raise AuditorReceiptError("audit report must contain exactly one L14_STATUS")
    if statuses[0] == "REMAND_WITH_AMENDMENTS":
        if _L14_INVARIANT_RE.search(content) is None:
            raise AuditorReceiptError("remand report must name an INVARIANT")
        if _L14_REPRODUCTION_RE.search(content) is None:
            raise AuditorReceiptError("remand report must include REPRODUCTION")


def persist_auditor_report(content: str, path: Path) -> Path:
    """Persist the model's audit findings separately from the content-free physical receipt."""

    if not path.is_absolute():
        raise AuditorReceiptError("audit report path must be absolute")
    if not content.strip():
        raise AuditorReceiptError("audit report is empty")
    if path.exists() and path.is_symlink():
        raise AuditorReceiptError("audit report path cannot be a symlink")
    payload = content.encode("utf-8")
    if len(payload) > 4 * _MAX_RECEIPT_BYTES:
        raise AuditorReceiptError("audit report exceeds size limit")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        written = 0
        while written < len(payload):
            count = os.write(descriptor, payload[written:])
            if count <= 0:
                raise AuditorReceiptError("audit report write made no progress")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return path


def persist_auditor_receipt(receipt: PhysicalAuditorReceipt, path: Path) -> Path:
    """Persist one canonical receipt without overwriting an existing artifact."""

    if not path.is_absolute():
        raise AuditorReceiptError("receipt path must be absolute")
    if path.exists() and path.is_symlink():
        raise AuditorReceiptError("receipt path cannot be a symlink")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = _canonical_bytes(receipt.to_dict()) + b"\n"
    if len(payload) > _MAX_RECEIPT_BYTES:
        raise AuditorReceiptError("receipt exceeds size limit")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        written = 0
        while written < len(payload):
            count = os.write(descriptor, payload[written:])
            if count <= 0:
                raise AuditorReceiptError("receipt write made no progress")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return path


def _enum_value(payload: dict[str, Any], key: str, enum_type: type[Any]) -> Any:
    value = payload.get(key)
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise AuditorReceiptError(f"receipt field {key} is invalid") from error


def _string_value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise AuditorReceiptError(f"receipt field {key} is invalid")
    return value


def load_auditor_receipt(path: Path) -> PhysicalAuditorReceipt:
    """Load and hash-verify one persisted receipt without accepting schema drift."""

    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise AuditorReceiptError("receipt path is not a regular absolute file")
    if path.stat().st_size > _MAX_RECEIPT_BYTES:
        raise AuditorReceiptError("receipt exceeds size limit")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditorReceiptError("receipt JSON is malformed") from error
    if not isinstance(payload, dict):
        raise AuditorReceiptError("receipt JSON must be an object")
    required = {
        "a08_verdict",
        "actual_family",
        "actual_model_id",
        "actual_provider_id",
        "audit_id",
        "builder_family",
        "builder_model_id",
        "builder_provider",
        "candidate_sha256",
        "captured_at_unix",
        "configured_model_id",
        "configured_provider_id",
        "evidence_bundle_sha256",
        "fallback_chain",
        "invocation_id",
        "provider_attempt_count",
        "receipt_schema",
        "receipt_sha256",
        "review_scope_sha256",
        "session_id",
        "transport_id",
        "transport_request_sha256",
        "transport_response_sha256",
        "transcript_sha256",
    }
    if set(payload) != required:
        raise AuditorReceiptError("receipt schema keys are not exact")
    fallback = payload.get("fallback_chain")
    if not isinstance(fallback, list) or not all(isinstance(item, str) for item in fallback):
        raise AuditorReceiptError("receipt fallback chain is malformed")
    attempt_count = payload.get("provider_attempt_count")
    if isinstance(attempt_count, bool) or not isinstance(attempt_count, int):
        raise AuditorReceiptError("receipt provider attempt count is invalid")
    captured_at = payload.get("captured_at_unix")
    if isinstance(captured_at, bool) or not isinstance(captured_at, (int, float)):
        raise AuditorReceiptError("receipt capture timestamp is invalid")
    try:
        receipt = PhysicalAuditorReceipt(
            schema=_string_value(payload, "receipt_schema"),
            audit_id=_string_value(payload, "audit_id"),
            invocation_id=_string_value(payload, "invocation_id"),
            session_id=_string_value(payload, "session_id"),
            candidate_sha256=_string_value(payload, "candidate_sha256"),
            evidence_bundle_sha256=_string_value(payload, "evidence_bundle_sha256"),
            review_scope_sha256=_string_value(payload, "review_scope_sha256"),
            builder_provider=_string_value(payload, "builder_provider"),
            builder_model_id=_string_value(payload, "builder_model_id"),
            builder_family=_enum_value(payload, "builder_family", ModelFamily),
            configured_provider_id=_enum_value(payload, "configured_provider_id", ProviderId),
            configured_model_id=_string_value(payload, "configured_model_id"),
            actual_provider_id=_enum_value(payload, "actual_provider_id", ProviderId),
            actual_model_id=_string_value(payload, "actual_model_id"),
            actual_family=_enum_value(payload, "actual_family", ModelFamily),
            transport_id=_string_value(payload, "transport_id"),
            provider_attempt_count=attempt_count,
            fallback_chain=tuple(fallback),
            transport_request_sha256=_string_value(payload, "transport_request_sha256"),
            transport_response_sha256=_string_value(payload, "transport_response_sha256"),
            transcript_sha256=_string_value(payload, "transcript_sha256"),
            captured_at_unix=float(captured_at),
            a08_verdict=_string_value(payload, "a08_verdict"),
        )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise AuditorReceiptError("receipt field types are invalid") from error
    supplied_hash = payload["receipt_sha256"]
    if not isinstance(supplied_hash, str) or supplied_hash != receipt.receipt_sha256:
        raise AuditorReceiptError("receipt hash mismatch")
    return receipt
