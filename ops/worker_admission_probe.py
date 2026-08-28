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
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from paeos.model_router.types import ModelFamily
from runtime.integrations.cline_worker import ClineWorkerTransport
from runtime.worker_admission import AdmissionError, ProbeContract, RawWorkerRun

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


def _payload(
    *,
    probe_id: str,
    provider: str,
    model: str,
    family: ModelFamily,
    run: RawWorkerRun | None,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "probe_id": probe_id,
        "verdict": "ADMITTED" if run is not None else "REJECTED",
        "reason_codes": reason_codes,
        "provider": provider,
        "model": model,
        "family": family.value,
        "receipt_hash": run.receipt.receipt_hash if run is not None else "",
        "evidence": _evidence_hashes(run) if run is not None else {},
    }


def _print_summary(payload: dict[str, Any], evidence_dir: Path) -> None:
    for key in ("probe_id", "verdict", "provider", "model", "family", "receipt_hash"):
        print(f"{key}={payload[key]}")
    print(f"evidence_dir={evidence_dir}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Cline worker admission probe.")
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--probe-id", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--expected-family", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    return parser


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

    run: RawWorkerRun | None = None
    reason_codes: list[str] = []
    try:
        run = ClineWorkerTransport(
            timeout_seconds=args.timeout_seconds
        ).run_probe(contract, evidence_dir)
    except FileNotFoundError:
        reason_codes.append("CLINE_BINARY_NOT_FOUND")
    except AdmissionError:
        reason_codes.append("ADMISSION_REJECTED")
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
    return 0 if run is not None else 1


if __name__ == "__main__":
    sys.exit(main())
