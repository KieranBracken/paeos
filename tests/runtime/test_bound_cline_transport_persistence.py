"""Persistence tests for the bound worker transport's create-only evidence."""

from __future__ import annotations

from pathlib import Path

import pytest
from runtime.integrations.bound_cline_transport import (
    HandoffRecord,
    SideEffectCertainty,
    TransportFailure,
    TransportFailureKind,
    TransportProtocolError,
    _persist_handoff_once,
    _persist_response_once,
    _quarantine_failure_once,
)
from runtime.integrations.bridge_protocol import (
    SCHEMA_VERSION,
    BridgePaths,
    Disposition,
    ResponseEnvelope,
    canonical_json,
    content_hash,
)


def _response() -> ResponseEnvelope:
    return ResponseEnvelope(
        schema_version=SCHEMA_VERSION,
        request_id="request-1",
        transaction_key="a" * 64,
        run_id="run-1",
        stage_id="L12",
        payload_hash="d" * 64,
        lease_owner="overseer-1",
        overseer_model_provider="google",
        overseer_model_id="gemini-3.6-flash",
        overseer_model_family="gemini",
        disposition=Disposition.CONTINUE,
        response_text="worker result",
        response_hash=content_hash("worker result"),
        source_task_id="task-1",
        completed_at="2026-08-31T01:00:00Z",
    )


def _failure() -> TransportFailure:
    return TransportFailure(
        kind=TransportFailureKind.TIMEOUT,
        request_id="request-1",
        transaction_key="a" * 64,
        message="secret worker prose must not be persisted",
        side_effect_certainty=SideEffectCertainty.UNKNOWN,
        stdout_hash="c" * 64,
        stderr_hash="d" * 64,
        exit_code=None,
    )


def _handoff() -> HandoffRecord:
    return HandoffRecord(
        request_id="request-1",
        transaction_key="a" * 64,
        candidate_head="e" * 40,
        branch_name="codex/recovery",
        session_id="session-1",
        provider_id="cline-pass",
        model_id="z-ai/glm-5.3-flash",
        model_family="glm",
        policy_sha256="f" * 64,
        stdout_hash="c" * 64,
        stderr_hash="d" * 64,
        next_action="AWAIT_OVERSEER_REVIEW",
    )


def test_response_is_create_only_and_hash_bound(tmp_path: Path) -> None:
    paths = BridgePaths(tmp_path / "state")
    response = _response()
    response_path = _persist_response_once(paths, response)
    assert response_path.read_text() == canonical_json(response) + "\n"
    assert response_path.stat().st_mode & 0o777 == 0o600
    assert _persist_response_once(paths, response) == response_path


def test_preexisting_response_is_not_overwritten(tmp_path: Path) -> None:
    paths = BridgePaths(tmp_path / "state")
    paths.ensure()
    target = paths.responses / "request-1.json"
    target.write_bytes(b"different\n")
    with pytest.raises(TransportProtocolError, match="different content"):
        _persist_response_once(paths, _response())
    assert target.read_bytes() == b"different\n"


def test_timeout_writes_only_content_free_failure_and_handoff(tmp_path: Path) -> None:
    paths = BridgePaths(tmp_path / "state")
    quarantine = _quarantine_failure_once(paths, _failure())
    handoff_path = _persist_handoff_once(paths, _handoff())
    assert quarantine.path.exists()
    assert handoff_path.exists()
    quarantine_text = quarantine.path.read_text()
    assert "secret worker prose" not in quarantine_text
    assert "TIMEOUT" in quarantine_text
    assert not (paths.responses / "request-1.json").exists()
