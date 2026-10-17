from __future__ import annotations

import copy

from test_projection_schema import _errors, _request, _response, _schema


def test_request_budget_cannot_select_full_tier() -> None:
    schema = _schema()
    request = copy.deepcopy(_request())
    request["budget"]["tier"] = "FULL"
    assert _errors(schema, request)


def test_response_cannot_claim_full_tier() -> None:
    schema = _schema()
    response = copy.deepcopy(_response())
    response["tier"] = "FULL"
    assert _errors(schema, response)


def test_tier_definition_contains_only_advisory_levels() -> None:
    schema = _schema()
    assert schema["$defs"]["tier"]["enum"] == ["SUMMARY", "INDEX"]
