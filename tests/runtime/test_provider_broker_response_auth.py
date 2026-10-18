"""Response signatures bind synthetic exact requests, not provider identity claims."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest
from nacl.signing import SigningKey
from runtime.integrations import provider_broker as broker

DOMAIN = b"PAEOS-PROVIDER-RESPONSE-V1\0"
SIGNED_SCHEMA = "paeos.trusted-worker-signed-response/1"
SERVICE_SCHEMA = "paeos.trusted-worker-service/1"
RESPONSE_KEY = SigningKey(b"S" * 32)
REQUEST_KEY = SigningKey(b"R" * 32)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("utf-8")


def _request(kind: str, *, capability_id: str = "a" * 32, prompt: str = "synthetic") -> bytes:
    critic = kind == "critic"
    document = {
        "schema": (
            "paeos.trusted-cline-critic-capability/1"
            if critic
            else "paeos.trusted-worker-capability/1"
        ),
        "operation": "critic" if critic else "provider_chat",
        "capability_id": capability_id,
        "provider_id": "cline-pass" if critic else "openrouter",
        "model_id": (
            "cline-pass/glm-5.3" if critic else "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
        ),
        "model_family": "glm-5.3" if critic else "nemotron",
        "issued_at": 1000.0,
        "expires_at": 1030.0,
        "prompt": prompt,
    }
    return _canonical(
        {**document, "signature": REQUEST_KEY.sign(_canonical(document)).signature.hex()}
    )


def _response(request_bytes: bytes, *, ok: bool = True) -> dict:
    request = json.loads(request_bytes)
    result = {
        "schema": SERVICE_SCHEMA,
        "ok": ok,
        "capability_id": request["capability_id"],
    }
    if ok:
        result["observation"] = {
            "capability_id": request["capability_id"],
            "provider_id": request["provider_id"],
            "model_id": request["model_id"],
            "model_family": request["model_family"],
            "response_content": "synthetic result; not a qualified observation",
        }
    else:
        result.update(error="synthetic refusal", error_code="synthetic_denied")
    return result


def _payload(request_bytes: bytes, response: dict) -> dict:
    return {
        "schema": SIGNED_SCHEMA,
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "response": response,
    }


def _signed(payload: dict, *, key: SigningKey = RESPONSE_KEY, domain: bytes = DOMAIN) -> bytes:
    return _canonical(
        {"payload": payload, "signature": key.sign(domain + _canonical(payload)).signature.hex()}
    )


def _client(kind: str, tmp_path: Path, *, verify_key=RESPONSE_KEY.verify_key):
    common = {"queue_root": tmp_path / "queue", "response_verify_key": verify_key}
    if kind == "critic":
        return broker.HostClineCriticTransport(request_signing_key=REQUEST_KEY, **common)
    return broker.HostConfinedProviderClient(signing_key=REQUEST_KEY, **common)


@pytest.fixture(params=["critic", "client"])
def kind(request):
    return request.param


@pytest.mark.parametrize("ok", [True, False])
def test_authenticates_bound_success_or_failure_without_qualifying_observation(tmp_path, kind, ok):
    client = _client(kind, tmp_path)
    request_bytes = _request(kind)
    response = _response(request_bytes, ok=ok)
    assert (
        client._authenticate_response(_signed(_payload(request_bytes, response)), request_bytes)
        == response
    )
    assert not (tmp_path / "queue").exists()


def test_missing_verifier_denies_even_a_correct_signed_response(tmp_path, kind):
    client = _client(kind, tmp_path, verify_key=None)
    request_bytes = _request(kind)
    with pytest.raises(broker.ProviderBrokerError):
        client._authenticate_response(
            _signed(_payload(request_bytes, _response(request_bytes))), request_bytes
        )
    assert not (tmp_path / "queue").exists()


@pytest.mark.parametrize("ok", [True, False])
def test_unsigned_service_success_and_error_are_rejected(tmp_path, kind, ok):
    client = _client(kind, tmp_path)
    request_bytes = _request(kind)
    with pytest.raises(broker.ProviderBrokerError):
        client._authenticate_response(_canonical(_response(request_bytes, ok=ok)), request_bytes)


@pytest.mark.parametrize("defect", ["wrong-key", "no-domain", "tampered", "bad-signature"])
def test_signature_rejects_substitution_and_altered_payload(tmp_path, kind, defect):
    client = _client(kind, tmp_path)
    request_bytes = _request(kind)
    payload = _payload(request_bytes, _response(request_bytes))
    raw = _signed(
        payload,
        key=SigningKey(b"X" * 32) if defect == "wrong-key" else RESPONSE_KEY,
        domain=b"" if defect == "no-domain" else DOMAIN,
    )
    if defect in {"tampered", "bad-signature"}:
        envelope = json.loads(raw)
        if defect == "tampered":
            envelope["payload"]["response"]["observation"]["response_content"] = "changed"
        else:
            envelope["signature"] = "not-hex"
        raw = _canonical(envelope)
    with pytest.raises(broker.ProviderBrokerError):
        client._authenticate_response(raw, request_bytes)


@pytest.mark.parametrize(
    "defect",
    ["digest", "capability", "schema", "service-schema", "provider_id", "model_id", "model_family"],
)
def test_even_valid_signature_cannot_authorize_different_request_or_route(tmp_path, kind, defect):
    client = _client(kind, tmp_path)
    request_bytes = _request(kind)
    payload = _payload(request_bytes, _response(request_bytes))
    if defect == "digest":
        payload["request_sha256"] = "0" * 64
    elif defect == "capability":
        payload["response"]["capability_id"] = "b" * 32
    elif defect == "schema":
        payload["schema"] = "paeos.trusted-worker-signed-response/0"
    elif defect == "service-schema":
        payload["response"]["schema"] = "untrusted-service/1"
    else:
        payload["response"]["observation"][defect] = "different-route"
    with pytest.raises(broker.ProviderBrokerError):
        client._authenticate_response(_signed(payload), request_bytes)


@pytest.mark.parametrize(
    "defect", ["json", "utf8", "outer-extra", "outer-duplicate", "nested-duplicate"]
)
def test_strict_envelope_rejects_ambiguous_or_malformed_json(tmp_path, kind, defect):
    client = _client(kind, tmp_path)
    request_bytes = _request(kind)
    payload = _payload(request_bytes, _response(request_bytes))
    envelope = json.loads(_signed(payload))
    raw = _canonical(envelope)
    if defect == "json":
        raw = b"{"
    elif defect == "utf8":
        raw = b"\xff"
    elif defect == "outer-extra":
        raw = _canonical({**envelope, "trusted": True})
    elif defect == "outer-duplicate":
        encoded_payload = _canonical(payload).strip()
        raw = (
            b'{"payload":'
            + encoded_payload
            + b',"payload":'
            + encoded_payload
            + b',"signature":'
            + json.dumps(envelope["signature"]).encode()
            + b"}"
        )
    else:
        raw = raw.replace(b'"ok":true', b'"ok":true,"ok":true', 1)
    with pytest.raises(broker.ProviderBrokerError):
        client._authenticate_response(raw, request_bytes)


@pytest.mark.parametrize("change", ["prompt", "serialization"])
def test_reply_cannot_replay_against_changed_bytes_with_same_capability(tmp_path, kind, change):
    client = _client(kind, tmp_path)
    request_bytes = _request(kind)
    raw = _signed(_payload(request_bytes, _response(request_bytes)))
    successor = (
        _request(kind, prompt="different synthetic task")
        if change == "prompt"
        else json.dumps(json.loads(request_bytes), indent=2).encode()
    )
    assert json.loads(successor)["capability_id"] == json.loads(request_bytes)["capability_id"]
    with pytest.raises(broker.ProviderBrokerError):
        client._authenticate_response(raw, successor)


def test_concurrent_reversed_replies_do_not_share_request_identity(tmp_path, kind):
    client = _client(kind, tmp_path)
    requests = [_request(kind, capability_id=letter * 32) for letter in ("a", "b")]
    replies = [_signed(_payload(raw, _response(raw))) for raw in requests]
    barrier = Barrier(2)

    def crossed(index: int) -> None:
        barrier.wait(timeout=5)
        with pytest.raises(broker.ProviderBrokerError):
            client._authenticate_response(replies[1 - index], requests[index])
        assert client._authenticate_response(replies[index], requests[index]) == _response(
            requests[index]
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(crossed, (0, 1)))


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_queue_consumers_authenticate_signed_failure_before_semantic_rejection(
    tmp_path, monkeypatch, kind, cleanup_fails
):
    """Only this test bypasses disclosure denial to reach the synthetic receipt boundary."""
    client = _client(kind, tmp_path)
    authenticated: list[dict] = []
    original_authenticate = client._authenticate_response

    def observed_authenticate(raw_response: bytes, request_bytes: bytes) -> dict:
        response = original_authenticate(raw_response, request_bytes)
        authenticated.append(response)
        return response

    monkeypatch.setattr(client, "_authenticate_response", observed_authenticate)
    monkeypatch.setattr(broker, "_require_disclosure_authority", lambda: None)
    original_replace = broker.os.replace

    def publish_reply(source, destination):
        original_replace(source, destination)
        request_path = Path(destination)
        request_bytes = request_path.read_bytes()
        response = _response(request_bytes, ok=False)
        reply_path = request_path.with_name(
            request_path.name.replace(".request.json", ".response.json")
        )
        reply_path.write_bytes(_signed(_payload(request_bytes, response)))

    monkeypatch.setattr(broker.os, "replace", publish_reply)
    if cleanup_fails:
        original_unlink = Path.unlink

        def failed_cleanup(path, *args, **kwargs):
            if path.name.endswith(".response.json"):
                raise PermissionError("synthetic cleanup failure")
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", failed_cleanup)
    with pytest.raises(broker.ProviderBrokerError):
        if kind == "critic":
            client.run(
                SimpleNamespace(
                    stage="CRITIQUE",
                    task_id="synthetic-task",
                    goal_id="synthetic-goal",
                    run_id="synthetic-run",
                    prompt="synthetic receipt-only test",
                )
            )
        else:
            client.request("synthetic receipt-only test")
    assert len(authenticated) == 1
    assert authenticated[0]["ok"] is False
    if kind == "critic":
        assert client.last_observation is None


@pytest.mark.parametrize("ok", [True, False])
def test_untrusted_reply_does_not_destroy_request_or_response_evidence(
    tmp_path, monkeypatch, kind, ok
):
    client = _client(kind, tmp_path)
    monkeypatch.setattr(broker, "_require_disclosure_authority", lambda: None)
    original_replace = broker.os.replace
    captured = {}

    def forged_reply(source, destination):
        original_replace(source, destination)
        request_path = Path(destination)
        request_bytes = request_path.read_bytes()
        reply_path = request_path.with_name(
            request_path.name.replace(".request.json", ".response.json")
        )
        reply_bytes = _canonical(_response(request_bytes, ok=ok))
        reply_path.write_bytes(reply_bytes)
        captured.update(
            request=request_path,
            request_bytes=request_bytes,
            reply=reply_path,
            reply_bytes=reply_bytes,
        )

    monkeypatch.setattr(broker.os, "replace", forged_reply)
    with pytest.raises(broker.ProviderBrokerError):
        if kind == "critic":
            client.run(
                SimpleNamespace(
                    stage="CRITIQUE",
                    task_id="synthetic-task",
                    goal_id="synthetic-goal",
                    run_id="synthetic-run",
                    prompt="synthetic evidence-retention test",
                )
            )
        else:
            client.request("synthetic evidence-retention test")
    assert captured["request"].read_bytes() == captured["request_bytes"]
    assert captured["reply"].read_bytes() == captured["reply_bytes"]
