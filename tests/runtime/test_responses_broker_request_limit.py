"""Receipt-only loopback tests with the disclosure gate explicitly bypassed in test code.

These do not establish authorized egress. Unpatched denial is tested separately in
test_responses_broker_disclosure_denial.py. No providers or host credentials are used.
"""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path
from threading import Event

import pytest
from runtime.integrations.task_scoped_responses_broker import (
    MAX_TASK_REQUESTS,
    BrokerReply,
    ParentOwnedResponsesBroker,
)

MODEL_IDENTITY_CONTRACT = "codex-0.147.0:be6e8eac029b183056b7e4402879f15d2c85f61b"


def _response_body(marker="synthetic"):
    event = {
        "type": "response.completed",
        "response": {"id": marker, "status": "completed"},
    }
    return b"data: " + json.dumps(event).encode() + b"\n\n"


def _response(body=None, model="gpt-5.6-sol"):
    return BrokerReply(
        200,
        "text/event-stream",
        _response_body() if body is None else body,
        upstream_headers=(("openai-model", model),),
    )


def _post(broker, body=b'{"model":"gpt-5.6-sol","input":"synthetic"}'):
    connection = HTTPConnection("127.0.0.1", broker.loopback_port, timeout=3)
    try:
        connection.request(
            "POST",
            "/v1/responses",
            body=body,
            headers={"Authorization": f"Bearer {broker.task_token}"},
        )
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def _broker(monkeypatch, upstream, limit=1):
    # Isolate the existing receipt machinery; this is not a production permit interface.
    monkeypatch.setattr(
        "runtime.integrations.task_scoped_responses_broker._require_disclosure_authority",
        lambda: None,
    )
    broker = ParentOwnedResponsesBroker(
        auth_path=Path("/unused-synthetic-auth"), upstream=upstream, max_requests=limit
    )
    monkeypatch.setattr(
        broker, "_load_parent_auth", lambda: ("synthetic-token", "synthetic-account")
    )
    return broker


@pytest.mark.parametrize("limit", [True, False, 0, -1, 1.0, "1", MAX_TASK_REQUESTS + 1])
def test_request_limit_is_strict_and_cannot_expand_existing_ceiling(limit):
    with pytest.raises(ValueError, match="request limit"):
        ParentOwnedResponsesBroker(auth_path=Path("/unused"), max_requests=limit)


def test_one_call_ceiling_is_enforced_before_second_upstream_effect(monkeypatch):
    calls = []

    def upstream(body, _token, _account):
        calls.append(body)
        return _response()

    with _broker(monkeypatch, upstream) as broker:
        assert _post(broker) == 200
        assert _post(broker) == 429
        assert len(calls) == 1
        assert broker.evidence()["request_count"] == 1
        assert broker.evidence()["request_limit"] == 1


def test_concurrent_attempts_cannot_exceed_one_call(monkeypatch):
    entered, release = Event(), Event()
    calls = []

    def upstream(body, _token, _account):
        calls.append(body)
        entered.set()
        assert release.wait(3)
        return _response()

    with _broker(monkeypatch, upstream) as broker, ThreadPoolExecutor(max_workers=5) as pool:
        first = pool.submit(_post, broker)
        try:
            assert entered.wait(2)
            others = [pool.submit(_post, broker) for _ in range(4)]
            assert [future.result(timeout=2) for future in others] == [429] * 4
        finally:
            release.set()
        assert first.result(timeout=2) == 200
        assert len(calls) == 1


def test_upstream_ambiguity_consumes_the_only_call(monkeypatch):
    calls = []

    def upstream(body, _token, _account):
        calls.append(body)
        raise TimeoutError("synthetic timeout")

    with _broker(monkeypatch, upstream) as broker:
        assert _post(broker) == 502
        assert broker.evidence()["upstream_error_class"] == "timeout"
        assert _post(broker) == 429
        assert len(calls) == 1


def test_existing_general_task_ceiling_remains_available(monkeypatch):
    calls = []

    def upstream(body, _token, _account):
        calls.append(body)
        return _response()

    with _broker(monkeypatch, upstream, MAX_TASK_REQUESTS) as broker:
        assert _post(broker) == 200
        assert _post(broker) == 200
        assert len(calls) == 2
        assert broker.evidence()["request_limit"] == MAX_TASK_REQUESTS


@pytest.mark.parametrize("first_response", ["A", "B"])
def test_concurrent_receipts_pair_each_request_with_its_own_response(monkeypatch, first_response):
    from ops.trusted_codex_worker_supervisor import _broker_evidence_complete

    bodies = {
        "A": b'{"model":"gpt-5.6-sol","input":"synthetic A"}',
        "B": b'{"model":"gpt-5.6-sol","input":"synthetic B"}',
    }
    replies = {key: _response_body(key) for key in bodies}
    entered = {key: Event() for key in bodies}
    release = {key: Event() for key in bodies}

    def upstream(body, _token, _account):
        key = next(key for key, value in bodies.items() if value == body)
        entered[key].set()
        assert release[key].wait(3)
        return _response(replies[key])

    with _broker(monkeypatch, upstream, 2) as broker, ThreadPoolExecutor(2) as pool:
        futures = {}
        try:
            for key in ("A", "B"):
                futures[key] = pool.submit(_post, broker, bodies[key])
                assert entered[key].wait(2)
            pending = broker.evidence()
            release[first_response].set()
            assert futures[first_response].result(timeout=2) == 200
            partial = broker.evidence()
            other = "B" if first_response == "A" else "A"
            release[other].set()
            assert futures[other].result(timeout=2) == 200
        finally:
            for event in release.values():
                event.set()
        final = broker.evidence()
        # The baseline's A -> B -> response B -> response A race produces this false pair.
        assert (final["request_sha256"], final["response_sha256"]) != (
            hashlib.sha256(bodies["B"]).hexdigest(),
            hashlib.sha256(replies["A"]).hexdigest(),
        )
        assert final["schema"] == "paeos.task-scoped-responses-broker/3"
        assert final["request_sha256"] == final["response_sha256"] == ""
        assert final["upstream_status"] is None
        assert final["transport_outcome"] == "response_received"
        assert _broker_evidence_complete(final, "gpt-5.6-sol")
        assert partial["transport_outcome"] == "upstream_started"
        assert not _broker_evidence_complete(partial, "gpt-5.6-sol")
        for sequence, key in enumerate(("A", "B"), 1):
            record = final["request_receipts"][sequence - 1]
            assert record == {
                "request_id": sequence,
                "request_sha256": hashlib.sha256(bodies[key]).hexdigest(),
                "response_sha256": hashlib.sha256(replies[key]).hexdigest(),
                "transport_outcome": "response_received",
                "upstream_status": 200,
                "upstream_error_class": None,
                "observed_model_id": "gpt-5.6-sol",
                "model_identity_contract": MODEL_IDENTITY_CONTRACT,
                "model_identity_error": None,
            }
        assert [row["transport_outcome"] for row in pending["request_receipts"]] == [
            "upstream_started",
            "upstream_started",
        ]
        final["request_receipts"][0]["request_sha256"] = "mutated public snapshot"
        assert (
            broker.evidence()["request_receipts"][0]["request_sha256"]
            == hashlib.sha256(bodies["A"]).hexdigest()
        )


@pytest.mark.parametrize("failure", ["timeout", "invalid", "invalid_status", "oversize"])
def test_failed_call_and_later_success_keep_distinct_receipts_and_deny_task_success(
    monkeypatch, failure
):
    from ops.trusted_codex_worker_supervisor import _broker_evidence_complete

    failed_body = b'{"model":"gpt-5.6-sol","input":"synthetic failure"}'
    success_body = b'{"model":"gpt-5.6-sol","input":"synthetic success"}'

    def upstream(body, _token, _account):
        if body == success_body:
            return BrokerReply(429, "application/json", b'{"synthetic":"upstream refusal"}')
        if failure == "timeout":
            raise TimeoutError("synthetic timeout")
        if failure == "oversize":
            return BrokerReply(200, "application/json", b"x" * (8 * 1024 * 1024 + 1))
        if failure == "invalid_status":
            return BrokerReply("200", "application/json", b"{}")
        return None

    with _broker(monkeypatch, upstream, 2) as broker:
        assert _post(broker, failed_body) == 502
        assert _post(broker, success_body) == 429
        evidence = broker.evidence()
        assert evidence["transport_outcome"] != "response_received"
        assert not _broker_evidence_complete(evidence, "gpt-5.6-sol")
        failed, returned = evidence["request_receipts"]
        assert failed["request_id"] == 1
        assert failed["request_sha256"] == hashlib.sha256(failed_body).hexdigest()
        assert failed["response_sha256"] == ""
        assert failed["upstream_status"] is None
        assert failed["transport_outcome"] == (
            "upstream_failure" if failure == "timeout" else "invalid_upstream_response"
        )
        assert failed["upstream_error_class"] == ("timeout" if failure == "timeout" else None)
        assert returned["request_id"] == 2
        assert returned["request_sha256"] == hashlib.sha256(success_body).hexdigest()
        assert returned["upstream_status"] == 429  # Receipt is not an HTTP-success claim.
        assert returned["transport_outcome"] == "response_received"
        assert returned["observed_model_id"] is None
        assert returned["model_identity_contract"] is None
        assert returned["model_identity_error"] == "unverified_server_model"
        assert _post(broker, success_body) == 429
        denied = broker.evidence()
        assert denied["request_receipts"] == evidence["request_receipts"]
        assert denied["request_count"] == 2
        assert denied["local_rejection_count"] == 1


def test_single_call_scalar_evidence_is_exactly_its_immutable_receipt(monkeypatch):
    from ops.trusted_codex_worker_supervisor import _broker_evidence_complete

    with _broker(monkeypatch, lambda *_: _response()) as broker:
        assert broker.evidence()["request_receipts"] == []
        assert _post(broker) == 200
        evidence = broker.evidence()
        assert _broker_evidence_complete(evidence, "gpt-5.6-sol")
        record = evidence["request_receipts"][0]
        assert record["request_id"] == 1
        for field in (
            "request_sha256",
            "response_sha256",
            "upstream_status",
            "upstream_error_class",
        ):
            assert evidence[field] == record[field]
        assert _post(broker) == 429
        assert broker.evidence()["request_receipts"] == [record]


def test_reverse_completion_keeps_model_identity_failure_on_its_own_request(monkeypatch):
    from ops.trusted_codex_worker_supervisor import _broker_evidence_complete

    bodies = {
        "A": b'{"model":"gpt-5.6-sol","input":"synthetic A"}',
        "B": b'{"model":"gpt-5.6-sol","input":"synthetic B"}',
    }
    entered = {key: Event() for key in bodies}
    release = {key: Event() for key in bodies}

    def upstream(body, _token, _account):
        key = next(key for key, value in bodies.items() if value == body)
        entered[key].set()
        assert release[key].wait(3)
        return _response(_response_body(key), "gpt-5.6-sol" if key == "A" else "gpt-5.6-luna")

    with _broker(monkeypatch, upstream, 2) as broker, ThreadPoolExecutor(2) as pool:
        futures = {}
        try:
            for key in ("A", "B"):
                futures[key] = pool.submit(_post, broker, bodies[key])
                assert entered[key].wait(2)
            for key in ("B", "A"):
                release[key].set()
                assert futures[key].result(timeout=2) == 200
        finally:
            for event in release.values():
                event.set()
        evidence = broker.evidence()
        first, second = evidence["request_receipts"]
        assert first["request_sha256"] == hashlib.sha256(bodies["A"]).hexdigest()
        assert first["observed_model_id"] == "gpt-5.6-sol"
        assert first["model_identity_error"] is None
        assert second["request_sha256"] == hashlib.sha256(bodies["B"]).hexdigest()
        assert second["observed_model_id"] is None
        assert second["model_identity_contract"] is None
        assert second["model_identity_error"] == "unverified_server_model"
        assert evidence["transport_outcome"] == "response_received"
        assert not _broker_evidence_complete(evidence, "gpt-5.6-sol")
