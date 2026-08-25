"""Protocol-level tests for the paeos-bridge-v2 immutable envelopes.

Approved contract:
docs/superpowers/plans/2026-08-25-paeos-control-plane-recovery-subproject-1.md
"""

from pathlib import Path
from typing import Any

import pytest
from runtime.integrations.bridge_protocol import (
    SCHEMA_VERSION,
    BridgePaths,
    Disposition,
    ProtocolViolation,
    RequestEnvelope,
    ResponseEnvelope,
    canonical_json,
    content_hash,
    load_json,
    transaction_key,
    validate_request,
    validate_response,
    write_once_json,
)


def valid_request(**changes: object) -> RequestEnvelope:
    values: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "request_id": "req-001",
        "transaction_key": transaction_key(
            request_id="req-001",
            run_id="run-001",
            stage_id="L14",
            semantic_hash="a" * 64,
            evidence_manifest_hash="b" * 64,
            payload_hash="c" * 64,
        ),
        "created_at": "2026-08-25T10:00:00+00:00",
        "expires_at": "2026-08-25T10:10:00+00:00",
        "goal_id": "goal-001",
        "run_id": "run-001",
        "stage_id": "L14",
        "role": "BUILDER_OUTPUT_REVIEW",
        "workspace_root": "/private/tmp/paeos-control-plane-recovery-s1",
        "worker_transport_id": "cline:paeos-code",
        "worker_session_id": "session-001",
        "worker_pid": 4242,
        "worker_tty": "/dev/ttys001",
        "worker_model_provider": "openai",
        "worker_model_id": "implementation-model",
        "worker_model_family": "implementation-family",
        "semantic_hash": "a" * 64,
        "evidence_manifest_hash": "b" * 64,
        "payload_hash": "c" * 64,
        "allowed_dispositions": (
            Disposition.CONTINUE,
            Disposition.REMAND,
            Disposition.HALT,
            Disposition.NEEDS_FOUNDER,
        ),
    }
    values.update(changes)
    return RequestEnvelope(**values)


def valid_response(request: RequestEnvelope, **changes: object) -> ResponseEnvelope:
    text = "Evidence is incomplete; remand."
    values: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request.request_id,
        "transaction_key": request.transaction_key,
        "run_id": request.run_id,
        "stage_id": request.stage_id,
        "payload_hash": request.payload_hash,
        "lease_owner": "codex-overseer",
        "overseer_model_provider": "openai",
        "overseer_model_id": "gpt-5.6-sol",
        "overseer_model_family": "gpt-5.6",
        "disposition": Disposition.REMAND,
        "response_text": text,
        "response_hash": content_hash(text),
        "source_task_id": "codex-task-001",
        "completed_at": "2026-08-25T10:02:00+00:00",
    }
    values.update(changes)
    return ResponseEnvelope(**values)


def test_bridge_paths_are_contained_by_injected_root(tmp_path: Path) -> None:
    paths = BridgePaths(state_root=tmp_path / "state")
    bridge_root = paths.bridge_root
    assert bridge_root.is_relative_to(paths.state_root)
    for directory in (
        paths.requests,
        paths.responses,
        paths.quarantine,
        paths.transactions,
    ):
        assert directory.is_relative_to(bridge_root)
    assert bridge_root == (tmp_path / "state" / "bridge").resolve()


def test_canonical_hash_is_order_independent() -> None:
    ordered = {"alpha": 1, "beta": {"gamma": [True, 2], "delta": "x"}}
    shuffled = {"beta": {"delta": "x", "gamma": [True, 2]}, "alpha": 1}
    assert canonical_json(ordered) == canonical_json(shuffled)
    assert content_hash(ordered) == content_hash(shuffled)


def test_distinct_event_identity_changes_transaction_key() -> None:
    identity: dict[str, str] = {
        "request_id": "req-001",
        "run_id": "run-001",
        "stage_id": "L14",
        "semantic_hash": "a" * 64,
        "evidence_manifest_hash": "b" * 64,
        "payload_hash": "c" * 64,
    }
    baseline = transaction_key(**identity)
    assert baseline == transaction_key(**dict(identity))
    assert baseline != transaction_key(**{**identity, "request_id": "req-002"})


def test_request_rejects_missing_or_unknown_worker_identity() -> None:
    validate_request(valid_request())
    for field in ("worker_model_provider", "worker_model_id", "worker_model_family"):
        for bad in ("", "   ", "unknown", "None", "null", "UNAVAILABLE"):
            with pytest.raises(ProtocolViolation):
                validate_request(valid_request(**{field: bad}))


def test_request_allows_null_tty_only_for_declared_headless_transport() -> None:
    with pytest.raises(ProtocolViolation):
        validate_request(valid_request(worker_tty=None))

    headless = valid_request(
        worker_transport_id="headless:cline-paeos-code",
        worker_tty=None,
    )
    validate_request(headless)

    with pytest.raises(ProtocolViolation):
        validate_request(
            valid_request(
                worker_transport_id="headless:cline-paeos-code",
                worker_tty=None,
                worker_session_id="",
            )
        )
    with pytest.raises(ProtocolViolation):
        validate_request(
            valid_request(
                worker_transport_id="headless:cline-paeos-code",
                worker_tty=None,
                worker_pid=0,
            )
        )


def test_response_disposition_has_no_ratify_member() -> None:
    assert [member.value for member in Disposition] == [
        "CONTINUE",
        "REMAND",
        "HALT",
        "NEEDS_FOUNDER",
    ]
    assert not hasattr(Disposition, "RATIFY")

    request = valid_request()
    response = valid_response(request)
    validate_response(response)
    assert response.request_id == request.request_id
    assert response.transaction_key == request.transaction_key
    assert response.payload_hash == request.payload_hash
    assert response.disposition is Disposition.REMAND


def test_write_once_json_refuses_overwrite(tmp_path: Path) -> None:
    paths = BridgePaths(state_root=tmp_path / "state")
    paths.ensure()
    target = paths.transactions / "tx-001.json"
    first = {"schema_version": SCHEMA_VERSION, "state": "NEW", "sequence": 1}
    write_once_json(target, first)
    original = target.read_bytes()

    second = {
        "schema_version": SCHEMA_VERSION,
        "state": "RESPONDED",
        "sequence": 2,
    }
    with pytest.raises(FileExistsError):
        write_once_json(target, second)

    assert target.read_bytes() == original
    assert load_json(target) == first


def test_load_json_rejects_malformed_input(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed_bytes = b'{"state": "NEW", "sequence": '
    malformed.write_bytes(malformed_bytes)
    with pytest.raises(ProtocolViolation):
        load_json(malformed)
    assert malformed.read_bytes() == malformed_bytes

    non_object = tmp_path / "array.json"
    non_object_bytes = b'["NEW", "PREPARED"]'
    non_object.write_bytes(non_object_bytes)
    with pytest.raises(ProtocolViolation):
        load_json(non_object)
    assert non_object.read_bytes() == non_object_bytes

    invalid_utf8 = tmp_path / "binary.json"
    invalid_utf8_bytes = b"\xff\xfe\x00corrupted"
    invalid_utf8.write_bytes(invalid_utf8_bytes)
    with pytest.raises(ProtocolViolation):
        load_json(invalid_utf8)
    assert invalid_utf8.read_bytes() == invalid_utf8_bytes
