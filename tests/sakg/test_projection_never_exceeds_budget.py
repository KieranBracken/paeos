"""A projection never exceeds either declared budget."""
from __future__ import annotations

from sakg.project import project


def node(index: int, tokens: int) -> dict[str, object]:
    return {
        "id": f"sakg://budget/Option/01ARZ3NDEKTSV4RRFFQ69G5F{index:02d}",
        "type": "Option", "namespace": "budget", "status": "candidate",
        "label": f"Option {index}", "summary": "A complete result", "confidence": 0.9,
        "estimated_tokens": tokens,
    }


def request(max_tokens: int, max_nodes: int) -> dict[str, object]:
    return {
        "method": "query_architectures", "subject": "complete result", "namespace": ["budget"],
        "budget": {"max_tokens": max_tokens, "max_nodes": max_nodes, "tier": "SUMMARY"},
        "filters": {"min_confidence": 0, "as_of": "2026-09-02T00:00:00Z", "status": ["candidate"]},
    }


def test_hard_limits_drop_whole_results_and_count_them() -> None:
    response = project(request(50, 2), (node(1, 40), node(2, 40), node(3, 1)))
    assert len(response["results"]) == 2
    assert response["omitted"] == 1
    assert response["truncated"] is True
    assert [item["node_summary"]["id"] for item in response["results"]] == [
        "sakg://budget/Option/01ARZ3NDEKTSV4RRFFQ69G5F01",
        "sakg://budget/Option/01ARZ3NDEKTSV4RRFFQ69G5F03",
    ]
