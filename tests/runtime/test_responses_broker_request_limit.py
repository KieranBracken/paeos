"""Synthetic loopback tests: no provider calls or host credential access."""

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


def _post(broker):
    connection = HTTPConnection("127.0.0.1", broker.loopback_port, timeout=3)
    try:
        connection.request(
            "POST",
            "/v1/responses",
            body=b'{"model":"gpt-5.6-sol","input":"synthetic","max_requests":32}',
            headers={"Authorization": f"Bearer {broker.task_token}"},
        )
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def _broker(monkeypatch, upstream, limit=1):
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
        return BrokerReply(200, "application/json", b'{"synthetic":true}')

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
        return BrokerReply(200, "application/json", b'{"synthetic":true}')

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
        return BrokerReply(200, "application/json", b"{}")

    with _broker(monkeypatch, upstream, MAX_TASK_REQUESTS) as broker:
        assert _post(broker) == 200
        assert _post(broker) == 200
        assert len(calls) == 2
        assert broker.evidence()["request_limit"] == MAX_TASK_REQUESTS
