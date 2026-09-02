"""Every emitted result carries a complete explanation path."""
from __future__ import annotations

from sakg.project import project


def test_every_result_has_nonempty_why_path() -> None:
    request = {
        "method": "memory_augment", "subject": "reliability", "namespace": ["demo"],
        "budget": {"max_tokens": 1000, "max_nodes": 4, "tier": "SUMMARY"},
        "filters": {"min_confidence": 0, "as_of": "2026-09-02T00:00:00Z", "status": ["candidate"]},
    }
    nodes = ({
        "id": "sakg://demo/Pattern/01ARZ3NDEKTSV4RRFFQ69G5F01", "type": "Pattern",
        "namespace": "demo", "status": "candidate", "label": "Reliability pattern",
        "summary": "A tested reliability approach", "confidence": 0.8,
    },)
    response = project(request, nodes)
    assert response["results"]
    assert all(isinstance(item["why"], str) and item["why"] for item in response["results"])
    assert all("->" in item["why"] for item in response["results"])
