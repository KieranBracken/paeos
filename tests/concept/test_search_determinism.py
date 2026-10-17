from __future__ import annotations

from concept.model import SearchRequest
from concept.search import SearchOrchestra, SeededRandomWalkSearchArm, TraversalSearchArm
from concept.store import ConceptStore

from ._inspiration_fixtures import append, concept, edge, uri_text


def request(root: str) -> SearchRequest:
    return SearchRequest(
        namespace="demo",
        query_text="",
        anchor_uris=(root,),
        seed=44,
        desired_output_kinds=("Concept", "Hypothesis"),
        algorithm_allow_list=(("traversal", "v1"), ("seeded-random-walk", "v1")),
        budgets={"max_expansions": 12, "max_results": 5, "max_hops": 2, "max_tokens": 500},
    )


def test_repeated_and_reordered_arm_execution_is_byte_stable(tmp_path) -> None:
    root = concept("root")
    children = tuple(concept(label) for label in ("one", "two", "three"))
    edges = tuple(edge(root, child) for child in children)
    with ConceptStore(tmp_path / "determinism.db") as store:
        append(store, (root, *children), edges)
        first = SearchOrchestra(store, arms=(TraversalSearchArm(), SeededRandomWalkSearchArm())).search(
            request(uri_text(root.id))
        )
        second = SearchOrchestra(store, arms=(SeededRandomWalkSearchArm(), TraversalSearchArm())).search(
            request(uri_text(root.id))
        )
        third = SearchOrchestra(store, arms=(TraversalSearchArm(), SeededRandomWalkSearchArm())).search(
            request(uri_text(root.id))
        )

    assert first.to_dict() == second.to_dict() == third.to_dict()
