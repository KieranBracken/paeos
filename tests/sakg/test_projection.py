"""Core ranking, filtering, and advisory response behavior."""
from __future__ import annotations

import json

import pytest
from sakg.project import ProjectionError, project

REQUEST = {
    "method": "tradeoff_precedents",
    "subject": "latency durability",
    "namespace": ["demo"],
    "budget": {"max_tokens": 500, "max_nodes": 8, "tier": "SUMMARY"},
    "filters": {"min_confidence": 0.5, "as_of": "2026-09-02T00:00:00Z", "status": ["canonical", "candidate"]},
}
NODES = (
    {"id": "sakg://demo/Decision/01ARZ3NDEKTSV4RRFFQ69G5F01", "type": "Decision", "namespace": "demo", "status": "candidate", "label": "Durability decision", "summary": "Retain durability despite latency", "confidence": 0.9},
    {"id": "sakg://demo/Decision/01ARZ3NDEKTSV4RRFFQ69G5F02", "type": "Decision", "namespace": "demo", "status": "canonical", "label": "Latency decision", "summary": "Optimize for latency", "confidence": 0.7},
    {"id": "sakg://other/Decision/01ARZ3NDEKTSV4RRFFQ69G5F03", "type": "Decision", "namespace": "other", "status": "canonical", "label": "Foreign", "summary": "Must not cross namespace", "confidence": 1.0},
)


def test_project_ranks_and_filters_without_mutating_nodes() -> None:
    original = json.dumps(NODES, sort_keys=True)
    response = project(REQUEST, NODES)
    assert [item["node_summary"]["id"] for item in response["results"]] == [NODES[0]["id"], NODES[1]["id"]]
    assert response["trust"] == "untrusted"
    assert response["omitted"] == 0
    assert json.dumps(NODES, sort_keys=True) == original


def test_project_rejects_full_tier_and_malformed_budget() -> None:
    full = {**REQUEST, "budget": {**REQUEST["budget"], "tier": "FULL"}}
    with pytest.raises(ProjectionError):
        project(full, NODES)
    bad = {**REQUEST, "budget": {**REQUEST["budget"], "max_tokens": 0}}
    with pytest.raises(ProjectionError):
        project(bad, NODES)
