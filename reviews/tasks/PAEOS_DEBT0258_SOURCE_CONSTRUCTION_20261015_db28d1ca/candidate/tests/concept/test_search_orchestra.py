from __future__ import annotations

from dataclasses import dataclass

from concept.model import SearchRequest
from concept.search import (
    SearchArmResult,
    SearchCandidate,
    SearchOrchestra,
)
from concept.store import ConceptStore

from ._inspiration_fixtures import append, concept, uri_text


@dataclass(frozen=True)
class StaticArm:
    name: str
    version: str
    nodes: tuple[object, ...]

    def search(self, request, snapshot, budget, seed):
        candidates = tuple(
            SearchCandidate(
                candidate=node,
                candidate_uri=uri_text(node.id),
                arm_name=self.name,
                arm_version=self.version,
                why=({"kind": "static", "seed": seed},),
            )
            for node in self.nodes
        )
        return SearchArmResult(
            candidates=candidates,
            budgets_requested=budget.to_dict(),
            budgets_consumed={"expansions": len(candidates), "results": len(candidates), "tokens": len(candidates)},
        )


def request(**changes: object) -> SearchRequest:
    values: dict[str, object] = {
        "namespace": "demo",
        "query_text": "same",
        "anchor_uris": (),
        "desired_output_kinds": ("Concept",),
        "algorithm_allow_list": (("alpha", "1"), ("beta", "1")),
        "budgets": {"max_expansions": 10, "max_results": 4, "max_hops": 1, "max_tokens": 500},
        "ranking_weights": {"relevance": "1.00"},
    }
    values.update(changes)
    return SearchRequest(**values)


def test_orchestra_deduplicates_and_exposes_all_score_components(tmp_path) -> None:
    first = concept("first")
    second = concept("second")
    with ConceptStore(tmp_path / "orchestra.db") as store:
        append(store, (first, second))
        result = SearchOrchestra(
            store,
            arms=(StaticArm("alpha", "1", (first, second)), StaticArm("beta", "1", (second,))),
        ).search(request())

    assert {item.candidate_uri for item in result.results} == {
        uri_text(first.id),
        uri_text(second.id),
    }
    assert result.rejected_by_reason["duplicate_candidate"] == 1
    keys = set(result.results[0].score_components.to_dict())
    assert keys == {
        "relevance",
        "novelty",
        "coherence",
        "diversity_contribution",
        "cost",
        "provenance_completeness",
    }
    assert all("confidence" not in item.to_dict() for item in result.results)


def test_orchestra_uses_arm_and_candidate_uri_as_stable_tie_breakers(tmp_path) -> None:
    left = concept("left")
    right = concept("right")
    with ConceptStore(tmp_path / "tie.db") as store:
        append(store, (left, right))
        result = SearchOrchestra(
            store,
            arms=(StaticArm("zeta", "1", (right,)), StaticArm("alpha", "1", (left,))),
        ).search(request(algorithm_allow_list=(("zeta", "1"), ("alpha", "1"))))

    assert tuple(item.arm_name for item in result.results) == ("alpha", "zeta")
    assert tuple(item.rank for item in result.results) == (1, 2)
