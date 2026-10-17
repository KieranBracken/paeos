from __future__ import annotations

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from sakg.mcp_server import build_sakg_mcp_server


def test_unknown_and_mutating_names_are_denied_by_the_structural_surface() -> None:
    server = build_sakg_mcp_server(nodes=(), edges=())
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert names == {"tradeoff_precedents"}
    for denied in ("append", "write", "promote", "ingest", "delete"):
        assert denied not in names
        with pytest.raises(ToolError):
            asyncio.run(server.call_tool(denied, {}))


def test_graph_is_snapshotted_and_server_has_no_mutating_tool() -> None:
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    server = build_sakg_mcp_server(nodes=nodes, edges=edges)
    nodes.append({"id": "unexpected", "type": "Decision"})
    response = asyncio.run(
        server.call_tool("tradeoff_precedents", {"subject": "x", "axes": ["a", "b"]})
    )
    assert response.structured_content["results"] == []
