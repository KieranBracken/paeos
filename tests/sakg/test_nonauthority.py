from __future__ import annotations

import asyncio
import pytest

from sakg.mcp_server import build_sakg_mcp_server


def test_consumer_surface_is_query_only_and_advisory() -> None:
    server = build_sakg_mcp_server(nodes=(), edges=())
    tools = asyncio.run(server.list_tools())
    assert [tool.name for tool in tools] == ["tradeoff_precedents"]

    response = asyncio.run(
        server.call_tool(
            "tradeoff_precedents",
            {"subject": "latency", "axes": ["latency", "accuracy"]},
        )
    )
    payload = response.structured_content
    assert response.is_error is False
    assert payload["provenance"] == "sakg"
    assert payload["trust"] == "untrusted"
    assert payload["tier"] in {"SUMMARY", "INDEX"}


def test_full_tier_is_not_an_admissible_consumer_contract() -> None:
    with pytest.raises(ValueError, match="tier"):
        build_sakg_mcp_server(nodes=(), edges=(), tier="FULL")
