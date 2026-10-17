"""Read-only L01-L19 lifecycle revalidation over a state-root-bound SQLite ledger.

The command verifies the ledger chain without acquiring a writer token, folds the canonical
evidence matrix, and emits one stable JSON report.  It never changes the ledger, repository, CAS,
or lifecycle state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from kernel.cas import is_valid_hash
from kernel.ledger import GENESIS_HASH, Event, LedgerRow, compute_row_hash
from runtime.lifecycle_audit import LayerDisposition, LayerEvidence, audit_run


class LifecycleCliError(ValueError):
    """The requested read-only audit cannot be bound or verified."""


def _git_toplevel() -> Path | None:
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


def _bound_ledger(path: Path, state_root: Path) -> Path:
    if not path.is_absolute():
        raise LifecycleCliError("ledger path must be absolute")
    resolved = path.resolve()
    try:
        resolved.relative_to(state_root)
    except ValueError as exc:
        raise LifecycleCliError("ledger must be inside the state root") from exc
    if path.is_symlink() or not path.is_file():
        raise LifecycleCliError("ledger must be an existing regular file")
    return resolved


def _read_rows(path: Path) -> tuple[list[LedgerRow], str]:
    """Read and verify every row through SQLite's read-only URI mode."""

    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise LifecycleCliError(f"ledger cannot be opened read-only: {exc}") from exc
    rows: list[LedgerRow] = []
    try:
        connection.execute("PRAGMA query_only=ON")
        records = connection.execute(
            "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload "
            "FROM ledger_rows ORDER BY seq"
        ).fetchall()
    except (sqlite3.Error, ValueError) as exc:
        raise LifecycleCliError(f"ledger cannot be read: {exc}") from exc
    finally:
        connection.close()

    previous = GENESIS_HASH
    expected_seq = 1
    for record in records:
        if len(record) != 7:
            raise LifecycleCliError("ledger row has an invalid shape")
        seq, timestamp, prev_hash, row_hash, schema_ver, kind, raw_payload = record
        if not isinstance(seq, int) or not isinstance(timestamp, str):
            raise LifecycleCliError("ledger row has invalid sequence or timestamp")
        if not isinstance(prev_hash, str) or not isinstance(row_hash, str):
            raise LifecycleCliError("ledger row has invalid hash fields")
        if not isinstance(schema_ver, int) or not isinstance(kind, str):
            raise LifecycleCliError("ledger row has invalid event fields")
        if not isinstance(raw_payload, str):
            raise LifecycleCliError("ledger row payload is not text")
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise LifecycleCliError(f"ledger payload is malformed at sequence {seq}") from exc
        if not isinstance(payload, dict):
            raise LifecycleCliError(f"ledger payload is not an object at sequence {seq}")
        if seq != expected_seq:
            raise LifecycleCliError(
                f"ledger sequence gap/reorder: expected {expected_seq}, found {seq}"
            )
        if prev_hash != previous:
            raise LifecycleCliError(f"ledger predecessor mismatch at sequence {seq}")
        event = Event(schema_ver=schema_ver, kind=kind, payload=cast(Any, payload))
        calculated = compute_row_hash(prev_hash, seq, timestamp, event)
        if row_hash != calculated:
            raise LifecycleCliError(f"ledger content hash mismatch at sequence {seq}")
        rows.append(
            LedgerRow(
                seq=seq,
                timestamp=timestamp,
                event=event,
                prev_hash=prev_hash,
                row_hash=row_hash,
            )
        )
        previous = row_hash
        expected_seq += 1
    return rows, previous


class _ReadOnlyCas:
    """Minimal CAS view used by the auditor; it has no write or delete operation."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def has(self, key: str) -> bool:
        if not is_valid_hash(key):
            return False
        path = self._root / key[:2] / key[2:]
        try:
            data = path.read_bytes()
        except OSError:
            return False
        return hashlib.sha256(data).hexdigest() == key


def _layer_payload(layer: LayerEvidence) -> dict[str, object]:
    return {
        "layer": f"L{layer.layer:02d}",
        "disposition": layer.disposition.value,
        "ledger_sequences": list(layer.ledger_sequences),
        "artifact_hashes": list(layer.artifact_hashes),
        "evidence_hashes": list(layer.evidence_hashes),
        "model_receipt_hashes": list(layer.model_receipt_hashes),
        "reason_code": layer.reason_code,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not args.json:
            raise LifecycleCliError("--json is required for stable machine output")
        if not args.state_root.is_absolute():
            raise LifecycleCliError("state root must be absolute")
        state_root = args.state_root.resolve()
        if not state_root.is_dir():
            raise LifecycleCliError("state root must be an existing directory")
        if not args.run_id or any(char.isspace() for char in args.run_id):
            raise LifecycleCliError("run ID must be a non-empty token")
        repository = args.repository.resolve()
        if not args.repository.is_absolute() or not repository.is_dir():
            raise LifecycleCliError("repository must be an existing directory")
        if repository == state_root or repository.is_relative_to(state_root):
            raise LifecycleCliError("repository must be separate from the state root")
        worktree = _git_toplevel()
        if worktree is not None and state_root.is_relative_to(worktree):
            raise LifecycleCliError("state root must be outside the Git worktree")
        ledger_path = _bound_ledger(args.ledger, state_root)
        rows, verified_head = _read_rows(ledger_path)
        cas_root = state_root / "cas"
        cas: object | None = _ReadOnlyCas(cas_root) if cas_root.is_dir() else None
        report = audit_run(
            args.run_id,
            rows=rows,
            cas=cast(Any, cas),
            repository=repository,
        )
        output: dict[str, object] = {
            "schema_version": 1,
            "run_id": report.run_id,
            "trace": report.trace,
            "ledger": str(ledger_path),
            "repository": str(repository),
            "verified_ledger_head": verified_head,
            "layers": [_layer_payload(layer) for layer in report.layers],
            "sealed": report.sealed,
            "remanded": report.remanded,
            "remediated": report.remediated,
            "blocking_reason_codes": list(report.blocking_reason_codes),
        }
        encoded = (json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n").encode()
        print(encoded.decode().rstrip("\n"))
        has_unresolved = any(
            layer.disposition in {LayerDisposition.UNPROVEN, LayerDisposition.REMANDED}
            for layer in report.layers
        )
        return 2 if has_unresolved or report.blocking_reason_codes else 0
    except (LifecycleCliError, OSError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
