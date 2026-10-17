from __future__ import annotations

import json
from pathlib import Path

from concept.inspiration import propose_analogies
from concept.store import ConceptStore
from jsonschema import Draft202012Validator

from ._inspiration_fixtures import analogy_node, append, concept, edge, uri_text


def test_analogy_proposal_has_explicit_roles_breaks_and_membership_edges(tmp_path):
    source = concept("source")
    target = concept("target")
    source_neighbor = concept("source-neighbor")
    target_neighbor = concept("target-neighbor")
    with ConceptStore(tmp_path / "analogy.db") as store:
        append(
            store,
            (source, target, source_neighbor, target_neighbor),
            (edge(source, source_neighbor), edge(target, target_neighbor)),
        )
        result = propose_analogies(
            store,
            {
                "namespace": "demo",
                "source_uris": [uri_text(source.id)],
                "target_uris": [uri_text(target.id)],
            },
            budget=4,
            seed=17,
        )
    assert result.budget_consumed <= 4
    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.node.type == "Analogy"
    assert proposal.node.payload.correspondences
    assert proposal.node.payload.preserved_relations
    assert "not_yet_tested" in proposal.node.payload.known_breaks
    assert {item.family for item in proposal.edges} == {"analogy"}
    assert {item.relation for item in proposal.edges} == {"has_source", "has_target"}
    assert all(item.source_uri == proposal.node.id for item in proposal.edges)


def test_analogy_never_uses_an_existing_analogy_as_transitive_evidence(tmp_path):
    source = concept("source")
    target = concept("target")
    existing = analogy_node()
    with ConceptStore(tmp_path / "nontransitive.db") as store:
        append(store, (source, target, existing), (edge(existing, source, family="analogy", relation="has_source"),))
        result = propose_analogies(
            store,
            {"namespace": "demo", "source_uris": [uri_text(existing.id)], "target_uris": [uri_text(target.id)]},
            budget=4,
            seed=0,
        )
    assert result.proposals == ()
    assert result.rejected_traces
    assert "transitive" in str(result.rejected_traces[0]).lower()


def test_analogy_proposal_is_a_schema_valid_node_envelope(tmp_path):
    source = concept("source")
    target = concept("target")
    with ConceptStore(tmp_path / "analogy-schema.db") as store:
        append(store, (source, target))
        result = propose_analogies(
            store,
            {"namespace": "demo", "source_uris": [uri_text(source.id)], "target_uris": [uri_text(target.id)]},
            budget=4,
            seed=2,
        )
    schema = json.loads((Path(__file__).parents[2] / "concept/schema/node.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(result.proposals[0].node.to_dict()))
    assert errors == []


def test_analogy_rejects_unequal_role_sets_instead_of_truncating(tmp_path):
    source_a = concept("source-a")
    source_b = concept("source-b")
    target = concept("target")
    with ConceptStore(tmp_path / "analogy-arity.db") as store:
        append(store, (source_a, source_b, target))
        result = propose_analogies(
            store,
            {
                "namespace": "demo",
                "source_uris": [uri_text(source_a.id), uri_text(source_b.id)],
                "target_uris": [uri_text(target.id)],
            },
            budget=4,
            seed=2,
        )
    assert result.proposals == ()
    assert result.rejected_traces[0]["reason"] == "source_target_arity_mismatch"
