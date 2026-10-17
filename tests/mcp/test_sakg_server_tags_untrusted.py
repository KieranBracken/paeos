from __future__ import annotations

import asyncio

import pytest
from sakg.mcp_server import build_sakg_mcp_server


def test_every_response_is_untrusted_sakg_advisory_data() -> None:
    server = build_sakg_mcp_server(nodes=(), edges=(), tier="INDEX")
    response = asyncio.run(
        server.call_tool("tradeoff_precedents", {"subject": "x", "axes": ["a", "b"]})
    )
    payload = response.structured_content
    assert payload["provenance"] == "sakg"
    assert payload["trust"] == "untrusted"
    assert payload["tier"] in {"SUMMARY", "INDEX"}
    assert payload["tier"] != "FULL"


def test_full_tier_cannot_be_configured() -> None:
    with pytest.raises(ValueError, match="tier"):
        build_sakg_mcp_server(nodes=(), edges=(), tier="FULL")

