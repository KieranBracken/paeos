from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

from concept.mcp_server import build_concept_mcp_server

from tests.mcp._fixtures import seed_empty

MISSING_URI = "concept://demo/concept/00000000000000000000000000"


def _call(server: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    response = asyncio.run(server.call_tool(name, arguments))
    assert response.is_error is False
    return cast(dict[str, object], response.structured_content)


def test_empty_store_returns_typed_empty_results_for_every_tool(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    try:
        requests = (
            ("concept_get", {"uri": MISSING_URI}),
            ("concept_search", {"request": {"namespace": "demo", "query_text": "missing"}}),
            ("concept_neighborhood", {"uri": MISSING_URI}),
            ("concept_path", {"source_uri": MISSING_URI, "target_uri": MISSING_URI}),
            ("concept_hypothesis_get", {"uri": MISSING_URI}),
        )
        for name, arguments in requests:
            response = _call(server, name, arguments)
            assert response["results"] == []
            assert isinstance(response["omitted"], int)
    finally:
        server.close()


def test_missing_uri_is_not_a_fabricated_candidate(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    try:
        response = _call(server, "concept_get", {"uri": MISSING_URI})
        assert response["results"] == []
        assert "error" not in response
    finally:
        server.close()


def test_invalid_namespace_and_uri_return_explicit_typed_errors(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    try:
        invalid_namespace = _call(
            server,
            "concept_search",
            {"request": {"namespace": "INVALID NAMESPACE", "query_text": "anything"}},
        )
        invalid_uri = _call(server, "concept_get", {"uri": "not-a-concept-uri"})
        assert invalid_namespace["results"] == []
        assert invalid_namespace["error"]["type"] == "InvalidNamespace"
        assert invalid_uri["results"] == []
        assert invalid_uri["error"]["type"] == "InvalidConceptURI"
    finally:
        server.close()


def test_unreachable_store_returns_availability_error_without_raising(tmp_path: Path) -> None:
    server = build_concept_mcp_server(tmp_path / "does-not-exist" / "graph.db")
    try:
        response = _call(server, "concept_get", {"uri": MISSING_URI})
        assert response["results"] == []
        assert response["error"]["type"] == "StoreUnavailable"
    finally:
        server.close()


def test_malformed_nested_search_budget_returns_an_envelope(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    try:
        response = _call(
            server,
            "concept_search",
            {"request": {"namespace": "demo", "query_text": "anything", "budgets": "x"}},
        )
        assert response["results"] == []
        assert response["error"]["type"] == "SchemaValidationError"
    finally:
        server.close()


def test_excessive_budgets_are_rejected_before_traversal(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    try:
        response = _call(
            server,
            "concept_neighborhood",
            {"uri": MISSING_URI, "budgets": {"max_hops": 1000000}},
        )
        assert response["results"] == []
        assert response["error"]["type"] == "BudgetExceeded"
    finally:
        server.close()


def test_search_cannot_expand_namespace_disclosure_policy(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    try:
        response = _call(
            server,
            "concept_search",
            {
                "request": {
                    "namespace": "demo",
                    "query_text": "anything",
                    "disclosure_policy": "*",
                }
            },
        )
        assert response["results"] == []
        assert response["error"]["type"] == "NamespaceDisclosureError"
    finally:
        server.close()
