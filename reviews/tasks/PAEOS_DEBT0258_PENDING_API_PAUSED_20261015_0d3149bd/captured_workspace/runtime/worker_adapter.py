"""Provider-neutral narrow waist for disposable worker-admission transports."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from paeos.model_router.types import NormalizedErrorType

from runtime.worker_admission import (
    AdmissionResult,
    AdmissionVerdict,
    ProbeContract,
    RawWorkerRun,
)

ADAPTER_PROTOCOL_VERSION = "paeos-worker-admission/1"


class SideEffectCertainty(StrEnum):
    NOT_DISPATCHED = "NOT_DISPATCHED"
    PROVIDER_ACCEPTED = "PROVIDER_ACCEPTED"
    TOOL_EFFECT_POSSIBLE = "TOOL_EFFECT_POSSIBLE"
    UNKNOWN = "UNKNOWN"


class AdapterFailureKind(StrEnum):
    ADAPTER_VERSION_UNQUALIFIED = "ADAPTER_VERSION_UNQUALIFIED"
    CAPABILITY_DRIFT = "CAPABILITY_DRIFT"
    PROFILE_LOCK_FAILED = "PROFILE_LOCK_FAILED"
    SESSION_AMBIGUOUS = "SESSION_AMBIGUOUS"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    UNKNOWN_MODEL_FAMILY = "UNKNOWN_MODEL_FAMILY"
    TOOL_DENIED = "TOOL_DENIED"
    COMMAND_EXPANSION = "COMMAND_EXPANSION"
    TIMEOUT_SAFE = "TIMEOUT_SAFE"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    VERIFICATION_NONDISCRIMINATIVE = "VERIFICATION_NONDISCRIMINATIVE"
    TRANSPORT_FAILED = "TRANSPORT_FAILED"


_FAILURE_PRECEDENCE = (
    AdapterFailureKind.EVIDENCE_INCOMPLETE,
    AdapterFailureKind.TRANSPORT_FAILED,
    AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED,
    AdapterFailureKind.PROFILE_LOCK_FAILED,
    AdapterFailureKind.CAPABILITY_DRIFT,
    AdapterFailureKind.SESSION_AMBIGUOUS,
    AdapterFailureKind.MODEL_MISMATCH,
    AdapterFailureKind.UNKNOWN_MODEL_FAMILY,
    AdapterFailureKind.SIDE_EFFECT_UNCERTAIN,
    AdapterFailureKind.TIMEOUT_SAFE,
    AdapterFailureKind.TOOL_DENIED,
    AdapterFailureKind.COMMAND_EXPANSION,
    AdapterFailureKind.VERIFICATION_NONDISCRIMINATIVE,
)
_PRECEDENCE_INDEX = {value: index for index, value in enumerate(_FAILURE_PRECEDENCE)}


def _is_hex64(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        asdict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class AdapterObservation:
    protocol_version: str
    invocation_id: str
    session_id: str
    provider_id: str
    model_id: str
    backend_mode: str
    declared_model_turn_count: int
    provider_attempts_by_turn: tuple[int, ...]
    side_effect_certainty: SideEffectCertainty
    capability_snapshot_sha256: str
    transcript_sha256: str

    @property
    def observation_sha256(self) -> str:
        return _canonical_hash(self)


@dataclass(frozen=True, slots=True)
class AdapterFailureReceipt:
    protocol_version: str
    invocation_id: str
    contract_id: str
    adapter_failure: AdapterFailureKind | None
    normalized_error: NormalizedErrorType | None
    additional_findings: tuple[AdapterFailureKind, ...]
    side_effect_certainty: SideEffectCertainty
    raw_stdout_sha256: str
    raw_stderr_sha256: str
    observation_sha256: str

    @property
    def receipt_sha256(self) -> str:
        return _canonical_hash(self)


@runtime_checkable
class AdmissionProbeTransport(Protocol):
    def run_probe(self, contract: ProbeContract) -> RawWorkerRun | AdapterFailureReceipt:
        """Run exactly one disposable probe without retry or provider fallback."""
        raise NotImplementedError


def validate_adapter_observation(
    observation: AdapterObservation,
) -> tuple[AdapterFailureKind, ...]:
    """Return stable fail-closed findings for one transport observation."""

    findings: set[AdapterFailureKind] = set()
    if observation.protocol_version != ADAPTER_PROTOCOL_VERSION:
        findings.add(AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED)
    if observation.backend_mode != "local":
        findings.add(AdapterFailureKind.CAPABILITY_DRIFT)
    if not observation.invocation_id or not observation.provider_id:
        findings.add(AdapterFailureKind.SESSION_AMBIGUOUS)
    if not observation.session_id:
        findings.add(AdapterFailureKind.SESSION_AMBIGUOUS)
    if not observation.model_id:
        findings.add(AdapterFailureKind.MODEL_MISMATCH)
    if (
        observation.declared_model_turn_count <= 0
        or len(observation.provider_attempts_by_turn) != observation.declared_model_turn_count
        or any(count != 1 for count in observation.provider_attempts_by_turn)
    ):
        findings.add(AdapterFailureKind.TRANSPORT_FAILED)
    if not _is_hex64(observation.capability_snapshot_sha256) or not _is_hex64(
        observation.transcript_sha256
    ):
        findings.add(AdapterFailureKind.TRANSPORT_FAILED)
    if observation.side_effect_certainty is SideEffectCertainty.UNKNOWN:
        findings.add(AdapterFailureKind.SIDE_EFFECT_UNCERTAIN)
    return tuple(sorted(findings, key=lambda item: _PRECEDENCE_INDEX[item]))


def select_primary_failure(
    adapter_findings: tuple[AdapterFailureKind, ...],
    normalized_error: NormalizedErrorType | None,
) -> str:
    """Select one deterministic primary reason without discarding other findings."""

    if adapter_findings:
        return min(adapter_findings, key=lambda item: _PRECEDENCE_INDEX[item]).value
    if normalized_error is not None:
        return normalized_error.value
    return AdapterFailureKind.TRANSPORT_FAILED.value


def assess_failure_receipt(receipt: AdapterFailureReceipt) -> AdmissionResult:
    """Convert a typed adapter failure into the existing admission result contract."""

    findings = set(receipt.additional_findings)
    if receipt.adapter_failure is not None:
        findings.add(receipt.adapter_failure)
    if receipt.side_effect_certainty is SideEffectCertainty.UNKNOWN:
        findings.add(AdapterFailureKind.SIDE_EFFECT_UNCERTAIN)
    if receipt.protocol_version != ADAPTER_PROTOCOL_VERSION:
        findings.add(AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED)
    if not all(
        _is_hex64(value)
        for value in (
            receipt.raw_stdout_sha256,
            receipt.raw_stderr_sha256,
            receipt.observation_sha256,
        )
    ):
        findings.add(AdapterFailureKind.TRANSPORT_FAILED)

    ordered = tuple(sorted(findings, key=lambda item: _PRECEDENCE_INDEX[item]))
    primary = select_primary_failure(ordered, receipt.normalized_error)
    reasons = [primary]
    reasons.extend(item.value for item in ordered if item.value != primary)
    if receipt.normalized_error is not None and receipt.normalized_error.value != primary:
        reasons.append(receipt.normalized_error.value)
    return AdmissionResult(verdict=AdmissionVerdict.REJECTED, reasons=tuple(reasons))
