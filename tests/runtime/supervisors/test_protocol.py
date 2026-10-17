"""RED/GREEN contract tests for strict supervisor request/response envelopes."""

import hashlib
import json
from dataclasses import replace

import pytest
from kernel.types import ArtifactRef
from paeos.model_router.types import ModelFamily
from runtime.integrations.bridge_protocol import Disposition, ProtocolViolation, canonical_json
from runtime.supervisors.protocol import (
    AdapterResult,
    SupervisorRequest,
    SupervisorResponse,
    SupervisorTier,
    TransportObservation,
    decode_request,
    decode_response,
    encode_request,
    encode_response,
    validate_response,
)


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _request() -> SupervisorRequest:
    return SupervisorRequest(
        request_id="request-1",
        transaction_key="tx-1",
        nonce="nonce-1",
        checkpoint_hash=_hash("checkpoint"),
        policy_hash=_hash("policy"),
        task_class="ARCHITECTURE",
        prompt_hash=_hash("prompt"),
        context_manifest_hash=_hash("context"),
        allowed_dispositions=(Disposition.CONTINUE, Disposition.REMAND),
    )


def _response() -> SupervisorResponse:
    return SupervisorResponse(
        request_id="request-1",
        transaction_key="tx-1",
        nonce="nonce-1",
        checkpoint_hash=_hash("checkpoint"),
        disposition=Disposition.CONTINUE,
        artifact_refs=(ArtifactRef(hash=_hash("artifact"), type="architecture/spec"),),
        rationale_ref=_hash("rationale"),
    )


def test_request_round_trip_is_canonical_and_strict() -> None:
    raw = encode_request(_request())
    assert raw == (canonical_json(json.loads(raw)) + "\n").encode()
    assert decode_request(raw) == _request()


def test_response_round_trip_and_correlation() -> None:
    request = _request()
    response = _response()
    validate_response(request, response)
    assert decode_response(encode_response(response)) == response


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: {**value, "extra": "ignored"},
        lambda value: {key: item for key, item in value.items() if key != "nonce"},
        lambda value: {**value, "schema_version": "old"},
    ],
)
def test_unknown_missing_or_wrong_schema_fields_are_rejected(mutator) -> None:
    value = json.loads(encode_request(_request()))
    raw = (canonical_json(mutator(value)) + "\n").encode()
    with pytest.raises(ProtocolViolation):
        decode_request(raw)


def test_prose_prefix_suffix_and_partial_json_are_rejected() -> None:
    raw = encode_response(_response())
    for malformed in (b"Here is the response: " + raw, raw[:-2], raw + b"\nextra"):
        with pytest.raises(ProtocolViolation):
            decode_response(malformed)


def test_correlation_and_disposition_are_fail_closed() -> None:
    response = _response()
    with pytest.raises(ProtocolViolation):
        validate_response(_request(), replace(response, nonce="other"))

    disallowed = SupervisorResponse(
        request_id=response.request_id,
        transaction_key=response.transaction_key,
        nonce=response.nonce,
        checkpoint_hash=response.checkpoint_hash,
        disposition=Disposition.HALT,
        artifact_refs=response.artifact_refs,
        rationale_ref=response.rationale_ref,
    )
    with pytest.raises(ProtocolViolation):
        validate_response(_request(), disallowed)


def test_hashes_artifacts_and_payload_limits_are_validated() -> None:
    with pytest.raises(ProtocolViolation):
        SupervisorResponse(
            request_id="request-1",
            transaction_key="tx-1",
            nonce="nonce-1",
            checkpoint_hash="not-a-hash",
            disposition=Disposition.CONTINUE,
            artifact_refs=(),
            rationale_ref=_hash("rationale"),
        )
    with pytest.raises(ProtocolViolation):
        decode_request(encode_request(_request()) + (b" " * (1_048_576)))


def test_context_is_opaque_and_observation_is_separate() -> None:
    observation = TransportObservation(
        provider="future-provider",
        actual_model_id="future/model-v1",
        model_family=ModelFamily.GLM,
        adapter_id="future-adapter",
        adapter_version="1.0.0",
        provider_request_id="provider-request-1",
        observed_at="2026-08-30T00:00:00+00:00",
        usage={"prompt_tokens": 1},
    )
    result = AdapterResult(response_bytes=encode_response(_response()), observation=observation)
    assert b"prompt injection" not in result.response_bytes
    assert result.observation.model_family is ModelFamily.GLM


def test_supervisor_tier_is_explicit() -> None:
    assert tuple(SupervisorTier) == (
        SupervisorTier.ARCHITECT,
        SupervisorTier.DEGRADED_TRACE_A,
        SupervisorTier.WORKER_ONLY,
        SupervisorTier.QUARANTINED,
    )
