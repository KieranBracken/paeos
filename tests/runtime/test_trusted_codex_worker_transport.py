from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from nacl.signing import SigningKey


def _broker_evidence(count=1):
    receipts = [
        {
            "request_id": index,
            "request_sha256": str(index) * 64,
            "response_sha256": "b" * 64,
            "transport_outcome": "response_received",
            "upstream_status": 200,
            "upstream_error_class": None,
            "observed_model_id": "gpt-5.6-sol",
            "model_identity_contract": ("codex-0.147.0:be6e8eac029b183056b7e4402879f15d2c85f61b"),
            "model_identity_error": None,
        }
        for index in range(1, count + 1)
    ]
    return {
        "schema": "paeos.task-scoped-responses-broker/3",
        "binding": "127.0.0.1",
        "model_id": "gpt-5.6-sol",
        "transport_outcome": "response_received",
        "upstream_status": 200 if count == 1 else None,
        "upstream_error_class": None,
        "request_count": count,
        "request_limit": 32,
        "local_rejection_count": 0,
        "local_error_class": None,
        "request_sha256": "1" * 64 if count == 1 else "",
        "response_sha256": "b" * 64 if count == 1 else "",
        "request_receipts": receipts,
    }


def _request(key: SigningKey, **overrides: object) -> dict[str, object]:
    from ops.trusted_codex_worker_supervisor import _canonical_bytes

    payload: dict[str, object] = {
        "schema": "paeos.trusted-codex-launch/1",
        "request_id": "a" * 32,
        "task_id": "t-transport",
        "goal_id": "g-transport",
        "run_id": "r-transport",
        "stage": "IMPLEMENT",
        "workspace_id": "ws-transport",
        "prompt": "Reply with the bounded transport nonce.",
        "issued_at": 1_000.0,
        "expires_at": 1_030.0,
        "provider_id": "codex",
        "model_id": "gpt-5.6-sol",
        "family": "gpt",
        "fallback_used": False,
        "manual_chat_bridge": False,
    }
    payload.update(overrides)
    return {
        **payload,
        "signature": key.sign(_canonical_bytes(payload)).signature.hex(),
    }


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
    evidence_root: Path,
    evidence_exists: bool,
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
    if evidence_exists:
        assert os.listdir(evidence_root) == []
    else:
        assert not os.path.lexists(evidence_root)
    assert transport.last_request_sha256 is None  # type: ignore[attr-defined]
    assert transport.last_response_sha256 is None  # type: ignore[attr-defined]
    assert transport.last_observation is None  # type: ignore[attr-defined]


@pytest.mark.parametrize("count", [1, 2])
def test_broker_receipt_validator_rejects_upstream_http_refusal(count):
    from ops.trusted_codex_worker_supervisor import _broker_evidence_complete

    evidence = _broker_evidence(count)
    evidence["request_receipts"][0]["upstream_status"] = 429
    if count == 1:
        evidence["upstream_status"] = 429
    assert not _broker_evidence_complete(evidence, "gpt-5.6-sol")


@pytest.mark.parametrize("count", [1, 2])
def test_broker_receipt_validator_accepts_matching_server_identity(count):
    from ops.trusted_codex_worker_supervisor import _broker_evidence_complete

    assert _broker_evidence_complete(_broker_evidence(count), "gpt-5.6-sol")


@pytest.mark.parametrize(
    "defect",
    [
        "legacy",
        "missing",
        "duplicate",
        "bool_id",
        "pending",
        "failure",
        "missing_hash",
        "invalid_hash",
        "invalid_status",
        "extra_field",
        "wrong_model",
        "missing_observed_model",
        "wrong_observed_model",
        "missing_identity_field",
        "wrong_identity_contract",
        "identity_error",
        "false_count",
        "count_mismatch",
        "limit",
        "local_rejection",
        "ambiguous_scalar",
        "missing_scalar",
    ],
)
def test_broker_receipt_validator_rejects_incomplete_or_ambiguous_task_evidence(defect):
    from ops.trusted_codex_worker_supervisor import _broker_evidence_complete

    evidence = _broker_evidence(2)
    first = evidence["request_receipts"][0]
    if defect == "legacy":
        evidence["schema"] = "paeos.task-scoped-responses-broker/1"
    elif defect == "missing":
        evidence.pop("request_receipts")
    elif defect == "duplicate":
        evidence["request_receipts"][1]["request_id"] = 1
    elif defect == "bool_id":
        first["request_id"] = True
    elif defect == "pending":
        first["transport_outcome"] = "upstream_started"
    elif defect == "failure":
        first["transport_outcome"] = "upstream_failure"
        first["upstream_error_class"] = "timeout"
    elif defect == "missing_hash":
        first.pop("response_sha256")
    elif defect == "invalid_hash":
        first["response_sha256"] = "z" * 64
    elif defect == "invalid_status":
        first["upstream_status"] = True
    elif defect == "extra_field":
        first["opaque"] = "unverified"
    elif defect == "wrong_model":
        evidence["model_id"] = "different-model"
    elif defect == "missing_observed_model":
        first["observed_model_id"] = None
    elif defect == "wrong_observed_model":
        first["observed_model_id"] = "gpt-5.6-luna"
    elif defect == "missing_identity_field":
        first.pop("observed_model_id")
    elif defect == "wrong_identity_contract":
        first["model_identity_contract"] = "unverified-contract"
    elif defect == "identity_error":
        first["model_identity_error"] = "unverified_server_model"
    elif defect == "false_count":
        evidence["request_count"] = True
    elif defect == "count_mismatch":
        evidence["request_count"] = 1
    elif defect == "limit":
        evidence["request_limit"] = 1
    elif defect == "local_rejection":
        evidence["local_rejection_count"] = 1
    elif defect == "ambiguous_scalar":
        evidence["request_sha256"] = "a" * 64
        evidence["response_sha256"] = "b" * 64
    elif defect == "missing_scalar":
        evidence.pop("upstream_status")
    assert not _broker_evidence_complete(evidence, "gpt-5.6-sol")


def test_broker_receipt_validator_rejects_single_call_scalar_mismatch():
    from ops.trusted_codex_worker_supervisor import _broker_evidence_complete

    evidence = _broker_evidence()
    evidence["response_sha256"] = "c" * 64
    assert not _broker_evidence_complete(evidence, "gpt-5.6-sol")


def _service(
    tmp_path: Path,
    key: SigningKey,
    *,
    response_key: SigningKey | None = None,
    qualification_path: Path | None = None,
):
    from ops.trusted_codex_worker_supervisor import TrustedCodexWorkerSupervisor

    public_key = tmp_path / "request-verify.key"
    public_key.write_text(bytes(key.verify_key).hex() + "\n", encoding="ascii")
    public_key.chmod(0o600)
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(mode=0o700, exist_ok=True)
    auth = codex_home / "auth.json"
    if not auth.exists():
        auth.write_text("{}\n", encoding="utf-8")
    auth.chmod(0o600)
    return TrustedCodexWorkerSupervisor(
        queue_root=tmp_path / "queue",
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        codex_home=codex_home,
        request_verify_key_path=public_key,
        response_signing_key=response_key or SigningKey.generate(),
        qualification_path=qualification_path,
        clock=lambda: 1_010.0,
    )


@pytest.mark.parametrize("qualification,expected_limit", [(True, 1), (False, 32)])
def test_supervisor_sets_qualification_broker_ceiling_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qualification: bool, expected_limit: int
) -> None:
    import ops.trusted_codex_worker_supervisor as supervisor

    key = SigningKey.generate()
    service = _service(tmp_path, key)
    (service.workspace_root / "ws-transport").mkdir(mode=0o700)
    overrides = {}
    if qualification:
        for field, prefix in [("task_id", "t"), ("goal_id", "g"), ("run_id", "r")]:
            overrides[field] = f"{prefix}-builder-transport-qualification-" + "b" * 32
    request, request_id = service._validate_request(_request(key, **overrides))
    captured = {}

    class StopBeforeBrokerStart(Exception):
        pass

    def broker(**kwargs):
        captured.update(kwargs)
        raise StopBeforeBrokerStart

    monkeypatch.setattr(service, "_validate_codex_home", lambda: None)
    monkeypatch.setattr(supervisor, "ParentOwnedResponsesBroker", broker)
    with pytest.raises(supervisor.SupervisorFailure) as failure:
        service._run_request(request, request_id)
    assert isinstance(failure.value.__cause__, StopBeforeBrokerStart)
    assert captured.get("max_requests") == expected_limit


def test_supervisor_rejects_caller_selected_argv_paths_and_environment(tmp_path: Path) -> None:
    key = SigningKey.generate()
    service = _service(tmp_path, key)

    forged = _request(key, argv=["/bin/sh"], workspace_root="/tmp", environment={"HOME": "/tmp"})

    with pytest.raises(RuntimeError, match="exact"):
        service._validate_request(forged)


def test_supervisor_derives_workspace_only_from_fixed_root(tmp_path: Path) -> None:
    key = SigningKey.generate()
    service = _service(tmp_path, key)
    request = _request(key)
    service.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    workspace = service.workspace_root / "ws-transport"
    workspace.mkdir(mode=0o700)

    validated, request_id = service._validate_request(request)
    assert request_id == "a" * 32
    assert service._workspace_for(validated) == workspace.resolve()


def test_supervisor_signed_failure_response_contains_no_worker_output(tmp_path: Path) -> None:
    key = SigningKey.generate()
    service = _service(tmp_path, key)
    response = json.loads(service.handle(json.dumps(_request(key)).encode("utf-8")))

    payload = response["payload"]
    assert payload["ok"] is False
    assert payload["error_code"] in {"workspace_failure", "codex_home_failure"}
    assert "stdout" not in payload
    assert "stderr" not in payload
    assert isinstance(response["signature"], str)


@pytest.mark.parametrize("broker_calls", [1, 2])
def test_supervisor_builder_deadline_is_longer_than_failed_p1_window_but_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broker_calls: int
) -> None:
    """A slow but live Builder must not be cut off by the old fixed 300-second deadline."""
    import ops.trusted_codex_worker_supervisor as supervisor

    key = SigningKey.generate()
    service = _service(tmp_path, key)
    workspace = service.workspace_root / "ws-transport"
    workspace.mkdir(mode=0o700)
    captured: dict[str, float] = {}

    class _Broker:
        loopback_port = 4000
        base_url = "http://127.0.0.1:4000"
        task_token = "task-scoped"

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def evidence(self) -> dict[str, object]:
            return _broker_evidence(broker_calls)

    class _Policy:
        seatbelt_profile = "test-profile"

        def wrap_argv(self, argv: tuple[str, ...]) -> tuple[str, ...]:
            return argv

    def _fake_run(
        argv: tuple[str, ...],
        *,
        cwd: Path,
        environment: dict[str, str],
        start_timeout_s: float,
        execution_timeout_s: float,
        state_path: Path,
    ):
        del cwd, environment, start_timeout_s
        captured["execution_timeout_s"] = execution_timeout_s
        state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        state_path.write_text('{"heartbeat_count": 1}\n', encoding="utf-8")
        from runtime.integrations.process_supervisor import (
            ProcessLifecycleState,
            ProcessObservation,
        )

        return ProcessObservation(
            argv=argv,
            executable="/bin/sh",
            executable_version="sha256:" + "c" * 64,
            cwd=str(workspace),
            environment_fingerprint="d" * 64,
            stdout=b"bounded builder response\n",
            stderr=b"",
            exit_code=0,
            duration_ms=1,
            lifecycle_state=ProcessLifecycleState.RETURNED,
        )

    monkeypatch.setattr(supervisor, "ParentOwnedResponsesBroker", lambda **_kwargs: _Broker())
    monkeypatch.setattr(service, "_validate_codex_home", lambda: None)
    monkeypatch.setattr(
        service,
        "_policy",
        lambda _workspace, loopback_port, broker_token: (_Policy(), {"PATH": "/bin"}, "/bin/sh"),
    )
    monkeypatch.setattr(service, "_run_canaries", lambda *_args: {"canary": "PASS"})
    monkeypatch.setattr(supervisor, "_codex_argv", lambda *_args, **_kwargs: ("/bin/sh",))
    monkeypatch.setattr(supervisor, "run_bounded_process", _fake_run)

    validated, request_id = service._validate_request(_request(key))
    validated["workspace_id"] = workspace.name
    observation = service._run_request(validated, request_id)

    assert captured["execution_timeout_s"] > 300.0
    assert captured["execution_timeout_s"] <= 900.0
    assert observation["process_state"] == "RETURNED"


def test_supervisor_canary_program_uses_host_builtin_shell_not_xcode_python_shim() -> None:
    from ops.trusted_codex_worker_supervisor import CANARY_EXECUTABLE, _canary_program

    assert Path("/bin/sh") == CANARY_EXECUTABLE
    syntax = subprocess.run(
        [str(CANARY_EXECUTABLE), "-n"],
        input=_canary_program(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_supervisor_resolves_fixed_homebrew_launcher_inside_pinned_install_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ops import trusted_codex_worker_supervisor as supervisor

    install_root = tmp_path / "Caskroom" / "codex"
    executable = install_root / "0.147.0" / "bin" / "codex"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    launcher = tmp_path / "bin" / "codex"
    launcher.parent.mkdir()
    launcher.symlink_to(executable)
    monkeypatch.setattr(supervisor, "CODEX_EXECUTABLE", launcher)
    monkeypatch.setattr(supervisor, "CODEX_INSTALL_ROOT", install_root)

    assert supervisor._fixed_codex_executable() == executable


def test_supervisor_rejects_fixed_launcher_target_outside_pinned_install_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ops import trusted_codex_worker_supervisor as supervisor

    install_root = tmp_path / "Caskroom" / "codex"
    install_root.mkdir(parents=True)
    executable = tmp_path / "outside" / "codex"
    executable.parent.mkdir()
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    launcher = tmp_path / "bin" / "codex"
    launcher.parent.mkdir()
    launcher.symlink_to(executable)
    monkeypatch.setattr(supervisor, "CODEX_EXECUTABLE", launcher)
    monkeypatch.setattr(supervisor, "CODEX_INSTALL_ROOT", install_root)

    with pytest.raises(supervisor.SupervisorFailure, match="pinned install root"):
        supervisor._fixed_codex_executable()


def test_supervisor_policy_exposes_only_task_scoped_loopback_broker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ops import trusted_codex_worker_supervisor as supervisor

    key = SigningKey.generate()
    service = _service(tmp_path, key)
    workspace = service.workspace_root / "ws-transport"
    workspace.mkdir(mode=0o700, parents=True)
    install_root = tmp_path / "Caskroom" / "codex"
    executable = install_root / "0.147.0" / "bin" / "codex"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    launcher = tmp_path / "bin" / "codex"
    launcher.parent.mkdir()
    launcher.symlink_to(executable)
    monkeypatch.setattr(supervisor, "CODEX_EXECUTABLE", launcher)
    monkeypatch.setattr(supervisor, "CODEX_INSTALL_ROOT", install_root)

    policy, environment, resolved = service._policy(
        workspace,
        loopback_port=43123,
        broker_token="ephemeral-task-token",
    )

    assert resolved == executable
    assert policy.loopback_port == 43123
    assert policy.network_hosts == ()
    assert '(remote tcp "localhost:43123")' in policy.seatbelt_profile
    assert policy.preference_domains == ("com.openai.codex", "kCFPreferencesAnyApplication")
    assert (
        '(allow user-preference-read (preference-domain "com.openai.codex"))'
        in policy.seatbelt_profile
    )
    assert (
        '(allow user-preference-read (preference-domain "kCFPreferencesAnyApplication"))'
        in policy.seatbelt_profile
    )
    assert "(allow user-preference-read)" not in policy.seatbelt_profile
    assert '(allow file-read* (literal "/etc/codex/requirements.toml"))' in policy.seatbelt_profile
    assert '(allow file-read* (subpath "/etc/codex"))' not in policy.seatbelt_profile
    assert "api.openai.com" not in policy.seatbelt_profile
    assert str(service.codex_home) not in policy.seatbelt_profile
    assert environment == {
        "HOME": str(workspace / ".paeos-codex-runtime"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C",
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "TMPDIR": str(workspace / ".paeos-codex-tmp"),
        "CODEX_HOME": str(workspace / ".paeos-codex-runtime"),
        "PAEOS_TASK_BROKER_TOKEN": "ephemeral-task-token",
    }


def test_supervisor_codex_argv_binds_custom_provider_without_embedding_token(
    tmp_path: Path,
) -> None:
    from ops.trusted_codex_worker_supervisor import _codex_argv

    argv = _codex_argv(
        Path("/opt/homebrew/Caskroom/codex/0.147.0/bin/codex"),
        prompt="bounded task",
        workspace=tmp_path,
        broker_base_url="http://127.0.0.1:43123/v1",
    )

    rendered = "\n".join(argv)
    assert argv[0] == "/opt/homebrew/Caskroom/codex/0.147.0/bin/codex"
    assert 'model_provider="paeos_broker"' in argv
    assert 'model_providers.paeos_broker.env_key="PAEOS_TASK_BROKER_TOKEN"' in argv
    assert 'model_providers.paeos_broker.base_url="http://127.0.0.1:43123/v1"' in argv
    assert "ephemeral-task-token" not in rendered
    assert "--dangerously-bypass-approvals-and-sandbox" in argv


def test_supervisor_persists_structured_failure_after_launch_acceptance(
    tmp_path: Path, monkeypatch
) -> None:
    from runtime.integrations.worker_confinement import WorkerConfinementError

    key = SigningKey.generate()
    service = _service(tmp_path, key)
    service.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    workspace = service.workspace_root / "ws-transport"
    workspace.mkdir(mode=0o700)

    def fail_policy(_workspace: Path):
        raise WorkerConfinementError("test confinement failure")

    monkeypatch.setattr(service, "_policy", fail_policy)

    response = json.loads(service.handle(json.dumps(_request(key)).encode("utf-8")))
    payload = response["payload"]
    assert payload["ok"] is False
    assert payload["error_code"] == "supervisor_failure"
    lifecycle = json.loads(
        (service.state_root / ("a" * 32) / "lifecycle.json").read_text(encoding="utf-8")
    )
    assert lifecycle["state"] == "STRUCTURED_FAILURE"
    assert lifecycle["error_code"] == "supervisor_failure"


def test_supervisor_restart_proof_requires_a_new_signed_boot_identity(tmp_path: Path) -> None:
    from ops.trusted_codex_worker_supervisor import _canonical_bytes

    key = SigningKey.generate()
    response_key = SigningKey.generate()
    first = _service(tmp_path, key, response_key=response_key)
    second = _service(tmp_path, key, response_key=response_key)

    assert first._previous_boot_verified is False
    assert second._previous_boot_verified is True
    assert first._boot_id != second._boot_id
    identity = json.loads((second.state_root / "identity.json").read_text(encoding="utf-8"))
    signature = identity.pop("signature")
    response_key.verify_key.verify(_canonical_bytes(identity), bytes.fromhex(signature))


def test_qualification_is_signed_by_supervisor_key_not_request_key(tmp_path: Path) -> None:
    from ops.trusted_codex_worker_supervisor import SupervisorFailure
    from runtime.builder_transport import BuilderTransportNotReady, BuilderTransportReadiness

    request_key = SigningKey.generate()
    response_key = SigningKey.generate()
    qualification_nonce = "d" * 32
    qualification_path = tmp_path / "qualification.json"
    service = _service(
        tmp_path,
        request_key,
        response_key=response_key,
        qualification_path=qualification_path,
    )
    observation = {
        "provider_id": "codex",
        "model_id": "gpt-5.6-sol",
        "family": "gpt",
        "request_id": "e" * 32,
        "task_id": f"t-builder-transport-qualification-{qualification_nonce}",
        "goal_id": f"g-builder-transport-qualification-{qualification_nonce}",
        "run_id": f"r-builder-transport-qualification-{qualification_nonce}",
        "stage": "IMPLEMENT",
        "artifact_sha256": "a" * 64,
        "broker_request_count": 1,
        "lifecycle": ["STARTING", "RUNNING", "PROGRESS", "COMPLETED"],
        "canaries": {
            key: "PASS"
            for key in {
                "approved_read",
                "approved_write",
                "forbidden_read_denied",
                "forbidden_write_denied",
                "parent_secret_invisible",
                "provider_credential_absent",
                "symlink_escape_denied",
                "traversal_escape_denied",
                "child_subprocess_confined",
                "broker_capability_task_scoped",
                "supervisor_restart_no_fallback",
            }
        },
    }

    service._claim_qualification_identity(
        {
            "task_id": observation["task_id"],
            "goal_id": observation["goal_id"],
            "run_id": observation["run_id"],
            "stage": observation["stage"],
        },
        str(observation["request_id"]),
    )
    service._write_qualification(
        observation,
        request_sha256="b" * 64,
        response_sha256="c" * 64,
    )

    qualified = BuilderTransportReadiness(
        qualification_path,
        response_key.verify_key,
        clock=lambda: 1_020,
    ).require()
    assert qualified.response_sha256 == "c" * 64
    with pytest.raises(SupervisorFailure, match="already used"):
        service._claim_qualification_identity(
            {
                "task_id": observation["task_id"],
                "goal_id": observation["goal_id"],
                "run_id": observation["run_id"],
                "stage": observation["stage"],
            },
            "f" * 32,
        )
    with pytest.raises(BuilderTransportNotReady):
        BuilderTransportReadiness(
            qualification_path,
            request_key.verify_key,
            clock=lambda: 1_020,
        ).require()


def test_arbitrary_successful_worker_cannot_mint_transport_readiness(tmp_path: Path) -> None:
    key = SigningKey.generate()
    qualification_path = tmp_path / "qualification.json"
    service = _service(
        tmp_path,
        key,
        response_key=SigningKey.generate(),
        qualification_path=qualification_path,
    )
    observation = {
        "provider_id": "codex",
        "model_id": "gpt-5.6-sol",
        "family": "gpt",
        "task_id": "t-arbitrary-worker",
        "goal_id": "g-arbitrary-worker",
        "run_id": "r-arbitrary-worker",
        "stage": "RESEARCH",
        "artifact_sha256": "a" * 64,
        "lifecycle": ["STARTING", "RUNNING", "PROGRESS", "COMPLETED"],
        "canaries": {
            key: "PASS"
            for key in {
                "approved_read",
                "approved_write",
                "forbidden_read_denied",
                "forbidden_write_denied",
                "parent_secret_invisible",
                "provider_credential_absent",
                "symlink_escape_denied",
                "traversal_escape_denied",
                "child_subprocess_confined",
                "broker_capability_task_scoped",
                "supervisor_restart_no_fallback",
            }
        },
    }

    service._write_qualification(
        observation,
        request_sha256="b" * 64,
        response_sha256="c" * 64,
    )

    assert not qualification_path.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"goal_id": "g-builder-transport-qualification-" + "f" * 32},
        {"stage": "RESEARCH"},
        {"broker_request_count": 2},
        {"broker_request_count": True},
    ],
)
def test_qualification_requires_correlated_fresh_identity_and_one_broker_request(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    key = SigningKey.generate()
    qualification_path = tmp_path / "qualification.json"
    service = _service(
        tmp_path,
        key,
        response_key=SigningKey.generate(),
        qualification_path=qualification_path,
    )
    nonce = "9" * 32
    observation: dict[str, object] = {
        "provider_id": "codex",
        "model_id": "gpt-5.6-sol",
        "family": "gpt",
        "request_id": "8" * 32,
        "task_id": f"t-builder-transport-qualification-{nonce}",
        "goal_id": f"g-builder-transport-qualification-{nonce}",
        "run_id": f"r-builder-transport-qualification-{nonce}",
        "stage": "IMPLEMENT",
        "artifact_sha256": "a" * 64,
        "broker_request_count": 1,
        "lifecycle": ["STARTING", "RUNNING", "PROGRESS", "COMPLETED"],
        "canaries": {
            name: "PASS"
            for name in {
                "approved_read",
                "approved_write",
                "forbidden_read_denied",
                "forbidden_write_denied",
                "parent_secret_invisible",
                "provider_credential_absent",
                "symlink_escape_denied",
                "traversal_escape_denied",
                "child_subprocess_confined",
                "broker_capability_task_scoped",
                "supervisor_restart_no_fallback",
            }
        },
    }
    observation.update(changes)

    service._write_qualification(
        observation,
        request_sha256="b" * 64,
        response_sha256="c" * 64,
    )

    assert not qualification_path.exists()


def test_qualification_identity_is_consumed_before_any_provider_launch(tmp_path: Path) -> None:
    from ops.trusted_codex_worker_supervisor import SupervisorFailure

    key = SigningKey.generate()
    service = _service(tmp_path, key)
    workspace = service.workspace_root / "ws-qualification-replay"
    workspace.mkdir(mode=0o700, parents=True)
    nonce = "7" * 32
    base = {
        "task_id": f"t-builder-transport-qualification-{nonce}",
        "goal_id": f"g-builder-transport-qualification-{nonce}",
        "run_id": f"r-builder-transport-qualification-{nonce}",
        "stage": "IMPLEMENT",
        "workspace_id": workspace.name,
    }
    requests = [_request(key, request_id=request_id, **base) for request_id in ("1" * 32, "2" * 32)]
    launch_checks = 0

    def reject_after_claim() -> None:
        nonlocal launch_checks
        launch_checks += 1
        raise SupervisorFailure("codex_home_failure", "synthetic local prelaunch rejection")

    service._validate_codex_home = reject_after_claim
    validated = [service._validate_request(item) for item in requests]

    with pytest.raises(SupervisorFailure, match="synthetic local prelaunch rejection"):
        service._run_request(*validated[0])
    with pytest.raises(SupervisorFailure, match="already used"):
        service._run_request(*validated[1])

    assert launch_checks == 1


def test_post_response_process_failure_records_its_boundary_before_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The .05 failure must be attributable to the child process, not later capture stages."""
    import ops.trusted_codex_worker_supervisor as supervisor
    from ops.trusted_codex_worker_supervisor import SupervisorFailure
    from runtime.integrations.process_supervisor import ProcessLifecycleState, ProcessObservation

    key = SigningKey.generate()
    service = _service(tmp_path, key)
    workspace = service.workspace_root / "ws-transport"
    workspace.mkdir(mode=0o700, parents=True)

    class _Broker:
        loopback_port = 4000
        base_url = "http://127.0.0.1:4000"
        task_token = "task-scoped"

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def evidence(self) -> dict[str, object]:
            return _broker_evidence()

    class _Policy:
        seatbelt_profile = "test-profile"

        def wrap_argv(self, argv: tuple[str, ...]) -> tuple[str, ...]:
            return argv

    def _fake_run(
        argv: tuple[str, ...],
        *,
        cwd: Path,
        environment: dict[str, str],
        start_timeout_s: float,
        execution_timeout_s: float,
        state_path: Path,
    ) -> ProcessObservation:
        del cwd, environment, start_timeout_s, execution_timeout_s
        state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        state_path.write_text('{"heartbeat_count": 1}\n', encoding="utf-8")
        return ProcessObservation(
            argv=argv,
            executable="/bin/sh",
            executable_version="sha256:" + "c" * 64,
            cwd=str(workspace),
            environment_fingerprint="d" * 64,
            stdout=b"nonempty response before worker exit\n",
            stderr=b"bounded worker diagnostic\n",
            exit_code=1,
            duration_ms=1,
            lifecycle_state=ProcessLifecycleState.FAILED,
        )

    capture_reached = False

    def _unexpected_capture(_workspace: Path) -> str:
        nonlocal capture_reached
        capture_reached = True
        raise AssertionError("workspace capture must not run after child-process failure")

    monkeypatch.setattr(supervisor, "ParentOwnedResponsesBroker", lambda **_kwargs: _Broker())
    monkeypatch.setattr(supervisor, "run_bounded_process", _fake_run)
    monkeypatch.setattr(supervisor, "_codex_argv", lambda *_args, **_kwargs: ("/bin/sh",))
    monkeypatch.setattr(supervisor, "_workspace_tree_sha256", _unexpected_capture)
    service._validate_codex_home = lambda: None
    service._policy = lambda *_args, **_kwargs: (_Policy(), {"PATH": "/bin"}, "/bin/sh")
    service._run_canaries = lambda *_args: {"confinement": "PASS"}

    validated, request_id = service._validate_request(_request(key))
    validated["workspace_id"] = workspace.name
    with pytest.raises(SupervisorFailure) as raised:
        service._run_request(validated, request_id)

    lifecycle = json.loads(
        (service.state_root / request_id / "lifecycle.json").read_text(encoding="utf-8")
    )
    assert raised.value.code == "provider_execution_failure"
    assert lifecycle["state"] == "STRUCTURED_FAILURE"
    assert lifecycle["error_code"] == "provider_execution_failure"
    assert lifecycle["failure_boundary"] == "post_response_process"
    assert lifecycle["observation"]["lifecycle_state"] == "FAILED"
    assert lifecycle["observation"]["exit_code"] == 1
    assert lifecycle["observation"]["stdout_bytes"] > 0
    assert capture_reached is False


def test_qualification_transport_denies_before_writing_signed_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from runtime.integrations.trusted_codex_transport import (
        HostCodexWorkerTransport,
    )

    queue = tmp_path / "queue"
    workspace_root = tmp_path / "workspaces"
    workspace = workspace_root / "ws-bootstrap-receipts"
    workspace.mkdir(mode=0o700, parents=True)
    evidence_root = workspace / "qualification-evidence"
    evidence_root.mkdir(mode=0o700)
    request_signer = _CountingSigner()
    transport = HostCodexWorkerTransport(
        queue_root=queue,
        workspace_root=workspace_root,
        request_signing_key=request_signer,  # type: ignore[arg-type]
        response_verify_key=SigningKey.generate().verify_key,
        timeout_s=1,
        evidence_root=evidence_root,
    )
    _assert_disclosure_denial_has_no_effects(
        transport,
        request_signer,
        queue_root=queue,
        evidence_root=evidence_root,
        evidence_exists=True,
        monkeypatch=monkeypatch,
    )


def test_qualification_transport_denies_before_ambiguous_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from runtime.integrations.trusted_codex_transport import (
        HostCodexWorkerTransport,
    )

    workspace_root = tmp_path / "workspaces"
    workspace = workspace_root / "ws-bootstrap-timeout"
    workspace.mkdir(mode=0o700, parents=True)
    evidence_root = workspace / "qualification-evidence"
    evidence_root.mkdir(mode=0o700)
    queue = tmp_path / "queue"
    request_signer = _CountingSigner()
    transport = HostCodexWorkerTransport(
        queue_root=queue,
        workspace_root=workspace_root,
        request_signing_key=request_signer,  # type: ignore[arg-type]
        response_verify_key=SigningKey.generate().verify_key,
        timeout_s=0.001,
        evidence_root=evidence_root,
    )
    _assert_disclosure_denial_has_no_effects(
        transport,
        request_signer,
        queue_root=queue,
        evidence_root=evidence_root,
        evidence_exists=True,
        monkeypatch=monkeypatch,
    )


def test_trusted_transport_claims_before_fake_queue_send_and_settles_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    from datetime import UTC, datetime

    import runtime.integrations.trusted_codex_transport as transport_module
    from kernel.ledger import Event, Ledger
    from kernel.ledger_sqlite import SqliteLedgerStore
    from runtime.autonomy.admission_send_fence import AdmissionSendFence
    from runtime.integrations import SessionSpec
    from runtime.integrations.trusted_codex_transport import HostCodexWorkerTransport

    route_id = "trusted-codex-worker/v1"
    route_digest = hashlib.sha256(route_id.encode("ascii")).hexdigest()
    policy_digest = "a" * 64
    workspace_root = tmp_path / "workspaces"
    workspace = workspace_root / "ws-send-fence"
    workspace.mkdir(mode=0o700, parents=True)
    queue = tmp_path / "queue"
    queue.mkdir(mode=0o700)
    ledger_store = SqliteLedgerStore(tmp_path / "canonical-ledger.db")
    ledger = Ledger(ledger_store, writer_id="trusted-transport-test")
    ledger.append(
        Event(
            1,
            "DISCLOSURE_POLICY_CURRENT",
            {
                "policy_id": "synthetic-policy",
                "revision": 1,
                "digest": policy_digest,
                "expires_at": "2026-10-20T12:00:00+00:00",
                "proof": "synthetic-policy-proof",
            },
        ),
        domain_tag="TEST",
    )
    ledger.append(
        Event(
            1,
            "ADMISSION_CURRENT",
            {
                "admission_ref": "synthetic-admission",
                "epoch": 4,
                "logical_job_id": "synthetic-logical-job",
                "task_id": "t-send-fence",
                "goal_id": "g-send-fence",
                "run_id": "r-send-fence",
                "stage": "IMPLEMENT",
                "role": "BUILDER",
                "workspace_id": workspace.name,
                "route_id": route_id,
                "route_digest": route_digest,
                "policy_id": "synthetic-policy",
                "policy_revision": 1,
                "policy_digest": policy_digest,
                "expires_at": "2026-10-20T12:00:00+00:00",
                "proof": "synthetic-admission-proof",
            },
        ),
        domain_tag="TEST",
    )

    class SyntheticAuthority:
        def verify_policy(self, payload):
            return payload.get("proof") == "synthetic-policy-proof"

        def verify_admission(self, payload):
            return payload.get("proof") == "synthetic-admission-proof"

        def authorize_frame(self, admission, policy, *, frame_digest, route_digest):
            return (
                admission.get("policy_id") == policy.get("policy_id")
                and admission.get("route_digest") == route_digest
                and len(frame_digest) == 64
            )

    fence = AdmissionSendFence(
        ledger,
        authority=SyntheticAuthority(),
        domain_tag="TEST",
        now=lambda: datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
    )
    request_key = SigningKey.generate()
    response_key = SigningKey.generate()
    transport = HostCodexWorkerTransport(
        queue_root=queue,
        workspace_root=workspace_root,
        request_signing_key=request_key,
        response_verify_key=response_key.verify_key,
        timeout_s=0.1,
        admission_send_fence=fence,
        admission_ref="synthetic-admission",
        expected_admission_epoch=4,
    )
    fake_sink: list[bytes] = []
    fake_responses: list[bytes] = []
    write_atomic = transport_module._write_atomic

    def fake_write(path: Path, payload: bytes) -> None:
        if path.name.endswith(".request.json"):
            fake_sink.append(payload)
        write_atomic(path, payload)
        if path.name.endswith(".request.json"):
            request = json.loads(payload.decode("utf-8"))
            response_payload = {
                "schema": transport_module._SCHEMA,
                "ok": False,
                "request_id": request["request_id"],
                "error_code": "supervisor_failure",
                "error": transport_module._FAILURE_ERROR,
            }
            response = {
                "payload": response_payload,
                "signature": response_key.sign(
                    transport_module._canonical_bytes(response_payload)
                ).signature.hex(),
            }
            response_path = queue / f"{request['request_id']}.response.json"
            response_bytes = transport_module._canonical_bytes(response)
            fake_responses.append(response_bytes)
            response_path.write_bytes(response_bytes)

    monkeypatch.setattr(transport_module, "_write_atomic", fake_write)
    result = transport.run(
        SessionSpec(
            workspace=workspace,
            prompt="synthetic prompt only",
            allowed_tools=(),
            read_scopes=(),
            timeout_s=1,
            task_id="t-send-fence",
            goal_id="g-send-fence",
            run_id="r-send-fence",
            stage="IMPLEMENT",
        )
    )

    assert result.failure_code == "supervisor_failure"
    assert len(fake_sink) == 1
    request = json.loads(fake_sink[0].decode("utf-8"))
    claim = next(row for row in ledger.read() if row.event.kind == "ADMISSION_SEND_CLAIMED")
    settlement = next(row for row in ledger.read() if row.event.kind == "ADMISSION_SEND_SETTLED")
    assert claim.event.payload["request_id"] == request["request_id"]
    assert claim.event.payload["frame_digest"] == hashlib.sha256(fake_sink[0]).hexdigest()
    assert settlement.event.payload["outcome"] == "RETURNED"
    assert settlement.event.payload["outcome_ref"] == hashlib.sha256(fake_responses[0]).hexdigest()


def test_revoked_admission_denies_at_trusted_transport_before_queue_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    from datetime import UTC, datetime

    import runtime.integrations.trusted_codex_transport as transport_module
    from kernel.ledger import Event, Ledger
    from kernel.ledger_sqlite import SqliteLedgerStore
    from runtime.autonomy.admission_send_fence import AdmissionSendFence
    from runtime.integrations import SessionSpec, TrustedTransportFailure
    from runtime.integrations.trusted_codex_transport import HostCodexWorkerTransport

    route_id = "trusted-codex-worker/v1"
    route_digest = hashlib.sha256(route_id.encode("ascii")).hexdigest()
    workspace_root = tmp_path / "workspaces"
    workspace = workspace_root / "ws-revoked"
    workspace.mkdir(mode=0o700, parents=True)
    queue = tmp_path / "queue"
    ledger_store = SqliteLedgerStore(tmp_path / "canonical-ledger.db")
    ledger = Ledger(ledger_store, writer_id="trusted-transport-test")
    ledger.append(
        Event(
            1,
            "DISCLOSURE_POLICY_CURRENT",
            {
                "policy_id": "synthetic-policy",
                "revision": 1,
                "digest": "a" * 64,
                "expires_at": "2026-10-20T12:00:00+00:00",
                "proof": "synthetic-policy-proof",
            },
        ),
        domain_tag="TEST",
    )
    ledger.append(
        Event(
            1,
            "ADMISSION_CURRENT",
            {
                "admission_ref": "synthetic-admission",
                "epoch": 4,
                "logical_job_id": "synthetic-logical-job",
                "task_id": "t-revoked",
                "goal_id": "g-revoked",
                "run_id": "r-revoked",
                "stage": "IMPLEMENT",
                "role": "BUILDER",
                "workspace_id": workspace.name,
                "route_id": route_id,
                "route_digest": route_digest,
                "policy_id": "synthetic-policy",
                "policy_revision": 1,
                "policy_digest": "a" * 64,
                "expires_at": "2026-10-20T12:00:00+00:00",
                "proof": "synthetic-admission-proof",
            },
        ),
        domain_tag="TEST",
    )
    ledger.append(
        Event(1, "ADMISSION_REVOKED", {"admission_ref": "synthetic-admission", "epoch": 4}),
        domain_tag="TEST",
    )

    class SyntheticAuthority:
        def verify_policy(self, payload):
            return payload.get("proof") == "synthetic-policy-proof"

        def verify_admission(self, payload):
            return payload.get("proof") == "synthetic-admission-proof"

        def authorize_frame(self, *_args, **_kwargs):
            return True

    fence = AdmissionSendFence(
        ledger,
        authority=SyntheticAuthority(),
        domain_tag="TEST",
        now=lambda: datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
    )

    class CountingSigner:
        calls = 0

        def sign(self, _payload: bytes):
            self.calls += 1
            raise AssertionError("revoked admission must deny before request signing")

    signer = CountingSigner()
    transport = HostCodexWorkerTransport(
        queue_root=queue,
        workspace_root=workspace_root,
        request_signing_key=signer,  # type: ignore[arg-type]
        response_verify_key=SigningKey.generate().verify_key,
        timeout_s=0.1,
        admission_send_fence=fence,
        admission_ref="synthetic-admission",
        expected_admission_epoch=4,
    )

    def forbidden_write(*_args: object, **_kwargs: object) -> None:
        pytest.fail("revoked request reached the trusted transport sink")

    monkeypatch.setattr(transport_module, "_write_atomic", forbidden_write)
    with pytest.raises(TrustedTransportFailure) as raised:
        transport.run(
            SessionSpec(
                workspace=workspace,
                prompt="synthetic prompt only",
                allowed_tools=(),
                read_scopes=(),
                timeout_s=1,
                task_id="t-revoked",
                goal_id="g-revoked",
                run_id="r-revoked",
                stage="IMPLEMENT",
            )
        )

    assert raised.value.code == "disclosure_authority_unavailable"
    assert signer.calls == 0
    assert not queue.exists()


def test_qualification_wrapper_sends_one_request_and_preserves_unknown_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nacl.signing import VerifyKey

    from ops import verify_builder_transport_ready as qualification

    request_key = SigningKey.generate()
    response_key = SigningKey.generate()
    calls: list[object] = []
    events: list[str] = []

    class _AmbiguousClient:
        last_request_sha256 = "a" * 64
        last_response_sha256 = None
        last_observation = None

        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(self, spec: object) -> None:
            events.append("request")
            calls.append(spec)
            raise qualification.TrustedCodexTransportError(
                "supervisor restart qualification is pending"
            )

    monkeypatch.setattr(qualification, "_classify_nested_seatbelt", lambda: {"available": False})

    def _restart_once() -> dict[str, str]:
        events.append("restart")
        return {"current_boot_id": "restarted"}

    monkeypatch.setattr(qualification, "_restart_supervisor", _restart_once)
    monkeypatch.setattr(qualification, "HostCodexWorkerTransport", _AmbiguousClient)
    monkeypatch.setattr(
        qualification,
        "_read_key",
        lambda path, private: bytes(request_key) if private else bytes(response_key.verify_key),
    )
    monkeypatch.setattr(qualification, "DEFAULT_CODEX_WORKSPACE_ROOT", tmp_path / "workspaces")
    monkeypatch.setattr(qualification, "DEFAULT_CODEX_REQUEST_KEY", tmp_path / "request.key")
    monkeypatch.setattr(
        qualification, "DEFAULT_CODEX_RESPONSE_VERIFY_KEY", tmp_path / "response.key"
    )
    monkeypatch.setattr(
        qualification, "DEFAULT_BUILDER_TRANSPORT_VERIFY_KEY", tmp_path / "qualification.key"
    )
    monkeypatch.setattr(
        qualification, "DEFAULT_BUILDER_TRANSPORT_QUALIFICATION", tmp_path / "qualification.json"
    )
    monkeypatch.setattr(qualification, "VerifyKey", VerifyKey)

    assert qualification.qualify() == 17

    assert len(calls) == 1
    assert events == ["restart", "request"]
    spec = calls[0]
    assert spec.task_id.startswith("t-builder-transport-qualification-")
    assert spec.goal_id.removeprefix(
        "g-builder-transport-qualification-"
    ) == spec.task_id.removeprefix("t-builder-transport-qualification-")
    assert spec.run_id.removeprefix(
        "r-builder-transport-qualification-"
    ) == spec.task_id.removeprefix("t-builder-transport-qualification-")
    assert spec.workspace.is_dir()
    attempt = json.loads((spec.workspace / "attempt.json").read_text(encoding="utf-8"))
    assert attempt["status"] == "UNKNOWN"
    assert attempt["request_sha256"] == "a" * 64


def test_qualification_restart_withholds_when_signed_request_is_queued(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    import plistlib

    from ops import verify_builder_transport_ready as qualification

    response_key = SigningKey.generate()
    ops_root = tmp_path / "ops" / ".trusted-codex-worker"
    queue_root = ops_root / "queue"
    state_root = tmp_path / "install" / "state"
    workspace_root = ops_root / "workspaces"
    bundle_root = tmp_path / "install" / "bundle"
    manifest_path = tmp_path / "install" / "manifest.json"
    qualification_path = ops_root / "qualification.json"
    for path in (queue_root, state_root, workspace_root, bundle_root):
        path.mkdir(mode=0o700, parents=True)

    identity = {
        "schema": "paeos.trusted-codex-worker-service/1",
        "supervisor_identity_sha256": hashlib.sha256(bytes(response_key.verify_key)).hexdigest(),
        "provider_id": "codex",
        "model_id": "gpt-5.6-sol",
        "family": "gpt",
        "codex_executable": "/opt/homebrew/bin/codex",
        "workspace_root": str(workspace_root),
        "boot_id": "previous-boot",
    }
    identity_envelope = {
        **identity,
        "signature": response_key.sign(qualification._canonical_bytes(identity)).signature.hex(),
    }
    (state_root / "identity.json").write_bytes(qualification._canonical_bytes(identity_envelope))
    plist_path = tmp_path / "LaunchAgents" / "supervisor.plist"
    plist_path.parent.mkdir(mode=0o700)
    args = [
        "/Users/bob/GitHub/paeos/.venv/bin/python3",
        str(bundle_root / "ops" / "trusted_codex_worker_supervisor.py"),
        "--bundle-root",
        str(bundle_root),
        "--bundle-manifest",
        str(manifest_path),
        "--state-root",
        str(state_root),
        "--queue-root",
        str(queue_root),
        "--workspace-root",
        str(workspace_root),
        "--request-verify-key",
        str(bundle_root / "request-verify.key"),
        "--qualification-path",
        str(qualification_path),
    ]
    plist_path.write_bytes(
        plistlib.dumps(
            {
                "Label": qualification.SUPERVISOR_LABEL,
                "ProgramArguments": args,
                "EnvironmentVariables": {
                    "HOME": str(tmp_path),
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C",
                    "PATH": "/usr/bin:/bin",
                    "PYTHONPATH": str(bundle_root),
                },
                "RunAtLoad": True,
                "KeepAlive": True,
            }
        )
    )
    plist_path.chmod(0o600)
    (queue_root / f"{'a' * 32}.request.json").write_text("{}\n", encoding="utf-8")
    subprocess_calls: list[list[str]] = []

    monkeypatch.setattr(qualification, "LAUNCH_AGENT", plist_path)
    monkeypatch.setattr(qualification, "DEFAULT_CODEX_REQUEST_KEY", ops_root / "request.key")
    monkeypatch.setattr(
        qualification, "DEFAULT_CODEX_RESPONSE_VERIFY_KEY", ops_root / "response.key"
    )
    monkeypatch.setattr(qualification, "DEFAULT_CODEX_WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(
        qualification, "DEFAULT_BUILDER_TRANSPORT_QUALIFICATION", qualification_path
    )
    monkeypatch.setattr(
        qualification, "_read_key", lambda *_args, **_kwargs: bytes(response_key.verify_key)
    )
    monkeypatch.setattr(qualification, "verify_bundle_manifest", lambda *_args: None)
    monkeypatch.setattr(
        qualification,
        "subprocess",
        type(
            "Subprocess",
            (),
            {"run": staticmethod(lambda args, **_kwargs: subprocess_calls.append(args))},
        ),
    )

    with pytest.raises(RuntimeError, match="queue is not idle"):
        qualification._restart_supervisor()

    assert subprocess_calls == []


def test_stale_supervisor_lifecycle_requires_process_pid_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    from ops import verify_builder_transport_ready as qualification

    state_root = tmp_path / "state"
    request_state = state_root / ("a" * 32)
    request_state.mkdir(mode=0o700, parents=True)
    (request_state / "lifecycle.json").write_text(
        '{"request_id":"' + "a" * 32 + '","state":"STARTING","observed_at":1}\n',
        encoding="utf-8",
    )
    (request_state / "process.json").write_text(
        '{"pid":424242,"terminal_state":"RUNNING"}\n', encoding="utf-8"
    )

    def dead_process(pid: int, signal_number: int) -> None:
        assert pid == 424242
        assert signal_number == 0
        raise ProcessLookupError

    monkeypatch.setattr(qualification.os, "kill", dead_process)
    stale = qualification._stale_lifecycle_records(state_root)

    assert stale == [
        {
            "request_identity_sha256": hashlib.sha256(("a" * 32).encode()).hexdigest(),
            "lifecycle_state": "STARTING",
            "worker_pid": 424242,
            "worker_terminal_state": "RUNNING",
            "classification": "STALE_WORKER_PID_NOT_RUNNING",
        }
    ]

    monkeypatch.setattr(qualification.os, "kill", lambda *_args: None)
    with pytest.raises(RuntimeError, match="active request process is still running"):
        qualification._stale_lifecycle_records(state_root)

    missing_root = tmp_path / "missing-process-state"
    missing_request = missing_root / ("b" * 32)
    missing_request.mkdir(mode=0o700, parents=True)
    (missing_request / "lifecycle.json").write_text(
        '{"request_id":"' + "b" * 32 + '","state":"RUNNING","observed_at":1}\n',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="no trustworthy process receipt"):
        qualification._stale_lifecycle_records(missing_root)
