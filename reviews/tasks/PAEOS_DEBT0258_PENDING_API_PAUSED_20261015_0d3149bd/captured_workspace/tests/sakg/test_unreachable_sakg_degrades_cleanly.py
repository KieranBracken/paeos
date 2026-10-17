from __future__ import annotations

from sakg.baseline import run_baseline


class UnreachableGraph:
    def baseline_metrics(self, goal_id: str) -> object:
        raise ConnectionError(f"unreachable graph: {goal_id}")


def test_unreachable_sakg_degrades_to_baseline_without_error() -> None:
    payload = run_baseline(graph=UnreachableGraph())
    assert payload["degraded_cleanly"] is True
    assert payload["sakg_reachable"] is False
    assert payload["with_sakg"] == payload["without_sakg"]
