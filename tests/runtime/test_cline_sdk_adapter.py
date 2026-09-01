"""Integration tests for the provider-neutral public Cline SDK admission adapter."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from uuid import UUID

import pytest
import runtime.integrations.cline_sdk as cline_sdk
from paeos.model_router.types import ModelFamily, NormalizedErrorType
from runtime.integrations.cline_sdk import ClineSdkAdapterConfig, ClineSdkAdmissionAdapter
from runtime.integrations.cline_sdk_protocol import ProtocolError, read_frame
from runtime.integrations.cline_sdk_qualification import (
    SDK_QUALIFICATION_SCHEMA,
    AdapterQualificationRecord,
    QualifiedFile,
)
from runtime.worker_adapter import (
    AdapterFailureKind,
    AdapterFailureReceipt,
    SideEffectCertainty,
)
from runtime.worker_admission import (
    AdmissionVerdict,
    ProbeContract,
    RawWorkerRun,
    assess_worker_run,
)
from runtime.worker_profile import AuthenticatedProfileHandle

ROOT = Path(__file__).parents[2]
HOST = ROOT / "runtime/integrations/cline_sdk_host.mjs"
FAKE_SDK = ROOT / "tests/fixtures/cline_sdk/fake_sdk.mjs"
OLD = b"baseline-worker\n"
NEW = b"admitted-worker\n"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _qualification(node: Path) -> AdapterQualificationRecord:
    sdk_hash = _sha(FAKE_SDK)
    record = AdapterQualificationRecord(
        schema=SDK_QUALIFICATION_SCHEMA,
        cline_version="3.0.60",
        sdk_version="0.0.81",
        core_version="0.0.81",
        node_version="24.1.0",
        node_executable=str(node),
        node_sha256=_sha(node),
        package_root=str(FAKE_SDK.parent),
        sdk_entrypoint=str(FAKE_SDK),
        core_entrypoint=str(FAKE_SDK),
        files=(QualifiedFile("sdk", FAKE_SDK.name, sdk_hash, FAKE_SDK.stat().st_size),),
        required_symbols=("ClineCore.create", "ClineCore.start"),
        record_sha256="",
    )
    payload = asdict(record)
    payload.pop("record_sha256")
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return replace(record, record_sha256=digest)


def _rehash_record(record: AdapterQualificationRecord) -> AdapterQualificationRecord:
    payload = asdict(record)
    payload.pop("record_sha256")
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return replace(record, record_sha256=digest)


@pytest.fixture()
def adapter_case(tmp_path: Path) -> tuple[ClineSdkAdmissionAdapter, ProbeContract]:
    node_name = "node"
    node = Path(shutil.which(node_name) or pytest.skip(f"{node_name} unavailable")).resolve()
    profile = tmp_path / "profile"
    lease_root = tmp_path / "leases"
    profile.mkdir(mode=0o700)
    lease_root.mkdir(mode=0o700)
    sandbox = tmp_path / "sandbox"
    contract = ProbeContract(
        probe_id="probe-sdk-001",
        sandbox=sandbox,
        provider_id="cline-pass",
        model_id="cline-pass/qwen3.8-max",
        expected_family=ModelFamily.QWEN,
        artifact_name="artifact.txt",
        initial_bytes=OLD,
        expected_bytes=NEW,
        verification_command="python3 verify_probe.py",
    )
    config = ClineSdkAdapterConfig(
        node_executable=node,
        host_module=HOST,
        qualification=_qualification(node),
        profile=AuthenticatedProfileHandle(
            root=profile,
            profile_uuid=UUID("12345678-1234-5678-1234-567812345678"),
            auth_epoch=1,
        ),
        timeout_seconds=15,
        lease_root=lease_root,
        process_start_token="test-process-start",
        boot_id="test-boot",
    )
    return ClineSdkAdmissionAdapter(config), contract


def test_three_turn_probe_produces_admissible_raw_worker_run(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(contract)

    assert isinstance(result, RawWorkerRun)
    assert [decision.tool_name for decision in result.tool_decisions] == [
        "editor",
        "run_commands",
    ]
    assert all(decision.approved for decision in result.tool_decisions)
    assert result.artifact_hash == hashlib.sha256(NEW).hexdigest()
    assert result.verification.candidate_exit_code == 0
    assert result.verification.mutation_exit_code != 0
    assert assess_worker_run(contract, result).verdict is AdmissionVerdict.ADMITTED
    assert not any(Path(adapter._config.lease_root).glob("*.active.json"))
    assert os.environ.get("SYNTHETIC_SECRET_FOR_TEST") is None


def test_batched_tool_approvals_execute_in_contract_order(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id="probe-batched-approvals"))

    assert isinstance(result, RawWorkerRun)
    assert [decision.tool_name for decision in result.tool_decisions] == [
        "editor",
        "run_commands",
    ]
    assert result.verification.candidate_exit_code == 0


@pytest.mark.parametrize(
    "tool_name",
    ["read", "search", "mcp", "spawn", "team", "skill", "unknown"],
)
def test_unauthorized_tool_is_rejected_before_execution(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    tool_name: str,
) -> None:
    adapter, contract = adapter_case
    contract = replace(contract, probe_id=f"probe-unauthorized-{tool_name}")

    result = adapter.run_probe(contract)

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.TOOL_DENIED
    assert contract.artifact_path.read_bytes() == OLD


@pytest.mark.parametrize(
    "expansion",
    ["cd", "pipe", "separator", "substitution", "redirection", "extra"],
)
def test_command_expansion_is_denied_before_subprocess(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    expansion: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, contract = adapter_case
    contract = replace(contract, probe_id=f"probe-expansion-{expansion}")
    subprocess_called = False

    def forbidden_run(*_args: object, **_kwargs: object) -> None:
        nonlocal subprocess_called
        subprocess_called = True
        raise AssertionError("expanded command reached subprocess")

    monkeypatch.setattr("runtime.integrations.cline_sdk.subprocess.run", forbidden_run)

    result = adapter.run_probe(contract)

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.COMMAND_EXPANSION
    assert not subprocess_called


@pytest.mark.parametrize(
    ("probe_id", "failure"),
    [
        ("probe-manifest-provider", AdapterFailureKind.MODEL_MISMATCH),
        ("probe-manifest-model", AdapterFailureKind.MODEL_MISMATCH),
        ("probe-manifest-session", AdapterFailureKind.SESSION_AMBIGUOUS),
        ("probe-manifest-capabilities", AdapterFailureKind.CAPABILITY_DRIFT),
    ],
)
def test_manifest_identity_and_capabilities_are_cross_checked(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    probe_id: str,
    failure: AdapterFailureKind,
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id=probe_id))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is failure
    assert result.raw_stdout_sha256 != hashlib.sha256(b"").hexdigest()


def test_hidden_retry_in_one_declared_turn_fails_closed(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id="probe-hidden-retry"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.TRANSPORT_FAILED


def test_structured_auth_failure_remains_auth_failed(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id="probe-auth-failed"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.normalized_error is NormalizedErrorType.AUTH_FAILED


def test_raw_auth_failure_remains_auth_failed_when_transport_message_is_generic(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, contract = adapter_case

    def fail(_contract: ProbeContract) -> RawWorkerRun:
        raise cline_sdk._ProbeFailure(
            "SDK terminal failure: failure",
            b"provider frame",
            b"Unauthorized: re-authenticate the Cline account",
        )

    monkeypatch.setattr(adapter, "_run_probe", fail)

    result = adapter.run_probe(replace(contract, probe_id="probe-raw-auth-failed"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is None
    assert result.normalized_error is NormalizedErrorType.AUTH_FAILED


def test_protocol_truncation_is_typed_transport_rejection(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, contract = adapter_case

    def fail(_contract: ProbeContract) -> RawWorkerRun:
        raise ProtocolError("truncated frame")

    monkeypatch.setattr(adapter, "_run_probe", fail)

    result = adapter.run_probe(replace(contract, probe_id="probe-truncated-frame"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.TRANSPORT_FAILED
    assert result.side_effect_certainty is SideEffectCertainty.UNKNOWN


def test_rejected_probe_releases_profile_lease_with_failure_evidence(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id="probe-manifest-provider"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.MODEL_MISMATCH
    assert not tuple(adapter._config.lease_root.glob("*.active.json"))
    released = tuple(adapter._config.lease_root.glob("*.released.json"))
    assert len(released) == 1
    record = json.loads(released[0].read_text(encoding="utf-8"))
    assert record["auth_epoch"] == adapter._config.profile.auth_epoch


def test_protocol_failure_releases_profile_lease(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, contract = adapter_case

    def fail_read(_stream: object, _deadline: float) -> dict[str, object]:
        raise ProtocolError("truncated frame")

    monkeypatch.setattr(adapter, "_read_event", fail_read)
    result = adapter.run_probe(replace(contract, probe_id="probe-protocol-lease"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.TRANSPORT_FAILED
    assert not tuple(adapter._config.lease_root.glob("*.active.json"))


def test_sdk_start_failure_is_emitted_as_typed_rejection(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id="probe-start-throws"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.TRANSPORT_FAILED
    assert result.raw_stdout_sha256 != hashlib.sha256(b"").hexdigest()


def test_sdk_known_auth_start_failure_is_typed_auth_rejection(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id="probe-start-auth-error"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is None
    assert result.normalized_error is NormalizedErrorType.AUTH_FAILED


def test_unfinished_provider_attempt_times_out_with_unknown_side_effects(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case
    adapter._config = replace(adapter._config, timeout_seconds=0.2)

    result = adapter.run_probe(replace(contract, probe_id="probe-timeout-unfinished"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.side_effect_certainty.value == "UNKNOWN"
    assert result.adapter_failure is AdapterFailureKind.SIDE_EFFECT_UNCERTAIN


def test_child_environment_is_exact_allowlist_without_parent_secret(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, contract = adapter_case
    original_popen = subprocess.Popen
    node_env: dict[str, str] | None = None

    def capture_popen(argv: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        nonlocal node_env
        if Path(argv[0]).resolve() == adapter._config.node_executable:
            node_env = dict(kwargs["env"])  # type: ignore[arg-type]
        return original_popen(argv, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setenv("SYNTHETIC_SECRET_FOR_TEST", "must-not-cross-boundary")
    monkeypatch.setattr("runtime.integrations.cline_sdk.subprocess.Popen", capture_popen)

    result = adapter.run_probe(contract)

    assert isinstance(result, RawWorkerRun)
    assert node_env == {
        "CLINE_DATA_DIR": str(adapter._config.profile.root / "data"),
        "LANG": "C.UTF-8",
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
    }
    assert "SYNTHETIC_SECRET_FOR_TEST" not in node_env


def test_timeout_sends_one_cancel_and_terminates_once_without_retry(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, contract = adapter_case
    adapter._config = replace(adapter._config, timeout_seconds=0.2)
    original_popen = subprocess.Popen
    command_frames: list[dict[str, object]] = []
    terminate_count = 0
    close_count = 0

    class TrackingInput:
        def __init__(self, wrapped: object) -> None:
            self._wrapped = wrapped

        def write(self, value: bytes) -> int:
            command_frames.append(read_frame(io.BytesIO(value)))
            return self._wrapped.write(value)  # type: ignore[no-any-return,union-attr]

        def flush(self) -> None:
            self._wrapped.flush()  # type: ignore[union-attr]

        def close(self) -> None:
            nonlocal close_count
            close_count += 1
            self._wrapped.close()  # type: ignore[union-attr]

    def capture_popen(argv: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        nonlocal terminate_count
        process = original_popen(argv, **kwargs)  # type: ignore[arg-type]
        if Path(argv[0]).resolve() == adapter._config.node_executable:
            assert process.stdin is not None
            process.stdin = TrackingInput(process.stdin)  # type: ignore[assignment]
            original_terminate = process.terminate

            def terminate() -> None:
                nonlocal terminate_count
                terminate_count += 1
                original_terminate()

            process.terminate = terminate  # type: ignore[method-assign]
        return process

    monkeypatch.setattr("runtime.integrations.cline_sdk.subprocess.Popen", capture_popen)

    result = adapter.run_probe(replace(contract, probe_id="probe-timeout-unfinished"))

    assert isinstance(result, AdapterFailureReceipt)
    assert [frame["type"] for frame in command_frames].count("cancel") == 1
    assert terminate_count == 1
    assert close_count == 1


def test_changed_qualification_tuple_fails_before_dispatch(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, contract = adapter_case
    adapter._config = replace(
        adapter._config,
        qualification=replace(adapter._config.qualification, record_sha256="0" * 64),
    )
    dispatched = False

    def forbidden_popen(*_args: object, **_kwargs: object) -> None:
        nonlocal dispatched
        dispatched = True
        raise AssertionError("unqualified tuple dispatched")

    monkeypatch.setattr("runtime.integrations.cline_sdk.subprocess.Popen", forbidden_popen)

    result = adapter.run_probe(contract)

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED
    assert result.side_effect_certainty.value == "NOT_DISPATCHED"
    assert not dispatched


def test_profile_lease_failure_returns_typed_rejection(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case
    adapter._config.lease_root.chmod(0o755)

    result = adapter.run_probe(contract)

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.PROFILE_LOCK_FAILED
    assert result.side_effect_certainty.value == "NOT_DISPATCHED"


def test_rehashed_record_with_changed_qualified_file_is_still_rejected(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, contract = adapter_case
    changed_file = replace(adapter._config.qualification.files[0], sha256="0" * 64)
    changed_record = _rehash_record(replace(adapter._config.qualification, files=(changed_file,)))
    adapter._config = replace(adapter._config, qualification=changed_record)

    result = adapter.run_probe(contract)

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED
