from __future__ import annotations

import asyncio

from sakg.mcp_server import build_sakg_mcp_server

T = "sakg://demo/TradeOff/01ARZ3NDEKTSV4RRFFQ69G5F01"
D = "sakg://demo/Decision/01ARZ3NDEKTSV4RRFFQ69G5F02"
OUTCOME = "sakg://demo/Outcome/01ARZ3NDEKTSV4RRFFQ69G5F03"


def graph() -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    nodes = (
        {
            "id": T,
            "type": "TradeOff",
            "namespace": "demo",
            "facets": {"axes": ["latency", "accuracy"]},
            "confidence": 0.9,
        },
        {"id": D, "type": "Decision", "namespace": "demo", "confidence": 0.9},
        {
            "id": OUTCOME,
            "type": "Outcome",
            "namespace": "demo",
            "status": "realized",
            "summary": "bounded result",
        },
    )
    edges = (
        {
            "edge_id": "e1",
            "source": T,
            "target": D,
            "family": "tradeoff",
            "relation": "resolves_to",
            "properties": {},
        },
        {
            "edge_id": "e2",
            "source": D,
            "target": OUTCOME,
            "family": "causal",
            "relation": "realized_as",
            "properties": {},
        },
    )
    return nodes, edges


def test_only_tradeoff_tool_is_exposed_and_returns_results() -> None:
    nodes, edges = graph()
    server = build_sakg_mcp_server(nodes=nodes, edges=edges)
    tools = asyncio.run(server.list_tools())
    assert [tool.name for tool in tools] == ["tradeoff_precedents"]
    response = asyncio.run(
        server.call_tool(
            "tradeoff_precedents", {"subject": "latency", "axes": ["latency", "accuracy"]}
        )
    )
    assert response.is_error is False
    assert response.structured_content["results"][0]["decision_id"] == D
