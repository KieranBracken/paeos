"""Run one fail-closed Cline worker-admission probe.

The utility owns only a fresh external evidence directory. It performs one
transport invocation, writes one atomic hash-only result, and never retries.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from paeos.model_router.types import ModelFamily
from runtime.integrations.cline_sdk import ClineSdkAdapterConfig, ClineSdkAdmissionAdapter
from runtime.integrations.cline_sdk_protocol import ProtocolError
from runtime.integrations.cline_sdk_qualification import (
    AdapterQualificationRecord,
    QualifiedFile,
)
from runtime.integrations.cline_worker import ClineWorkerTransport
from runtime.worker_adapter import AdapterFailureReceipt
from runtime.worker_admission import AdmissionError, ProbeContract, RawWorkerRun
from runtime.worker_profile import AuthenticatedProfileHandle

_PROBE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_PROVIDER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,255}\Z")


def _git_toplevel() -> Path | None:
    """Return the current worktree root without mutating repository state."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Durably publish canonical JSON in the already-private evidence dir."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    try:
        with temporary.open("xb") as handle:
            os.chmod(temporary, 0o600)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _evidence_hashes(run: RawWorkerRun) -> dict[str, Any]:
    verification = run.verification
    return {
        "artifact_hash": run.artifact_hash,
        "argv_hash": run.receipt.argv_hash,
        "manifest_hash": run.receipt.manifest_hash,
        "messages_hash": run.receipt.messages_hash,
        "stderr_hash": run.receipt.stderr_hash,
        "stdout_hash": run.receipt.stdout_hash,
        "verification": {
            "argv_hash": verification.argv_hash,
            "baseline_artifact_hash": verification.baseline_artifact_hash,
            "baseline_stderr_hash": verification.baseline_stderr_hash,
            "baseline_stdout_hash": verification.baseline_stdout_hash,
            "candidate_artifact_hash": verification.candidate_artifact_hash,
            "candidate_stderr_hash": verification.candidate_stderr_hash,
            "candidate_stdout_hash": verification.candidate_stdout_hash,
            "mutation_hash": verification.mutation_hash,
            "mutation_stderr_hash": verification.mutation_stderr_hash,
            "mutation_stdout_hash": verification.mutation_stdout_hash,
            "restored_artifact_hash": verification.artifact_restored_hash,
            "restored_stderr_hash": verification.restored_stderr_hash,
            "restored_stdout_hash": verification.restored_stdout_hash,
        },
    }


def _failure_evidence(failure: AdapterFailureReceipt) -> dict[str, Any]:
    return {
        "adapter_failure": failure.adapter_failure.value if failure.adapter_failure else "",
        "normalized_error": failure.normalized_error.value if failure.normalized_error else "",
        "observation_hash": failure.observation_sha256,
        "stderr_hash": failure.raw_stderr_sha256,
        "stdout_hash": failure.raw_stdout_sha256,
    }


def _payload(
    *,
    probe_id: str,
    provider: str,
    model: str,
    family: ModelFamily,
    run: RawWorkerRun | AdapterFailureReceipt | None,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "probe_id": probe_id,
        "verdict": "ADMITTED" if isinstance(run, RawWorkerRun) else "REJECTED",
        "reason_codes": reason_codes,
        "provider": provider,
        "model": model,
        "family": family.value,
        "receipt_hash": run.receipt.receipt_hash if isinstance(run, RawWorkerRun) else "",
        "evidence": (
            _evidence_hashes(run)
            if isinstance(run, RawWorkerRun)
            else _failure_evidence(run)
            if isinstance(run, AdapterFailureReceipt)
            else {}
        ),
        "worker_counts": {
            "admitted": 1 if isinstance(run, RawWorkerRun) else 0,
            "rejected": 0 if isinstance(run, RawWorkerRun) else 1,
            "remediated": 0,
        },
        "court_counts": {"sealed": 0, "remanded": 0, "remediated": 0},
    }


def _print_summary(payload: dict[str, Any], evidence_dir: Path) -> None:
    for key in ("probe_id", "verdict", "provider", "model", "family", "receipt_hash"):
        print(f"{key}={payload[key]}")
    print(f"worker_counts={json.dumps(payload['worker_counts'], sort_keys=True)}")
    print(f"court_counts={json.dumps(payload['court_counts'], sort_keys=True)}")
    print(f"evidence_dir={evidence_dir}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Cline worker admission probe.")
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--probe-id", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--expected-family", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--transport", choices=("cline-sdk", "cline-cli-diagnostic"))
    parser.add_argument("--qualification-record", type=Path)
    parser.add_argument("--profile-root", type=Path)
    parser.add_argument("--profile-uuid")
    parser.add_argument("--auth-epoch", type=int)
    parser.add_argument("--node-executable", type=Path)
    return parser


def _load_qualification(path: Path) -> AdapterQualificationRecord:
    value = json.loads(path.read_bytes())
    files = tuple(QualifiedFile(**item) for item in value.pop("files"))
    value["files"] = files
    return AdapterQualificationRecord(**value)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if not args.state_root.is_absolute():
        print("ERROR: state root must be absolute", file=sys.stderr)
        return 2
    if _PROBE_ID.fullmatch(args.probe_id) is None:
        print("ERROR: probe ID is invalid", file=sys.stderr)
        return 2
    if _PROVIDER_ID.fullmatch(args.provider) is None:
        print("ERROR: provider ID is invalid", file=sys.stderr)
        return 2
    if _MODEL_ID.fullmatch(args.model) is None or ".." in args.model.split("/"):
        print("ERROR: model ID is invalid", file=sys.stderr)
        return 2
    try:
        family = ModelFamily(args.expected_family)
    except ValueError:
        print("ERROR: expected family is not recognized", file=sys.stderr)
        return 2
    if family is ModelFamily.UNKNOWN:
        print("ERROR: expected family must be attributable", file=sys.stderr)
        return 2
    if not 1 <= args.timeout_seconds <= 1800:
        print("ERROR: timeout must be between 1 and 1800 seconds", file=sys.stderr)
        return 2
    if args.transport is None:
        print("ERROR: transport is required", file=sys.stderr)
        return 2

    qualification: AdapterQualificationRecord | None = None
    profile_uuid: uuid.UUID | None = None
    if args.transport == "cline-sdk":
        required = (
            (args.qualification_record, "qualification record"),
            (args.profile_root, "profile root"),
            (args.profile_uuid, "profile UUID"),
            (args.auth_epoch, "auth epoch"),
            (args.node_executable, "Node executable"),
        )
        missing = [label for value, label in required if value is None]
        if missing:
            print(f"ERROR: missing required SDK arguments: {', '.join(missing)}", file=sys.stderr)
            return 2
        assert args.qualification_record is not None
        assert args.profile_root is not None
        assert args.profile_uuid is not None
        assert args.auth_epoch is not None
        assert args.node_executable is not None
        if not args.qualification_record.is_absolute() or not args.profile_root.is_absolute():
            print("ERROR: qualification and profile paths must be absolute", file=sys.stderr)
            return 2
        if args.auth_epoch <= 0:
            print("ERROR: auth epoch must be positive", file=sys.stderr)
            return 2
        if not args.node_executable.is_absolute():
            print("ERROR: Node executable must be absolute", file=sys.stderr)
            return 2
        try:
            profile_uuid = uuid.UUID(args.profile_uuid)
            qualification = _load_qualification(args.qualification_record)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            print(f"ERROR: invalid qualification/profile arguments: {error}", file=sys.stderr)
            return 2

    state_root = args.state_root.resolve()
    git_root = _git_toplevel()
    if git_root is not None and state_root.is_relative_to(git_root):
        print("ERROR: state root is inside the Git worktree", file=sys.stderr)
        return 2

    evidence_dir = state_root / "worker-admission" / args.probe_id
    try:
        evidence_dir.mkdir(parents=True, mode=0o700)
        os.chmod(evidence_dir, 0o700)
    except FileExistsError:
        print("ERROR: probe directory already exists", file=sys.stderr)
        return 2

    if args.transport == "cline-sdk":
        assert args.qualification_record is not None
        assert args.profile_root is not None
        assert args.profile_uuid is not None
        assert args.auth_epoch is not None
        assert args.node_executable is not None
        assert qualification is not None
        assert profile_uuid is not None
        lease_root = evidence_dir / "leases"
        lease_root.mkdir(mode=0o700)
        transport: Any = ClineSdkAdmissionAdapter(
            ClineSdkAdapterConfig(
                node_executable=args.node_executable,
                host_module=Path(__file__).resolve().parents[1]
                / "runtime/integrations/cline_sdk_host.mjs",
                qualification=qualification,
                profile=AuthenticatedProfileHandle(
                    root=args.profile_root,
                    profile_uuid=profile_uuid,
                    auth_epoch=args.auth_epoch,
                ),
                timeout_seconds=float(args.timeout_seconds),
                lease_root=lease_root,
                process_start_token="operator-probe",
                boot_id="operator-boot",
            )
        )
    else:
        transport = ClineWorkerTransport()

    contract = ProbeContract(
        probe_id=args.probe_id,
        sandbox=evidence_dir / "sandbox",
        provider_id=args.provider,
        model_id=args.model,
        expected_family=family,
        artifact_name="artifact.txt",
        initial_bytes=b"baseline-worker\n",
        expected_bytes=b"admitted-worker\n",
        verification_command="python3 verify_probe.py",
    )

    run: RawWorkerRun | AdapterFailureReceipt | None = None
    reason_codes: list[str] = []
    try:
        run = (
            transport.run_probe(contract)
            if args.transport == "cline-sdk"
            else transport.run_probe(contract, evidence_dir)
        )
        if isinstance(run, AdapterFailureReceipt):
            reason_codes.extend(
                value
                for value in (
                    run.adapter_failure.value if run.adapter_failure else "",
                    run.normalized_error.value if run.normalized_error else "",
                )
                if value
            )
    except FileNotFoundError:
        reason_codes.append("CLINE_BINARY_NOT_FOUND")
    except AdmissionError:
        reason_codes.append("ADMISSION_REJECTED")
    except ProtocolError:
        reason_codes.append("TRANSPORT_FAILED")
    except OSError:
        reason_codes.append("TRANSPORT_IO_ERROR")

    payload = _payload(
        probe_id=args.probe_id,
        provider=args.provider,
        model=args.model,
        family=family,
        run=run,
        reason_codes=reason_codes,
    )
    _atomic_write_json(evidence_dir / "admission-result.json", payload)
    _print_summary(payload, evidence_dir)
    return 0 if isinstance(run, RawWorkerRun) else 1


if __name__ == "__main__":
    sys.exit(main())
