from __future__ import annotations

import pytest
from concept.traverse import CrossNamespaceDenied, TraversalRequest, traverse

from tests.concept._traverse_fixtures import MappingSnapshot, concept, mapping_edge


def test_cross_namespace_root_is_denied_without_explicit_read_policy() -> None:
    local = concept("local", namespace="demo")
    foreign = concept("foreign", namespace="other")
    snapshot = MappingSnapshot((local, foreign), ())

    with pytest.raises(CrossNamespaceDenied):
        traverse(snapshot, TraversalRequest(namespace="demo", roots=(foreign.id,)))


def test_cross_namespace_edge_requires_explicit_read_policy_and_is_then_visible() -> None:
    local = concept("local", namespace="demo")
    foreign = concept("foreign", namespace="other")
    cross_edge = mapping_edge(
        "edge-cross",
        "demo",
        local.id,
        foreign.id,
    )
    snapshot = MappingSnapshot((local, foreign), (cross_edge,))

    with pytest.raises(CrossNamespaceDenied):
        traverse(
            snapshot,
            TraversalRequest(namespace="demo", roots=(local.id,), max_hops=1),
        )

    result = traverse(
        snapshot,
        TraversalRequest(
            namespace="demo",
            roots=(local.id,),
            max_hops=1,
            read_policy={"demo": {"read": ("other",)}, "other": {"read": ("demo",)}},
        ),
    )

    assert result.nodes == (local.id, foreign.id)
    assert result.why[foreign.id.uri].steps[0].direction.value == "outgoing"
