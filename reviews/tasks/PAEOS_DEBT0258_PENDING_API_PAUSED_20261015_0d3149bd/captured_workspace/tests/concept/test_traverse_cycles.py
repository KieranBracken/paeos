from __future__ import annotations

import pytest
from concept.store import ConceptStore
from concept.traverse import TraversalCycleError, TraversalRequest, traverse

from tests.concept._traverse_fixtures import append_graph, concept, edge


@pytest.mark.parametrize("relation", ["derived_from", "supersedes"])
def test_derivation_and_supersession_cycles_fail_closed(tmp_path, relation: str) -> None:
    store = ConceptStore(tmp_path / f"{relation}.db")
    first, second = concept("first"), concept("second")
    edges = (
        edge(first, second, "derivation", relation, edge_tag="1"),
        edge(second, first, "derivation", relation, edge_tag="2"),
    )
    append_graph(store, (first, second), edges)

    with pytest.raises(TraversalCycleError) as exc_info:
        traverse(
            store,
            TraversalRequest(
                namespace="demo",
                roots=(first.id,),
                families=("derivation",),
                relations=(relation,),
                max_hops=20,
                max_expansions=20,
                max_results=20,
            ),
        )

    assert exc_info.value.cycle == (first.id, second.id, first.id)
    store.close()


def test_noncyclic_converging_derivation_paths_are_deduplicated(tmp_path) -> None:
    store = ConceptStore(tmp_path / "converging.db")
    root, left, right, target = (concept(name) for name in ("root", "left", "right", "target"))
    edges = (
        edge(root, left, "derivation", "derived_from", edge_tag="1"),
        edge(root, right, "derivation", "derived_from", edge_tag="2"),
        edge(left, target, "derivation", "derived_from", edge_tag="3"),
        edge(right, target, "derivation", "derived_from", edge_tag="4"),
    )
    append_graph(store, (root, left, right, target), edges)

    result = traverse(
        store,
        TraversalRequest(
            namespace="demo",
            roots=(root.id,),
            families=("derivation",),
            max_hops=2,
            max_expansions=10,
            max_results=10,
        ),
    )

    expected_level = tuple(sorted((left.id, right.id), key=lambda uri: uri.uri))
    assert result.nodes == (root.id, *expected_level, target.id)
    assert len(result.why[target.id.uri].edge_uris) == 2
    assert result.budgets_consumed["nodes"] == 4
    store.close()
