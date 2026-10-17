from __future__ import annotations

import sqlite3

import pytest
from concept.ids import IdentityCollisionError
from concept.store import CandidateOutboxEvent, ConceptStore

from tests.concept._store_fixtures import concept_node, hypothesis_node, outbox_event


def test_outbox_accepts_only_same_namespace_hypothesis(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    hypothesis = hypothesis_node()
    concept = concept_node("not a hypothesis")
    store.append_nodes_and_edges([hypothesis, concept], [])

    assert store.append_outbox_event(outbox_event(hypothesis))
    wrong_type = {
        "namespace": "demo",
        "hypothesis_uri": concept.id.uri,
        "event_type": "EMITTED",
        "schema_version": 1,
        "candidate": {"proposal": "wrong type"},
    }
    with pytest.raises(ValueError, match="Hypothesis"):
        store.append_outbox_event(wrong_type)

    foreign_hypothesis = hypothesis_node(namespace="other")
    foreign_event = {
        "namespace": "demo",
        "hypothesis_uri": foreign_hypothesis.id.uri,
        "event_type": "EMITTED",
        "schema_version": 1,
        "candidate": {"proposal": "foreign"},
    }
    with pytest.raises(ValueError, match="namespace"):
        store.append_outbox_event(foreign_event)


def test_outbox_trigger_rejects_existing_non_hypothesis_endpoint(tmp_path) -> None:
    path = tmp_path / "concept.db"
    store = ConceptStore(path)
    concept = concept_node("concept")
    store.append_node(concept)
    store.close()
    connection = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="same-namespace Hypothesis"):
            connection.execute(
                "INSERT INTO candidate_outbox "
                "(uri, namespace, hypothesis_uri, event_type, schema_version, canonical_json, content_hash, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "concept://demo/outbox/00000000000000000000000000",
                    "demo",
                    concept.id.uri,
                    "EMITTED",
                    1,
                    b"{}",
                    "0" * 64,
                    "2026-09-04T20:00:00Z",
                ),
            )
    finally:
        connection.close()


def test_identical_outbox_replay_is_idempotent_and_different_bytes_collide(tmp_path) -> None:
    idempotent_store = ConceptStore(tmp_path / "idempotent.db")
    hypothesis = hypothesis_node()
    idempotent_store.append_node(hypothesis)
    event = outbox_event(hypothesis)
    assert idempotent_store.append_outbox_event(event) == idempotent_store.append_outbox_event(event)
    idempotent_store.close()

    path = tmp_path / "collision.db"
    collision_store = ConceptStore(path)
    collision_store.append_node(hypothesis)
    collision_store.close()

    connection = sqlite3.connect(path)
    try:
        preimage_uri = event.uri
        assert isinstance(preimage_uri, str)
        connection.execute(
            "INSERT INTO candidate_outbox "
            "(uri, namespace, hypothesis_uri, event_type, schema_version, canonical_json, content_hash, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                preimage_uri,
                event.namespace,
                    event.hypothesis_uri,
                event.event_type,
                event.schema_version,
                b'{"different":true}',
                "f" * 64,
                event.recorded_at,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    reopened = ConceptStore(path)
    with pytest.raises(IdentityCollisionError):
        reopened.append_outbox_event(event)


def test_outbox_event_model_has_stable_public_shape() -> None:
    event = CandidateOutboxEvent(
        uri="",
        namespace="demo",
        hypothesis_uri="concept://demo/hypothesis/00000000000000000000000000",
        event_type="EMITTED",
        schema_version=1,
        candidate={"proposal": True},
    )
    assert event.to_dict()["candidate"] == {"proposal": True}
