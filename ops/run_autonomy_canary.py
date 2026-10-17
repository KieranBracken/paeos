"""Run one synthetic autonomy canary and persist its raw evidence.

The runner is deliberately one-shot.  It reads a verifier-owned manifest and observation stream,
evaluates the ordered installed/reached/killed contract, and writes an immutable result beneath an
external state root.  It does not invoke a worker, provider, browser, shell mutation, or ref
operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from kernel.cas import is_valid_hash
from kernel.ledger import Event
from runtime.autonomy.canary import CanaryManifest, CanaryResult, adjudicate_canary


class CanaryRunnerError(ValueError):
    """The canary request or its verifier-owned inputs are invalid."""


def _git_toplevel() -> Path | None:
    """Return the current worktree root without changing repository state."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).resolve()


def _state_bound_file(path: Path, state_root: Path, label: str) -> Path:
    if not path.is_absolute():
        raise CanaryRunnerError(f"{label} must be an absolute path")
    resolved = path.resolve()
    try:
        resolved.relative_to(state_root)
    except ValueError as exc:
        raise CanaryRunnerError(f"{label} must be inside the external state root") from exc
    if path.is_symlink() or not path.is_file():
        raise CanaryRunnerError(f"{label} must be an existing regular file")
    return resolved


def _read_json(path: Path, state_root: Path, label: str) -> tuple[bytes, object]:
    bound = _state_bound_file(path, state_root, label)
    try:
        raw = bound.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise CanaryRunnerError(f"{label} is not valid JSON: {exc}") from exc
    return raw, value


def _manifest(value: object) -> CanaryManifest:
    if not isinstance(value, dict):
        raise CanaryRunnerError("manifest must be a JSON object")
    required = (
        "canary_id",
        "version",
        "target_hash",
        "mutation_hash",
        "expected_failure_code",
        "installer_hash",
    )
    missing = [key for key in required if key not in value]
    if missing:
        raise CanaryRunnerError("manifest is missing: " + ", ".join(missing))
    fields: dict[str, str] = {}
    for key in required:
        field = value[key]
        if not isinstance(field, str) or not field.strip() or any(char.isspace() for char in field):
            raise CanaryRunnerError(f"manifest field {key!r} must be a non-empty token")
        fields[key] = field
    for key in ("target_hash", "mutation_hash", "installer_hash"):
        if not is_valid_hash(fields[key]):
            raise CanaryRunnerError(f"manifest field {key!r} must be a lowercase SHA-256")
    return CanaryManifest(**fields)


def _observations(value: object) -> tuple[Event, ...]:
    if not isinstance(value, list) or not value:
        raise CanaryRunnerError("observations must be a non-empty JSON list")
    events: list[Event] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise CanaryRunnerError(f"observation {index} must be a JSON object")
        schema_ver = item.get("schema_ver")
        kind = item.get("kind")
        payload = item.get("payload", {})
        if isinstance(schema_ver, bool) or not isinstance(schema_ver, int) or schema_ver <= 0:
            raise CanaryRunnerError(f"observation {index} has an invalid schema_ver")
        if not isinstance(kind, str) or not kind.strip() or any(char.isspace() for char in kind):
            raise CanaryRunnerError(f"observation {index} has an invalid kind")
        if not isinstance(payload, dict):
            raise CanaryRunnerError(f"observation {index} payload must be an object")
        events.append(Event(schema_ver=schema_ver, kind=kind, payload=cast(Any, payload)))
    return tuple(events)


def _write_once(path: Path, data: bytes) -> None:
    """Publish one private immutable artifact, refusing replacement."""

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(data):
            written = os.write(descriptor, data[offset:])
            if written <= 0:
                raise CanaryRunnerError("evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _result_payload(
    *,
    manifest: CanaryManifest,
    result: CanaryResult,
    manifest_raw: bytes,
    observations_raw: bytes,
    sandbox_root: Path,
    task_package_hash: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "canary_id": result.canary_id,
        "manifest_hash": hashlib.sha256(manifest_raw).hexdigest(),
        "observations_hash": hashlib.sha256(observations_raw).hexdigest(),
        "target_hash": manifest.target_hash,
        "mutation_hash": manifest.mutation_hash,
        "task_package_hash": task_package_hash,
        "sandbox_root": str(sandbox_root),
        "installed": result.installed,
        "reached": result.reached,
        "killed": result.killed,
        "observed_failure_code": result.observed_failure_code,
        "evidence_refs": list(result.evidence_refs),
        "verdict": "PASS" if result.killed else "REMAND",
        "worker_counts": {"admitted": 0, "rejected": 0, "remediated": 0},
        "court_counts": {"sealed": 0, "remanded": 0, "remediated": 0},
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--sandbox-root", required=True, type=Path)
    parser.add_argument("--task-package-hash", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not args.state_root.is_absolute():
            raise CanaryRunnerError("state root must be absolute")
        state_root = args.state_root.resolve()
        if not state_root.is_dir():
            raise CanaryRunnerError("state root must be an existing directory")
        worktree = _git_toplevel()
        if worktree is not None and state_root.is_relative_to(worktree):
            raise CanaryRunnerError("state root must be outside the Git worktree")
        if not args.sandbox_root.is_absolute():
            raise CanaryRunnerError("sandbox root must be absolute")
        sandbox_root = args.sandbox_root.resolve()
        if not sandbox_root.is_dir():
            raise CanaryRunnerError("sandbox root must be an existing directory")
        if not is_valid_hash(args.task_package_hash):
            raise CanaryRunnerError("task package hash must be a lowercase SHA-256")

        manifest_raw, manifest_value = _read_json(args.manifest, state_root, "manifest")
        observations_raw, observations_value = _read_json(
            args.observations, state_root, "observations"
        )
        manifest = _manifest(manifest_value)
        observations = _observations(observations_value)
        result = adjudicate_canary(manifest, observations)

        evidence_dir = state_root / "autonomy-canary" / manifest.canary_id
        try:
            evidence_dir.mkdir(parents=True, mode=0o700)
        except FileExistsError as exc:
            raise CanaryRunnerError("canary transaction already exists") from exc
        os.chmod(evidence_dir, 0o700)
        _write_once(evidence_dir / "manifest.raw.json", manifest_raw)
        _write_once(evidence_dir / "observations.raw.json", observations_raw)
        payload = _result_payload(
            manifest=manifest,
            result=result,
            manifest_raw=manifest_raw,
            observations_raw=observations_raw,
            sandbox_root=sandbox_root,
            task_package_hash=args.task_package_hash,
        )
        result_raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        _write_once(evidence_dir / "result.json", result_raw)
        print(result_raw.decode().rstrip("\n"))
        return 0 if result.killed else 2
    except (CanaryRunnerError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
