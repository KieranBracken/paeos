"""Coverage for all eight typed traversal families."""

from __future__ import annotations

import pytest
from sakg.traverse import TraversalError, walk_ids

NODES = (
    "sakg://demo/Decision/01J000000000000000000000001",
    "sakg://demo/Outcome/01J000000000000000000000002",
)
FAMILIES = (
    "structural",
    "dependency",
    "causal",
    "optimization",
    "constraint",
    "tradeoff",
    "problem",
    "similarity",
)


def _edge(family: str) -> dict[str, object]:
    return {
        "edge_id": f"edge-{family}",
        "namespace": "demo",
        "source": NODES[0],
        "target": NODES[1],
        "family": family,
        "relation": "links",
        "properties": {},
        "evidence": [],
        "created_at": "2026-09-02T00:00:00Z",
    }


@pytest.mark.parametrize("family", FAMILIES)
def test_each_registered_family_is_walkable(family: str) -> None:
    assert walk_ids((_edge(family),), NODES[0], family) == (NODES[1],)


def test_unknown_family_fails_closed() -> None:
    with pytest.raises(TraversalError):
        walk_ids((), NODES[0], "ranking")
