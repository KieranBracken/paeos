from __future__ import annotations

import json
import threading
import time
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


def test_client_requires_fixed_workspace_root_and_signed_response(tmp_path: Path) -> None:
    from runtime.integrations.trusted_codex_transport import HostCodexWorkerTransport

    request_key = SigningKey.generate()
    response_key = SigningKey.generate()
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()
    workspace = workspace_root / "ws-transport"
    workspace.mkdir()
    queue = tmp_path / "queue"
    client = HostCodexWorkerTransport(
        queue_root=queue,
        workspace_root=workspace_root,
        request_signing_key=request_key,
        response_verify_key=response_key.verify_key,
        timeout_s=1,
    )

    def respond() -> None:
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            requests = list(queue.glob("*.request.json"))
            if requests:
                request = json.loads(requests[0].read_text(encoding="utf-8"))
                response = json.loads(_signed_response(response_key, workspace=workspace))
                response["payload"]["request_id"] = request["request_id"]
                response["payload"]["observation"]["request_id"] = request["request_id"]
                signed_payload = response["payload"]
                response["signature"] = response_key.sign(
                    __import__(
                        "ops.trusted_codex_worker_supervisor", fromlist=["_canonical_bytes"]
                    )._canonical_bytes(signed_payload)
                ).signature.hex()
                (queue / f"{request['request_id']}.response.json").write_text(
                    json.dumps(response), encoding="utf-8"
                )
                return
            time.sleep(0.01)

    thread = threading.Thread(target=respond)
    thread.start()
    result = client.run(_spec(workspace))
    thread.join()

    assert result.transcript.startswith('{"type":"run_result"')
    assert result.lifecycle_state == "RETURNED"
    assert result.environment_fingerprint == "b" * 64


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
