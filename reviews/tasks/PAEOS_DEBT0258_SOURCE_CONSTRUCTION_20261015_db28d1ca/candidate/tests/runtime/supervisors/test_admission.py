"""Admission matrix for task-scoped headless supervisors."""

import hashlib
from dataclasses import replace

import pytest
from paeos.model_router.types import ModelFamily
from runtime.supervisors.admission import (
    SupervisorAdmissionProfile,
    decide_supervisor_admission,
)
from runtime.supervisors.protocol import ProtocolViolation, SupervisorTier, TransportObservation


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _profile(tier: SupervisorTier = SupervisorTier.ARCHITECT) -> SupervisorAdmissionProfile:
    return SupervisorAdmissionProfile(
        profile_id="profile-1",
        tier=tier,
        task_classes=("ARCHITECTURE", "CODE_REVIEW"),
        provider="future-provider",
        actual_model_id="future/model-v1",
        model_family=ModelFamily.GLM,
        adapter_hash=_hash("adapter"),
        binary_hash=_hash("binary"),
        prompt_hash=_hash("prompt"),
        policy_hash=_hash("policy"),
        sandbox_profile_hash=_hash("sandbox"),
        canary_set_version="canary-v1",
        admitted_at="2026-08-30T00:00:00+00:00",
        expires_at="2026-09-10T00:00:00+00:00",
    )


def _observation(family: ModelFamily = ModelFamily.GLM) -> TransportObservation:
    return TransportObservation(
        provider="future-provider",
        actual_model_id="future/model-v1",
        model_family=family,
        adapter_id="future-adapter",
        adapter_version="1.0.0",
        provider_request_id="provider-request-1",
        observed_at="2026-08-30T00:00:00+00:00",
        usage={},
    )


def _decide(profile=None, observation=None, **kwargs):
    return decide_supervisor_admission(
        profile or _profile(),
        observation or _observation(),
        task_class="ARCHITECTURE",
        committed_trace="TRACE_B_COMMITTED",
        now="2026-08-31T00:00:00+00:00",
        **kwargs,
    )


def test_architect_profile_admits_with_matching_physical_observation() -> None:
    decision = _decide()
    assert decision.admitted is True
    assert decision.reason_code == "ADMITTED"
    assert decision.profile_hash is not None and len(decision.profile_hash) == 64
    assert decision.profile_hash == _decide().profile_hash


@pytest.mark.parametrize(
    ("profile", "observation", "expected"),
    [
        (
            replace(_profile(), provider="other-provider"),
            _observation(),
            "PHYSICAL_IDENTITY_MISMATCH",
        ),
        (
            replace(_profile(), actual_model_id="future/model-v2"),
            _observation(),
            "PHYSICAL_IDENTITY_MISMATCH",
        ),
        (_profile(), _observation(ModelFamily.UNKNOWN), "UNKNOWN_MODEL_FAMILY"),
        (_profile(), _observation(ModelFamily.GEMINI), "MODEL_FAMILY_CONFLICT"),
        (
            replace(_profile(), expires_at="2026-08-30T12:00:00+00:00"),
            _observation(),
            "PROFILE_EXPIRED",
        ),
        (_profile(SupervisorTier.QUARANTINED), _observation(), "PROFILE_QUARANTINED"),
        (_profile(SupervisorTier.WORKER_ONLY), _observation(), "WORKER_ONLY_NOT_SUPERVISOR"),
    ],
)
def test_admission_rejects_identity_policy_and_tier_failures(
    profile, observation, expected
) -> None:
    assert _decide(profile, observation).reason_code == expected


def test_task_class_and_trace_gates_are_categorical() -> None:
    result = decide_supervisor_admission(
        _profile(),
        _observation(),
        task_class="IMPLEMENTATION",
        committed_trace="TRACE_B_COMMITTED",
        now="2026-08-31T00:00:00+00:00",
    )
    assert result.reason_code == "TASK_CLASS_NOT_ADMITTED"

    degraded = decide_supervisor_admission(
        _profile(SupervisorTier.DEGRADED_TRACE_A),
        _observation(),
        task_class="ARCHITECTURE",
        committed_trace="TRACE_B_COMMITTED",
        now="2026-08-31T00:00:00+00:00",
    )
    assert degraded.reason_code == "DEGRADED_TRACE_NOT_COMMITTED"


def test_profile_ttl_is_capped_at_thirty_days() -> None:
    with pytest.raises(ProtocolViolation, match="30 days"):
        replace(_profile(), expires_at="2026-10-01T00:00:00+00:00")


def test_missing_or_invalid_hashes_fail_before_admission() -> None:
    with pytest.raises(ProtocolViolation, match="SHA-256"):
        replace(_profile(), binary_hash="")

    result = decide_supervisor_admission(
        _profile(),
        _observation(),
        task_class="ARCHITECTURE",
        committed_trace="UNCOMMITTED",
        now="not-a-time",
    )
    assert result.reason_code == "INVALID_NOW"
