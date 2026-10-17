"""Operator-boundary tests for the qualified SDK admission transport."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from paeos.model_router.types import ModelFamily, NormalizedErrorType
from runtime.integrations.cline_sdk_protocol import ProtocolError
from runtime.worker_adapter import (
    ADAPTER_PROTOCOL_VERSION,
    AdapterFailureKind,
    AdapterFailureReceipt,
    SideEffectCertainty,
)

from ops import worker_admission_probe
from tests.ops.test_worker_admission_probe import _admitted_run, _sdk_args


def _failure(normalized: NormalizedErrorType | None = None) -> AdapterFailureReceipt:
    empty = hashlib.sha256(b"").hexdigest()
    return AdapterFailureReceipt(
        protocol_version=ADAPTER_PROTOCOL_VERSION,
        invocation_id="test-probe",
        contract_id="test-probe",
        adapter_failure=AdapterFailureKind.ADAPTER_VERSION_UNQUALIFIED
        if normalized is None
        else None,
        normalized_error=normalized,
        additional_findings=(),
        side_effect_certainty=SideEffectCertainty.NOT_DISPATCHED,
        raw_stdout_sha256=empty,
        raw_stderr_sha256=empty,
        observation_sha256=empty,
    )


def test_sdk_tuple_is_required_before_state_creation(tmp_path: Path, capsys) -> None:
    state_root = tmp_path / "state"

    code = worker_admission_probe.main(
        [
            "--state-root",
            str(state_root),
            "--probe-id",
            "test-probe",
            "--provider",
            "cline-pass",
            "--model",
            "cline-pass/qwen3.8-max",
            "--expected-family",
            "qwen",
            "--transport",
            "cline-sdk",
        ]
    )

    assert code == 2
    assert "missing required SDK" in capsys.readouterr().err
    assert not state_root.exists()


def test_diagnostic_transport_is_rejected_and_counts_are_separate(tmp_path: Path, capsys) -> None:
    code = worker_admission_probe.main(
        [
            "--state-root",
            str(tmp_path / "state"),
            "--probe-id",
            "test-probe",
            "--provider",
            "cline-pass",
            "--model",
            "cline-pass/qwen3.8-max",
            "--expected-family",
            "qwen",
            "--transport",
            "cline-cli-diagnostic",
        ]
    )

    assert code == 1
    payload = json.loads(
        (tmp_path / "state/worker-admission/test-probe/admission-result.json").read_text()
    )
    assert payload["reason_codes"] == ["ADAPTER_VERSION_UNQUALIFIED"]
    assert payload["worker_counts"] == {"admitted": 0, "rejected": 1, "remediated": 0}
    assert payload["court_counts"] == {"sealed": 0, "remanded": 0, "remediated": 0}
    assert "worker_counts=" in capsys.readouterr().out


def test_typed_auth_failure_is_preserved_without_retry(tmp_path: Path, monkeypatch, capsys) -> None:
    calls = 0

    class AuthFailureAdapter:
        def __init__(self, config: object) -> None:
            pass

        def run_probe(self, contract: object) -> AdapterFailureReceipt:
            nonlocal calls
            calls += 1
            return _failure(NormalizedErrorType.AUTH_FAILED)

    monkeypatch.setattr(worker_admission_probe, "ClineSdkAdmissionAdapter", AuthFailureAdapter)

    code = worker_admission_probe.main(
        [
            "--state-root",
            str(tmp_path / "state"),
            "--probe-id",
            "test-probe",
            "--provider",
            "cline-pass",
            "--model",
            "cline-pass/qwen3.8-max",
            "--expected-family",
            "qwen",
            *_sdk_args(tmp_path),
        ]
    )

    assert code == 1
    assert calls == 1
    payload = json.loads(
        (tmp_path / "state/worker-admission/test-probe/admission-result.json").read_text()
    )
    assert payload["reason_codes"] == ["AUTH_FAILED"]
    assert payload["evidence"]["normalized_error"] == "AUTH_FAILED"
    assert "verdict=REJECTED" in capsys.readouterr().out


def test_sdk_success_has_no_court_seal_side_effect(tmp_path: Path, monkeypatch) -> None:
    calls = 0

    class SuccessAdapter:
        def __init__(self, config: object) -> None:
            pass

        def run_probe(self, contract: object):
            nonlocal calls
            calls += 1
            return _admitted_run()

    monkeypatch.setattr(worker_admission_probe, "ClineSdkAdmissionAdapter", SuccessAdapter)
    code = worker_admission_probe.main(
        [
            "--state-root",
            str(tmp_path / "state"),
            "--probe-id",
            "test-probe",
            "--provider",
            "cline-pass",
            "--model",
            "cline-pass/qwen3.8-max",
            "--expected-family",
            ModelFamily.QWEN.value,
            "--timeout-seconds",
            "17",
            *_sdk_args(tmp_path),
        ]
    )
    assert code == 0
    assert calls == 1
    payload = json.loads(
        (tmp_path / "state/worker-admission/test-probe/admission-result.json").read_text()
    )
    assert payload["court_counts"] == {"sealed": 0, "remanded": 0, "remediated": 0}


def test_protocol_error_is_persisted_as_canonical_rejection(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    class ProtocolFailureAdapter:
        def __init__(self, config: object) -> None:
            pass

        def run_probe(self, contract: object):
            raise ProtocolError("truncated frame")

    monkeypatch.setattr(worker_admission_probe, "ClineSdkAdmissionAdapter", ProtocolFailureAdapter)
    state_root = tmp_path / "state"
    code = worker_admission_probe.main(
        [
            "--state-root",
            str(state_root),
            "--probe-id",
            "test-probe",
            "--provider",
            "cline-pass",
            "--model",
            "cline-pass/qwen3.8-max",
            "--expected-family",
            ModelFamily.QWEN.value,
            *_sdk_args(tmp_path),
        ]
    )

    assert code == 1
    payload = json.loads(
        (state_root / "worker-admission/test-probe/admission-result.json").read_text()
    )
    assert payload["reason_codes"] == ["TRANSPORT_FAILED"]
    output = capsys.readouterr()
    assert "Traceback" not in output.out + output.err
