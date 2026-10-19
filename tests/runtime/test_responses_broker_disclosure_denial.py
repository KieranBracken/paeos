"""Exercise the unmodified disclosure boundary with synthetic data and no remote transport."""

import json
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path

import pytest
from runtime.integrations import task_scoped_responses_broker as module


def _post(broker, body):
    connection = HTTPConnection("127.0.0.1", broker.loopback_port, timeout=3)
    try:
        connection.request(
            "POST",
            "/v1/responses",
            body=body,
            headers={"Authorization": f"Bearer {broker.task_token}"},
        )
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def _denial_broker(monkeypatch, model):
    forwarded = []

    def upstream(body, _token, _account):
        forwarded.append(body)
        return module.BrokerReply(200, "application/json", b'{"synthetic":true}')

    broker = module.ParentOwnedResponsesBroker(
        auth_path=Path("/unused-synthetic-auth"), model_id=model, upstream=upstream
    )
    # Only the external credential dependency is replaced. The guard and handler stay real.
    monkeypatch.setattr(
        broker, "_load_parent_auth", lambda: ("synthetic-token", "synthetic-account")
    )
    return broker, forwarded


@pytest.mark.parametrize("model", ["gpt-5.6-sol", "gpt-5.6-luna"])
@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"data_class": "PUBLIC"},
        {"data_class": "INTERNAL"},
        {"data_class": "SECRET"},
        {"data_class": "unknown"},
        {"data_class": None},
        {"attachments": [{"file_data": "synthetic-excluded-sentinel"}]},
        {"tool_results": [{"output": "synthetic-excluded-sentinel"}]},
        {"workspace": "/synthetic/excluded", "file_url": "file:///synthetic/excluded"},
        {"history": [{"content": "synthetic-excluded-sentinel"}]},
        {"disclosure_permit": {"status": "ACTIVE", "signature": "synthetic-forgery"}},
        {"disclosure_permit": {"status": "REVOKED"}},
        {"disclosure_permit": {"expires_at": "2000-01-01T00:00:00Z"}},
        {"disclosure_permit": {"payload_sha256": "0" * 64, "route": "unrelated"}},
        {"disclosure_permit": {"attempt_id": "reused-synthetic-attempt", "used": True}},
        {"disclosure_permit": "malformed"},
    ],
)
def test_untrusted_payload_claims_cannot_enable_egress(monkeypatch, model, claims):
    # Removing the handler guard or trusting any worker claim causes an actual mock-upstream call.
    broker, forwarded = _denial_broker(monkeypatch, model)
    payload = {"model": model, "input": "synthetic-excluded-sentinel", **claims}
    body = json.dumps(payload).encode()
    with broker:
        status, response = _post(broker, body)
        assert status == 403
        assert forwarded == []
        evidence = broker.evidence()
        assert evidence["request_count"] == 0
        assert evidence["request_receipts"] == []
        assert evidence["local_rejection_count"] == 1
        assert evidence["transport_outcome"] == "local_rejection"
        assert b"synthetic-excluded-sentinel" not in response
        assert "synthetic-excluded-sentinel" not in json.dumps(evidence)
        from ops.trusted_codex_worker_supervisor import _broker_evidence_complete

        assert not _broker_evidence_complete(evidence, model)


def test_concurrent_repeated_denials_never_reserve_or_forward(monkeypatch):
    broker, forwarded = _denial_broker(monkeypatch, "gpt-5.6-sol")
    body = b'{"model":"gpt-5.6-sol","attempt_id":"same-synthetic-attempt"}'
    with broker, ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_post, broker, body) for _ in range(8)]
        assert [future.result(timeout=5)[0] for future in futures] == [403] * 8
        assert forwarded == []
        evidence = broker.evidence()
        assert evidence["local_rejection_count"] == 8
        assert evidence["request_count"] == 0
        assert evidence["request_receipts"] == []


def test_direct_forwarding_cannot_bypass_authority_guard(monkeypatch):
    connections = []

    def forbidden_connection(*args, **kwargs):
        connections.append((args, kwargs))
        raise RuntimeError("network-constructor-reached")

    monkeypatch.setattr(module.http.client, "HTTPSConnection", forbidden_connection)
    with pytest.raises(RuntimeError):
        module.ParentOwnedResponsesBroker._forward_to_chatgpt(
            b'{"model":"gpt-5.6-sol","input":"synthetic"}',
            "synthetic-token",
            "synthetic-account",
        )
    assert connections == []


def test_absent_authority_does_not_read_parent_credentials(monkeypatch):
    reads = []
    broker = module.ParentOwnedResponsesBroker(auth_path=Path("/unused-synthetic-auth"))

    def forbidden_read():
        reads.append("read")
        raise AssertionError("credential loading must follow actual frame authorization")

    monkeypatch.setattr(broker, "_load_parent_auth", forbidden_read)
    with broker:
        assert _post(broker, b'{"model":"gpt-5.6-sol","input":"synthetic"}')[0] == 403
    assert reads == []


@pytest.mark.parametrize(
    "extra",
    [
        {"attachments": [{"file_data": "synthetic-excluded-sentinel"}]},
        {"previous_response_id": "opaque-remote"},
        {"tools": [{"type": "local_shell"}]},
        {"input": [{"type": "function_call_output", "call_id": "orphan", "output": "synthetic"}]},
    ],
)
def test_frame_inspection_is_enforced_before_even_injected_forwarder(monkeypatch, extra):
    # Isolate frame enforcement from the still-disabled authority-composition boundary.
    monkeypatch.setattr(module, "_require_disclosure_authority", lambda: None)
    broker, forwarded = _denial_broker(monkeypatch, "gpt-5.6-sol")
    with broker:
        status, _ = _post(
            broker, json.dumps({"model": "gpt-5.6-sol", "input": "synthetic", **extra}).encode()
        )
    assert status == 403
    assert forwarded == []
    assert broker.evidence()["request_count"] == 0


def test_direct_network_method_also_enforces_full_frame(monkeypatch):
    monkeypatch.setattr(module, "_require_disclosure_authority", lambda: None)
    calls = []
    monkeypatch.setattr(
        module.http.client, "HTTPSConnection", lambda *a, **k: calls.append("network")
    )
    with pytest.raises(ValueError):
        module.ParentOwnedResponsesBroker._forward_to_chatgpt(
            b'{"model":"gpt-5.6-sol","input":"synthetic","attachments":[]}',
            "synthetic-token",
            "synthetic-account",
        )
    assert calls == []


@pytest.mark.parametrize("link", ["ancestor", "leaf"])
def test_parent_auth_rejects_symlinked_components(tmp_path, link):
    original = tmp_path / "original"
    original.mkdir()
    auth = original / "auth.json"
    auth.write_text(
        json.dumps({"tokens": {"access_token": "synthetic", "account_id": "synthetic-account"}})
    )
    auth.chmod(0o600)
    if link == "ancestor":
        (tmp_path / "alias").symlink_to(original, target_is_directory=True)
        candidate = tmp_path / "alias" / "auth.json"
    else:
        candidate = tmp_path / "alias.json"
        candidate.symlink_to(auth)
    broker = module.ParentOwnedResponsesBroker(auth_path=candidate)
    with pytest.raises(RuntimeError):
        broker._load_parent_auth()


def test_parent_auth_reads_bounded_private_regular_file(tmp_path):
    auth = tmp_path / "auth.json"
    auth.write_text(
        json.dumps({"tokens": {"access_token": "synthetic", "account_id": "synthetic-account"}})
    )
    auth.chmod(0o600)
    broker = module.ParentOwnedResponsesBroker(auth_path=auth)
    assert broker._load_parent_auth() == ("synthetic", "synthetic-account")
    auth.chmod(0o644)
    with pytest.raises(RuntimeError):
        broker._load_parent_auth()
    auth.chmod(0o600)
    auth.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(RuntimeError):
        broker._load_parent_auth()


def test_parent_auth_duplicate_identity_and_header_injection_reject(tmp_path):
    auth = tmp_path / "auth.json"
    broker = module.ParentOwnedResponsesBroker(auth_path=auth)
    auth.write_text(
        '{"tokens":{"access_token":"synthetic","access_token":"other","account_id":"synthetic"}}'
    )
    auth.chmod(0o600)
    with pytest.raises(RuntimeError):
        broker._load_parent_auth()
    auth.write_text(
        json.dumps(
            {"tokens": {"access_token": "synthetic\r\nx-bad: yes", "account_id": "synthetic"}}
        )
    )
    with pytest.raises(RuntimeError):
        broker._load_parent_auth()
