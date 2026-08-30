"""Task 9A tests for candidate-bound physical auditor receipts."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from paeos.model_router.auditor_receipt import (
    AUDITOR_RECEIPT_SCHEMA,
    AuditorReceiptContract,
    AuditorReceiptError,
    capture_auditor_receipt,
    load_auditor_receipt,
    persist_auditor_receipt,
    persist_auditor_report,
    request_fingerprint,
    response_fingerprint,
    validate_auditor_receipt,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.router import ModelRouter
from paeos.model_router.state import RouterStateDB
from paeos.model_router.transport import LiteLLMTransport
from paeos.model_router.types import (
    DataClass,
    LogicalModel,
    ModelFamily,
    ProviderId,
    RouterResponse,
    TaskClass,
    TaskRequest,
)

_CANDIDATE = "adf76c61972554f71f2c863b3113f07d19dd1a52"
_EVIDENCE = "e" * 64


class FakeRouter:
    def __init__(self, response: RouterResponse, catalog: ModelCatalog) -> None:
        self.response = response
        self.catalog = catalog
        self.seen_request: TaskRequest | None = None

    def route(self, request: TaskRequest) -> RouterResponse:
        self.seen_request = request
        return self.response


def _request() -> TaskRequest:
    return TaskRequest(
        messages=[
            {
                "role": "system",
                "content": "Perform an independent L14 audit without changing files.",
            },
            {
                "role": "user",
                "content": f"Candidate {_CANDIDATE}; evidence bundle {_EVIDENCE}.",
            },
        ],
        task_class=TaskClass.AUDIT,
        data_class=DataClass.INTERNAL,
        logical_model=LogicalModel.PAEOS_AUDIT,
        builder_family=ModelFamily.GLM,
        max_tokens=100,
        temperature=0.0,
    )


def _contract(request: TaskRequest, **changes: object) -> AuditorReceiptContract:
    values: dict[str, Any] = {
        "audit_id": "audit-9a-001",
        "candidate_sha256": _CANDIDATE,
        "evidence_bundle_sha256": _EVIDENCE,
        "review_scope_sha256": request_fingerprint(request),
        "builder_provider": "cline-pass",
        "builder_model_id": "z-ai/glm-5.3-flash",
        "builder_family": ModelFamily.GLM,
    }
    values.update(changes)
    return AuditorReceiptContract(**values)


def _catalog() -> ModelCatalog:
    return ModelCatalog()


def _response(request: TaskRequest, **changes: object) -> RouterResponse:
    result = RouterResponse(
        content="audit result: candidate is not yet eligible",
        model_id="gemini-3.6-flash",
        provider_id=ProviderId.GOOGLE,
        family=ModelFamily.GEMINI,
        actual_model="gemini-3.6-flash",
        actual_family=ModelFamily.GEMINI,
        prompt_tokens=12,
        completion_tokens=9,
        total_tokens=21,
        latency_ms=123.4,
        attempts=1,
        fallback_chain=["google:gemini-3.6-flash"],
        finish_reason="stop",
        raw_response={"model": "gemini-3.6-flash", "id": "provider-response-1"},
        transport_request_sha256=request_fingerprint(request),
    )
    for key, value in changes.items():
        setattr(result, key, value)
    result.transport_response_sha256 = response_fingerprint(result)
    return result


def test_capture_binds_candidate_and_physical_non_glm_identity() -> None:
    request = _request()
    response = _response(request)
    router = FakeRouter(response, _catalog())

    receipt = capture_auditor_receipt(router, _contract(request), request)

    assert receipt.schema == AUDITOR_RECEIPT_SCHEMA
    assert receipt.candidate_sha256 == _CANDIDATE
    assert receipt.evidence_bundle_sha256 == _EVIDENCE
    assert receipt.actual_provider_id == ProviderId.GOOGLE
    assert receipt.actual_model_id == "gemini-3.6-flash"
    assert receipt.actual_family == ModelFamily.GEMINI
    assert receipt.provider_attempt_count == 1
    assert receipt.fallback_chain == ("google:gemini-3.6-flash",)
    assert validate_auditor_receipt(receipt, _contract(request), _catalog()).passed


def test_litellm_transport_captures_content_free_fingerprints(tmp_path) -> None:
    request = _request()
    credentials = CredentialStore(tmp_path / "router.env")
    credentials._keys = {"GEMINI_API_KEY": "test-only-key"}
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="provider audit response", tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=9),
        model="gemini-3.6-flash",
    )
    transport = LiteLLMTransport(credentials, _catalog())
    entry = _catalog().get("gemini-3.6-flash")
    assert entry is not None

    with patch("paeos.model_router.transport.litellm.completion", return_value=response):
        captured = transport.dispatch(entry, request)

    assert captured.transport_request_sha256 == request_fingerprint(request)
    assert captured.transport_response_sha256 == response_fingerprint(captured)
    assert captured.raw_response is response


def test_capture_uses_router_audit_policy_and_records_selected_family(tmp_path) -> None:
    request = _request()
    credentials = CredentialStore(tmp_path / "router.env")
    credentials._keys = {
        "GEMINI_API_KEY": "test-google-key",
        "CLINE_API_KEY": "test-cline-key",
        "NVIDIA_API_KEY": "test-nvidia-key",
        "KILO_API_KEY": "test-kilo-key",
        "OPENROUTER_API_KEY": "test-openrouter-key",
    }

    class DeterministicTransport(LiteLLMTransport):
        def dispatch(self, model_entry, request, timeout=60.0):
            del timeout
            response = RouterResponse(
                content=f"audit response from {model_entry.model_id}",
                model_id=model_entry.model_id,
                provider_id=model_entry.provider_id,
                family=model_entry.family,
                actual_model=model_entry.model_id,
                actual_family=model_entry.family,
                attempts=1,
                fallback_chain=[],
            )
            response.transport_request_sha256 = request_fingerprint(request)
            response.transport_response_sha256 = response_fingerprint(response)
            return response

    catalog = _catalog()
    router = ModelRouter(
        credentials=credentials,
        catalog=catalog,
        state_db=RouterStateDB(tmp_path / "router.sqlite3"),
        transport=DeterministicTransport(credentials, catalog),
    )
    receipt = capture_auditor_receipt(router, _contract(request), request)

    assert receipt.actual_family is ModelFamily.GEMINI
    assert receipt.actual_provider_id is ProviderId.GOOGLE
    assert receipt.provider_attempt_count == 1


def test_capture_rejects_same_family_auditor() -> None:
    request = _request()
    response = _response(
        request,
        model_id="z-ai/glm-5.3-flash",
        family=ModelFamily.GLM,
        actual_model="z-ai/glm-5.3-flash",
        actual_family=ModelFamily.GLM,
        provider_id=ProviderId.NVIDIA,
        fallback_chain=["nvidia:z-ai/glm-5.3-flash"],
    )

    with pytest.raises(AuditorReceiptError, match="FAIL_SAME_FAMILY"):
        capture_auditor_receipt(FakeRouter(response, _catalog()), _contract(request), request)


def test_capture_rejects_unknown_physical_family() -> None:
    request = _request()
    response = _response(
        request,
        model_id="openrouter/free",
        family=ModelFamily.UNKNOWN,
        actual_model="provider/opaque-model-7",
        actual_family=ModelFamily.UNKNOWN,
        provider_id=ProviderId.OPENROUTER,
        fallback_chain=["openrouter:openrouter/free"],
    )

    with pytest.raises(AuditorReceiptError, match="unknown auditor family"):
        capture_auditor_receipt(FakeRouter(response, _catalog()), _contract(request), request)


def test_capture_rejects_claimed_family_that_differs_from_physical_model() -> None:
    request = _request()
    response = _response(request, actual_family=ModelFamily.LLAMA)

    with pytest.raises(AuditorReceiptError, match="does not match"):
        capture_auditor_receipt(FakeRouter(response, _catalog()), _contract(request), request)


def test_capture_rejects_retry_or_fallback_telemetry() -> None:
    request = _request()
    response = _response(
        request,
        attempts=2,
        fallback_chain=["google:gemini-3.6-flash", "nvidia:meta/llama-3.1-8b-instruct"],
    )

    with pytest.raises(AuditorReceiptError, match="exactly one provider attempt"):
        capture_auditor_receipt(FakeRouter(response, _catalog()), _contract(request), request)


def test_capture_rejects_request_without_candidate_and_evidence_binding() -> None:
    request = replace(
        _request(),
        messages=[{"role": "user", "content": "Review this code."}],
    )
    response = _response(request)

    with pytest.raises(AuditorReceiptError, match="candidate and evidence"):
        capture_auditor_receipt(FakeRouter(response, _catalog()), _contract(request), request)


def test_capture_rejects_transport_request_hash_mismatch() -> None:
    request = _request()
    response = _response(request, transport_request_sha256="a" * 64)

    with pytest.raises(AuditorReceiptError, match="request fingerprint"):
        capture_auditor_receipt(FakeRouter(response, _catalog()), _contract(request), request)


def test_receipt_persistence_is_canonical_create_only_and_content_free(tmp_path) -> None:
    request = _request()
    response = _response(request)
    contract = _contract(request)
    receipt = capture_auditor_receipt(FakeRouter(response, _catalog()), contract, request)
    path = tmp_path / "audit-receipt.json"

    persisted = persist_auditor_receipt(receipt, path)
    assert persisted == path
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    assert b"audit result" not in raw
    assert b"Perform an independent" not in raw
    assert raw == json.dumps(
        json.loads(raw), sort_keys=True, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    assert load_auditor_receipt(path) == receipt

    with pytest.raises(FileExistsError):
        persist_auditor_receipt(receipt, path)


def test_auditor_report_persistence_is_separate_and_create_only(tmp_path) -> None:
    path = tmp_path / "audit-report.md"

    assert persist_auditor_report("finding: remand", path) == path
    assert path.read_text(encoding="utf-8") == "finding: remand"
    with pytest.raises(FileExistsError):
        persist_auditor_report("replacement", path)


def test_tampered_receipt_hash_fails_closed(tmp_path) -> None:
    request = _request()
    response = _response(request)
    contract = _contract(request)
    receipt = capture_auditor_receipt(FakeRouter(response, _catalog()), contract, request)
    path = tmp_path / "audit-receipt.json"
    persist_auditor_receipt(receipt, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["actual_family"] = "glm"
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AuditorReceiptError):
        load_auditor_receipt(path)
