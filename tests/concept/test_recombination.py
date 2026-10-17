from __future__ import annotations

import json
from pathlib import Path

from concept.inspiration import propose_recombinations
from concept.store import ConceptStore
from jsonschema import Draft202012Validator

from ._inspiration_fixtures import append, concept, edge, uri_text


def test_recombination_emits_two_ordered_contribution_edges(tmp_path):
    first = concept("first", domain_tags=("mechanics",))
    second = concept("second", domain_tags=("biology",))
    with ConceptStore(tmp_path / "recombination.db") as store:
        append(store, (first, second))
        result = propose_recombinations(
            store,
            {"namespace": "demo", "source_uris": [uri_text(first.id), uri_text(second.id)], "output_kind": "Concept"},
            budget=3,
            seed=3,
        )
    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.node.type == "Concept"
    assert len(proposal.edges) >= 2
    assert all(item.family == "recombination" for item in proposal.edges)
    ordered = sorted(proposal.edges, key=lambda item: item.payload.contribution_order)
    assert [item.payload.contribution_order for item in ordered] == [0, 1]
    assert {uri_text(item.source_uri) for item in ordered} == {uri_text(first.id), uri_text(second.id)}


def test_incompatible_hard_constraints_are_rejected_with_a_trace(tmp_path):
    first = concept("first")
    second = concept("second")
    with ConceptStore(tmp_path / "rejection.db") as store:
        append(store, (first, second))
        result = propose_recombinations(
            store,
            {
                "namespace": "demo",
                "source_uris": [uri_text(first.id), uri_text(second.id)],
                "constraints": {"incompatible_pairs": [[uri_text(first.id), uri_text(second.id)]]},
            },
            budget=2,
            seed=1,
        )
    assert result.proposals == ()
    assert len(result.rejected_traces) == 1
    assert result.rejected_traces[0]["reason"] == "incompatible_hard_constraint"


def test_incompatible_constraints_cover_every_selected_source_pair(tmp_path):
    first = concept("first")
    second = concept("second")
    third = concept("third")
    with ConceptStore(tmp_path / "three-source-rejection.db") as store:
        append(store, (first, second, third))
        result = propose_recombinations(
            store,
            {
                "namespace": "demo",
                "source_uris": [uri_text(first.id), uri_text(second.id), uri_text(third.id)],
                "constraints": {"incompatible_pairs": [[uri_text(second.id), uri_text(third.id)]]},
            },
            budget=2,
            seed=1,
        )
    assert result.proposals == ()
    assert result.rejected_traces[0]["reason"] == "incompatible_hard_constraint"


def test_max_distance_constraint_covers_every_selected_source_pair(tmp_path):
    first = concept("first")
    second = concept("second")
    third = concept("third")
    with ConceptStore(tmp_path / "three-source-distance.db") as store:
        append(store, (first, second, third), (edge(first, second),))
        result = propose_recombinations(
            store,
            {
                "namespace": "demo",
                "source_uris": [uri_text(first.id), uri_text(second.id), uri_text(third.id)],
                "constraints": {"max_distance": 0.5},
            },
            budget=2,
            seed=1,
        )
    assert result.proposals == ()
    assert result.rejected_traces[0]["reason"] == "maximum_distance_exceeded"


def test_recombination_requires_distinct_sources(tmp_path):
    first = concept("first")
    with ConceptStore(tmp_path / "distinct.db") as store:
        append(store, (first,))
        result = propose_recombinations(
            store,
            {"namespace": "demo", "source_uris": [uri_text(first.id), uri_text(first.id)]},
            budget=2,
            seed=1,
        )
    assert result.proposals == ()
    assert result.rejected_traces[0]["reason"] == "requires_two_distinct_sources"


def test_recombination_proposal_envelopes_are_schema_valid(tmp_path):
    first = concept("first")
    second = concept("second")
    with ConceptStore(tmp_path / "recombination-schema.db") as store:
        append(store, (first, second))
        result = propose_recombinations(
            store,
            {"namespace": "demo", "source_uris": [uri_text(first.id), uri_text(second.id)]},
            budget=3,
            seed=3,
        )
    root = Path(__file__).parents[2] / "concept/schema"
    node_schema = json.loads((root / "node.schema.json").read_text())
    edge_schema = json.loads((root / "edge.schema.json").read_text())
    proposal = result.proposals[0]
    assert list(Draft202012Validator(node_schema).iter_errors(proposal.node.to_dict())) == []
    assert all(list(Draft202012Validator(edge_schema).iter_errors(edge.to_dict())) == [] for edge in proposal.edges)
