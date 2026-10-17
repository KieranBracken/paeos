"""Provider-neutral admission-adapter contract tests (Gate A Task 2)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, replace

import pytest
from paeos.model_router.types import NormalizedErrorType
from runtime.worker_adapter import (
    ADAPTER_PROTOCOL_VERSION,
    AdapterFailureKind,
    AdapterFailureReceipt,
    AdapterObservation,
    SideEffectCertainty,
    assess_failure_receipt,
    select_primary_failure,
    validate_adapter_observation,
)

HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def observation(**changes: object) -> AdapterObservation:
    value = AdapterObservation(
        protocol_version=ADAPTER_PROTOCOL_VERSION,
        invocation_id="probe-002",
        session_id="session-002",
        provider_id="cline-pass",
        model_id="cline-pass/qwen3.8-max",
        backend_mode="local",
        declared_model_turn_count=2,
        provider_attempts_by_turn=(1, 1),
        side_effect_certainty=SideEffectCertainty.PROVIDER_ACCEPTED,
        capability_snapshot_sha256=HEX_A,
        transcript_sha256=HEX_B,
    )
    return replace(value, **changes)


def failure_receipt(**changes: object) -> AdapterFailureReceipt:
    value = AdapterFailureReceipt(
        protocol_version=ADAPTER_PROTOCOL_VERSION,
        invocation_id="probe-002",
        contract_id="probe-contract-002",
        adapter_failure=None,
        normalized_error=NormalizedErrorType.AUTH_FAILED,
        additional_findings=(),
        side_effect_certainty=SideEffectCertainty.NOT_DISPATCHED,
        raw_stdout_sha256=HEX_A,
        raw_stderr_sha256=HEX_B,
        observation_sha256=HEX_C,
    )
    return replace(value, **changes)


def test_adapter_observation_is_transport_neutral_immutable_and_hash_bound() -> None:
    value = observation()

    assert value.backend_mode == "local"
    assert len(value.observation_sha256) == 64
    assert value.observation_sha256 != replace(value, session_id="other").observation_sha256
    with pytest.raises(FrozenInstanceError):
        value.session_id = "forged"  # type: ignore[misc]


def test_failure_receipt_contains_hashes_and_enums_not_raw_provider_text() -> None:
    value = failure_receipt()
    serialized = repr(asdict(value))

    assert value.normalized_error is NormalizedErrorType.AUTH_FAILED
    assert "Unauthorized: copy this secret" not in serialized
    assert set(value.raw_stdout_sha256) == {"a"}
    assert set(value.raw_stderr_sha256) == {"b"}


def test_unknown_side_effect_certainty_can_never_admit() -> None:
    result = assess_failure_receipt(
        failure_receipt(
            normalized_error=None,
            adapter_failure=AdapterFailureKind.SIDE_EFFECT_UNCERTAIN,
            side_effect_certainty=SideEffectCertainty.UNKNOWN,
        )
    )

    assert result.verdict.value == "REJECTED"
    assert result.reasons[0] == "SIDE_EFFECT_UNCERTAIN"


@pytest.mark.parametrize("attempts", [(0,), (2,), (1, 0), (1, 2)])
def test_attempt_count_other_than_one_per_declared_turn_rejects(
    attempts: tuple[int, ...],
) -> None:
    findings = validate_adapter_observation(
        observation(
            declared_model_turn_count=len(attempts),
            provider_attempts_by_turn=attempts,
        )
    )

    assert AdapterFailureKind.TRANSPORT_FAILED in findings


def test_undeclared_or_missing_turn_rejects() -> None:
    findings = validate_adapter_observation(
        observation(declared_model_turn_count=2, provider_attempts_by_turn=(1,))
    )

    assert AdapterFailureKind.TRANSPORT_FAILED in findings


def test_exactly_one_attempt_per_declared_turn_is_valid() -> None:
    assert validate_adapter_observation(observation()) == ()


def test_capability_drift_precedes_verification_mismatch() -> None:
    primary = select_primary_failure(
        (
            AdapterFailureKind.VERIFICATION_NONDISCRIMINATIVE,
            AdapterFailureKind.CAPABILITY_DRIFT,
        ),
        None,
    )

    assert primary == AdapterFailureKind.CAPABILITY_DRIFT.value


def test_auth_failure_is_not_collapsed_to_admission_rejected() -> None:
    result = assess_failure_receipt(failure_receipt())

    assert result.reasons == (NormalizedErrorType.AUTH_FAILED.value,)


def test_adapter_specific_primary_preserves_provider_error_as_additional() -> None:
    value = failure_receipt(
        adapter_failure=AdapterFailureKind.CAPABILITY_DRIFT,
        normalized_error=NormalizedErrorType.AUTH_FAILED,
        additional_findings=(AdapterFailureKind.MODEL_MISMATCH,),
    )
    result = assess_failure_receipt(value)

    assert result.reasons == (
        AdapterFailureKind.CAPABILITY_DRIFT.value,
        AdapterFailureKind.MODEL_MISMATCH.value,
        NormalizedErrorType.AUTH_FAILED.value,
    )


@pytest.mark.parametrize(
    "field",
    [
        "capability_snapshot_sha256",
        "transcript_sha256",
    ],
)
def test_observation_rejects_malformed_hash(field: str) -> None:
    findings = validate_adapter_observation(observation(**{field: "not-a-hash"}))

    assert AdapterFailureKind.TRANSPORT_FAILED in findings


def test_observation_rejects_nonlocal_or_wrong_protocol() -> None:
    assert AdapterFailureKind.CAPABILITY_DRIFT in validate_adapter_observation(
        observation(backend_mode="auto")
    )
    assert AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED in validate_adapter_observation(
        observation(protocol_version="future/99")
    )
