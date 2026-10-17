from __future__ import annotations

from concept.model import SearchRequest
from concept.search import SearchOrchestra
from concept.store import ConceptStore

from ._inspiration_fixtures import append, concept, edge, uri_text


def test_replay_manifest_contains_complete_inputs_consumption_rejections_and_why(tmp_path) -> None:
    root = concept("root")
    child = concept("child")
    with ConceptStore(tmp_path / "replay.db") as store:
        append(store, (root, child), (edge(root, child),))
        request = SearchRequest(
            namespace="demo",
            query_text="child",
            anchor_uris=(uri_text(root.id),),
            seed=5,
            desired_output_kinds=("Concept",),
            algorithm_allow_list=(("traversal", "v1"), ("seeded-random-walk", "v1")),
            budgets={"max_expansions": 8, "max_results": 3, "max_hops": 2, "max_tokens": 300},
        )
        result = SearchOrchestra(store).search(request)
        manifest = result.replay_manifest

    assert set(manifest) == {
        "query_hash",
        "graph_snapshot_hash",
        "algorithm_versions",
        "heuristic_versions",
        "seeds",
        "budgets_requested",
        "budgets_consumed",
        "rejected_by_reason",
        "omitted",
        "truncated",
        "why",
    }
    assert manifest["query_hash"] == result.query_hash
    assert manifest["graph_snapshot_hash"] == result.graph_snapshot_hash
    assert manifest["budgets_requested"]["max_results"] == 3
    assert manifest["budgets_consumed"]["results"] == len(result.results)
    assert all(item.candidate_uri in manifest["why"] for item in result.results)
    assert all(manifest["why"][item.candidate_uri] for item in result.results)
    assert result.to_dict()["results"][0]["why"]
