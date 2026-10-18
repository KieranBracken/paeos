from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from nacl.signing import SigningKey
from runtime.integrations import SessionSpec


def _signed_response(
    key: SigningKey,
    *,
    workspace: Path,
    observation_workspace: str | None = None,
    **overrides: object,
) -> bytes:
    from ops.trusted_codex_worker_supervisor import _canonical_bytes

    transcript = '{"type":"run_result","finishReason":"completed"}\n'
    observation: dict[str, object] = {
        "provider_id": "codex",
        "model_id": "gpt-5.6-sol",
        "family": "gpt",
        "request_id": "a" * 32,
        "task_id": "t-transport",
        "goal_id": "g-transport",
        "run_id": "r-transport",
        "stage": "IMPLEMENT",
        "workspace_id": workspace.name,
        "workspace": str(workspace) if observation_workspace is None else observation_workspace,
        "transcript": transcript,
        "stdout_sha256": __import__("hashlib").sha256(transcript.encode()).hexdigest(),
        "stderr_sha256": __import__("hashlib").sha256(b"").hexdigest(),
        "stdout_bytes": len(transcript.encode()),
        "stderr_bytes": 0,
        "exit_code": 0,
        "process_state": "RETURNED",
        "lifecycle": ["STARTING", "RUNNING", "PROGRESS", "COMPLETED"],
        "heartbeat_count": 1,
        "executable": "/opt/homebrew/bin/codex",
        "executable_version": "sha256:" + "a" * 64,
        "environment_fingerprint": "b" * 64,
        "profile_sha256": "c" * 64,
        "broker_evidence_sha256": "d" * 64,
        "broker_request_count": 1,
        "supervisor_identity_sha256": __import__("hashlib")
        .sha256(bytes(key.verify_key))
        .hexdigest(),
        "boot_id": "boot-transport",
        "artifact_sha256": "e" * 64,
        "canaries": {
            "approved_read": "PASS",
            "approved_write": "PASS",
            "forbidden_read_denied": "PASS",
            "forbidden_write_denied": "PASS",
            "parent_secret_invisible": "PASS",
            "provider_credential_absent": "PASS",
            "symlink_escape_denied": "PASS",
            "traversal_escape_denied": "PASS",
            "child_subprocess_confined": "PASS",
            "broker_capability_task_scoped": "PASS",
            "supervisor_restart_no_fallback": "PASS",
        },
        "fallback_used": False,
        "manual_chat_bridge": False,
    }
    observation.update(overrides)
    payload = {
        "schema": "paeos.trusted-codex-worker-service/1",
        "ok": True,
        "request_id": "a" * 32,
        "observation": observation,
    }
    return _canonical_bytes(
        {"payload": payload, "signature": key.sign(_canonical_bytes(payload)).signature.hex()}
    )


def _signed_failure_response(
    key: SigningKey,
    *,
    request_id: str = "a" * 32,
    error_code: str = "provider_execution_failure",
    failure_observation: dict[str, object] | None = None,
    **overrides: object,
) -> bytes:
    from ops.trusted_codex_worker_supervisor import _canonical_bytes

    payload: dict[str, object] = {
        "schema": "paeos.trusted-codex-worker-service/1",
        "ok": False,
        "request_id": request_id,
        "error_code": error_code,
        "error": "trusted Codex launch rejected or failed closed",
    }
    if failure_observation is not None:
        payload["failure_observation"] = failure_observation
    payload.update(overrides)
    return _canonical_bytes(
        {"payload": payload, "signature": key.sign(_canonical_bytes(payload)).signature.hex()}
    )


def _spec(workspace: Path) -> SessionSpec:
    return SessionSpec(
        workspace=workspace,
        prompt="bounded",
        allowed_tools=(),
        read_scopes=(),
        timeout_s=2,
        task_id="t-transport",
        goal_id="g-transport",
        run_id="r-transport",
        stage="IMPLEMENT",
    )


class _CountingSigner:
    def __init__(self) -> None:
        self.calls = 0

    def sign(self, _message: bytes) -> None:
        self.calls += 1
        raise AssertionError("request signing must not be reached")


def _assert_disclosure_denial_has_no_effects(
    transport: object,
    signer: _CountingSigner,
    *,
    queue_root: Path,
    evidence_root: Path | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import runtime.integrations.trusted_codex_transport as codex_transport
    from runtime.integrations import TrustedTransportFailure

    spec_accesses: list[str] = []
    effects: list[str] = []

    class _UninspectableSpec:
        def __getattribute__(self, name: str) -> object:
            spec_accesses.append(name)
            raise AssertionError("session data must not be read before disclosure authorization")

    def blocked(label: str):
        def fail(*_args: object, **_kwargs: object) -> None:
            effects.append(label)
            raise AssertionError(f"unexpected transport effect: {label}")

        return fail

    class _NoClockAccess:
        def __getattr__(self, name: str) -> object:
            effects.append(f"clock:{name}")
            raise AssertionError("clock access must not occur before disclosure authorization")

    with monkeypatch.context() as guard:
        for method in (
            "resolve",
            "is_symlink",
            "is_dir",
            "exists",
            "is_file",
            "read_bytes",
            "write_bytes",
            "write_text",
            "open",
            "unlink",
        ):
            guard.setattr(Path, method, blocked(f"path:{method}"))
        guard.setattr(codex_transport, "_write_atomic", blocked("queue-write"))
        guard.setattr(codex_transport, "_write_receipt_once", blocked("evidence-write"))
        guard.setattr(codex_transport, "_canonical_bytes", blocked("serialization"))
        guard.setattr(codex_transport, "_sha256", blocked("hashing"))
        guard.setattr(codex_transport, "time", _NoClockAccess())
        with pytest.raises(TrustedTransportFailure) as raised:
            transport.run(_UninspectableSpec())  # type: ignore[attr-defined]

    assert raised.value.code == "disclosure_authority_unavailable"
    assert str(raised.value) == "trusted disclosure authority is unavailable"
    assert spec_accesses == []
    assert effects == []
    assert signer.calls == 0
    assert not os.path.lexists(queue_root)
    if evidence_root is not None:
        assert not os.path.lexists(evidence_root)
    assert transport.last_request_sha256 is None  # type: ignore[attr-defined]
    assert transport.last_response_sha256 is None  # type: ignore[attr-defined]
    assert transport.last_observation is None  # type: ignore[attr-defined]


def test_client_denies_run_without_trusted_disclosure_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from runtime.integrations.trusted_codex_transport import HostCodexWorkerTransport

    workspace_root = tmp_path / "workspaces"
    queue = tmp_path / "queue"
    evidence = tmp_path / "evidence"
    request_signer = _CountingSigner()
    client = HostCodexWorkerTransport(
        queue_root=queue,
        workspace_root=workspace_root,
        request_signing_key=request_signer,  # type: ignore[arg-type]
        response_verify_key=SigningKey.generate().verify_key,
        timeout_s=1,
        evidence_root=evidence,
    )

    _assert_disclosure_denial_has_no_effects(
        client,
        request_signer,
        queue_root=queue,
        evidence_root=evidence,
        monkeypatch=monkeypatch,
    )

    from runtime.integrations.trusted_codex_planner_transport import HostCodexPlannerTransport

    planner_queue = tmp_path / "planner-queue"
    planner_evidence = tmp_path / "planner-evidence"
    planner_signer = _CountingSigner()
    planner = HostCodexPlannerTransport(
        queue_root=planner_queue,
        workspace_root=workspace_root,
        request_signing_key=planner_signer,  # type: ignore[arg-type]
        response_verify_key=SigningKey.generate().verify_key,
        timeout_s=1,
        evidence_root=planner_evidence,
    )
    _assert_disclosure_denial_has_no_effects(
        planner,
        planner_signer,
        queue_root=planner_queue,
        evidence_root=planner_evidence,
        monkeypatch=monkeypatch,
    )


def test_client_rejects_response_with_fallback_or_wrong_workspace(tmp_path: Path) -> None:
    from runtime.integrations.trusted_codex_transport import (
        HostCodexWorkerTransport,
        TrustedCodexTransportError,
    )

    request_key = SigningKey.generate()
    response_key = SigningKey.generate()
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()
    workspace = workspace_root / "ws-transport"
    workspace.mkdir()
    client = HostCodexWorkerTransport(
        queue_root=tmp_path / "queue",
        workspace_root=workspace_root,
        request_signing_key=request_key,
        response_verify_key=response_key.verify_key,
        timeout_s=1,
    )
    with pytest.raises(TrustedCodexTransportError, match="unqualified"):
        client._validate_response(
            json.loads(
                _signed_response(
                    response_key,
                    workspace=workspace,
                    observation_workspace="/tmp/other",
                )
            ),
            request_id="a" * 32,
            spec=_spec(workspace),
        )


@pytest.mark.parametrize("exit_code", [17, -15, -9])
def test_client_accepts_signed_bounded_worker_failure(tmp_path: Path, exit_code: int) -> None:
    from runtime.integrations.trusted_codex_transport import HostCodexWorkerTransport

    request_key = SigningKey.generate()
    response_key = SigningKey.generate()
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()
    workspace = workspace_root / "ws-transport"
    workspace.mkdir()
    client = HostCodexWorkerTransport(
        queue_root=tmp_path / "queue",
        workspace_root=workspace_root,
        request_signing_key=request_key,
        response_verify_key=response_key.verify_key,
        timeout_s=1,
    )
    response = json.loads(
        _signed_failure_response(
            response_key,
            failure_observation={
                "lifecycle_state": "FAILED",
                "exit_code": exit_code,
                "stdout_bytes": 0,
                "stdout_sha256": "a" * 64,
                "stderr_bytes": 0,
                "stderr_sha256": "b" * 64,
            },
        )
    )

    result = client._validate_response(response, request_id="a" * 32, spec=_spec(workspace))

    assert result.failure_code == "provider_execution_failure"
    assert result.lifecycle_state == "FAILED"
    assert result.exit_code == exit_code
    assert result.transcript == "trusted_worker_failure:provider_execution_failure"
    assert client.last_observation == response["payload"]["failure_observation"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"unexpected": "field"},
        {"error_code": "unknown_failure"},
        {"error": "provider supplied details"},
        {
            "failure_observation": {
                "lifecycle_state": "FAILED",
                "exit_code": 1,
                "stdout_bytes": 0,
                "stdout_sha256": "a" * 64,
                "stderr_bytes": 0,
                "stderr_sha256": "b" * 64,
                "raw_stderr": "must not cross boundary",
            }
        },
    ],
)
def test_client_rejects_unbounded_or_malformed_worker_failure(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    from runtime.integrations.trusted_codex_transport import (
        HostCodexWorkerTransport,
        TrustedCodexTransportError,
    )

    request_key = SigningKey.generate()
    response_key = SigningKey.generate()
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()
    workspace = workspace_root / "ws-transport"
    workspace.mkdir()
    client = HostCodexWorkerTransport(
        queue_root=tmp_path / "queue",
        workspace_root=workspace_root,
        request_signing_key=request_key,
        response_verify_key=response_key.verify_key,
        timeout_s=1,
    )

    with pytest.raises(TrustedCodexTransportError):
        client._validate_response(
            json.loads(_signed_failure_response(response_key, **overrides)),
            request_id="a" * 32,
            spec=_spec(workspace),
        )
