"""Contract tests for the one-shot, no-promotion autonomy canary runner."""

from __future__ import annotations

import json
from pathlib import Path

from ops import run_autonomy_canary


def _write_inputs(root: Path, *, killed: bool = True) -> tuple[Path, Path]:
    manifest = root / "manifest.json"
    observations = root / "observations.json"
    manifest.write_text(
        json.dumps(
            {
                "canary_id": "CANARY-CLI-001",
                "version": "1",
                "target_hash": "a" * 64,
                "mutation_hash": "b" * 64,
                "expected_failure_code": "FENCE_EXPIRED",
                "installer_hash": "c" * 64,
            }
        ),
        encoding="utf-8",
    )
    bound = {
        "canary_id": "CANARY-CLI-001",
        "version": "1",
        "target_hash": "a" * 64,
        "mutation_hash": "b" * 64,
        "installer_hash": "c" * 64,
        "transaction_id": "tx-cli-001",
    }
    events = [
        {"schema_ver": 1, "kind": "CANARY_INSTALLED", "payload": bound},
        {"schema_ver": 1, "kind": "CANARY_REACHED", "payload": bound},
    ]
    if killed:
        events.append(
            {
                "schema_ver": 1,
                "kind": "CANARY_KILLED",
                "payload": {
                    **bound,
                    "observed_failure_code": "FENCE_EXPIRED",
                    "evidence_ref": "evidence-cli-001",
                },
            }
        )
    observations.write_text(json.dumps(events), encoding="utf-8")
    return manifest, observations


def _argv(state_root: Path, manifest: Path, observations: Path) -> list[str]:
    return [
        "--state-root",
        str(state_root),
        "--manifest",
        str(manifest),
        "--observations",
        str(observations),
        "--sandbox-root",
        str(state_root / "sandbox"),
        "--task-package-hash",
        "d" * 64,
    ]


def test_one_shot_runner_records_pass_without_side_effects(tmp_path: Path, capsys) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    (state_root / "sandbox").mkdir()
    manifest, observations = _write_inputs(state_root)

    assert run_autonomy_canary.main(_argv(state_root, manifest, observations)) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["verdict"] == "PASS"
    assert output["canary_id"] == "CANARY-CLI-001"
    assert output["worker_counts"] == {"admitted": 0, "rejected": 0, "remediated": 0}
    assert output["court_counts"] == {"sealed": 0, "remanded": 0, "remediated": 0}
    evidence_dir = state_root / "autonomy-canary" / "CANARY-CLI-001"
    assert (evidence_dir / "manifest.raw.json").read_bytes() == manifest.read_bytes()
    assert (evidence_dir / "observations.raw.json").read_bytes() == observations.read_bytes()
    assert (evidence_dir / "result.json").exists()


def test_runner_returns_nonzero_and_preserves_remand(tmp_path: Path, capsys) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    (state_root / "sandbox").mkdir()
    manifest, observations = _write_inputs(state_root, killed=False)

    assert run_autonomy_canary.main(_argv(state_root, manifest, observations)) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["verdict"] == "REMAND"
    assert output["killed"] is False


def test_runner_refuses_reuse_of_canary_transaction(tmp_path: Path, capsys) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    (state_root / "sandbox").mkdir()
    manifest, observations = _write_inputs(state_root)
    argv = _argv(state_root, manifest, observations)

    assert run_autonomy_canary.main(argv) == 0
    capsys.readouterr()
    assert run_autonomy_canary.main(argv) == 2
    assert "already exists" in capsys.readouterr().err.lower()


def test_runner_requires_inputs_under_external_state_root(tmp_path: Path, capsys) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    (state_root / "sandbox").mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    argv = _argv(state_root, outside, outside)
    assert run_autonomy_canary.main(argv) == 2
    assert "state root" in capsys.readouterr().err.lower()


def test_active_runner_has_no_transport_or_ref_update_path() -> None:
    source = Path(run_autonomy_canary.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "update-ref",
        "git push",
        "git merge",
        "osascript",
        "pbcopy",
        "time.sleep",
        "retry",
    ):
        assert forbidden not in source
