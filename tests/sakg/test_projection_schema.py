from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "sakg/schema/projection.schema.json"


def _schema() -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    return schema


def _request() -> dict[str, Any]:
    return {
        "method": "tradeoff_precedents",
        "subject": "latency-versus-durability",
        "namespace": ["sakg-runtime"],
        "budget": {"max_tokens": 1200, "max_nodes": 8, "tier": "SUMMARY"},
        "filters": {
            "min_confidence": 0.5,
            "as_of": "2026-09-02T00:00:00Z",
            "status": ["canonical", "refuted"],
        },
    }


def _response() -> dict[str, Any]:
    return {
        "results": [
            {
                "node_summary": {
                    "id": "sakg://sakg-runtime/TradeOff/01ARZ3NDEKTSV4RRFFQ69G5FAV",
                    "type": "TradeOff",
                    "namespace": "sakg-runtime",
                    "status": "canonical",
                    "label": "Latency versus durability",
                    "summary": "Durability was retained at the cost of write latency.",
                },
                "score": 0.91,
                "why": "tradeoff_precedents:axes=latency,durability -> Decision -> Outcome",
            }
        ],
        "provenance": {
            "sakg_version": "1.0.0",
            "corpus_hash": "a" * 64,
            "query_hash": "b" * 64,
        },
        "truncated": False,
        "omitted": 0,
        "trust": "untrusted",
        "tier": "SUMMARY",
    }


def _errors(schema: dict[str, Any], value: Any) -> list[str]:
    return [error.message for error in Draft202012Validator(schema).iter_errors(value)]


def test_schema_is_draft_2020_12_and_freezes_request_response_shapes() -> None:
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["oneOf"] == [{"$ref": "#/$defs/request"}, {"$ref": "#/$defs/response"}]
    defs = schema["$defs"]
    assert set(defs["request"]["required"]) == {
        "method",
        "subject",
        "namespace",
        "budget",
        "filters",
    }
    assert set(defs["response"]["required"]) == {
        "results",
        "provenance",
        "truncated",
        "omitted",
        "trust",
        "tier",
    }
    assert defs["method"]["enum"] == [
        "query_architectures",
        "dependency_impact",
        "tradeoff_precedents",
        "pattern_retrieval",
        "memory_augment",
    ]


def test_valid_request_and_response_match_the_frozen_contract() -> None:
    schema = _schema()
    assert _errors(schema, _request()) == []
    assert _errors(schema, _response()) == []


def test_unknown_fields_and_invalid_budget_are_rejected() -> None:
    schema = _schema()
    request = _request()
    request["unexpected"] = True
    assert _errors(schema, request)
    invalid = _request()
    invalid["budget"] = {"max_tokens": 0, "max_nodes": 0, "tier": "SUMMARY"}
    assert _errors(schema, invalid)


def test_response_result_requires_explanation_and_bounded_score() -> None:
    schema = _schema()
    response = copy.deepcopy(_response())
    result = response["results"][0]
    del result["why"]
    result["score"] = 2
    assert _errors(schema, response)
