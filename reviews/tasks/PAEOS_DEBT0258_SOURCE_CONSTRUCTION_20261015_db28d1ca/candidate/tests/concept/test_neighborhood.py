from __future__ import annotations

from concept.model import SemanticNeighborhood
from concept.store import ConceptStore
from concept.traverse import Direction, TraversalRequest, materialize_neighborhood, traverse

from tests.concept._traverse_fixtures import append_graph, concept, edge


def test_materialize_neighborhood_is_reproducible_and_persisted(tmp_path) -> None:
    store = ConceptStore(tmp_path / "neighborhood.db")
    root, member = concept("root"), concept("member")
    relation = edge(root, member, "derivation", "derived_from")
    append_graph(store, (root, member), (relation,))
    request = TraversalRequest(
        namespace="demo",
        roots=(root.id,),
        direction=Direction.OUTGOING,
        families=("derivation",),
        max_hops=1,
        max_expansions=5,
        max_results=5,
    )
    result = traverse(store, request)

    first_uri = materialize_neighborhood(store, result)
    second_uri = materialize_neighborhood(store, result)

    assert first_uri == second_uri
    materialized = store.get_node(first_uri.uri)
    assert materialized is not None
    assert isinstance(materialized.payload, SemanticNeighborhood)
    assert materialized.payload.center_uri == root.id
    assert materialized.payload.members[0]["uri"] == member.id.uri
    assert materialized.payload.members[0]["why"][0]["relation"] == "derived_from"
    store.close()
