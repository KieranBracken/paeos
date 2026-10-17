from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from concept.mcp_server import build_concept_mcp_server
from mcp.server.mcpserver.exceptions import ToolError

from tests.mcp._fixtures import seed_empty


def test_server_registers_exactly_the_five_read_tools(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    try:
        tools = asyncio.run(server.list_tools())
        assert [tool.name for tool in tools] == [
            "concept_get",
            "concept_search",
            "concept_neighborhood",
            "concept_path",
            "concept_hypothesis_get",
        ]
    finally:
        server.close()


def test_tool_schemas_require_typed_query_arguments(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    try:
        tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
        assert tools["concept_get"].input_schema["required"] == ["uri"]
        assert tools["concept_search"].input_schema["required"] == ["request"]
        assert tools["concept_neighborhood"].input_schema["required"] == ["uri"]
        assert tools["concept_path"].input_schema["required"] == ["source_uri", "target_uri"]
        assert tools["concept_hypothesis_get"].input_schema["required"] == ["uri"]
        for tool in tools.values():
            assert tool.output_schema["type"] == "object"
    finally:
        server.close()


def test_server_lifecycle_is_idempotent_and_closed_queries_degrade(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    server.close()
    server.close()
    response = asyncio.run(
        server.call_tool(
            "concept_get",
            {"uri": "concept://demo/concept/00000000000000000000000000"},
        )
    )
    assert response.is_error is False
    assert response.structured_content["results"] == []
    assert response.structured_content["error"]["type"] == "StoreUnavailable"


def test_unknown_tool_names_are_rejected_by_mcp(tmp_path: Path) -> None:
    server = build_concept_mcp_server(seed_empty(tmp_path / "empty.db"))
    try:
        with pytest.raises(ToolError):
            asyncio.run(server.call_tool("concept_mutate", {}))
    finally:
        server.close()
