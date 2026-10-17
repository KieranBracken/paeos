from __future__ import annotations

from concept.store import ConceptStore
from concept.traverse import TraversalRequest, materialize_neighborhood, traverse

from tests.concept._traverse_fixtures import append_graph, concept, edge


def test_neighborhood_budget_drops_whole_members_and_counts_omissions(tmp_path) -> None:
    store = ConceptStore(tmp_path / "budget.db")
    root, first, second = concept("root"), concept("first"), concept("second")
    edges = (
        edge(root, first, "derivation", "derived_from", edge_tag="1"),
        edge(root, second, "derivation", "derived_from", edge_tag="2"),
    )
    append_graph(store, (root, first, second), edges)

    result = traverse(
        store,
        TraversalRequest(
            namespace="demo",
            roots=(root.id,),
            families=("derivation",),
            max_hops=1,
            max_expansions=10,
            max_results=10,
            max_serialized_bytes=1,
        ),
    )
    uri = materialize_neighborhood(store, result)
    materialized = store.get_node(uri.uri)

    assert materialized is not None
    payload = materialized.payload
    assert payload.members == ()
    assert payload.to_dict()["omitted"] == 2
    assert payload.to_dict()["truncated"] is True
    store.close()
