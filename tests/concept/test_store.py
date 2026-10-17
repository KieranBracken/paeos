from __future__ import annotations

from concept.model import NodeEnvelope
from concept.store import ConceptStore, EdgeQuery, NodeQuery

from tests.concept._store_fixtures import concept_node, derivation_edge


def test_store_appends_and_reads_nodes_and_edges(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    source = concept_node("source")
    target = concept_node("target")

    assert store.append_node(source) == source.id.uri
    assert store.append_node(target) == target.id.uri
    edge = derivation_edge(source, target)
    assert store.append_edge(edge) == edge.id.uri

    assert store.get_node(source.id.uri) == source
    assert list(store.iter_nodes(NodeQuery(namespace="demo"))) == sorted(
        [source, target], key=lambda node: node.id.uri
    )
    assert list(store.iter_edges(EdgeQuery(namespace="demo"))) == [edge]
    assert store.get_node("concept://demo/concept/00000000000000000000000000") is None
    store.close()


def test_store_reopens_without_losing_immutable_rows(tmp_path) -> None:
    path = tmp_path / "concept.db"
    node = concept_node("durable")
    first = ConceptStore(path)
    first.append_node(node)
    first.close()

    second = ConceptStore(path)
    result = second.get_node(node.id.uri)
    assert isinstance(result, NodeEnvelope)
    assert result == node
    second.close()
