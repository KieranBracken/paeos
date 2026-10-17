import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

SCHEMA = Path(__file__).parents[2] / "concept/schema/search.schema.json"


def request() -> dict[str, object]:
    return {"query_text":"feedback", "anchor_uris":["concept://demo/concept/00000000000000000000000000"], "namespace":"demo", "disclosure_policy":"same_namespace", "desired_output_kinds":["Concept"], "required_edge_families":["derivation"], "forbidden_edge_families":[], "required_relations":[], "forbidden_relations":[], "constraints":{}, "representation_requirements":["symbolic"], "algorithm_allow_list":[{"name":"bfs","version":"1"}], "budgets":{"max_expansions":10,"max_results":2,"max_hops":2,"max_tokens":100}, "seed":7, "ranking_weights":{"relevance":"0.50","novelty":"0.50"}, "score_versions":{"relevance":"v1","novelty":"v1"}}


def test_request_schema() -> None:
    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(request())


def test_confidence_is_forbidden() -> None:
    value = request()
    value["ranking_weights"] = {"confidence":"1.00"}
    with pytest.raises(ValidationError):
        Draft202012Validator(json.loads(SCHEMA.read_text())).validate(value)


def test_result_has_score_components_without_confidence() -> None:
    value = {"query_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "graph_snapshot_hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "algorithm_versions":{"bfs":"1"}, "heuristic_versions":{}, "seeds":{"bfs":7}, "budgets_requested":{"max_results":2}, "budgets_consumed":{"results":1}, "results":[{"candidate_uri":"concept://demo/concept/00000000000000000000000000","rank":1,"score_components":{"relevance":"0.80","novelty":"0.20","coherence":"0.70","diversity_contribution":"0.30","cost":"0.10","provenance_completeness":"1.00"},"why":[]}], "rejected_by_reason":{}, "errors":[], "omitted":0,"truncated":False}
    Draft202012Validator(json.loads(SCHEMA.read_text())).validate(value)
