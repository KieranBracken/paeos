from __future__ import annotations

from concept.inspiration import score_novelty
from concept.store import ConceptStore

from ._inspiration_fixtures import append, concept, edge, hypothesis, uri_text


def test_novelty_projects_available_components_and_duplication_penalty(tmp_path):
    existing = concept("existing")
    with ConceptStore(tmp_path / "novelty.db") as store:
        append(store, (existing,))
        result = score_novelty(
            {
                "namespace": "demo",
                "distance": 0.8,
                "structural_surprise": 0.6,
                "domain_span": 0.4,
                "recombination_rarity": 0.2,
                "duplication_penalty": 0.25,
            },
            store,
            {
                "heuristic_version": "novelty/v1",
                "weights": {
                    "distance": 1.0,
                    "structural_surprise": 1.0,
                    "domain_span": 1.0,
                    "recombination_rarity": 1.0,
                },
                "duplication_weight": 0.2,
            },
        )
    assert result.heuristic_version == "novelty/v1"
    assert result.missing_components == ()
    assert result.novelty_score == 0.45
    assert len(result.snapshot_hash) == 64


def test_novelty_reports_missing_components_without_fabricating_zero_as_evidence(tmp_path):
    with ConceptStore(tmp_path / "missing.db") as store:
        result = score_novelty({"namespace": "demo", "distance": 0.9}, store)
    assert result.novelty_score == 0.9
    assert set(result.missing_components) == {
        "structural_surprise",
        "domain_span",
        "recombination_rarity",
        "duplication_penalty",
    }


def test_novelty_finds_nearest_comparator_for_a_graph_node(tmp_path):
    candidate = concept("candidate", vector=(1.0, 0.0))
    near = concept("near", vector=(1.0, 0.0))
    far = concept("far", vector=(0.0, 1.0))
    with ConceptStore(tmp_path / "comparators.db") as store:
        append(store, (candidate, near, far))
        result = score_novelty(candidate, store)
    assert uri_text(near.id) in result.nearest_comparators


def test_zero_configured_novelty_weights_are_not_replaced_by_defaults(tmp_path):
    with ConceptStore(tmp_path / "zero-weight.db") as store:
        result = score_novelty(
            {
                "namespace": "demo",
                "distance": 0.9,
                "structural_surprise": 0.2,
                "domain_span": 0.8,
                "recombination_rarity": 0.7,
                "duplication_penalty": 0.0,
            },
            store,
            {
                "weights": {
                    "distance": 0.0,
                    "structural_surprise": 1.0,
                    "domain_span": 0.0,
                    "recombination_rarity": 0.0,
                }
            },
        )
    assert result.novelty_score == 0.2
    assert result.weights["structural_surprise"] == 1.0
    assert result.weights.get("distance", 0.0) == 0.0


def test_recombination_rarity_counts_existing_ordered_signatures(tmp_path):
    first = concept("first")
    second = concept("second")
    output = hypothesis("combined")
    with ConceptStore(tmp_path / "rarity.db") as store:
        append(store, (first, second, output), (edge(first, second, family="recombination"),))
        result = score_novelty(
            {
                "namespace": "demo",
                "source_uris": [uri_text(first.id), uri_text(second.id)],
                "distance": 0.5,
            },
            store,
        )
    assert result.components["recombination_rarity"] == 0.5


def test_duplication_penalty_considers_existing_hypotheses(tmp_path):
    existing = hypothesis("same proposition")
    with ConceptStore(tmp_path / "hypothesis-duplicate.db") as store:
        append(store, (existing,))
        result = score_novelty(
            {"namespace": "demo", "proposition": "same proposition", "distance": 0.6},
            store,
        )
    assert result.components["duplication_penalty"] == 1.0
