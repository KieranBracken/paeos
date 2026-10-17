from __future__ import annotations

from concept.store import ConceptStore
from concept.traverse import TraversalRequest, traverse

from tests.concept._traverse_fixtures import analogy, append_graph, concept, edge, neighborhood


def test_analogy_edges_are_direct_only_and_not_transitive(tmp_path) -> None:
    store = ConceptStore(tmp_path / "analogy.db")
    analogy_one, analogy_two = analogy("one"), analogy("two")
    first, second = concept("first"), concept("second")
    edges = (
        edge(analogy_one, first, "analogy", "has_source", edge_tag="1"),
        edge(analogy_one, analogy_two, "analogy", "refines", edge_tag="2"),
        edge(analogy_two, second, "analogy", "has_target", edge_tag="3"),
    )
    append_graph(store, (analogy_one, analogy_two, first, second), edges)

    result = traverse(
        store,
        TraversalRequest(
            namespace="demo",
            roots=(analogy_one.id,),
            families=("analogy",),
            max_hops=10,
            max_expansions=10,
            max_results=10,
        ),
    )

    assert result.nodes == (analogy_one.id, analogy_two.id, first.id)
    assert second.id not in result.nodes
    assert max(len(path.edge_uris) for path in result.why.values()) == 1
    store.close()


def test_neighborhood_membership_is_a_nontransitive_snapshot_edge(tmp_path) -> None:
    store = ConceptStore(tmp_path / "neighborhood.db")
    center, member, nested = concept("center"), concept("member"), neighborhood(concept("nested"))
    nested_member = concept("nested-member")
    edges = (
        edge(center, member, "derivation", "derived_from", edge_tag="1"),
        edge(nested, nested_member, "neighborhood", "contains", edge_tag="2"),
        edge(center, nested, "neighborhood", "contains", edge_tag="3"),
    )
    append_graph(store, (center, member, nested, nested_member), edges)

    result = traverse(
        store,
        TraversalRequest(
            namespace="demo",
            roots=(center.id,),
            direction="outgoing",
            families=("neighborhood",),
            max_hops=10,
            max_expansions=10,
            max_results=10,
        ),
    )

    assert result.nodes == (center.id, nested.id)
    assert nested_member.id not in result.nodes
    assert len(result.why[nested.id.uri].edge_uris) == 1
    store.close()
