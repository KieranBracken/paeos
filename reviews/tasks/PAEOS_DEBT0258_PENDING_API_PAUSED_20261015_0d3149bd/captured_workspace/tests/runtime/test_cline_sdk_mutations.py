"""Mutation-kill tests for identity, capability, ordering, and receipt invariants (Task 8)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from paeos.model_router.types import ModelFamily
from runtime.worker_adapter import (
    ADAPTER_PROTOCOL_VERSION,
    AdapterFailureKind,
    AdapterObservation,
    SideEffectCertainty,
    validate_adapter_observation,
)
from runtime.worker_admission import (
    AdmissionError,
    PhysicalModelReceipt,
    ProbeContract,
    RawWorkerRun,
    ToolDecisionRecord,
    VerificationReceipt,
    assess_worker_run,
    validate_physical_receipt,
)

HEX = "a" * 64


def _contract(tmp_path: Path) -> ProbeContract:
    return ProbeContract(
        probe_id="mutation-probe",
        sandbox=tmp_path / "sandbox",
        provider_id="cline-pass",
        model_id="cline-pass/qwen3.8-max",
        expected_family=ModelFamily.QWEN,
        artifact_name="artifact.txt",
        initial_bytes=b"old\n",
        expected_bytes=b"new\n",
        verification_command="python3 verify_probe.py",
    )


def _receipt() -> PhysicalModelReceipt:
    return PhysicalModelReceipt(
        transport_id="headless:cline-sdk:qualified",
        session_id="mutation-session",
        pid=1234,
        configured_provider_id="cline-pass",
        configured_model_id="cline-pass/qwen3.8-max",
        actual_provider_id="cline-pass",
        actual_model_id="cline-pass/qwen3.8-max",
        actual_family=ModelFamily.QWEN,
        manifest_provider_id="cline-pass",
        manifest_model_id="cline-pass/qwen3.8-max",
        message_models=("cline-pass/qwen3.8-max",),
        argv_hash=HEX,
        stdout_hash=HEX,
        stderr_hash=HEX,
        manifest_hash=HEX,
        messages_hash=HEX,
    )


def _verification(contract: ProbeContract) -> VerificationReceipt:
    argv = ("python3", "verify_probe.py")
    argv_hash = hashlib.sha256(json.dumps(argv, separators=(",", ":")).encode()).hexdigest()
    return VerificationReceipt(
        argv=argv,
        argv_hash=argv_hash,
        baseline_artifact_hash=hashlib.sha256(contract.initial_bytes).hexdigest(),
        baseline_exit_code=1,
        baseline_stdout_hash=HEX,
        baseline_stderr_hash=HEX,
        candidate_artifact_hash=hashlib.sha256(contract.expected_bytes).hexdigest(),
        candidate_exit_code=0,
        candidate_stdout_hash=HEX,
        candidate_stderr_hash=HEX,
        mutation_hash=hashlib.sha256(b"seeded-mutation\n").hexdigest(),
        mutation_exit_code=1,
        mutation_stdout_hash=HEX,
        mutation_stderr_hash=HEX,
        artifact_restored_hash=hashlib.sha256(contract.expected_bytes).hexdigest(),
        restored_exit_code=0,
        restored_stdout_hash=HEX,
        restored_stderr_hash=HEX,
    )


def _run(contract: ProbeContract) -> RawWorkerRun:
    return RawWorkerRun(
        probe_id=contract.probe_id,
        receipt=_receipt(),
        tool_decisions=(
            ToolDecisionRecord("editor", True, ""),
            ToolDecisionRecord("run_commands", True, ""),
        ),
        artifact_name=contract.artifact_name,
        artifact_hash=hashlib.sha256(contract.expected_bytes).hexdigest(),
        artifact_size=len(contract.expected_bytes),
        verification=_verification(contract),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_id", ""),
        ("pid", 0),
        ("transport_id", ""),
        ("configured_provider_id", "other-provider"),
        ("configured_model_id", "other/model"),
        ("actual_provider_id", "other-provider"),
        ("actual_model_id", "other/model"),
        ("actual_family", ModelFamily.GPT),
        ("manifest_provider_id", "other-provider"),
        ("manifest_model_id", "other/model"),
        ("message_models", ("other/model",)),
        ("argv_hash", "not-a-hash"),
    ],
)
def test_each_physical_identity_mutation_is_rejected(
    tmp_path: Path, field: str, value: object
) -> None:
    contract = _contract(tmp_path)
    baseline = _receipt()
    validate_physical_receipt(baseline, contract)

    mutated = replace(baseline, **{field: value})
    with pytest.raises(AdmissionError):
        validate_physical_receipt(mutated, contract)


@pytest.mark.parametrize(
    ("field", "value", "finding"),
    [
        ("protocol_version", "future/99", AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED),
        ("backend_mode", "auto", AdapterFailureKind.CAPABILITY_DRIFT),
        ("invocation_id", "", AdapterFailureKind.SESSION_AMBIGUOUS),
        ("session_id", "", AdapterFailureKind.SESSION_AMBIGUOUS),
        ("model_id", "", AdapterFailureKind.MODEL_MISMATCH),
        ("provider_attempts_by_turn", (2, 1), AdapterFailureKind.TRANSPORT_FAILED),
        ("capability_snapshot_sha256", "bad", AdapterFailureKind.TRANSPORT_FAILED),
        ("transcript_sha256", "bad", AdapterFailureKind.TRANSPORT_FAILED),
        (
            "side_effect_certainty",
            SideEffectCertainty.UNKNOWN,
            AdapterFailureKind.SIDE_EFFECT_UNCERTAIN,
        ),
    ],
)
def test_each_transport_observation_mutation_is_detected(
    field: str, value: object, finding: AdapterFailureKind
) -> None:
    baseline = AdapterObservation(
        protocol_version=ADAPTER_PROTOCOL_VERSION,
        invocation_id="mutation-probe",
        session_id="mutation-session",
        provider_id="cline-pass",
        model_id="cline-pass/qwen3.8-max",
        backend_mode="local",
        declared_model_turn_count=2,
        provider_attempts_by_turn=(1, 1),
        side_effect_certainty=SideEffectCertainty.PROVIDER_ACCEPTED,
        capability_snapshot_sha256=HEX,
        transcript_sha256=HEX,
    )
    assert validate_adapter_observation(baseline) == ()

    mutated = replace(baseline, **{field: value})
    assert finding in validate_adapter_observation(mutated)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "tool_decisions",
            (
                ToolDecisionRecord("run_commands", True, ""),
                ToolDecisionRecord("editor", True, ""),
            ),
        ),
        ("artifact_hash", "0" * 64),
        ("verification", replace(_verification(_contract(Path("/tmp"))), candidate_exit_code=1)),
    ],
)
def test_worker_run_mutations_fail_after_unmutated_fixture_passes(
    tmp_path: Path, field: str, value: object
) -> None:
    contract = _contract(tmp_path)
    baseline = _run(contract)
    assert assess_worker_run(contract, baseline).verdict.value == "ADMITTED"

    mutated = replace(baseline, **{field: value})
    assert assess_worker_run(contract, mutated).verdict.value == "REJECTED"
