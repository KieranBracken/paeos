from __future__ import annotations

from concept.model import SearchRequest
from concept.search import (
    SearchBudget,
    SeededRandomWalkSearchArm,
    TraversalSearchArm,
    compile_query,
)
from concept.store import ConceptStore

from ._inspiration_fixtures import append, concept, edge, uri_text


def search_request(**changes: object) -> SearchRequest:
    values: dict[str, object] = {
        "namespace": "demo",
        "query_text": "target",
        "anchor_uris": (),
        "seed": 9,
        "desired_output_kinds": ("Concept",),
        "algorithm_allow_list": (("traversal", "v1"), ("seeded-random-walk", "v1")),
        "budgets": {"max_expansions": 8, "max_results": 4, "max_hops": 2, "max_tokens": 200},
    }
    values.update(changes)
    return SearchRequest(**values)


def test_traversal_arm_returns_whole_nodes_with_typed_why_paths(tmp_path) -> None:
    root = concept("root")
    target = concept("target")
    with ConceptStore(tmp_path / "traversal-arm.db") as store:
        append(store, (root, target), (edge(root, target),))
        request = search_request(
            anchor_uris=(uri_text(root.id),),
            required_edge_families=("derivation",),
            required_relations=("derived_from",),
        )
        compiled = compile_query(request)
        result = TraversalSearchArm().search(
            compiled,
            store,
            SearchBudget(max_expansions=4, max_results=2, max_hops=2, max_tokens=100),
            seed=9,
        )

    assert tuple(item.candidate_uri for item in result.candidates) == (uri_text(target.id),)
    assert result.paths[uri_text(target.id)].steps[0].family == "derivation"
    assert result.budgets_consumed["expansions"] <= 4
    assert result.errors == ()


def test_seeded_inspiration_arm_generates_a_different_candidate_kind_deterministically(tmp_path) -> None:
    nodes = tuple(concept(label) for label in ("alpha", "beta", "gamma"))
    with ConceptStore(tmp_path / "random-arm.db") as store:
        append(store, nodes)
        request = search_request(
            query_text="",
            anchor_uris=(uri_text(nodes[0].id),),
            desired_output_kinds=("Hypothesis",),
        )
        compiled = compile_query(request)
        budget = SearchBudget(max_expansions=4, max_results=2, max_hops=2, max_tokens=200)
        first = SeededRandomWalkSearchArm().search(compiled, store, budget, seed=21)
        second = SeededRandomWalkSearchArm().search(compiled, store, budget, seed=21)

    assert first == second
    assert first.candidates
    assert first.candidates[0].candidate.type == "Hypothesis"
    assert first.candidates[0].metadata["kind"] == "recombination"
    assert first.budgets_consumed["proposals"] <= 4
