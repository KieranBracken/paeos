"""Live SQLite-to-MCP validation for outcome-joined SAKG precedents."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from time import perf_counter

import pytest
from sakg.mcp_server import build_sakg_mcp_server
from sakg.outcome_observer import OutcomeObserver
from sakg.store import Edge, GraphStore

NAMESPACE = "paeos-history"
OBSERVED_AT = "2026-09-04T20:26:00Z"
AXES = ["latency", "reliability", "maintainability"]


def _identifier(kind: str, index: int) -> str:
    return f"sakg://{NAMESPACE}/{kind}/{index:026d}"


def _evidence(label: str) -> dict[str, object]:
    digest = hashlib.sha256(label.encode()).hexdigest()
    return {
        "hash": digest,
        "uri": f"receipt://sakg-task-26/{label}",
        "kind": "test",
        "reverification": "run tests/mcp/test_live_mcp_query.py",
    }


def _node(kind: str, index: int, *, facets: dict[str, object]) -> dict[str, object]:
    node_id = _identifier(kind, index)
    return {
        "id": node_id,
        "type": kind,
        "namespace": NAMESPACE,
        "facets": facets,
        "label": f"Task 26 {kind} {index}",
        "summary": f"Live MCP validation {kind.lower()} {index}.",
        "provenance": {
            "origin": {"system": "sakg-task-26", "run_id": "live-mcp-spike"},
            "author_kind": "human",
            "ingested_at": OBSERVED_AT,
            "source_hash": _evidence(node_id)["hash"],
        },
        "evidence": [_evidence(node_id)],
        "status": "canonical",
        "confidence": 0.9,
        "valid_from": OBSERVED_AT,
        "valid_until": None,
        "falsifier": None,
        "coordinates": {"domain": ["paeos"]},
    }


def _seed_live_store(path: Path, count: int = 3) -> tuple[GraphStore, tuple[str, ...]]:
    store = GraphStore(path, NAMESPACE)
    outcome_ids: list[str] = []
    for index in range(1, count + 1):
        tradeoff_id = _identifier("TradeOff", index)
        decision_id = _identifier("Decision", index)
        store.append_node(
            _node(
                "TradeOff",
                index,
                facets={"tradeoff": {"dimensions": AXES, "source": "historical-paeos"}},
            )
        )
        store.append_node(_node("Decision", index, facets={"decision": {"sealed": True}}))
        store.append_edge(
            Edge(
                edge_id=f"task26:resolves:{index}",
                namespace=NAMESPACE,
                source=tradeoff_id,
                target=decision_id,
                family="tradeoff",
                relation="resolves",
                evidence=(_evidence(f"resolves-{index}"),),
                created_at=OBSERVED_AT,
            )
        )
        result = OutcomeObserver(store).observe(
            {
                "event_id": f"task-26-verification-{index}",
                "event_type": "test_run",
                "decision_id": decision_id,
                "tradeoff_ids": [tradeoff_id],
                "status": "passed",
                "observed_at": OBSERVED_AT,
                "summary": f"Historical decision {index} remained reliable under live verification.",
                "evidence": _evidence(f"outcome-{index}"),
            }
        )
        outcome_ids.append(result.node_id)
    return store, tuple(outcome_ids)


@pytest.fixture
def live_server(tmp_path: Path):
    store, outcome_ids = _seed_live_store(tmp_path / "sakg.db")
    try:
        yield build_sakg_mcp_server(graph=store), outcome_ids
    finally:
        store.close()


def _call(server: object, arguments: dict[str, object]):
    return asyncio.run(server.call_tool("tradeoff_precedents", arguments))


def _token_cost(result: dict[str, object]) -> int:
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
    return max(1, (len(encoded) + 3) // 4)


@pytest.mark.parametrize(
    "axis_container",
    [
        {"payload": {"facets": {"axes": AXES}}},
        {"payload": {"axes": AXES}},
        {"properties": {"dimensions": AXES}},
    ],
)
def test_mcp_parses_axes_from_live_payload_and_dimension_containers(
    axis_container: dict[str, object],
) -> None:
    tradeoff_id = _identifier("TradeOff", 11)
    decision_id = _identifier("Decision", 11)
    outcome_id = _identifier("Outcome", 11)
    nodes = (
        {"id": tradeoff_id, "type": "TradeOff", "namespace": NAMESPACE, **axis_container},
        {"id": decision_id, "type": "Decision", "namespace": NAMESPACE},
        {
            "id": outcome_id,
            "type": "Outcome",
            "namespace": NAMESPACE,
            "status": "realized",
            "summary": "The historical decision was realized.",
        },
    )
    edges = (
        {
            "source": tradeoff_id,
            "target": decision_id,
            "family": "tradeoff",
            "relation": "resolves",
        },
        {
            "source": decision_id,
            "target": outcome_id,
            "family": "causal",
            "relation": "outcome",
        },
    )

    response = _call(
        build_sakg_mcp_server(nodes=nodes, edges=edges),
        {"subject": "payload compatibility", "axes": AXES[:2]},
    )

    assert response.is_error is False
    assert response.structured_content["results"][0]["decision_id"] == decision_id


def test_live_mcp_returns_verified_outcome_precedents_with_complete_why_paths(
    live_server,
) -> None:
    server, outcome_ids = live_server
    response = _call(
        server,
        {"subject": "PAEOS runtime architecture", "axes": AXES[:2], "max_nodes": 10},
    )

    assert response.is_error is False
    precedents = response.structured_content["results"]
    assert len(precedents) == 3
    assert {item["outcome"]["id"] for item in precedents} == set(outcome_ids)
    assert all(item["outcome"]["status"] == "candidate" for item in precedents)
    assert all(item["outcome"]["state"] == "VERIFIED" for item in precedents)
    assert all(
        item["why"]
        == [
            "TradeOff axes matched: latency,reliability",
            "TradeOff resolves_to Decision",
            "Decision realized_as Outcome",
        ]
        for item in precedents
    )


def test_live_mcp_enforces_node_and_token_ceilings(live_server) -> None:
    server, _outcome_ids = live_server
    request = {"subject": "PAEOS runtime architecture", "axes": AXES[:2]}
    unbounded = _call(server, request).structured_content["results"]

    node_bounded = _call(server, {**request, "max_nodes": 1, "max_tokens": 4000})
    assert len(node_bounded.structured_content["results"]) == 1
    assert node_bounded.structured_content["truncated"] is True
    assert node_bounded.structured_content["omitted"] == 2

    token_budget = _token_cost(unbounded[0])
    token_bounded = _call(
        server,
        {**request, "max_nodes": 10, "max_tokens": token_budget},
    )
    retained = token_bounded.structured_content["results"]
    assert retained
    assert sum(_token_cost(item) for item in retained) <= token_budget
    assert token_bounded.structured_content["truncated"] is True


def test_unresolvable_and_empty_queries_degrade_to_empty_results(
    live_server, tmp_path: Path
) -> None:
    server, _outcome_ids = live_server
    unreachable = _call(
        server,
        {"subject": "unknown tradeoff", "axes": ["energy", "portability"]},
    )
    assert unreachable.is_error is False
    assert unreachable.structured_content["results"] == []

    empty = _call(server, {"subject": "", "axes": []})
    assert empty.is_error is False
    assert empty.structured_content["results"] == []

    with GraphStore(tmp_path / "empty-sakg.db", NAMESPACE) as empty_store:
        empty_graph = _call(
            build_sakg_mcp_server(graph=empty_store),
            {"subject": "no corpus", "axes": AXES[:2]},
        )
    assert empty_graph.is_error is False
    assert empty_graph.structured_content["results"] == []


def test_live_mcp_query_latency_is_under_100ms(live_server) -> None:
    server, _outcome_ids = live_server
    started = perf_counter()
    response = _call(
        server,
        {"subject": "PAEOS runtime architecture", "axes": AXES[:2], "max_nodes": 10},
    )
    latency_ms = (perf_counter() - started) * 1000

    assert response.is_error is False
    assert response.structured_content["results"]
    assert latency_ms < 100, f"live MCP query took {latency_ms:.3f}ms"
