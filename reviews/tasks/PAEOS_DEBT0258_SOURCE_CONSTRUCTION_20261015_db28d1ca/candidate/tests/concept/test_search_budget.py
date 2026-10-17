from __future__ import annotations

from dataclasses import dataclass

from concept.model import SearchRequest
from concept.search import SearchArmResult, SearchCandidate, SearchOrchestra
from concept.store import ConceptStore

from ._inspiration_fixtures import append, concept, uri_text


@dataclass(frozen=True)
class BudgetArm:
    name: str
    version: str = "1"
    nodes: tuple[object, ...] = ()

    def search(self, request, snapshot, budget, seed):
        items = tuple(
            SearchCandidate(
                candidate=node,
                candidate_uri=uri_text(node.id),
                arm_name=self.name,
                arm_version=self.version,
                why=({"kind": "budget-fixture"},),
            )
            for node in self.nodes
        )
        return SearchArmResult(
            candidates=items,
            budgets_requested=budget.to_dict(),
            budgets_consumed={"expansions": len(items), "results": len(items), "tokens": len(items)},
        )


def test_global_result_budget_drops_whole_candidates_and_counts_omissions(tmp_path) -> None:
    nodes = tuple(concept(label) for label in ("a", "b", "c", "d"))
    with ConceptStore(tmp_path / "result-budget.db") as store:
        append(store, nodes)
        result = SearchOrchestra(
            store,
            arms=(BudgetArm("alpha", nodes=nodes),),
        ).search(
            SearchRequest(
                namespace="demo",
                query_text="all",
                desired_output_kinds=("Concept",),
                algorithm_allow_list=(("alpha", "1"),),
                budgets={"max_expansions": 20, "max_results": 2, "max_hops": 1, "max_tokens": 100},
            )
        )

    assert len(result.results) == 2
    assert result.omitted == 2
    assert result.truncated is True
    assert result.budgets_consumed["results"] <= 2


def test_global_serialization_budget_never_emits_a_partial_result(tmp_path) -> None:
    nodes = tuple(concept(label) for label in ("long-a", "long-b"))
    with ConceptStore(tmp_path / "token-budget.db") as store:
        append(store, nodes)
        result = SearchOrchestra(store, arms=(BudgetArm("alpha", nodes=nodes),)).search(
            SearchRequest(
                namespace="demo",
                query_text="all",
                desired_output_kinds=("Concept",),
                algorithm_allow_list=(("alpha", "1"),),
                budgets={"max_expansions": 10, "max_results": 5, "max_hops": 1, "max_tokens": 1},
            )
        )

    assert result.results == ()
    assert result.omitted == 2
    assert result.truncated is True
    assert result.budgets_consumed["tokens"] <= 1
