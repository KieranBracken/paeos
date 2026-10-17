from __future__ import annotations

from dataclasses import dataclass

from concept.model import SearchRequest
from concept.search import SearchArmResult, SearchCandidate, SearchOrchestra
from concept.store import ConceptStore

from ._inspiration_fixtures import append, concept, uri_text


@dataclass(frozen=True)
class GoodArm:
    name: str = "good"
    version: str = "1"
    node: object | None = None

    def search(self, request, snapshot, budget, seed):
        assert self.node is not None
        item = SearchCandidate(
            candidate=self.node,
            candidate_uri=uri_text(self.node.id),
            arm_name=self.name,
            arm_version=self.version,
            why=({"kind": "good"},),
        )
        return SearchArmResult(candidates=(item,), budgets_consumed={"results": 1})


class FailingArm:
    name = "failing"
    version = "1"

    def search(self, request, snapshot, budget, seed):
        raise RuntimeError("fixture arm failed")


def test_one_arm_failure_is_visible_while_successful_arm_results_survive(tmp_path) -> None:
    node = concept("survives")
    with ConceptStore(tmp_path / "failure.db") as store:
        append(store, (node,))
        result = SearchOrchestra(store, arms=(FailingArm(), GoodArm(node=node))).search(
            SearchRequest(
                namespace="demo",
                query_text="survives",
                desired_output_kinds=("Concept",),
                algorithm_allow_list=(("failing", "1"), ("good", "1")),
                budgets={"max_expansions": 4, "max_results": 2, "max_hops": 1, "max_tokens": 100},
            )
        )

    assert len(result.results) == 1
    assert result.errors[0]["arm_name"] == "failing"
    assert result.errors[0]["message"] == "fixture arm failed"
    assert result.arm_results["failing"].errors[0]["type"] == "RuntimeError"
    assert result.arm_results["good"].errors == ()
