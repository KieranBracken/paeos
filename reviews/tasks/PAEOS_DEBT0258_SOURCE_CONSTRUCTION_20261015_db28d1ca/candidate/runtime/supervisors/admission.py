"""Fail-closed, task-scoped admission for headless supervisor profiles."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from paeos.model_router.types import ModelFamily

from runtime.integrations.bridge_protocol import ProtocolViolation, canonical_json
from runtime.supervisors.protocol import SupervisorTier, TransportObservation

_HASH = set("0123456789abcdef")
MAX_PROFILE_TTL_SECONDS = 30 * 24 * 60 * 60


def _hash(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or set(value) - _HASH:
        raise ProtocolViolation(f"{field} must be a lowercase SHA-256 digest")


def _timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise ProtocolViolation(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProtocolViolation(f"{field} must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ProtocolViolation(f"{field} must be timezone-aware")
    return parsed


@dataclass(frozen=True, slots=True)
class SupervisorAdmissionProfile:
    profile_id: str
    tier: SupervisorTier
    task_classes: tuple[str, ...]
    provider: str
    actual_model_id: str
    model_family: ModelFamily
    adapter_hash: str
    binary_hash: str
    prompt_hash: str
    policy_hash: str
    sandbox_profile_hash: str
    canary_set_version: str
    admitted_at: str
    expires_at: str

    def __post_init__(self) -> None:
        for field in (
            "profile_id",
            "provider",
            "actual_model_id",
            "canary_set_version",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value or "\x00" in value:
                raise ProtocolViolation(f"{field} must be a non-empty string")
        if not isinstance(self.tier, SupervisorTier):
            raise ProtocolViolation("tier must be a SupervisorTier")
        if not self.task_classes or any(
            not isinstance(item, str) or not item for item in self.task_classes
        ):
            raise ProtocolViolation("task_classes must contain non-empty strings")
        if len(set(self.task_classes)) != len(self.task_classes):
            raise ProtocolViolation("task_classes must not contain duplicates")
        if not isinstance(self.model_family, ModelFamily):
            raise ProtocolViolation("model_family must be a ModelFamily")
        for field in (
            "adapter_hash",
            "binary_hash",
            "prompt_hash",
            "policy_hash",
            "sandbox_profile_hash",
        ):
            _hash(getattr(self, field), field)
        admitted = _timestamp(self.admitted_at, "admitted_at")
        expires = _timestamp(self.expires_at, "expires_at")
        ttl = (expires - admitted).total_seconds()
        if ttl <= 0 or ttl > MAX_PROFILE_TTL_SECONDS:
            raise ProtocolViolation("profile TTL must be positive and no longer than 30 days")


@dataclass(frozen=True, slots=True)
class SupervisorAdmissionDecision:
    admitted: bool
    reason_code: str
    profile_hash: str | None


def _profile_hash(profile: SupervisorAdmissionProfile) -> str:
    payload = {
        "profile_id": profile.profile_id,
        "tier": profile.tier,
        "task_classes": profile.task_classes,
        "provider": profile.provider,
        "actual_model_id": profile.actual_model_id,
        "model_family": profile.model_family,
        "adapter_hash": profile.adapter_hash,
        "binary_hash": profile.binary_hash,
        "prompt_hash": profile.prompt_hash,
        "policy_hash": profile.policy_hash,
        "sandbox_profile_hash": profile.sandbox_profile_hash,
        "canary_set_version": profile.canary_set_version,
        "admitted_at": profile.admitted_at,
        "expires_at": profile.expires_at,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _reject(reason_code: str) -> SupervisorAdmissionDecision:
    return SupervisorAdmissionDecision(admitted=False, reason_code=reason_code, profile_hash=None)


def decide_supervisor_admission(
    profile: SupervisorAdmissionProfile,
    observation: TransportObservation,
    *,
    task_class: str,
    committed_trace: str,
    now: str,
) -> SupervisorAdmissionDecision:
    """Evaluate a profile in deterministic fail-closed order."""

    try:
        now_dt = _timestamp(now, "now")
    except ProtocolViolation:
        return _reject("INVALID_NOW")

    # Tuple and physical-lineage checks precede policy checks.  The observation is local transport
    # evidence; model-authored bytes cannot override it.
    if (
        profile.provider != observation.provider
        or profile.actual_model_id != observation.actual_model_id
    ):
        return _reject("PHYSICAL_IDENTITY_MISMATCH")
    if (
        profile.model_family is ModelFamily.UNKNOWN
        or observation.model_family is ModelFamily.UNKNOWN
    ):
        return _reject("UNKNOWN_MODEL_FAMILY")
    if profile.model_family is not observation.model_family:
        return _reject("MODEL_FAMILY_CONFLICT")

    admitted = _timestamp(profile.admitted_at, "admitted_at")
    expires = _timestamp(profile.expires_at, "expires_at")
    if now_dt < admitted or now_dt >= expires:
        return _reject("PROFILE_EXPIRED")
    if (expires - admitted).total_seconds() > MAX_PROFILE_TTL_SECONDS:
        return _reject("PROFILE_TTL_EXCEEDED")

    if profile.tier is SupervisorTier.QUARANTINED:
        return _reject("PROFILE_QUARANTINED")
    if task_class not in profile.task_classes:
        return _reject("TASK_CLASS_NOT_ADMITTED")
    if profile.tier is SupervisorTier.WORKER_ONLY:
        return _reject("WORKER_ONLY_NOT_SUPERVISOR")
    if profile.tier is SupervisorTier.DEGRADED_TRACE_A and committed_trace != "TRACE_A_COMMITTED":
        return _reject("DEGRADED_TRACE_NOT_COMMITTED")
    if profile.tier is SupervisorTier.ARCHITECT and committed_trace not in {
        "TRACE_A_COMMITTED",
        "TRACE_B_COMMITTED",
    }:
        return _reject("TRACE_NOT_COMMITTED")

    return SupervisorAdmissionDecision(
        admitted=True,
        reason_code="ADMITTED",
        profile_hash=_profile_hash(profile),
    )
