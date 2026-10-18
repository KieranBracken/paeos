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
