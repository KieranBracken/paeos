from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sakg.baseline import GoalMetrics, GoalObservation, run_baseline


def test_fixed_goal_harness_reports_all_required_deltas(tmp_path: Path) -> None:
    payload = run_baseline()
    assert set(payload) >= {"research_spawns_delta", "remands_delta", "tokens_delta"}
    assert payload["goal_count"] == 3
    assert payload["allow_list"] == {"without_sakg": [], "with_sakg": ["sakg:read"]}
    output = tmp_path / "baseline.json"
    subprocess.run(
        [
            "/Users/bob/GitHub/paeos/.venv/bin/python",
            "-m",
            "sakg.baseline",
            "report",
            "--emit-json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert set(json.loads(output.read_text(encoding="utf-8"))) >= {
        "research_spawns_delta",
        "remands_delta",
        "tokens_delta",
    }


def test_bound_graph_observation_is_compared_without_inference() -> None:
    goals = (GoalObservation("g1", GoalMetrics(3, 2, 100), GoalMetrics(1, 0, 70)),)
    payload = run_baseline(
        goals, graph={"metrics": {"g1": {"research_spawns": 1, "l10_remands": 0, "tokens": 70}}}
    )
    assert payload["research_spawns_delta"] == -2
    assert payload["remands_delta"] == -2
    assert payload["tokens_delta"] == -30
