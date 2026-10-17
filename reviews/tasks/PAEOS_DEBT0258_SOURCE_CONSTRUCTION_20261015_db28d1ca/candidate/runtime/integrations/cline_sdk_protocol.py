"""Canonical length-prefixed protocol for the policy-free Cline SDK host."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import BinaryIO

from runtime.worker_adapter import ADAPTER_PROTOCOL_VERSION

PROTOCOL_VERSION = ADAPTER_PROTOCOL_VERSION
MAX_FRAME_BYTES = 1_048_576

HOST_MESSAGE_TYPES = frozenset(
    {
        "hello",
        "session_created",
        "capability_snapshot",
        "provider_attempt_started",
        "provider_attempt_finished",
        "tool_request",
        "session_snapshot",
        "terminal",
        "failure",
        "cancelled",
    }
)
PYTHON_MESSAGE_TYPES = frozenset({"start", "tool_response", "cancel"})
TERMINAL_HOST_TYPES = frozenset({"terminal", "failure", "cancelled"})


class ProtocolError(RuntimeError):
    """A fail-closed framing or message-state violation."""


def _canonical_json(message: dict[str, object]) -> bytes:
    return json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def encode_frame(message: dict[str, object]) -> bytes:
    if not isinstance(message, dict):
        raise ProtocolError("frame payload must be object")
    payload = _canonical_json(message)
    if not payload or len(payload) > MAX_FRAME_BYTES:
        raise ProtocolError("frame size invalid")
    return len(payload).to_bytes(4, "big") + payload


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ProtocolError("truncated frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(stream: BinaryIO) -> dict[str, object]:
    header = _read_exact(stream, 4)
    length = int.from_bytes(header, "big")
    if length <= 0 or length > MAX_FRAME_BYTES:
        raise ProtocolError("frame size invalid")
    payload = _read_exact(stream, length)
    try:
        text = payload.decode("utf-8")
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid JSON frame") from exc
    if not isinstance(value, dict):
        raise ProtocolError("frame payload must be object")
    if _canonical_json(value) != payload:
        raise ProtocolError("non-canonical frame")
    return value


def _base_message(
    message: dict[str, object], allowed_types: frozenset[str]
) -> tuple[str, str, int, str | None, dict[str, object]]:
    message_type = message.get("type")
    invocation_id = message.get("invocation_id")
    sequence = message.get("sequence")
    protocol = message.get("protocol_version")
    payload = message.get("payload")
    session_id = message.get("session_id")
    allowed_keys = {
        "type",
        "invocation_id",
        "sequence",
        "protocol_version",
        "payload",
        "session_id",
    }
    if set(message) - allowed_keys:
        raise ProtocolError("unknown message field")
    if protocol != PROTOCOL_VERSION:
        raise ProtocolError("protocol version mismatch")
    if not isinstance(message_type, str) or message_type not in allowed_types:
        raise ProtocolError("unknown message type")
    if not isinstance(invocation_id, str) or not invocation_id:
        raise ProtocolError("invalid invocation")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise ProtocolError("invalid sequence")
    if session_id is not None and not isinstance(session_id, str):
        raise ProtocolError("invalid session")
    if not isinstance(payload, dict):
        raise ProtocolError("invalid payload")
    return message_type, invocation_id, sequence, session_id, payload


@dataclass(slots=True)
class HostEventMachine:
    invocation_id: str
    # The public SDK transport uses phase-bound identity.  The older bound
    # stdio adapter has a deliberately smaller, already-validated frame shape;
    # it opts into that compatibility mode explicitly at its call site.
    strict_tool_identity: bool = True
    expected_sequence: int = 0
    session_id: str | None = None
    terminal: bool = False
    _started_attempts: set[str] = field(default_factory=set)
    _finished_attempts: set[str] = field(default_factory=set)
    _tool_calls: set[str] = field(default_factory=set)

    def accept(self, message: dict[str, object]) -> None:
        if self.terminal:
            raise ProtocolError("post-terminal message")
        message_type, invocation_id, sequence, session_id, payload = _base_message(
            message, HOST_MESSAGE_TYPES
        )
        if invocation_id != self.invocation_id:
            raise ProtocolError("cross-invocation message")
        if sequence != self.expected_sequence:
            raise ProtocolError("sequence mismatch")
        if sequence == 0 and message_type != "hello":
            raise ProtocolError("hello must be first")
        if sequence == 1 and message_type != "session_created":
            raise ProtocolError("session_created must be second")
        if sequence > 0 and self.session_id is None and message_type != "session_created":
            raise ProtocolError("session not created")
        if message_type == "session_created":
            if self.session_id is not None or not session_id:
                raise ProtocolError("session ambiguous")
            self.session_id = session_id
        elif message_type != "hello" and session_id != self.session_id:
            raise ProtocolError("session mismatch")
        elif message_type == "hello" and session_id is not None:
            raise ProtocolError("hello cannot bind session")

        if message_type.startswith("provider_attempt_"):
            correlation = payload.get("correlation_id")
            if not isinstance(correlation, str) or not correlation:
                raise ProtocolError("attempt correlation missing")
            if message_type == "provider_attempt_started":
                if correlation in self._started_attempts:
                    raise ProtocolError("duplicate attempt")
                self._started_attempts.add(correlation)
            elif (
                correlation not in self._started_attempts or correlation in self._finished_attempts
            ):
                raise ProtocolError("unmatched attempt")
            else:
                self._finished_attempts.add(correlation)
        if message_type == "tool_request":
            if self.strict_tool_identity:
                expected_tool_keys = {
                    "agent_id",
                    "call_id",
                    "conversation_id",
                    "input",
                    "iteration",
                    "phase",
                    "tool_name",
                }
                if set(payload) != expected_tool_keys:
                    raise ProtocolError("tool request schema mismatch")
                call_id = payload.get("call_id")
                phase = payload.get("phase")
                if (
                    not isinstance(call_id, str)
                    or not call_id
                    or not isinstance(phase, str)
                    or phase not in {"approval", "execution"}
                    or f"{phase}:{call_id}" in self._tool_calls
                ):
                    raise ProtocolError("duplicate or missing tool call")
                for field_name in ("agent_id", "conversation_id", "tool_name"):
                    value = payload.get(field_name)
                    if not isinstance(value, str) or not value:
                        raise ProtocolError("tool request identity missing")
                iteration = payload.get("iteration")
                if not isinstance(iteration, int) or isinstance(iteration, bool) or iteration <= 0:
                    raise ProtocolError("tool request iteration invalid")
                if not isinstance(payload.get("input"), dict):
                    raise ProtocolError("tool request input invalid")
                self._tool_calls.add(f"{phase}:{call_id}")
            else:
                expected_tool_keys = {"call_id", "input", "tool_name"}
                if set(payload) != expected_tool_keys:
                    raise ProtocolError("legacy tool request schema mismatch")
                call_id = payload.get("call_id")
                if not isinstance(call_id, str) or not call_id:
                    raise ProtocolError("legacy tool request identity missing")
                for field_name in ("tool_name",):
                    value = payload.get(field_name)
                    if not isinstance(value, str) or not value:
                        raise ProtocolError("legacy tool request identity missing")
                if not isinstance(payload.get("input"), dict):
                    raise ProtocolError("legacy tool request input invalid")
                key = f"legacy:{call_id}"
                if key in self._tool_calls:
                    raise ProtocolError("duplicate legacy tool call")
                self._tool_calls.add(key)
        if message_type in TERMINAL_HOST_TYPES:
            if self._started_attempts != self._finished_attempts:
                raise ProtocolError("terminal with unfinished provider attempt")
            self.terminal = True
        self.expected_sequence += 1

    def eof(self) -> None:
        if not self.terminal:
            raise ProtocolError("EOF before terminal")


@dataclass(slots=True)
class PythonCommandMachine:
    invocation_id: str
    expected_sequence: int = 0
    session_id: str | None = None
    started: bool = False
    terminal: bool = False

    def accept(self, message: dict[str, object]) -> None:
        if self.terminal:
            raise ProtocolError("post-terminal command")
        message_type, invocation_id, sequence, session_id, _ = _base_message(
            message, PYTHON_MESSAGE_TYPES
        )
        if invocation_id != self.invocation_id or sequence != self.expected_sequence:
            raise ProtocolError("command binding mismatch")
        if not self.started:
            if message_type != "start" or session_id is not None:
                raise ProtocolError("start must be first")
            self.started = True
        elif message_type == "start":
            raise ProtocolError("duplicate start")
        elif not session_id:
            raise ProtocolError("session required")
        elif self.session_id is None:
            self.session_id = session_id
        elif session_id != self.session_id:
            raise ProtocolError("session mismatch")
        if message_type == "cancel":
            self.terminal = True
        self.expected_sequence += 1

    def eof(self) -> None:
        if not self.terminal:
            raise ProtocolError("EOF before terminal")
