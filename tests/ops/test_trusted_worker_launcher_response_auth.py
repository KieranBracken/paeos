"""Synthetic producer authentication, with every provider route still denied."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey

from ops import trusted_worker_launcher_service as service

DOMAIN = b"PAEOS-PROVIDER-RESPONSE-V1\0"
SIGNED_SCHEMA = "paeos.trusted-worker-signed-response/1"
SERVICE_SCHEMA = "paeos.trusted-worker-service/1"
CAPABILITY_ID = "0123456789abcdef0123456789abcdef"
SYNTHETIC_MARKER = "synthetic-prompt-must-not-appear-in-refusal"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("utf-8")


def _producer(tmp_path: Path):
    request_key = SigningKey(b"R" * 32)
    response_key = SigningKey(b"S" * 32)
    public_key = tmp_path / "synthetic-request-public.hex"
    public_key.write_text(bytes(request_key.verify_key).hex(), encoding="ascii")
    producer = service.TrustedProviderService(
        socket_path=tmp_path / "launcher.sock",
        state_root=tmp_path / "state",
        public_key_path=public_key,
        queue_root=tmp_path / "queue",
        response_signing_key=response_key,
    )
    return producer, request_key, response_key


def _request(key: SigningKey, schema: str) -> bytes:
    document = {
        "schema": schema,
        "operation": "provider_chat",
        "capability_id": CAPABILITY_ID,
        "issued_at": 1000.0,
        "expires_at": 1030.0,
        "provider_id": "openrouter",
        "model_id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "model_family": "nemotron",
        "data_class": "PUBLIC",
        "task_class": "ROUTINE",
        "prompt": SYNTHETIC_MARKER,
    }
    return _canonical({**document, "signature": key.sign(_canonical(document)).signature.hex()})


def _verified_payload(raw: bytes, key: SigningKey, request_bytes: bytes) -> dict:
    envelope = json.loads(raw)
    assert set(envelope) == {"payload", "signature"}
    payload = envelope["payload"]
    assert set(payload) == {"schema", "request_sha256", "response"}
    assert payload["schema"] == SIGNED_SCHEMA
    assert payload["request_sha256"] == hashlib.sha256(request_bytes).hexdigest()
    signature = bytes.fromhex(envelope["signature"])
    key.verify_key.verify(DOMAIN + _canonical(payload), signature)
    with pytest.raises(BadSignatureError):
        key.verify_key.verify(_canonical(payload), signature)
    return payload


def test_missing_response_signer_denies_before_state_or_key_access(tmp_path, monkeypatch):
    effects: list[str] = []

    def forbidden_path(*args, **kwargs):
        effects.append("path-access")
        raise AssertionError("missing response identity reached filesystem handling")

    monkeypatch.setattr(service, "_safe_path", forbidden_path)
    with pytest.raises(RuntimeError):
        service.TrustedProviderService(
            socket_path=tmp_path / "socket",
            state_root=tmp_path / "state",
            public_key_path=tmp_path / "absent-request-public.hex",
        )
    assert effects == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("ok", [True, False])
def test_signed_response_binds_exact_bytes_and_separate_response_identity(tmp_path, ok):
    producer, request_key, response_key = _producer(tmp_path)
    request_bytes = b'{ "capability_id": "synthetic", "prompt": "caf\\u00e9" }\n'
    response = {
        "schema": SERVICE_SCHEMA,
        "ok": ok,
        "capability_id": "synthetic",
        **({"observation": {"synthetic": "caf\u00e9"}} if ok else {"error_code": "denied"}),
    }
    raw = producer._signed_response(response, request_bytes)
    payload = _verified_payload(raw, response_key, request_bytes)
    assert payload["response"] == response
    assert (
        payload["request_sha256"]
        != hashlib.sha256(_canonical(json.loads(request_bytes))).hexdigest()
    )
    with pytest.raises(BadSignatureError):
        request_key.verify_key.verify(
            DOMAIN + _canonical(payload), bytes.fromhex(json.loads(raw)["signature"])
        )


@pytest.mark.parametrize(
    "schema",
    [
        "paeos.trusted-worker-capability/1",
        "paeos.trusted-cline-critic-capability/1",
        "paeos.trusted-nvidia-critic-capability/1",
        "paeos.trusted-gemini36-critic-capability/1",
        "paeos.trusted-gemini36-adversary-capability/1",
        "paeos.trusted-gemini38-critic-capability/1",
        "paeos.trusted-gemini38-adversary-capability/1",
    ],
)
def test_handle_signs_refusal_before_any_provider_branch(
    tmp_path, monkeypatch, capsys, caplog, schema
):
    producer, request_key, response_key = _producer(tmp_path)
    effects: list[str] = []

    def forbidden_branch(*args, **kwargs):
        effects.append("provider-or-admission")
        raise AssertionError("disclosure denial reached a provider branch")

    for name in dir(producer):
        if (name.startswith("_validate_") and name.endswith("capability")) or (
            name.startswith("_run_") and "provider" in name
        ):
            monkeypatch.setattr(producer, name, forbidden_branch)
    request_bytes = _request(request_key, schema)
    raw = producer.handle(request_bytes)
    response = _verified_payload(raw, response_key, request_bytes)["response"]
    assert response["schema"] == SERVICE_SCHEMA
    assert response["ok"] is False
    assert response["capability_id"] == CAPABILITY_ID
    assert isinstance(response["error_code"], str) and response["error_code"]
    assert "observation" not in response
    assert effects == []
    assert SYNTHETIC_MARKER.encode() not in raw
    captured = capsys.readouterr()
    assert SYNTHETIC_MARKER not in captured.out + captured.err + caplog.text


def test_process_queue_publishes_nested_signed_refusal_for_same_request(tmp_path, monkeypatch):
    producer, request_key, response_key = _producer(tmp_path)
    request_bytes = _request(request_key, "paeos.trusted-worker-capability/1")
    queue = tmp_path / "queue"
    queue.mkdir()
    request_path = queue / f"{CAPABILITY_ID}.request.json"
    request_path.write_bytes(request_bytes)
    effects: list[str] = []

    def forbidden_provider(*args, **kwargs):
        effects.append("provider")
        raise AssertionError("queue processing invoked provider")

    monkeypatch.setattr(producer, "_run_provider", forbidden_provider)
    producer.process_queue()
    response_path = queue / f"{CAPABILITY_ID}.response.json"
    payload = _verified_payload(response_path.read_bytes(), response_key, request_bytes)
    assert payload["response"]["capability_id"] == CAPABILITY_ID
    assert payload["response"]["ok"] is False
    assert not request_path.exists()
    assert effects == []
    assert sorted(item.name for item in queue.iterdir()) == [response_path.name]
