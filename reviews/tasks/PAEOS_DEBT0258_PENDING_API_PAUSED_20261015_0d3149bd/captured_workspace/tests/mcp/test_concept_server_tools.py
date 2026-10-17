from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, cast

from concept.mcp_server import build_concept_mcp_server

from tests.mcp._fixtures import SeededGraph, seed_graph

REQUIRED_ENVELOPE_KEYS = {
    "authority",
    "trust",
    "graph_snapshot_hash",
    "query_hash",
    "truncated",
    "omitted",
    "results",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _call(server: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    response = asyncio.run(server.call_tool(name, arguments))
    assert response.is_error is False
    return cast(dict[str, object], response.structured_content)


def _assert_envelope(envelope: dict[str, object]) -> None:
    assert REQUIRED_ENVELOPE_KEYS.issubset(envelope)
    assert envelope["authority"] == "exploratory"
    assert envelope["trust"] == "untrusted_candidate"
    assert SHA256.fullmatch(cast(str, envelope["graph_snapshot_hash"]))
    query_hash = envelope["query_hash"]
    assert query_hash is None or SHA256.fullmatch(cast(str, query_hash))
    assert isinstance(envelope["truncated"], bool)
    assert isinstance(envelope["omitted"], int)
    assert isinstance(envelope["results"], list)


def _seeded_server(tmp_path: Path) -> tuple[Any, SeededGraph]:
    seeded = seed_graph(tmp_path / "graph.db")
    return build_concept_mcp_server(seeded.database), seeded


def test_concept_get_returns_a_node_and_an_edge_envelope(tmp_path: Path) -> None:
    server, seeded = _seeded_server(tmp_path)
    try:
        node_response = _call(server, "concept_get", {"uri": seeded.root_uri})
        edge_response = _call(server, "concept_get", {"uri": seeded.edge_uri})
        _assert_envelope(node_response)
        _assert_envelope(edge_response)
        assert node_response["results"][0]["type"] == "Concept"
        assert edge_response["results"][0]["family"] == "derivation"
    finally:
        server.close()


def test_concept_search_returns_budgeted_orchestra_results_without_writes(tmp_path: Path) -> None:
    server, seeded = _seeded_server(tmp_path)
    try:
        response = _call(
            server,
            "concept_search",
            {
                "request": {
                    "namespace": "demo",
                    "query_text": "root concept",
                    "desired_output_kinds": ["Concept"],
                    "budgets": {
                        "max_expansions": 10,
                        "max_results": 2,
                        "max_hops": 2,
                        "max_tokens": 500,
                    },
                }
            },
        )
        _assert_envelope(response)
        assert response["results"]
        assert response["results"][0]["candidate_uri"] != seeded.root_uri
        assert response["orchestra"]["query_hash"] == response["query_hash"]
    finally:
        server.close()


def test_concept_neighborhood_returns_ephemeral_snapshot_with_why(tmp_path: Path) -> None:
    server, seeded = _seeded_server(tmp_path)
    try:
        response = _call(
            server,
            "concept_neighborhood",
            {
                "uri": seeded.root_uri,
                "budgets": {"max_hops": 1, "max_expansions": 4, "max_results": 4},
            },
        )
        _assert_envelope(response)
        snapshot = response["results"][0]
        assert snapshot["center_uri"] == seeded.root_uri
        assert snapshot["members"][0]["uri"] == seeded.child_uri
        assert snapshot["why"][seeded.child_uri]["steps"][0]["relation"] == "derived_from"
    finally:
        server.close()


def test_concept_path_returns_typed_bounded_path_explanation(tmp_path: Path) -> None:
    server, seeded = _seeded_server(tmp_path)
    try:
        response = _call(
            server,
            "concept_path",
            {
                "source_uri": seeded.root_uri,
                "target_uri": seeded.child_uri,
                "budgets": {"max_hops": 1, "max_expansions": 4, "max_results": 4},
            },
        )
        _assert_envelope(response)
        path = response["results"][0]
        assert path["source_uri"] == seeded.root_uri
        assert path["target_uri"] == seeded.child_uri
        assert path["why"]["steps"][0]["family"] == "derivation"
    finally:
        server.close()


def test_concept_hypothesis_get_returns_lineage_scores_and_observations(tmp_path: Path) -> None:
    server, seeded = _seeded_server(tmp_path)
    try:
        response = _call(server, "concept_hypothesis_get", {"uri": seeded.hypothesis_uri})
        _assert_envelope(response)
        hypothesis = response["results"][0]
        assert hypothesis["hypothesis"]["type"] == "Hypothesis"
        assert hypothesis["lineage"] == []
        assert hypothesis["score_snapshot"] == {"novelty": "0.80"}
        assert hypothesis["export_observations"][0]["event_type"] == "EMITTED"
    finally:
        server.close()
