from __future__ import annotations

from concept.ids import canonical_json, content_hash
from concept.store import ConceptStore

from tests.concept._store_fixtures import (
    concept_node,
    derivation_edge,
    hypothesis_node,
    outbox_event,
)


def test_empty_snapshot_is_deterministic_and_namespace_scoped(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    assert store.snapshot_hash("demo") == store.snapshot_hash("demo")
    assert store.snapshot_hash("demo") != store.snapshot_hash("other")


def test_snapshot_hash_is_invariant_to_insertion_order(tmp_path) -> None:
    first_store = ConceptStore(tmp_path / "first.db")
    second_store = ConceptStore(tmp_path / "second.db")
    first = concept_node("first")
    second = concept_node("second")
    edge = derivation_edge(first, second)

    first_store.append_nodes_and_edges([first, second], [edge])
    second_store.append_nodes_and_edges([second, first], [edge])
    assert first_store.snapshot_hash("demo") == second_store.snapshot_hash("demo")


def test_nodes_edges_change_snapshot_but_outbox_does_not(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    first = concept_node("first")
    second = concept_node("second")
    hypothesis = hypothesis_node()
    store.append_nodes_and_edges([first, second, hypothesis], [derivation_edge(first, second)])
    before_outbox = store.snapshot_hash("demo")
    store.append_outbox_event(outbox_event(hypothesis))
    assert store.snapshot_hash("demo") == before_outbox

    store.append_node(concept_node("third"))
    assert store.snapshot_hash("demo") != before_outbox


def test_snapshot_digest_has_explicit_versioned_canonical_preimage(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    node = concept_node("known")
    store.append_node(node)
    node_preimage = node.to_dict()
    node_preimage.pop("id")
    node_preimage.pop("recorded_at")
    expected = content_hash(
        canonical_json(
            {
                "domain": "concept-os/graph-snapshot",
                "version": 1,
                "namespace": "demo",
                "nodes": [[node.id.uri, content_hash(canonical_json(node_preimage))]],
                "edges": [],
            }
        )
    )
    assert store.snapshot_hash("demo") == expected
