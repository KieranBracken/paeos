from __future__ import annotations

from concept.inspiration import score_novelty
from concept.store import ConceptStore, NodeQuery

from ._inspiration_fixtures import append, hypothesis, uri_text


def test_high_novelty_never_changes_hypothesis_lifecycle_or_appends_graph_state(tmp_path):
    candidate = hypothesis("A high novelty proposition remains exploratory.")
    with ConceptStore(tmp_path / "quarantine.db") as store:
        append(store, (candidate,))
        before_hash = store.snapshot_hash("demo")
        result = score_novelty(
            {
                "namespace": "demo",
                "distance": 1.0,
                "structural_surprise": 1.0,
                "domain_span": 1.0,
                "recombination_rarity": 1.0,
                "duplication_penalty": 0.0,
            },
            store,
        )
        stored = store.get_node(uri_text(candidate.id))
        after_hash = store.snapshot_hash("demo")
        nodes = tuple(store.iter_nodes(NodeQuery(namespace="demo")))
    assert result.novelty_score == 1.0
    assert stored is not None
    assert stored.payload.lifecycle == "candidate"
    assert before_hash == after_hash
    assert len(nodes) == 1
