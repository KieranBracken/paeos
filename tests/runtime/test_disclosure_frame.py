"""Synthetic closed-frame inspection; these tests do not establish disclosure authority."""

import hashlib
import importlib.util
import json

import pytest


def _module():
    assert importlib.util.find_spec("runtime.integrations.disclosure_frame") is not None, (
        "complete-frame inspection is not implemented"
    )
    from runtime.integrations import disclosure_frame

    return disclosure_frame


def _body(**changes):
    return json.dumps({"model": "gpt-5.6-sol", "input": "synthetic prompt", **changes}).encode()


def _inspect(body=None, **kwargs):
    return _module().inspect_responses_frame(
        _body() if body is None else body, expected_model="gpt-5.6-sol", **kwargs
    )


def test_exact_bytes_and_all_instruction_history_text_are_bound():
    body = _body(
        instructions="synthetic instructions",
        input=[
            {"role": "user", "content": [{"type": "input_text", "text": "synthetic source"}]},
            {"role": "assistant", "content": [{"type": "output_text", "text": "synthetic prior"}]},
        ],
    )
    frame = _inspect(body)
    assert frame.body is body
    assert frame.sha256 == hashlib.sha256(body).hexdigest()
    components = {x.location: x.sha256 for x in frame.components}
    assert components["/instructions"] == hashlib.sha256(b"synthetic instructions").hexdigest()
    assert components["/input/0/content/0/text"] == hashlib.sha256(b"synthetic source").hexdigest()
    assert components["/input/1/content/0/text"] == hashlib.sha256(b"synthetic prior").hexdigest()
    assert not hasattr(frame, "authorized")
    assert "synthetic instructions" not in repr(frame)


@pytest.mark.parametrize(
    "extra",
    [
        {"attachments": []},
        {"data_class": "PUBLIC"},
        {"history": []},
        {"previous_response_id": "remote-id"},
        {"conversation": "remote-id"},
        {"metadata": {"label": "PUBLIC"}},
        {"workspace": "/synthetic"},
        {"prompt": {"id": "remote-template"}},
        {"tools": [{"type": "web_search"}]},
        {"tools": [{"type": "local_shell"}]},
        {"tools": [{"type": "mcp", "server_url": "https://invalid"}]},
        {"include": ["reasoning.encrypted_content"]},
        {"store": True},
        {"parallel_tool_calls": True},
        {"stream": False},
        {"model": "gpt-5.6-luna"},
        {"reasoning": {"effort": "high", "opaque": "value"}},
        {"text": {"format": {"type": "json_schema", "schema": {"$ref": "https://invalid"}}}},
        {"service_tier": "priority"},
        {"unknown": None},
    ],
)
def test_unsupported_or_unbound_fields_are_rejected_without_payload_in_error(extra):
    module = _module()
    with pytest.raises(module.FrameRejected) as raised:
        _inspect(_body(**extra))
    assert "synthetic" not in str(raised.value)


@pytest.mark.parametrize(
    "content",
    [
        [{"type": "input_image", "image_url": "https://invalid/image"}],
        [{"type": "input_file", "file_id": "opaque-id"}],
        [{"type": "input_file", "file_data": "synthetic encoded data"}],
        [{"type": "input_audio", "data": "synthetic audio"}],
        [{"type": "input_text", "text": "safe", "file_url": "file:///excluded"}],
    ],
)
def test_attachment_and_reference_paths_are_not_silently_ignored(content):
    with pytest.raises(_module().FrameRejected):
        _inspect(_body(input=[{"role": "user", "content": content}]))


@pytest.mark.parametrize(
    "body",
    [
        b'{"model":"gpt-5.6-sol","input":"a","input":"b"}',
        b'{"model":"gpt-5.6-sol","input":[{"role":"user","role":"assistant","content":"a"}]}',
        b'{"model":"gpt-5.6-sol","input":NaN}',
        b'{"model":"gpt-5.6-sol","input":"\\ud800"}',
        b"[]",
        b"null",
        b"\xff",
        b"",
    ],
)
def test_ambiguous_or_invalid_json_rejects(body):
    with pytest.raises(_module().FrameRejected):
        _inspect(body)


def test_mutable_buffer_rejected_and_size_bound_enforced():
    module = _module()
    for body in [bytearray(_body()), b" " * (2 * 1024 * 1024 + 1)]:
        with pytest.raises(module.FrameRejected):
            _inspect(body)


def _tool():
    return {
        "type": "function",
        "name": "read_artifact",
        "description": "Read approved artifact",
        "parameters": {
            "type": "object",
            "properties": {"artifact_id": {"type": "string"}},
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
        "strict": True,
    }


def test_tools_must_equal_parent_bound_definitions_and_results_are_inspected():
    tool = _tool()
    parent = {"read_artifact": json.dumps(tool, sort_keys=True, separators=(",", ":")).encode()}
    body = _body(
        tools=[tool],
        input=[
            {
                "type": "function_call",
                "name": "read_artifact",
                "call_id": "call-1",
                "arguments": '{"artifact_id":"source-1"}',
            },
            {"type": "function_call_output", "call_id": "call-1", "output": "synthetic result"},
        ],
    )
    frame = _inspect(body, approved_tools=parent)
    assert frame.tool_calls == ("call-1",)
    assert frame.tool_results == ("call-1",)
    assert "/input/1/output" in [c.location for c in frame.components]
    with pytest.raises(_module().FrameRejected):
        _inspect(body)
    tool["description"] = "changed by worker"
    with pytest.raises(_module().FrameRejected):
        _inspect(_body(tools=[tool]), approved_tools=parent)


@pytest.mark.parametrize(
    "item",
    [
        {"type": "function_call_output", "call_id": "orphan", "output": "unbound"},
        {"type": "function_call", "name": "shell", "call_id": "call-1", "arguments": "{}"},
        {"type": "reasoning", "encrypted_content": "opaque"},
        {"type": "item_reference", "id": "remote-id"},
    ],
)
def test_orphan_tool_results_and_unapproved_tools_or_opaque_history_reject(item):
    with pytest.raises(_module().FrameRejected):
        _inspect(_body(input=[item]))


def test_nested_and_duplicate_tool_arguments_and_call_ids_reject():
    tool = _tool()
    parent = {"read_artifact": json.dumps(tool, sort_keys=True, separators=(",", ":")).encode()}
    call = {
        "type": "function_call",
        "name": "read_artifact",
        "call_id": "call-1",
        "arguments": "{}",
    }
    for items in [[call, call], [{**call, "arguments": '{"x":1,"x":2}'}]]:
        with pytest.raises(_module().FrameRejected):
            _inspect(_body(tools=[tool], input=items), approved_tools=parent)


def test_supported_control_fields_cannot_hide_arbitrary_disclosures():
    _inspect(
        _body(
            stream=True,
            store=False,
            parallel_tool_calls=False,
            tool_choice="none",
            reasoning={"effort": "high", "summary": "auto"},
            text={"format": {"type": "text"}, "verbosity": "low"},
        )
    )
    with pytest.raises(_module().FrameRejected):
        _inspect(_body(reasoning={"effort": "synthetic secret"}))


def test_diagnostics_and_repr_do_not_expose_dynamic_argument_keys_or_call_ids():
    tool = _tool()
    parent = {"read_artifact": json.dumps(tool, sort_keys=True, separators=(",", ":")).encode()}
    body = _body(
        tools=[tool],
        input=[
            {
                "type": "function_call",
                "name": "read_artifact",
                "call_id": "synthetic-excluded-sentinel",
                "arguments": '{"synthetic-excluded-sentinel":"value"}',
            }
        ],
    )
    frame = _inspect(body, approved_tools=parent)
    assert "synthetic-excluded-sentinel" not in repr(frame)
    assert all("synthetic-excluded-sentinel" not in c.location for c in frame.components)
