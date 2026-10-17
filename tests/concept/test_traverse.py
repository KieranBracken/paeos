from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest
from concept.store import ConceptStore
from concept.traverse import (
    Direction,
    TraversalRequest,
    TraversalResult,
    traverse,
)

from tests.concept._traverse_fixtures import append_graph, concept, edge


def test_traversal_request_and_result_are_frozen_slot_dataclasses() -> None:
    request = TraversalRequest(namespace="demo", roots=())
    assert request.__slots__
    assert TraversalResult.__slots__
    assert all(field not in {"__dict__", "__weakref__"} for field in TraversalResult.__slots__)
    with pytest.raises(FrozenInstanceError):
        request.namespace = "other"
    assert fields(request)


def test_outgoing_bfs_returns_typed_nodes_edges_paths_and_exact_consumption(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    root, middle, leaf = concept("root"), concept("middle"), concept("leaf")
    first = edge(root, middle, "derivation", "derived_from", edge_tag="1")
    second = edge(middle, leaf, "derivation", "supersedes", edge_tag="2")
    append_graph(store, (root, middle, leaf), (first, second))

    result = traverse(
        store,
        TraversalRequest(
            namespace="demo",
            roots=(root.id,),
            direction=Direction.OUTGOING,
            families=("derivation",),
            max_hops=2,
            max_expansions=10,
            max_results=10,
        ),
    )

    assert result.nodes == (root.id, middle.id, leaf.id)
    assert result.edges == (first.id, second.id)
    assert result.budgets_consumed == {
        "steps": 2,
        "nodes": 3,
        "edges": 2,
        "expansions": 2,
    }
    assert result.truncated is False
    assert result.graph_snapshot_hash == store.snapshot_hash("demo")
    leaf_path = result.why[leaf.id.uri]
    assert leaf_path.node_uris == (root.id, middle.id, leaf.id)
    assert leaf_path.edge_uris == (first.id, second.id)
    assert [step.direction for step in leaf_path.steps] == [Direction.OUTGOING, Direction.OUTGOING]
    assert [step.relation for step in leaf_path.steps] == ["derived_from", "supersedes"]
    assert leaf_path.reason == "matched allow-listed derivation/supersedes path"
    assert result.edge_why[first.id.uri] == result.why[middle.id.uri]
    store.close()


def test_direction_incoming_and_both_are_explicit(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    root, middle = concept("root"), concept("middle")
    relation = edge(root, middle, "abstraction", "abstracts_to")
    append_graph(store, (root, middle), (relation,))

    incoming = traverse(
        store,
        TraversalRequest(
            namespace="demo",
            roots=(middle.id,),
            direction=Direction.INCOMING,
            families=("abstraction",),
            max_hops=1,
            max_expansions=1,
            max_results=1,
        ),
    )
    both = traverse(
        store,
        TraversalRequest(
            namespace="demo",
            roots=(root.id,),
            direction=Direction.BOTH,
            families=("abstraction",),
            max_hops=1,
            max_expansions=1,
            max_results=1,
        ),
    )

    assert incoming.nodes == (middle.id, root.id)
    assert incoming.why[root.id.uri].steps[0].direction is Direction.INCOMING
    assert both.nodes == (root.id, middle.id)
    assert both.why[middle.id.uri].steps[0].direction is Direction.OUTGOING
    store.close()


def test_unknown_family_relation_and_negative_budget_fail_closed(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    root = concept("root")
    store.append_node(root)

    with pytest.raises(ValueError, match="unknown edge family"):
        traverse(
            store,
            TraversalRequest(namespace="demo", roots=(root.id,), families=("unknown",)),
        )
    with pytest.raises(ValueError, match="unknown relation"):
        traverse(
            store,
            TraversalRequest(namespace="demo", roots=(root.id,), relations=("unknown",)),
        )
    with pytest.raises(ValueError, match="non-negative"):
        TraversalRequest(namespace="demo", roots=(root.id,), max_hops=-1)
    store.close()


def test_expansion_budget_counts_only_admitted_hops_and_marks_omissions(tmp_path) -> None:
    store = ConceptStore(tmp_path / "expansions.db")
    root, first, second = concept("root"), concept("first"), concept("second")
    append_graph(
        store,
        (root, first, second),
        (
            edge(root, first, "derivation", "derived_from", edge_tag="1"),
            edge(root, second, "derivation", "derived_from", edge_tag="2"),
        ),
    )

    result = traverse(
        store,
        TraversalRequest(
            namespace="demo",
            roots=(root.id,),
            families=("derivation",),
            max_hops=1,
            max_expansions=1,
            max_results=10,
        ),
    )

    assert len(result.nodes) == 2
    assert result.budgets_consumed == {"steps": 1, "nodes": 2, "edges": 1, "expansions": 1}
    assert result.omitted == 1
    assert result.truncated is True
    store.close()
