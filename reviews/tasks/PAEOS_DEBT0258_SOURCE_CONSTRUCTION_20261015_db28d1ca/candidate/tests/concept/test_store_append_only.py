from __future__ import annotations

import sqlite3

import pytest
from concept.store import ConceptStore

from tests.concept._store_fixtures import (
    concept_node,
    derivation_edge,
    hypothesis_node,
    outbox_event,
)


def test_domain_tables_reject_update_and_delete_at_trigger_layer(tmp_path) -> None:
    path = tmp_path / "concept.db"
    store = ConceptStore(path)
    source = concept_node("source")
    target = concept_node("target")
    hypothesis = hypothesis_node()
    store.append_nodes_and_edges(
        [source, target, hypothesis],
        [derivation_edge(source, target)],
    )
    store.append_outbox_event(outbox_event(hypothesis))
    store.close()

    connection = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only table"):
            connection.execute("UPDATE nodes SET namespace = 'other'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only table"):
            connection.execute("DELETE FROM nodes")
        with pytest.raises(sqlite3.IntegrityError, match="append-only table"):
            connection.execute("UPDATE edges SET relation = 'changed'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only table"):
            connection.execute("DELETE FROM edges")
        with pytest.raises(sqlite3.IntegrityError, match="append-only table"):
            connection.execute("UPDATE candidate_outbox SET event_type = 'REJECTED'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only table"):
            connection.execute("DELETE FROM candidate_outbox")
    finally:
        connection.close()


def test_public_store_has_no_mutation_like_methods() -> None:
    forbidden = {"update", "delete", "promote", "validate", "execute"}
    assert forbidden.isdisjoint(dir(ConceptStore))
