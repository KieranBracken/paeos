"""Dependency edges are directed and must remain acyclic."""
from __future__ import annotations

import pytest

from sakg.traverse import DependencyCycleError, dependency_is_acyclic, validate_dependency_acyclic

A = "sakg://demo/Decision/01J000000000000000000000001"
B = "sakg://demo/Outcome/01J000000000000000000000002"
C = "sakg://demo/Option/01J000000000000000000000003"


def edge(source: str, target: str, name: str) -> dict[str, object]:
    return {"edge_id": name, "namespace": "demo", "source": source, "target": target, "family": "dependency", "relation": "requires", "properties": {}, "evidence": [], "created_at": "2026-09-02T00:00:00Z"}


def test_acyclic_chain_is_accepted() -> None:
    validate_dependency_acyclic((edge(A, B, "ab"), edge(B, C, "bc")))
    assert dependency_is_acyclic((edge(A, B, "ab"), edge(B, C, "bc")))


def test_cycle_is_rejected_with_cycle_path() -> None:
    graph = (edge(A, B, "ab"), edge(B, C, "bc"), edge(C, A, "ca"))
    with pytest.raises(DependencyCycleError) as caught:
        validate_dependency_acyclic(graph)
    assert caught.value.cycle[0] == caught.value.cycle[-1]
    assert not dependency_is_acyclic(graph)
