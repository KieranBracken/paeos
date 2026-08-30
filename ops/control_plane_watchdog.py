#!/usr/bin/env python3
"""Run-once event watchdog CLI.

The CLI reads one state-root-bound liveness snapshot and emits one JSON proposal.  It has no
process, browser, terminal, clipboard, or filesystem mutation path; a coordinator must apply any
proposal after its own compare-before-commit checks.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

class WatchdogCliError(ValueError):
    """The supplied state-root snapshot is absent, malformed, or out of scope."""


def _within_state_root(path: Path, state_root: Path) -> bool:
    try:
        path.relative_to(state_root)
    except ValueError:
        return False
    return True


def load_snapshot(
    snapshot_path: Path,
    state_root: Path,
) -> tuple[Any, bool, bool, bool, float]:
    """Load and validate one immutable JSON snapshot beneath ``state_root``."""

    resolved_root = state_root.resolve()
    resolved_path = snapshot_path.resolve()
    if not _within_state_root(resolved_path, resolved_root):
        raise WatchdogCliError("snapshot must be inside the state root")
    from runtime.control_plane.events import SideEffectCertainty
    from runtime.control_plane.liveness import LivenessSnapshot
    from runtime.integrations.bridge_protocol import TransactionState

    try:
        raw = resolved_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WatchdogCliError(f"snapshot cannot be read: {exc}") from exc
    try:
        payload: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WatchdogCliError("snapshot is malformed JSON") from exc
    if not isinstance(payload, dict):
        raise WatchdogCliError("snapshot must contain a JSON object")
    required = {
        "transaction_key",
        "state",
        "fencing_token",
        "last_heartbeat_monotonic",
        "last_meaningful_monotonic",
        "active_tool_deadline_monotonic",
        "transaction_deadline_monotonic",
        "side_effect_certainty",
        "projection_verified",
        "shared_integrity_healthy",
        "now_monotonic",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise WatchdogCliError("snapshot is missing required fields: " + ", ".join(missing))
    try:
        evidence_raw = payload.get("evidence_hashes", [])
        if not isinstance(evidence_raw, list):
            raise TypeError("evidence_hashes must be a JSON list")
        snapshot = LivenessSnapshot(
            request_id=_string(payload, "request_id", default=""),
            transaction_key=_string(payload, "transaction_key"),
            state=TransactionState(_string(payload, "state")),
            fencing_token=payload["fencing_token"],
            last_heartbeat_monotonic=payload["last_heartbeat_monotonic"],
            last_meaningful_monotonic=payload["last_meaningful_monotonic"],
            active_tool_deadline_monotonic=payload["active_tool_deadline_monotonic"],
            transaction_deadline_monotonic=payload["transaction_deadline_monotonic"],
            side_effect_certainty=SideEffectCertainty(
                _string(payload, "side_effect_certainty")
            ),
            observed_ledger_head=_string(payload, "observed_ledger_head", default=""),
            evidence_hashes=tuple(evidence_raw),
        )
        projection_verified = payload["projection_verified"]
        shared_integrity_healthy = payload["shared_integrity_healthy"]
        if not isinstance(projection_verified, bool):
            raise TypeError("projection_verified must be boolean")
        if not isinstance(shared_integrity_healthy, bool):
            raise TypeError("shared_integrity_healthy must be boolean")
        now_monotonic = payload["now_monotonic"]
        if isinstance(now_monotonic, bool) or not isinstance(now_monotonic, (int, float)):
            raise TypeError("now_monotonic must be numeric")
        return (
            snapshot,
            projection_verified,
            shared_integrity_healthy,
            bool(payload.get("trace_b", False)),
            float(now_monotonic),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WatchdogCliError(f"snapshot is invalid: {exc}") from exc


def _string(payload: dict[str, Any], key: str, *, default: str | None = None) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def run_once(
    state_root: Path,
    snapshot_path: Path | None = None,
) -> tuple[Any, dict[str, object], int]:
    from runtime.control_plane.liveness import assess_liveness
    from runtime.control_plane.watchdog import decide_recovery

    resolved_root = state_root.resolve()
    path = (resolved_root / "liveness.json") if snapshot_path is None else snapshot_path
    snapshot, projection_verified, shared_integrity_healthy, trace_b, now = load_snapshot(
        path,
        resolved_root,
    )
    decision = decide_recovery(
        snapshot,
        now_monotonic=now,
        projection_verified=projection_verified,
        shared_integrity_healthy=shared_integrity_healthy,
        trace_b=trace_b,
    )
    assessment = assess_liveness(snapshot, now_monotonic=now, trace_b=trace_b)
    output: dict[str, object] = {
        "action": decision.action.value,
        "reason_code": decision.reason_code,
        "transaction_key": decision.transaction_key,
        "request_id": decision.request_id,
        "fencing_token": decision.fencing_token,
        "observed_ledger_head": decision.observed_ledger_head,
        "evidence_hashes": list(decision.evidence_hashes),
        "assessment_status": assessment.status.value,
    }
    exit_code = 2 if decision.action.value == "HALT_SHARED_CONTROL_PLANE" else 0
    return decision, output, exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PAEOS run-once event watchdog")
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args(argv)
    try:
        _, output, exit_code = run_once(args.state_root, args.snapshot)
    except WatchdogCliError as exc:
        print(f"watchdog error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
