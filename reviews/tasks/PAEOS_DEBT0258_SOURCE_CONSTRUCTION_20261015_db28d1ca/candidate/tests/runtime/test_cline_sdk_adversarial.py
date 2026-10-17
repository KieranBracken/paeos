"""Adversarial, fail-closed tests for the qualified Cline SDK boundary (Task 8)."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from kernel.cas import CAS, InMemoryCasStore
from paeos.model_router.types import ModelFamily
from runtime.integrations.cline_sdk import ClineSdkAdapterConfig, ClineSdkAdmissionAdapter
from runtime.integrations.cline_sdk_protocol import HostEventMachine, ProtocolError
from runtime.integrations.cline_sdk_qualification import (
    SDK_QUALIFICATION_SCHEMA,
    AdapterQualificationRecord,
    QualifiedFile,
)
from runtime.integrations.cline_worker import ClineWorkerTransport
from runtime.worker_adapter import AdapterFailureReceipt
from runtime.worker_admission import AdmissionError, ProbeContract
from runtime.worker_evidence import (
    MIN_FREE_BYTES_BEFORE_CAPTURE,
    EvidencePublishError,
    publish_scanned_bundle,
    scan_and_stage_evidence,
)
from runtime.worker_profile import AuthenticatedProfileHandle, ProfileLease, ProfileLeaseError

ROOT = Path(__file__).parents[2]
HOST = ROOT / "runtime/integrations/cline_sdk_host.mjs"
FAKE_SDK = ROOT / "tests/fixtures/cline_sdk/fake_sdk.mjs"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _qualification(node: Path) -> AdapterQualificationRecord:
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
        files=(QualifiedFile("sdk", FAKE_SDK.name, _sha(FAKE_SDK), FAKE_SDK.stat().st_size),),
        required_symbols=("ClineCore.create", "ClineCore.start"),
        record_sha256="",
    )
    # Slots dataclasses have no __dict__; construct the canonical payload explicitly.
    payload = {
        "schema": record.schema,
        "cline_version": record.cline_version,
        "sdk_version": record.sdk_version,
        "core_version": record.core_version,
        "node_version": record.node_version,
        "node_executable": record.node_executable,
        "node_sha256": record.node_sha256,
        "package_root": record.package_root,
        "sdk_entrypoint": record.sdk_entrypoint,
        "core_entrypoint": record.core_entrypoint,
        "files": [
            {
                "role": item.role,
                "relative_path": item.relative_path,
                "sha256": item.sha256,
                "byte_count": item.byte_count,
            }
            for item in record.files
        ],
        "required_symbols": list(record.required_symbols),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return replace(record, record_sha256=digest)


@pytest.fixture()
def adapter_case(tmp_path: Path) -> tuple[ClineSdkAdmissionAdapter, ProbeContract]:
    node = Path(shutil.which("node") or pytest.skip("node unavailable")).resolve()
    profile = tmp_path / "profile"
    leases = tmp_path / "leases"
    profile.mkdir(mode=0o700)
    leases.mkdir(mode=0o700)
    contract = ProbeContract(
        probe_id="probe-adversarial-001",
        sandbox=tmp_path / "sandbox",
        provider_id="cline-pass",
        model_id="cline-pass/qwen3.8-max",
        expected_family=ModelFamily.QWEN,
        artifact_name="artifact.txt",
        initial_bytes=b"baseline-worker\n",
        expected_bytes=b"admitted-worker\n",
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
        timeout_seconds=60,
        lease_root=leases,
        process_start_token="adversarial-process",
        boot_id="adversarial-boot",
    )
    return ClineSdkAdmissionAdapter(config), contract


@pytest.mark.parametrize(
    "probe_id",
    [
        "probe-unauthorized-read",
        "probe-unauthorized-mcp",
        "probe-unauthorized-settings",
        "probe-unauthorized-skill",
        "probe-unauthorized-spawn",
        "probe-unauthorized-team",
    ],
)
def test_unauthorized_capability_is_denied_without_editing_artifact(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract], probe_id: str
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id=probe_id))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is not None
    assert result.adapter_failure.value == "TOOL_DENIED"
    assert contract.artifact_path.read_bytes() == b"baseline-worker\n"


@pytest.mark.parametrize("expansion", ["cd", "pipe", "separator", "redirection", "extra"])
def test_command_expansion_is_rejected_and_raw_transcript_is_nonempty(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract], expansion: str
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id=f"probe-expansion-{expansion}"))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.adapter_failure is not None
    assert result.adapter_failure.value == "COMMAND_EXPANSION"
    assert result.raw_stdout_sha256 != hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize(
    ("probe_id", "artifact_bytes", "certainty"),
    [
        ("probe-hidden-retry", b"baseline-worker\n", "UNKNOWN"),
        ("probe-manifest-provider", b"admitted-worker\n", "TOOL_EFFECT_POSSIBLE"),
        ("probe-manifest-model", b"admitted-worker\n", "TOOL_EFFECT_POSSIBLE"),
        ("probe-manifest-session", b"admitted-worker\n", "TOOL_EFFECT_POSSIBLE"),
        ("probe-manifest-capabilities", b"admitted-worker\n", "TOOL_EFFECT_POSSIBLE"),
    ],
)
def test_identity_retry_and_capability_drift_never_admit(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
    probe_id: str,
    artifact_bytes: bytes,
    certainty: str,
) -> None:
    adapter, contract = adapter_case

    result = adapter.run_probe(replace(contract, probe_id=probe_id))

    assert isinstance(result, AdapterFailureReceipt)
    assert result.raw_stdout_sha256 != hashlib.sha256(b"").hexdigest()
    assert result.side_effect_certainty.value == certainty
    assert (contract.sandbox / "artifact.txt").read_bytes() == artifact_bytes


def test_profile_manifest_escape_and_symlink_are_rejected(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract], tmp_path: Path
) -> None:
    adapter, _ = adapter_case
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    escaped = adapter._config.profile.root / "sessions" / "escape.json"
    escaped.parent.mkdir()
    escaped.symlink_to(outside)

    with pytest.raises(AdmissionError, match=r"symlink|escaped"):
        adapter._profile_path(str(escaped))


def test_free_profile_lock_with_active_record_requires_recovery(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, _ = adapter_case
    profile = adapter._config.profile
    active = adapter._config.lease_root / f"{profile.profile_uuid}.active.json"
    active.write_text('{"invocation_id":"stale"}\n')
    active.chmod(0o600)

    with pytest.raises(ProfileLeaseError) as error:
        ProfileLease.acquire(
            profile,
            invocation_id="probe-recovery",
            lease_root=adapter._config.lease_root,
            forbidden_roots=(),
            process_start_token="p",
            boot_id="b",
        )
    assert "reconciliation" in str(error.value)


def test_protocol_duplicate_unknown_and_post_terminal_events_fail_closed() -> None:
    machine = HostEventMachine("probe-protocol")
    hello = {
        "invocation_id": "probe-protocol",
        "payload": {},
        "protocol_version": "paeos-worker-admission/1",
        "sequence": 0,
        "type": "hello",
    }
    machine.accept(hello)
    with pytest.raises(ProtocolError):
        machine.accept({**hello, "sequence": 1, "type": "unknown"})

    session = {
        "invocation_id": "probe-protocol",
        "payload": {},
        "protocol_version": "paeos-worker-admission/1",
        "sequence": 1,
        "session_id": "session",
        "type": "session_created",
    }
    machine.accept(session)
    terminal = {**session, "sequence": 2, "type": "terminal"}
    machine.accept(terminal)
    with pytest.raises(ProtocolError, match="post-terminal"):
        machine.accept({**terminal, "sequence": 3})


def test_legacy_cli_transport_is_diagnostic_only_and_never_admits(
    tmp_path: Path,
) -> None:
    contract = ProbeContract(
        probe_id="diagnostic-only",
        sandbox=tmp_path / "sandbox",
        provider_id="cline-pass",
        model_id="cline-pass/qwen3.8-max",
        expected_family=ModelFamily.QWEN,
        artifact_name="artifact.txt",
        initial_bytes=b"old",
        expected_bytes=b"new",
        verification_command="python3 verify_probe.py",
    )
    result = ClineWorkerTransport().run_probe(contract, tmp_path / "evidence")

    assert result.adapter_failure is not None
    assert result.adapter_failure.value == "ADAPTER_VERSION_UNQUALIFIED"
    assert result.side_effect_certainty.value == "NOT_DISPATCHED"
    assert not contract.sandbox.exists()


def test_secret_evidence_is_quarantined_without_cas_publication(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    (source / "stdout.raw").write_bytes(b"Authorization: Bearer synthetic-never-publish")
    bundle = scan_and_stage_evidence(
        source,
        allowlist=("stdout.raw",),
        staging_root=tmp_path / "staging",
        quarantine_root=tmp_path / "quarantine",
        free_bytes=MIN_FREE_BYTES_BEFORE_CAPTURE,
    )
    cas = CAS(InMemoryCasStore())

    with pytest.raises(EvidencePublishError):
        publish_scanned_bundle(bundle, cas)
    assert list(cas._store.iter_keys()) == []  # type: ignore[attr-defined]


def test_profile_authentication_handle_is_secret_blind_and_immutable(
    adapter_case: tuple[ClineSdkAdmissionAdapter, ProbeContract],
) -> None:
    adapter, _ = adapter_case
    serialized = repr(adapter._config.profile)

    assert "credential" not in serialized.lower()
    assert "token" not in serialized.lower()
    with pytest.raises(AttributeError):
        adapter._config.profile.auth_epoch = 2  # type: ignore[misc]
