"""Gemini critic handoffs deny before capabilities or parent socket effects."""

from __future__ import annotations

import json

import pytest
from kernel.types import Role
from runtime.integrations import gemini36_critic_route as critic

MARKER = "synthetic-classified-gemini-critic-prompt"
PROMPT = json.dumps(
    {
        "content": MARKER,
        "data_class": "PUBLIC",
        "classification_authority": "worker-asserted",
        "disclosure_permit": {"approved": True, "signature": "forged"},
        "attachments": [{"content": MARKER}],
        "tool_results": [{"content": MARKER}],
        "history": [{"content": MARKER}],
    }
)
DENIAL_CODE = "disclosure_authority_unavailable"


class Spy:
    verify_key = None

    def __init__(self):
        self.calls = []
        self.verify_key = self

    def sign(self, _message):
        self.calls.append("sign")
        raise AssertionError("signer was called")

    def verify(self, *_args):
        self.calls.append("verify")
        raise AssertionError("verifier was called")


class Opaque:
    def __getattr__(self, _name):
        raise AssertionError("task object was inspected")


def _route(signer, exchange):
    return critic.Gemini36CriticRoute(
        request_signing_key=signer,
        parent_exchange=exchange,
        now=lambda: 100.0,
    )


def _signed_shape():
    capability_id = "a" * 32
    request = {
        "schema": critic.CAPABILITY_SCHEMA,
        "capability_id": capability_id,
        "task_id": "synthetic-task",
        "goal_id": "synthetic-goal",
        "run_id": "synthetic-run",
        "stage": "CRITIQUE",
        "role": "CRITIC",
        "operation": "critic",
        "provider_id": critic.PROVIDER,
        "model_id": critic.MODEL,
        "model_family": critic.FAMILY,
        "prompt": PROMPT,
        "read_only": True,
        "allow_tools": False,
        "allow_fallback": False,
        "require_confinement": True,
        "builder_family": "synthetic-builder",
        "critic_family": critic.FAMILY,
        "issued_at": 100.0,
        "expires_at": 145.0,
        "signature": "b" * 128,
    }
    environment = {
        "HOME": "/nonexistent/paeos-gemini36-critic",
        "LANG": "C.UTF-8",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
        "TMPDIR": "/nonexistent/paeos-gemini36-critic/tmp",
        "PAEOS_TASK_BEARER": capability_id,
        "PAEOS_TASK_BROKER_URL": "parent-owned:google-gemini36-critic",
    }
    return request, environment


@pytest.mark.parametrize("entry", ["host", "route", "issue"])
def test_critic_entrypoints_deny_before_reading_or_signing(entry):
    """A valid route or forged PUBLIC claim cannot invoke the Gemini signer."""
    signer = Spy()
    exchanges = []

    def exchange(**_kwargs):
        exchanges.append("exchange")
        raise AssertionError("parent exchange was called")

    route = _route(signer, exchange)
    if entry == "host":
        target = critic.HostGemini36CriticTransport(
            request_signing_key=signer,
            parent_exchange=exchange,
            builder_family="synthetic-builder",
        ).run
        value = Opaque()
    elif entry == "route":
        target = route.run
        value = Opaque()
    else:
        target = route.issue_task_capability
        value = {
            "task_id": "synthetic-task",
            "goal_id": "synthetic-goal",
            "run_id": "synthetic-run",
            "stage": "CRITIQUE",
            "role": Role.CRITIC,
            "operation": "critic",
            "prompt": PROMPT,
            "builder_family": "synthetic-builder",
        }
    with pytest.raises(critic.Gemini36CriticRouteError) as denied:
        target(**value) if entry == "issue" else target(value)
    assert denied.value.code == DENIAL_CODE
    assert MARKER not in str(denied.value)
    assert signer.calls == []
    assert exchanges == []
    assert route.last_observation is None


def test_critic_direct_parent_helper_denies_before_socket(monkeypatch):
    """Direct helper use cannot send a well-shaped signed frame over the socket."""
    request, environment = _signed_shape()
    calls = []

    def socket_call(*_args, **_kwargs):
        calls.append("socket")
        raise AssertionError("parent socket was opened")

    monkeypatch.setattr(critic.socket, "socket", socket_call)
    with pytest.raises(critic.Gemini36CriticRouteError) as denied:
        critic.parent_gemini36_exchange(request=request, environment=environment, timeout_s=1.0)
    assert denied.value.code == DENIAL_CODE
    assert MARKER not in str(denied.value)
    assert calls == []


def test_critic_direct_exchange_does_not_inspect_opaque_arguments():
    """The local denial runs before validation can inspect any caller-provided frame."""
    with pytest.raises(critic.Gemini36CriticRouteError) as denied:
        critic.parent_gemini36_exchange(request=Opaque(), environment=Opaque(), timeout_s=Opaque())
    assert denied.value.code == DENIAL_CODE
