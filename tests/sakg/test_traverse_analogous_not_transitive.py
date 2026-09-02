"""The analogous_to relation is intentionally non-transitive."""
from __future__ import annotations

from sakg.traverse import traverse_analogous

A = "sakg://demo/Decision/01J000000000000000000000001"
B = "sakg://demo/Decision/01J000000000000000000000002"
C = "sakg://demo/Decision/01J000000000000000000000003"


def edge(source: str, target: str, name: str) -> dict[str, object]:
    return {"edge_id": name, "namespace": "demo", "source": source, "target": target, "family": "similarity", "relation": "analogous_to", "properties": {}, "evidence": [], "created_at": "2026-09-02T00:00:00Z"}


def test_analogous_walk_stops_at_direct_neighbors() -> None:
    assert traverse_analogous((edge(A, B, "ab"), edge(B, C, "bc")), A) == (B,)
