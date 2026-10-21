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


# Synthetic queue peer: known inline bytes, real canonical TEST authority, no parent read.
def _tool_client_fixture(tmp_path):
    import hashlib
    import importlib.util

    from kernel.ledger import Ledger
    from kernel.ledger_sqlite import SqliteLedgerStore
    from nacl.signing import VerifyKey
    from runtime.autonomy.admission_send_fence import AdmissionSendFence, SendOperation
    from runtime.integrations import trusted_codex_transport as client_module

    fixture_path = Path(__file__).parent / "autonomy/test_admission_authority.py"
    spec = importlib.util.spec_from_file_location("synthetic_tool_wire_fixtures", fixture_path)
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    workspaces = tmp_path / "workspaces"
    workspace = workspaces / "ws-transport"
    workspace.mkdir(parents=True)
    session = _spec(workspace)
    fixtures.BINDINGS = dict(
        fixtures.BINDINGS,
        goal_id=session.goal_id,
        task_id=session.task_id,
        run_id=session.run_id,
        stage=session.stage,
        workspace_id=workspace.name,
        route_id=client_module._ROUTE_ID,
        route_digest=client_module._ROUTE_DIGEST,
    )
    store = SqliteLedgerStore(tmp_path / "synthetic-tool.db")
    f = fixtures.tool_fixture(Ledger(store))
    f.update(
        fixtures=fixtures, store=store, session=session, database=tmp_path / "synthetic-tool.db"
    )
    f["request_id"] = "a" * 32
    f["request"] = fixtures.tool_request(f, changes={"request_id": f["request_id"]})
    request = json.loads(f["request"])["body"]
    f["binding"] = fixtures.wire_json(
        {
            k: request[k]
            for k in ("context", "parent_identity_sha256", "parent_boot_id", "parent_process_id")
        }
    )
    f["fence"] = AdmissionSendFence(
        f["ledger"], authority=f["authority"], domain_tag="TEST", now=lambda: fixtures.NOW
    )
    f["fence"].acquire_send_lease(
        SendOperation(
            admission_ref="admission",
            expected_epoch=1,
            request_id=f["request_id"],
            frame=b"frame",
            operation_kind="WORKER_LAUNCH",
            frame_ordinal=0,
            **fixtures.BINDINGS,
        )
    )
    queue = tmp_path / "queue"
    queue.mkdir()
    f["kwargs"] = dict(
        queue_root=queue,
        workspace_root=workspaces,
        request_signing_key=SigningKey.generate(),
        response_verify_key=VerifyKey(f["parent"].public_key().public_bytes_raw()),
        admission_send_fence=f["fence"],
        admission_ref="admission",
        expected_admission_epoch=1,
        parent_tool_authority=f["authority"],
        parent_tool_binding=f["binding"],
        parent_tool_ack_issuer_id="issuer",
        parent_tool_ack_signer=f["issuer"].sign,
    )
    f["client"] = client_module.HostCodexWorkerTransport(**f["kwargs"])
    f["client"].last_request_sha256 = hashlib.sha256(b"frame").hexdigest()
    return f


def _tool_queue_event(f, file_phase, raw, **changes):
    import base64

    wrapper = dict(
        schema="paeos.parent-tool-queue-event/1",
        request_id=f["request_id"],
        phase=file_phase,
        envelope_b64=base64.b64encode(raw).decode(),
    )
    wrapper.update(changes)
    path = f["kwargs"]["queue_root"] / f"{f['request_id']}.parent-tool.{file_phase.lower()}.json"
    path.write_bytes(f["fixtures"].wire_json(wrapper))
    return path


def _poll_tool(f, *, expired=False):
    import time

    return f["client"]._poll_parent_tool_queue(
        f["request_id"], f["session"], deadline=time.monotonic() + (-1 if expired else 10)
    )


def _tool_ack(f, phase):
    import base64

    path = f["kwargs"]["queue_root"] / f"{f['request_id']}.parent-tool.{phase.lower()}-ack.json"
    wrapper = json.loads(path.read_bytes())
    assert wrapper["request_id"] == f["request_id"] and wrapper["phase"] == phase
    return base64.b64decode(wrapper["ack_b64"], validate=True)


def test_client_parent_tool_claim_and_returned_outcome_use_real_ledger(tmp_path):
    f = _tool_client_fixture(tmp_path)
    try:
        _tool_queue_event(f, "CLAIM", f["request"])
        assert _poll_tool(f) == "UNRESOLVED"
        claim_ack = _tool_ack(f, "CLAIM")
        view = f["authority"].verify_parent_tool_commit_ack(
            claim_ack, expected_request_bytes=f["request"]
        )
        assert view.outcome == "UNRESOLVED"
        claim = next(r for r in f["ledger"].read() if r.event.kind == "PARENT_TOOL_READ_CLAIMED")
        assert json.loads(claim_ack)["body"]["accepted_row_hash"] == claim.row_hash
        observation, result = f["fixtures"].tool_observation(f)
        _tool_queue_event(f, "OUTCOME", observation)
        assert _poll_tool(f) == "RETURNED"
        ack = _tool_ack(f, "OUTCOME")
        view = f["authority"].verify_parent_tool_commit_ack(
            ack, expected_request_bytes=f["request"], expected_observation_bytes=observation
        )
        assert view.result_bytes == result and view.raw_bytes == f["raw"]
        head = f["ledger"].head_hash()
        assert _poll_tool(f) == "RETURNED"
        assert f["ledger"].head_hash() == head and _tool_ack(f, "OUTCOME") == ack
    finally:
        f["ledger"].close()
        f["store"].close()


@pytest.mark.parametrize(
    "mutation",
    [
        "request",
        "phase",
        "extra",
        "signature",
        "purpose",
        "context",
        "symlink",
        "oversize",
        "noncanonical",
        "before_claim",
        "timeout",
        "launch",
    ],
)
def test_client_parent_tool_denies_unbound_or_malformed_events(tmp_path, mutation):
    from runtime.integrations.trusted_codex_transport import TrustedCodexTransportError

    f = _tool_client_fixture(tmp_path)
    try:
        raw = f["request"]
        changes = {}
        if mutation == "request":
            changes["request_id"] = "b" * 32
        if mutation == "phase":
            changes["phase"] = "OUTCOME"
        if mutation == "extra":
            changes["authority"] = True
        if mutation == "signature":
            envelope = json.loads(raw)
            envelope["signature"] = "0" * 128
            raw = f["fixtures"].wire_json(envelope)
        if mutation == "purpose":
            raw = f["fixtures"].tool_request(f, changes={"purpose": "PARENT_TOOL_OBSERVATION"})
        if mutation == "context":
            context = json.loads(raw)["body"]["context"]
            context["bindings"]["session_id"] = "wrong-session"
            raw = f["fixtures"].tool_request(f, changes={"context": context})
        phase = "OUTCOME" if mutation == "before_claim" else "CLAIM"
        path = _tool_queue_event(f, phase, raw, **changes)
        sentinel = tmp_path / "outside"
        sentinel.write_bytes(b"synthetic-outside-sentinel")
        if mutation == "symlink":
            path.unlink()
            path.symlink_to(sentinel)
        if mutation == "oversize":
            path.write_bytes(b"x" * 270337)
        if mutation == "noncanonical":
            path.write_bytes(path.read_bytes() + b"\n")
        if mutation == "launch":
            f["client"].last_request_sha256 = "0" * 64
        before = f["ledger"].head_hash()
        with pytest.raises(TrustedCodexTransportError):
            _poll_tool(f, expired=mutation == "timeout")
        assert f["ledger"].head_hash() == before
        assert sentinel.read_bytes() == b"synthetic-outside-sentinel"
        assert not list(f["kwargs"]["queue_root"].glob("*-ack.json"))
    finally:
        f["ledger"].close()
        f["store"].close()


@pytest.mark.parametrize("outcome", ["UNKNOWN", "ERROR"])
def test_client_parent_tool_uncertainty_never_releases_result(tmp_path, outcome):
    from runtime.integrations.trusted_codex_transport import TrustedCodexTransportError

    f = _tool_client_fixture(tmp_path)
    try:
        _tool_queue_event(f, "CLAIM", f["request"])
        _poll_tool(f)
        observation, _ = f["fixtures"].tool_observation(f, outcome=outcome)
        _tool_queue_event(f, "OUTCOME", observation)
        with pytest.raises(TrustedCodexTransportError):
            _poll_tool(f)
        assert f["authority"].read_parent_tool_operation(f["operation"]).outcome == outcome
        assert not list(f["kwargs"]["queue_root"].glob("*.outcome-ack.json"))
        replacement, _ = f["fixtures"].tool_observation(f)
        _tool_queue_event(f, "OUTCOME", replacement)
        head = f["ledger"].head_hash()
        with pytest.raises(TrustedCodexTransportError):
            _poll_tool(f)
        assert f["ledger"].head_hash() == head
    finally:
        f["ledger"].close()
        f["store"].close()


def test_client_parent_tool_reopen_uses_existing_claim_without_second_effect(tmp_path):
    from kernel.ledger import Ledger
    from kernel.ledger_sqlite import SqliteLedgerStore
    from runtime.autonomy.admission_send_fence import AdmissionSendFence
    from runtime.integrations.trusted_codex_transport import HostCodexWorkerTransport

    f = _tool_client_fixture(tmp_path)
    try:
        _tool_queue_event(f, "CLAIM", f["request"])
        _poll_tool(f)
        original_ack = _tool_ack(f, "CLAIM")
        f["ledger"].close()
        f["store"].close()
        f["store"] = SqliteLedgerStore(f["database"])
        f["ledger"] = Ledger(f["store"])
        f["authority"] = f["fixtures"].tool_rebuild(f)
        f["kwargs"].update(
            parent_tool_authority=f["authority"],
            admission_send_fence=AdmissionSendFence(
                f["ledger"],
                authority=f["authority"],
                domain_tag="TEST",
                now=lambda: f["fixtures"].NOW,
            ),
        )
        f["client"] = HostCodexWorkerTransport(**f["kwargs"])
        f["client"].last_request_sha256 = f["fixtures"].sha(b"frame")
        head = f["ledger"].head_hash()
        assert _poll_tool(f) == "UNRESOLVED"
        assert _tool_ack(f, "CLAIM") == original_ack and f["ledger"].head_hash() == head
        assert sum(r.event.kind == "PARENT_TOOL_READ_CLAIMED" for r in f["ledger"].read()) == 1
    finally:
        f["ledger"].close()
        f["store"].close()


def test_client_parent_tool_revocation_denies_fresh_ack(tmp_path):
    from runtime.integrations.trusted_codex_transport import TrustedCodexTransportError

    f = _tool_client_fixture(tmp_path)
    try:
        _tool_queue_event(f, "CLAIM", f["request"])
        _poll_tool(f)
        observation, _ = f["fixtures"].tool_observation(f)
        f["authority"].issue(
            "ADMISSION_REVOKED",
            dict(
                admission_ref="admission",
                epoch=1,
                grant_id="grant",
                expires_at=f["fixtures"].END,
                **f["fixtures"].BINDINGS,
            ),
            issuer_id="issuer",
            signer=f["issuer"].sign,
        )
        _tool_queue_event(f, "OUTCOME", observation)
        with pytest.raises(TrustedCodexTransportError):
            _poll_tool(f)
        assert not list(f["kwargs"]["queue_root"].glob("*.outcome-ack.json"))
    finally:
        f["ledger"].close()
        f["store"].close()


@pytest.mark.parametrize(
    "missing",
    [
        "parent_tool_authority",
        "parent_tool_binding",
        "parent_tool_ack_issuer_id",
        "parent_tool_ack_signer",
    ],
)
def test_client_parent_tool_configuration_has_no_positive_defaults(tmp_path, missing):
    from runtime.integrations.trusted_codex_transport import (
        HostCodexWorkerTransport,
        TrustedCodexTransportError,
    )

    f = _tool_client_fixture(tmp_path)
    try:
        kwargs = dict(f["kwargs"])
        kwargs.pop(missing)
        with pytest.raises(TrustedCodexTransportError):
            HostCodexWorkerTransport(**kwargs)
    finally:
        f["ledger"].close()
        f["store"].close()


def test_client_parent_tool_without_any_authority_rejects_event(tmp_path):
    from runtime.integrations.trusted_codex_transport import (
        HostCodexWorkerTransport,
        TrustedCodexTransportError,
    )

    f = _tool_client_fixture(tmp_path)
    try:
        kwargs = {k: v for k, v in f["kwargs"].items() if not k.startswith("parent_tool_")}
        f["client"] = HostCodexWorkerTransport(**kwargs)
        _tool_queue_event(f, "CLAIM", f["request"])
        head = f["ledger"].head_hash()
        with pytest.raises(TrustedCodexTransportError):
            _poll_tool(f)
        assert head == f["ledger"].head_hash()
        assert not list(f["kwargs"]["queue_root"].glob("*-ack.json"))
    finally:
        f["ledger"].close()
        f["store"].close()


def test_client_parent_tool_request_signer_cannot_be_reused_for_ack(tmp_path):
    from runtime.integrations.trusted_codex_transport import (
        HostCodexWorkerTransport,
        TrustedCodexTransportError,
    )

    f = _tool_client_fixture(tmp_path)
    try:
        kwargs = dict(f["kwargs"], request_signing_key=SigningKey(f["issuer"].private_bytes_raw()))
        with pytest.raises(TrustedCodexTransportError):
            HostCodexWorkerTransport(**kwargs)
    finally:
        f["ledger"].close()
        f["store"].close()


@pytest.mark.parametrize("mutation", ["phase", "signature", "body_type", "size", "symlink"])
def test_client_parent_tool_cannot_overwrite_conflicting_ack(tmp_path, mutation):
    import base64

    from runtime.integrations.trusted_codex_transport import TrustedCodexTransportError

    f = _tool_client_fixture(tmp_path)
    try:
        _tool_queue_event(f, "CLAIM", f["request"])
        _poll_tool(f)
        path = f["kwargs"]["queue_root"] / f"{f['request_id']}.parent-tool.claim-ack.json"
        wrapper = json.loads(path.read_bytes())
        if mutation == "phase":
            wrapper["phase"] = "OUTCOME"
        if mutation in {"signature", "body_type"}:
            signed = json.loads(base64.b64decode(wrapper["ack_b64"]))
            if mutation == "signature":
                signed["signature"] = "0" * 128
            else:
                signed["body"] = []
            wrapper["ack_b64"] = base64.b64encode(f["fixtures"].wire_json(signed)).decode()
        path.write_bytes(f["fixtures"].wire_json(wrapper))
        if mutation == "size":
            path.write_bytes(b"x" * 270337)
        sentinel = tmp_path / "outside-ack"
        sentinel.write_bytes(b"synthetic-outside-sentinel")
        if mutation == "symlink":
            path.unlink()
            path.symlink_to(sentinel)
        before = path.read_bytes()
        head = f["ledger"].head_hash()
        with pytest.raises(TrustedCodexTransportError):
            _poll_tool(f)
        assert head == f["ledger"].head_hash() and path.read_bytes() == before
        assert sentinel.read_bytes() == b"synthetic-outside-sentinel"
    finally:
        f["ledger"].close()
        f["store"].close()


def test_client_parent_tool_new_request_id_cannot_reset_allocation(tmp_path):
    from runtime.integrations.trusted_codex_transport import TrustedCodexTransportError

    f = _tool_client_fixture(tmp_path)
    try:
        _tool_queue_event(f, "CLAIM", f["request"])
        _poll_tool(f)
        f["request_id"] = "b" * 32
        new_request = f["fixtures"].tool_request(f, changes={"request_id": f["request_id"]})
        _tool_queue_event(f, "CLAIM", new_request)
        head = f["ledger"].head_hash()
        with pytest.raises(TrustedCodexTransportError):
            _poll_tool(f)
        assert f["ledger"].head_hash() == head
        assert sum(r.event.kind == "PARENT_TOOL_READ_CLAIMED" for r in f["ledger"].read()) == 1
    finally:
        f["ledger"].close()
        f["store"].close()


def test_client_parent_tool_returned_reopen_retains_same_ack_and_exact_bytes(tmp_path):
    from kernel.ledger import Ledger
    from kernel.ledger_sqlite import SqliteLedgerStore
    from runtime.autonomy.admission_send_fence import AdmissionSendFence
    from runtime.integrations.trusted_codex_transport import HostCodexWorkerTransport

    f = _tool_client_fixture(tmp_path)
    try:
        _tool_queue_event(f, "CLAIM", f["request"])
        _poll_tool(f)
        observation, result = f["fixtures"].tool_observation(f)
        _tool_queue_event(f, "OUTCOME", observation)
        _poll_tool(f)
        ack = _tool_ack(f, "OUTCOME")
        f["ledger"].close()
        f["store"].close()
        f["store"] = SqliteLedgerStore(f["database"])
        f["ledger"] = Ledger(f["store"])
        f["authority"] = f["fixtures"].tool_rebuild(f)
        f["kwargs"].update(
            parent_tool_authority=f["authority"],
            admission_send_fence=AdmissionSendFence(
                f["ledger"],
                authority=f["authority"],
                domain_tag="TEST",
                now=lambda: f["fixtures"].NOW,
            ),
        )
        f["client"] = HostCodexWorkerTransport(**f["kwargs"])
        f["client"].last_request_sha256 = f["fixtures"].sha(b"frame")
        head = f["ledger"].head_hash()
        assert _poll_tool(f) == "RETURNED" and _tool_ack(f, "OUTCOME") == ack
        assert f["ledger"].head_hash() == head
        assert f["authority"].read_parent_tool_operation(f["operation"]).result_bytes == result
    finally:
        f["ledger"].close()
        f["store"].close()


def test_client_parent_tool_missing_outcome_then_timeout_stays_unresolved(tmp_path):
    from runtime.integrations.trusted_codex_transport import TrustedCodexTransportError

    f = _tool_client_fixture(tmp_path)
    try:
        _tool_queue_event(f, "CLAIM", f["request"])
        assert _poll_tool(f) == "UNRESOLVED"
        head = f["ledger"].head_hash()
        with pytest.raises(TrustedCodexTransportError):
            _poll_tool(f, expired=True)
        assert f["authority"].read_parent_tool_operation(f["operation"]).outcome == "UNRESOLVED"
        assert f["ledger"].head_hash() == head
        assert not list(f["kwargs"]["queue_root"].glob("*.outcome-ack.json"))
    finally:
        f["ledger"].close()
        f["store"].close()
