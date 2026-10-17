from __future__ import annotations

from concept.inspiration import propose_analogies, propose_recombinations
from concept.store import ConceptStore

from ._inspiration_fixtures import append, concept, uri_text


def test_seeded_analogy_order_and_content_are_replayable(tmp_path):
    nodes = tuple(concept(label) for label in ("a", "b", "c", "d"))
    with ConceptStore(tmp_path / "deterministic-analogy.db") as store:
        append(store, nodes)
        request = {"namespace": "demo", "source_uris": [uri_text(nodes[0].id)], "target_uris": [uri_text(nodes[1].id)]}
        first = propose_analogies(store, request, budget=5, seed=22)
        second = propose_analogies(store, request, budget=5, seed=22)
    assert first == second


def test_seeded_recombination_order_and_rejections_are_replayable(tmp_path):
    nodes = tuple(concept(label) for label in ("a", "b", "c"))
    with ConceptStore(tmp_path / "deterministic-recombination.db") as store:
        append(store, nodes)
        request = {"namespace": "demo", "source_uris": [uri_text(node.id) for node in nodes]}
        first = propose_recombinations(store, request, budget=5, seed=22)
        second = propose_recombinations(store, request, budget=5, seed=22)
    assert first == second
    assert first.budget_consumed <= 5
