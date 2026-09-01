"""Frame, state-machine, and policy-free Node SDK-host tests."""

from __future__ import annotations

import hashlib
import io
import json
import os
import select
import subprocess
from pathlib import Path

import pytest
from runtime.integrations.cline_sdk_protocol import (
    MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    HostEventMachine,
    ProtocolError,
    PythonCommandMachine,
    encode_frame,
    read_frame,
)

ROOT = Path(__file__).parents[2]
HOST = ROOT / "runtime/integrations/cline_sdk_host.mjs"
FAKE_SDK = ROOT / "tests/fixtures/cline_sdk/fake_sdk.mjs"


def _host_env() -> dict[str, str]:
    env = os.environ.copy()
    env["CLINE_DATA_DIR"] = "/profile"
    return env


def _host_event(
    event_type: str,
    sequence: int,
    *,
    invocation_id: str = "probe-004",
    session_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "invocation_id": invocation_id,
        "payload": payload or {},
        "protocol_version": PROTOCOL_VERSION,
        "sequence": sequence,
        "type": event_type,
    }
    if session_id is not None:
        value["session_id"] = session_id
    return value


def _start_message(sequence: int = 0) -> dict[str, object]:
    digest = hashlib.sha256(FAKE_SDK.read_bytes()).hexdigest()
    return {
        "invocation_id": "probe-004",
        "payload": {
            "backend_mode": "local",
            "core_entrypoint": str(FAKE_SDK),
            "core_sha256": digest,
            "cwd": "/sandbox",
            "max_declared_model_turns": 3,
            "model_id": "cline-pass/qwen3.8-max",
            "prompt": "perform the disposable probe",
            "provider_id": "cline-pass",
            "sdk_entrypoint": str(FAKE_SDK),
            "sdk_sha256": digest,
            "session_id": "session-004",
        },
        "protocol_version": PROTOCOL_VERSION,
        "sequence": sequence,
        "type": "start",
    }


def _read(process: subprocess.Popen[bytes]) -> dict[str, object]:
    assert process.stdout is not None
    return read_frame(process.stdout)


def _write(process: subprocess.Popen[bytes], message: dict[str, object]) -> None:
    assert process.stdin is not None
    process.stdin.write(encode_frame(message))
    process.stdin.flush()


def test_frame_round_trip_is_canonical_json() -> None:
    message = {"z": 2, "a": {"y": 1, "b": True}}
    encoded = encode_frame(message)

    assert encoded[4:] == b'{"a":{"b":true,"y":1},"z":2}'
    assert read_frame(io.BytesIO(encoded)) == message
    assert encode_frame(read_frame(io.BytesIO(encoded))) == encoded


def test_frame_canonicalization_uses_utf8_not_ascii_escape() -> None:
    encoded = encode_frame({"value": "café"})

    assert encoded[4:] == '{"value":"café"}'.encode()
    assert b"\\u00e9" not in encoded


@pytest.mark.parametrize(
    "payload",
    [
        b"\x00\x00\x00\x00",
        (MAX_FRAME_BYTES + 1).to_bytes(4, "big"),
        b"\x00\x00\x00\x05{}",
        b"\x00\x00\x00\x02\xff\xff",
        b"\x00\x00\x00\x02[]",
        b'\x00\x00\x00\x08{"z": 1}',
    ],
)
def test_invalid_or_noncanonical_frame_terminates(payload: bytes) -> None:
    with pytest.raises(ProtocolError):
        read_frame(io.BytesIO(payload))


def test_unknown_message_type_terminates() -> None:
    machine = HostEventMachine("probe-004")
    with pytest.raises(ProtocolError, match="type"):
        machine.accept(_host_event("surprise", 0))


def test_sequence_gap_duplicate_and_cross_invocation_terminate() -> None:
    machine = HostEventMachine("probe-004")
    machine.accept(_host_event("hello", 0))
    for bad in (
        _host_event("session_created", 0, session_id="session-004"),
        _host_event("session_created", 2, session_id="session-004"),
        _host_event("session_created", 1, invocation_id="probe-other", session_id="session-004"),
    ):
        with pytest.raises(ProtocolError):
            machine.accept(bad)


def test_duplicate_terminal_and_post_terminal_terminate() -> None:
    machine = HostEventMachine("probe-004")
    machine.accept(_host_event("hello", 0))
    machine.accept(_host_event("session_created", 1, session_id="session-004"))
    machine.accept(_host_event("terminal", 2, session_id="session-004"))

    with pytest.raises(ProtocolError, match="terminal"):
        machine.accept(_host_event("terminal", 3, session_id="session-004"))


def test_terminal_with_unfinished_provider_attempt_terminates() -> None:
    machine = HostEventMachine("probe-004")
    machine.accept(_host_event("hello", 0))
    machine.accept(_host_event("session_created", 1, session_id="session-004"))
    machine.accept(
        _host_event(
            "provider_attempt_started",
            2,
            session_id="session-004",
            payload={"correlation_id": "attempt-001"},
        )
    )

    with pytest.raises(ProtocolError, match="unfinished"):
        machine.accept(_host_event("terminal", 3, session_id="session-004"))


def test_legacy_bound_transport_can_opt_into_legacy_tool_identity() -> None:
    machine = HostEventMachine("probe-004", strict_tool_identity=False)
    machine.accept(_host_event("hello", 0))
    machine.accept(_host_event("session_created", 1, session_id="session-legacy"))
    machine.accept(
        _host_event(
            "provider_attempt_started",
            2,
            session_id="session-legacy",
            payload={"correlation_id": "attempt-legacy"},
        )
    )
    machine.accept(
        _host_event(
            "provider_attempt_finished",
            3,
            session_id="session-legacy",
            payload={"correlation_id": "attempt-legacy"},
        )
    )
    machine.accept(
        _host_event(
            "tool_request",
            4,
            session_id="session-legacy",
            payload={
                "call_id": "call-legacy",
                "input": {"path": "artifact.txt"},
                "tool_name": "editor",
            },
        )
    )


def test_second_start_and_eof_before_terminal_terminate() -> None:
    machine = PythonCommandMachine("probe-004")
    machine.accept(_start_message())
    with pytest.raises(ProtocolError, match="start"):
        machine.accept(_start_message(sequence=1))
    with pytest.raises(ProtocolError, match="EOF"):
        machine.eof()


def test_node_host_forwards_tool_request_and_waits_for_python_decision() -> None:
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_host_env(),
    )
    try:
        _write(process, _start_message())
        events = [_read(process) for _ in range(5)]
        assert [event["type"] for event in events] == [
            "hello",
            "session_created",
            "capability_snapshot",
            "provider_attempt_started",
            "provider_attempt_finished",
        ]
        tool_request = _read(process)
        assert tool_request["type"] == "tool_request"
        assert tool_request["payload"]["tool_name"] == "editor"  # type: ignore[index]

        assert process.stdout is not None
        readable, _, _ = select.select([process.stdout], [], [], 0.15)
        assert readable == []

        _write(
            process,
            {
                "invocation_id": "probe-004",
                "payload": {
                    "approved": True,
                    "call_id": "tool-call-001",
                    "phase": "approval",
                    "result": {},
                },
                "protocol_version": PROTOCOL_VERSION,
                "sequence": 1,
                "session_id": "session-004",
                "type": "tool_response",
            },
        )
        snapshot = _read(process)
        terminal = _read(process)
        assert snapshot["type"] == "session_snapshot"
        assert terminal["type"] == "terminal"
        process.wait(timeout=5)
        assert process.returncode == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_node_host_adapts_canonical_tool_approval_identity(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CLINE_DATA_DIR"] = str(tmp_path / "cline")
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    message = _start_message()
    message["payload"]["prompt"] = "PAEOS_SDK_PROBE:" + json.dumps(
        {
            "artifact_path": "/sandbox/artifact.txt",
            "expected_text": "admitted-worker\n",
            "initial_text": "baseline-worker\n",
            "probe_id": "probe-canonical-approval",
            "verification_command": "python3 verify_probe.py",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        _write(process, message)
        events = [_read(process) for _ in range(6)]
        assert events[-1]["type"] == "tool_request"
        assert events[-1]["payload"]["call_id"] == "tool-call-001"  # type: ignore[index]
        assert events[-1]["payload"]["phase"] == "approval"  # type: ignore[index]
        _write(
            process,
            {
                "invocation_id": "probe-004",
                "payload": {
                    "approved": True,
                    "call_id": "tool-call-001",
                    "phase": "approval",
                    "result": {},
                },
                "protocol_version": PROTOCOL_VERSION,
                "sequence": 1,
                "session_id": "session-004",
                "type": "tool_response",
            },
        )
        execution = _read(process)
        assert execution["type"] == "tool_request"
        assert execution["payload"]["call_id"] == "tool-call-001"  # type: ignore[index]
        assert execution["payload"]["phase"] == "execution"  # type: ignore[index]
        _write(
            process,
            {
                "invocation_id": "probe-004",
                "payload": {
                    "approved": True,
                    "call_id": "tool-call-001",
                    "phase": "execution",
                    "result": {},
                },
                "protocol_version": PROTOCOL_VERSION,
                "sequence": 2,
                "session_id": "session-004",
                "type": "tool_response",
            },
        )
        second = _read(process)
        assert second["type"] == "provider_attempt_started"
        finished = _read(process)
        assert finished["type"] == "provider_attempt_finished"
        second_tool = _read(process)
        assert second_tool["type"] == "tool_request"
        assert second_tool["payload"]["call_id"] == "tool-call-002"  # type: ignore[index]
        assert second_tool["payload"]["phase"] == "approval"  # type: ignore[index]
        _write(
            process,
            {
                "invocation_id": "probe-004",
                "payload": {
                    "approved": True,
                    "call_id": "tool-call-002",
                    "phase": "approval",
                    "result": {},
                },
                "protocol_version": PROTOCOL_VERSION,
                "sequence": 3,
                "session_id": "session-004",
                "type": "tool_response",
            },
        )
        second_execution = _read(process)
        assert second_execution["type"] == "tool_request"
        assert second_execution["payload"]["call_id"] == "tool-call-002"  # type: ignore[index]
        assert second_execution["payload"]["phase"] == "execution"  # type: ignore[index]
        _write(
            process,
            {
                "invocation_id": "probe-004",
                "payload": {
                    "approved": True,
                    "call_id": "tool-call-002",
                    "phase": "execution",
                    "result": {},
                },
                "protocol_version": PROTOCOL_VERSION,
                "sequence": 4,
                "session_id": "session-004",
                "type": "tool_response",
            },
        )
        third = _read(process)
        assert third["type"] == "provider_attempt_started"
        third_finished = _read(process)
        assert third_finished["type"] == "provider_attempt_finished"
        snapshot = _read(process)
        terminal = _read(process)
        assert snapshot["type"] == "session_snapshot"
        assert terminal["type"] == "terminal"
        process.wait(timeout=5)
        assert process.returncode == 0
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def test_node_host_emits_terminal_failure_when_core_start_raises(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CLINE_DATA_DIR"] = str(tmp_path / "cline")
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    message = _start_message()
    message["payload"]["prompt"] = "PAEOS_SDK_PROBE:" + json.dumps(
        {
            "artifact_path": "/sandbox/artifact.txt",
            "expected_text": "admitted-worker\n",
            "initial_text": "baseline-worker\n",
            "probe_id": "probe-start-throws",
            "verification_command": "python3 verify_probe.py",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        _write(process, message)
        events: list[dict[str, object]] = []
        for _ in range(4):
            event = _read(process)
            events.append(event)
            if event["type"] in {"terminal", "failure", "cancelled"}:
                break
        assert events[-1]["type"] == "failure"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def test_node_host_binds_session_before_early_provider_attempt(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CLINE_DATA_DIR"] = str(tmp_path / "cline")
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    message = _start_message()
    message["payload"]["prompt"] = "PAEOS_SDK_PROBE:" + json.dumps(
        {
            "artifact_path": "/sandbox/artifact.txt",
            "expected_text": "admitted-worker\n",
            "initial_text": "baseline-worker\n",
            "probe_id": "probe-early-provider-attempt",
            "verification_command": "python3 verify_probe.py",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        _write(process, message)
        first = [_read(process) for _ in range(4)]
        assert [event["type"] for event in first] == [
            "hello",
            "session_created",
            "provider_attempt_started",
            "provider_attempt_finished",
        ]
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def test_node_host_consumes_real_sdk_ended_event(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CLINE_DATA_DIR"] = str(tmp_path / "cline")
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    message = _start_message()
    message["payload"]["prompt"] = "PAEOS_SDK_PROBE:" + json.dumps(
        {
            "artifact_path": "/sandbox/artifact.txt",
            "expected_text": "admitted-worker\n",
            "initial_text": "baseline-worker\n",
            "probe_id": "probe-ended-event",
            "verification_command": "python3 verify_probe.py",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        _write(process, message)
        events: list[dict[str, object]] = []
        for _ in range(8):
            event = _read(process)
            events.append(event)
            if event["type"] in {"terminal", "failure", "cancelled"}:
                break
        assert [event["type"] for event in events] == [
            "hello",
            "session_created",
            "capability_snapshot",
            "session_snapshot",
            "terminal",
        ]
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def test_node_host_normalizes_known_auth_start_failure(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CLINE_DATA_DIR"] = str(tmp_path / "cline")
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    message = _start_message()
    message["payload"]["prompt"] = "PAEOS_SDK_PROBE:" + json.dumps(
        {
            "artifact_path": "/sandbox/artifact.txt",
            "expected_text": "admitted-worker\n",
            "initial_text": "baseline-worker\n",
            "probe_id": "probe-start-auth-error",
            "verification_command": "python3 verify_probe.py",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        _write(process, message)
        events: list[dict[str, object]] = []
        for _ in range(4):
            event = _read(process)
            events.append(event)
            if event["type"] in {"terminal", "failure", "cancelled"}:
                break
        assert events[-1]["type"] == "failure"
        payload = events[-1]["payload"]
        assert payload["error_class"] == "OAuthReauthRequiredError"
        assert payload["normalized_error"] == "AUTH_FAILED"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def test_attempt_events_are_matched_and_content_free() -> None:
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_host_env(),
    )
    try:
        _write(process, _start_message())
        events = [_read(process) for _ in range(6)]
        started = next(event for event in events if event["type"] == "provider_attempt_started")
        finished = next(event for event in events if event["type"] == "provider_attempt_finished")
        assert started["payload"]["correlation_id"] == finished["payload"]["correlation_id"]  # type: ignore[index]
        serialized = repr((started, finished))
        assert "synthetic-secret" not in serialized
        assert "private-prompt" not in serialized
        assert "Authorization" not in serialized
        assert "data:application" not in serialized
    finally:
        process.kill()
        process.wait(timeout=5)


def test_second_fetch_before_tool_result_is_same_turn_retry_and_fails_closed() -> None:
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_host_env(),
    )
    message = _start_message()
    message["payload"]["prompt"] = "double-fetch-before-tool"  # type: ignore[index]
    try:
        _write(process, message)
        events: list[dict[str, object]] = []
        for _ in range(12):
            assert process.stdout is not None
            readable, _, _ = select.select([process.stdout], [], [], 2)
            assert readable
            event = _read(process)
            events.append(event)
            if event["type"] in {"terminal", "failure", "cancelled", "tool_request"}:
                break
        starts = [event for event in events if event["type"] == "provider_attempt_started"]
        assert [event["payload"]["turn_id"] for event in starts] == ["turn-1", "turn-1"]  # type: ignore[index]
        assert [event["payload"]["attempt_ordinal"] for event in starts] == [1, 2]  # type: ignore[index]
        assert events[-1]["type"] == "failure"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def test_host_rejects_hash_mismatch_before_import() -> None:
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    message = _start_message()
    message["payload"]["sdk_sha256"] = "0" * 64  # type: ignore[index]
    _write(process, message)
    process.wait(timeout=5)

    assert process.returncode != 0
    assert FAKE_SDK.name not in (process.stderr.read().decode() if process.stderr else "")


def test_host_rejects_relative_entrypoint_even_when_hash_matches() -> None:
    process = subprocess.Popen(
        ["node", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=ROOT,
    )
    message = _start_message()
    relative = str(FAKE_SDK.relative_to(ROOT))
    message["payload"]["sdk_entrypoint"] = relative  # type: ignore[index]
    message["payload"]["core_entrypoint"] = relative  # type: ignore[index]
    _write(process, message)
    timed_out = False
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait(timeout=5)

    assert not timed_out
    assert process.returncode != 0
