from __future__ import annotations

from sakg.baseline import run_baseline


def test_empty_graph_is_a_valid_cold_start_and_returns_empty_result() -> None:
    payload = run_baseline(graph=[])
    assert payload["empty_graph_result"] == []
    assert payload["sakg_reachable"] is False
    assert payload["with_sakg"] == payload["without_sakg"]
