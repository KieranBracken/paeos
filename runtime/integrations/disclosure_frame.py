"""Closed Responses-frame inspection, with no classification or egress authority.

The exact bytes are retained for the separate enrolled-authority verifier and durable
send claim. Successful inspection never means permission to disclose. Unsupported
references/attachments and opaque history are denied until their provenance can be
bound. Tool definitions must match the parent-approved closed tool envelope exactly.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

_MAX_BYTES = 2 * 1024 * 1024
_MAX_DEPTH = 32
_MAX_ITEMS = 32768
_TOOL_NAMES = frozenset({"read_artifact", "propose_patch", "run_test"})
_FIELDS = frozenset(
    {
        "model",
        "input",
        "instructions",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "stream",
        "store",
        "reasoning",
        "text",
    }
)


class FrameRejected(ValueError):
    """Content-free rejection; never include an outbound value in the diagnostic."""


def _reject() -> None:
    raise FrameRejected("unsupported or unbound outbound frame")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _reject()
        result[key] = value
    return result


def _parse(raw: bytes):
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_BYTES:
        _reject()
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=lambda _: _reject()
        )
    except (ValueError, UnicodeError, RecursionError):
        _reject()


def _canonical(obj) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _exact(obj, required: set[str], optional: set[str] | None = None):
    if (
        type(obj) is not dict
        or not required <= obj.keys()
        or obj.keys() - required - (optional or set())
    ):
        _reject()
    return obj


def _text(value):
    if type(value) is not str:
        _reject()
    try:
        value.encode("utf-8")
    except UnicodeError:
        _reject()
    return value


@dataclass(frozen=True, slots=True)
class FrameComponent:
    location: str
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class InspectedResponsesFrame:
    body: bytes = field(repr=False)
    sha256: str
    components: tuple[FrameComponent, ...]
    tool_calls: tuple[str, ...] = field(repr=False)
    tool_results: tuple[str, ...] = field(repr=False)


def inspect_responses_frame(
    body: bytes,
    *,
    expected_model: str,
    approved_tools: Mapping[str, bytes] | None = None,
) -> InspectedResponsesFrame:
    """Inspect one immutable frame; the caller must independently authorize all its bytes.

    Parent-approved tool schemas do not classify tool arguments or results. The caller
    still needs authenticated input/derivation provenance and current disclosure policy.
    In particular a worker cannot label its own tool output as an approved derivative.
    """
    try:
        return _inspect(body, expected_model, approved_tools or {})
    except (ValueError, TypeError, UnicodeError, RecursionError, KeyError):
        raise FrameRejected("unsupported or unbound outbound frame") from None


def _inspect(body: bytes, expected_model: str, approved_tools: Mapping[str, bytes]):
    obj = _parse(body)
    _exact(obj, {"model", "input"}, set(_FIELDS - {"model", "input"}))
    if expected_model not in {"gpt-5.6-sol", "gpt-5.6-luna"} or obj["model"] != expected_model:
        _reject()
    components: list[FrameComponent] = []
    count = 0

    def visit(value, location, depth=0):
        nonlocal count
        count += 1
        if depth > _MAX_DEPTH or count > _MAX_ITEMS:
            _reject()
        if type(value) is str:
            encoded = _text(value).encode("utf-8")
            components.append(
                FrameComponent(location, hashlib.sha256(encoded).hexdigest(), len(encoded))
            )
        elif type(value) is dict:
            for key, item in value.items():
                _text(key)
                # Caller-supplied schema/argument keys can themselves contain data.
                # Keep diagnostic paths content-free outside the fixed wire vocabulary.
                segment = (
                    key
                    if key
                    in _FIELDS
                    | {
                        "role",
                        "content",
                        "type",
                        "text",
                        "name",
                        "description",
                        "parameters",
                        "strict",
                        "properties",
                        "required",
                        "additionalProperties",
                        "call_id",
                        "arguments",
                        "output",
                        "effort",
                        "summary",
                        "format",
                        "verbosity",
                    }
                    else "key-sha256-" + hashlib.sha256(key.encode("utf-8")).hexdigest()
                )
                visit(item, location + "/" + segment, depth + 1)
        elif type(value) is list:
            for index, item in enumerate(value):
                visit(item, location + "/" + str(index), depth + 1)
        elif value is not None and type(value) not in (bool, int):
            _reject()

    # Includes all strings, including tool schema descriptions; root hash binds every byte.
    visit(obj, "")
    for name, required in (("stream", True), ("store", False), ("parallel_tool_calls", False)):
        if name in obj and obj[name] is not required:
            _reject()
    if "instructions" in obj:
        _text(obj["instructions"])
    if "reasoning" in obj:
        reasoning = _exact(obj["reasoning"], set(), {"effort", "summary"})
        if reasoning.get("effort", "medium") not in {
            "none",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
        }:
            _reject()
        if reasoning.get("summary", "auto") not in {"auto", "concise", "detailed"}:
            _reject()
    if "text" in obj:
        text = _exact(obj["text"], set(), {"format", "verbosity"})
        if "format" in text and text["format"] != {"type": "text"}:
            _reject()
        if text.get("verbosity", "medium") not in {"low", "medium", "high"}:
            _reject()

    definitions = obj.get("tools", [])
    if type(definitions) is not list:
        _reject()
    names: set[str] = set()
    for definition in definitions:
        _exact(definition, {"type", "name", "parameters"}, {"description", "strict"})
        name = definition["name"]
        if (
            type(name) is not str
            or name not in _TOOL_NAMES
            or name in names
            or definition["type"] != "function"
        ):
            _reject()
        expected = approved_tools.get(name)
        if type(expected) is not bytes or _canonical(definition) != expected:
            _reject()

        # No external schema resolution, regardless of parent configuration error.
        def schema_check(value):
            if type(value) is dict:
                if any(k in value for k in ("$ref", "$dynamicRef", "$id", "$schema")):
                    _reject()
                for item in value.values():
                    schema_check(item)
            elif type(value) is list:
                for item in value:
                    schema_check(item)

        schema_check(definition["parameters"])
        names.add(name)
    choice = obj.get("tool_choice", "auto")
    if (
        type(choice) is not str
        or choice not in {"auto", "none", "required"}
        or (choice == "required" and not names)
    ):
        _reject()

    calls: list[str] = []
    results: list[str] = []
    items = obj["input"]
    if type(items) is str:
        _text(items)
    elif type(items) is list:
        for item in items:
            if type(item) is not dict:
                _reject()
            kind = item.get("type", "message")
            if kind == "message":
                _exact(item, {"role", "content"}, {"type"})
                if item["role"] not in {"system", "developer", "user", "assistant"}:
                    _reject()
                content = item["content"]
                if type(content) is str:
                    _text(content)
                elif type(content) is list:
                    for part in content:
                        _exact(part, {"type", "text"})
                        if part["type"] not in {"input_text", "output_text"}:
                            _reject()
                        if part["type"] == "output_text" and item["role"] != "assistant":
                            _reject()
                        _text(part["text"])
                else:
                    _reject()
            elif kind == "function_call":
                _exact(item, {"type", "name", "call_id", "arguments"})
                call_id = _text(item["call_id"])
                if (
                    not call_id
                    or len(call_id) > 256
                    or call_id in calls
                    or item["name"] not in names
                ):
                    _reject()
                arguments = _parse(_text(item["arguments"]).encode("utf-8"))
                if type(arguments) is not dict:
                    _reject()
                visit(arguments, "/decoded_arguments/" + str(len(calls)))
                calls.append(call_id)
            elif kind == "function_call_output":
                _exact(item, {"type", "call_id", "output"})
                call_id = _text(item["call_id"])
                if call_id not in calls or call_id in results:
                    _reject()
                _text(item["output"])
                results.append(call_id)
            else:
                _reject()
    else:
        _reject()
    return InspectedResponsesFrame(
        body, hashlib.sha256(body).hexdigest(), tuple(components), tuple(calls), tuple(results)
    )
