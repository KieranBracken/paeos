from __future__ import annotations

import pytest
from concept.ids import canonical_json, content_hash
from concept.model import SearchRequest, ValidationError
from concept.search import SearchBudget, compile_query


def request_dict() -> dict[str, object]:
    return {
        "namespace": "demo",
        "query_text": "feedback loops",
        "anchor_uris": ["concept://demo/concept/00000000000000000000000000"],
        "seed": 17,
        "disclosure_policy": "same_namespace",
        "desired_output_kinds": ["Concept"],
        "required_edge_families": ["derivation"],
        "forbidden_edge_families": [],
        "required_relations": ["derived_from"],
        "forbidden_relations": [],
        "constraints": {"required_domain_tags": ["systems"]},
        "representation_requirements": ["symbolic"],
        "algorithm_allow_list": [
            {"name": "traversal", "version": "v1"},
            {"name": "seeded-random-walk", "version": "v1"},
        ],
        "budgets": {"max_expansions": 11, "max_results": 5, "max_hops": 3, "max_tokens": 101},
        "ranking_weights": {"relevance": "0.70", "novelty": "0.30"},
        "score_versions": {"relevance": "v1", "novelty": "v1"},
    }


def test_compile_canonicalizes_hash_and_preserves_original_inputs() -> None:
    raw = request_dict()
    compiled = compile_query(raw)
    expected_request = SearchRequest(**raw)

    assert compiled.query_hash == content_hash(canonical_json(expected_request.to_dict()))
    assert compiled.original_query_text == "feedback loops"
    assert compiled.anchor_uris == ("concept://demo/concept/00000000000000000000000000",)
    assert compiled.constraints["required_domain_tags"] == ("systems",)


def test_compile_allocates_each_consumable_budget_deterministically() -> None:
    compiled = compile_query(request_dict())
    allocations = compiled.arm_allocations

    assert tuple(allocations) == ("traversal", "seeded-random-walk")
    assert sum(value.max_expansions for value in allocations.values()) == 11
    assert sum(value.max_results for value in allocations.values()) == 5
    assert sum(value.max_tokens for value in allocations.values()) == 101
    assert all(value.max_hops == 3 for value in allocations.values())
    assert isinstance(next(iter(allocations.values())), SearchBudget)


def test_compile_requires_query_text_or_anchor_and_rejects_conflicting_filters() -> None:
    empty = request_dict()
    empty["query_text"] = ""
    empty["anchor_uris"] = []
    with pytest.raises(ValidationError):
        compile_query(empty)

    conflicting = request_dict()
    conflicting["required_edge_families"] = ["derivation"]
    conflicting["forbidden_edge_families"] = ["derivation"]
    with pytest.raises(ValidationError):
        compile_query(conflicting)


def test_compile_serialization_exposes_components_without_forbidden_ranking_key() -> None:
    compiled = compile_query(request_dict())
    serialized = compiled.to_dict()

    assert "confidence" not in serialized
    assert "confidence" not in serialized["request"]["ranking_weights"]
    assert serialized["constraints"]["required_edge_families"] == ["derivation"]
