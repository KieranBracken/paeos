from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "ops" / "control_plane_watchdog.py"


def snapshot_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_id": "req-001",
        "transaction_key": "a" * 64,
        "state": "CLAIMED",
        "fencing_token": 2,
        "last_heartbeat_monotonic": 700.0,
        "last_meaningful_monotonic": 700.0,
        "active_tool_deadline_monotonic": None,
        "transaction_deadline_monotonic": 1_000.0,
        "side_effect_certainty": "NOT_ATTEMPTED",
        "observed_ledger_head": "b" * 64,
        "evidence_hashes": ["c" * 64],
        "projection_verified": True,
        "shared_integrity_healthy": True,
        "now_monotonic": 700.0,
    }
    payload.update(changes)
    return payload


def run_cli(
    state_root: Path,
    snapshot_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(CLI), "--state-root", str(state_root)]
    if snapshot_path is not None:
        args.extend(["--snapshot", str(snapshot_path)])
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def test_cli_reads_one_bound_snapshot_and_prints_machine_json(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    snapshot_path = state_root / "liveness.json"
    snapshot_path.write_text(json.dumps(snapshot_payload()), encoding="utf-8")

    result = run_cli(state_root)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["action"] == "NONE"
    assert output["reason_code"] == "MEANINGFUL_PROGRESS_FRESH"
    assert output["transaction_key"] == "a" * 64
    assert "\n" not in result.stdout.strip()


def test_cli_returns_nonzero_for_unverified_projection(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    (state_root / "liveness.json").write_text(
        json.dumps(snapshot_payload(projection_verified=False)), encoding="utf-8"
    )

    result = run_cli(state_root)

    assert result.returncode != 0
    output = json.loads(result.stdout)
    assert output["action"] == "HALT_SHARED_CONTROL_PLANE"
    assert output["reason_code"] == "PROJECTION_UNVERIFIED"


def test_cli_rejects_snapshot_outside_state_root(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(snapshot_payload()), encoding="utf-8")

    result = run_cli(state_root, outside)

    assert result.returncode != 0
    assert "state root" in result.stderr.lower()


def test_cli_fails_closed_for_missing_or_malformed_snapshot(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    result = run_cli(state_root)
    assert result.returncode != 0
    assert "snapshot" in result.stderr.lower()

    (state_root / "liveness.json").write_text("{not-json", encoding="utf-8")
    malformed = run_cli(state_root)
    assert malformed.returncode != 0
    assert "malformed" in malformed.stderr.lower()


def test_active_cli_contains_no_gui_or_retry_paths() -> None:
    source = CLI.read_text(encoding="utf-8").lower()
    for forbidden in ("pbcopy", "osascript", "cdp", "websocket", "time.sleep", "retry"):
        assert forbidden not in source


@pytest.mark.parametrize("legacy", [ROOT / "ops" / "chatgpt_bridge" / "monitor_loop.py"])
def test_legacy_monitor_is_explicitly_disabled(legacy: Path) -> None:
    source = legacy.read_text(encoding="utf-8").lower()
    assert "disabled" in source
    assert "pbcopy" not in source
    assert "osascript" not in source
