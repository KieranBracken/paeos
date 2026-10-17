from __future__ import annotations

import sqlite3

import pytest
from concept.store import ConceptStore

from tests.concept._store_fixtures import concept_node, derivation_edge, typed_uri


def test_batch_appends_nodes_before_edges_and_returns_counts(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    first = concept_node("zeta")
    second = concept_node("alpha")
    receipt = store.append_nodes_and_edges([first, second], [derivation_edge(first, second)])

    assert receipt.node_uris == tuple(sorted((first.id.uri, second.id.uri)))
    assert receipt.edge_uris == (derivation_edge(first, second).id.uri,)
    assert receipt.inserted_node_count == 2
    assert receipt.inserted_edge_count == 1


def test_batch_rolls_back_nodes_when_an_edge_fails(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    source = concept_node("source")
    missing = concept_node("missing")
    edge = derivation_edge(source, missing)

    with pytest.raises(sqlite3.IntegrityError, match="endpoint"):
        store.append_nodes_and_edges([source], [edge])

    assert store.get_node(source.id.uri) is None
    assert store.get_node(missing.id.uri) is None


def test_equivalent_batches_have_same_canonical_write_order_and_snapshot(tmp_path) -> None:
    first_store = ConceptStore(tmp_path / "first.db")
    second_store = ConceptStore(tmp_path / "second.db")
    first = concept_node("first")
    second = concept_node("second")
    edge = derivation_edge(first, second)

    first_store.append_nodes_and_edges([second, first], [edge])
    second_store.append_nodes_and_edges([first, second], [edge])

    assert first_store.snapshot_hash("demo") == second_store.snapshot_hash("demo")


def test_batch_rejects_cross_namespace_endpoint_without_partial_write(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    source = concept_node("source", namespace="demo")
    target = concept_node("target", namespace="other")
    edge = derivation_edge(source, target)

    with pytest.raises(ValueError, match="namespace"):
        store.append_nodes_and_edges([source, target], [edge])
    assert store.get_node(source.id.uri) is None
    assert store.get_node(target.id.uri) is None
    assert typed_uri(source.id.uri).namespace == "demo"
