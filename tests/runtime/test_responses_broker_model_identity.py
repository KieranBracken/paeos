"""Synthetic tests of the pinned upstream contract, not evidence of a provider run."""

import json

import pytest
import runtime.integrations.task_scoped_responses_broker as broker_module

MODEL = "gpt-5.6-sol"
OTHER = "gpt-5.6-luna"


def _event(value):
    return b"data: " + json.dumps(value).encode() + b"\n\n"


def _completed(**fields):
    return _event(
        {
            "type": "response.completed",
            "response": {"id": "synthetic-response", "status": "completed", **fields},
        }
    )


def _reply(body=None, headers=(("openai-model", MODEL),), status=200, content_type=None):
    # Defer construction so the preimplementation baseline reaches test execution.
    return {
        "status": status,
        "content_type": content_type or "text/event-stream; charset=utf-8",
        "body": _completed() if body is None else body,
        "upstream_headers": headers,
    }


def _validate(reply):
    return broker_module.validate_server_model(broker_module.BrokerReply(**reply), MODEL)


def test_contract_is_bound_to_the_verified_codex_source_revision():
    assert broker_module.MODEL_IDENTITY_CONTRACT == (
        "codex-0.147.0:be6e8eac029b183056b7e4402879f15d2c85f61b"
    )


@pytest.mark.parametrize(
    "reply",
    [
        _reply(),
        _reply(headers=(("OpenAI-Model", MODEL),)),
        _reply(_completed(headers={"OpenAI-Model": MODEL}), headers=()),
        _reply(_completed(headers={"X-OpenAI-Model": MODEL}), headers=()),
        _reply(
            _event({"type": "response.created", "response": {"headers": {"openai-model": MODEL}}})
            + _completed(headers={"x-openai-model": MODEL})
        ),
        _reply(_completed() + b"data: [DONE]\n\n"),
        _reply(_completed().replace(b"\n", b"\r\n")),
    ],
)
def test_matching_server_model_is_reported_from_supported_header_sources(reply):
    assert _validate(reply) == MODEL


@pytest.mark.parametrize(
    "reply",
    [
        _reply(headers=()),
        _reply(headers=(("openai-model", OTHER),)),
        _reply(headers=(("x-openai-model", MODEL),)),
        _reply(headers=(("openai-model", MODEL), ("OpenAI-Model", OTHER))),
        _reply(_completed(headers={"openai-model": OTHER})),
        _reply(_completed(headers={"openai-model": MODEL, "x-openai-model": OTHER})),
        _reply(_completed(model=MODEL), headers=()),
        _reply(
            _event({"type": "response.metadata", "headers": {"openai-model": MODEL}})
            + _completed(),
            headers=(),
        ),
        _reply(
            _event(
                {"type": "response.output_item.done", "item": {"headers": {"openai-model": MODEL}}}
            )
            + _completed(),
            headers=(),
        ),
        _reply(
            _event({"type": "response.created", "response": {"headers": {"openai-model": MODEL}}})
        ),
        _reply(_completed() + _completed()),
        _reply(_completed() + _event({"type": "response.output_text.delta", "delta": "later"})),
        _reply(_event({"type": "response.failed", "response": {"id": "synthetic-response"}})),
        _reply(_event({"type": "response.incomplete", "response": {"id": "synthetic-response"}})),
        _reply(_completed(status="in_progress")),
        _reply(_completed(id=7)),
        _reply(b'data: {"type":"response.completed","type":"response.created"}\n\n'),
        _reply(
            b'data: {"type":"response.completed","response":{"id":"synthetic-response",'
            b'"status":"completed","headers":{"openai-model":"gpt-5.6-sol",'
            b'"openai-model":"gpt-5.6-luna"}}}\n\n'
        ),
        _reply(b"data: synthetic-private-marker-not-json\n\n"),
        _reply(b"data: \xff\n\n"),
        _reply(status=429),
        _reply(content_type="application/json"),
    ],
)
def test_absent_conflicting_malformed_or_incomplete_identity_fails_closed(reply):
    with pytest.raises(broker_module.ModelIdentityError) as raised:
        _validate(reply)
    assert isinstance(raised.value, ValueError)
    assert "synthetic-private-marker" not in str(raised.value)
    assert MODEL not in str(raised.value)
    assert OTHER not in str(raised.value)


def test_response_model_is_not_a_fallback_or_an_identity_declaration():
    assert _validate(_reply(_completed(model=OTHER))) == MODEL
