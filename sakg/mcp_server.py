"""Read-only MCP surface for the SAKG tradeoff-precedents query.

This module is a deliberate vendor boundary.  It registers exactly one MCP tool, snapshots the
graph at construction, and never exposes a mutation or promotion operation.  Results are advisory
and carry explicit ``provenance=sakg``, ``trust=untrusted`` and a non-FULL tier.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, cast

from mcp.server import MCPServer  # pyright: ignore[reportMissingImports]


from sakg.methods.tradeoff_precedents import TradeoffPrecedentError, tradeoff_precedents

__all__ = ["build_sakg_mcp_server", "build_server", "main"]

_TIERS = frozenset({"SUMMARY", "INDEX"})
_DEFAULT_TIER = "SUMMARY"
_DEFAULT_MAX_NODES = 20
_DEFAULT_MAX_TOKENS = 4000


def _records(value: object, label: str) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if hasattr(value, "nodes"):
        source = cast(Any, value)
        value = source.nodes() if callable(source.nodes) else value
    if isinstance(value, Mapping):
        if "id" in value or "type" in value or "node_id" in value:
            return (cast(Mapping[str, object], value),)
        value = tuple(value.values())
    elif isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
        raise ValueError(f"{label} must be an iterable of objects")
    else:
        value = tuple(value)
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} contains a non-object")
    return cast(tuple[Mapping[str, object], ...], tuple(value))


def _edges(value: object) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if hasattr(value, "edges"):
        source = cast(Any, value)
        value = source.edges() if callable(source.edges) else value
    if isinstance(value, Mapping):
        if "source" in value or "target" in value or "edge_id" in value:
            return (cast(Mapping[str, object], value),)
        value = tuple(value.values())
    elif isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
        raise ValueError("edges must be an iterable of objects")
    else:
        value = tuple(value)
    result: list[Mapping[str, object]] = []
    for item in value:
        if isinstance(item, Mapping):
            result.append(item)
            continue
        if not hasattr(item, "source") or not hasattr(item, "target"):
            raise ValueError("edges contains a non-object")
        edge = cast(Any, item)
        result.append(
            {
                "source": edge.source,
                "target": edge.target,
                "family": getattr(edge, "family", ""),
                "relation": getattr(edge, "relation", ""),
                "namespace": getattr(edge, "namespace", None),
                "properties": getattr(edge, "properties", {}),
            }
        )
    return tuple(result)


def _snapshot(
    graph: object, nodes: object | None, edges: object | None
) -> tuple[tuple[Mapping[str, object], ...], tuple[Mapping[str, object], ...]]:
    if graph is not None:
        if nodes is not None or edges is not None:
            raise ValueError("provide graph or nodes/edges, not both")
        if isinstance(graph, Mapping) and ("nodes" in graph or "edges" in graph):
            nodes, edges = graph.get("nodes"), graph.get("edges")
        else:
            nodes = graph
            edges = graph
    return _records(nodes, "nodes"), _edges(edges)


def _positive(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _bounded(
    results: tuple[dict[str, object], ...], max_nodes: int, max_tokens: int
) -> tuple[list[dict[str, object]], int]:
    retained: list[dict[str, object]] = []
    retained_tokens = 0
    omitted = 0
    for result in results:
        cost = max(1, (len(json.dumps(result, sort_keys=True, separators=(",", ":"))) + 3) // 4)
        if len(retained) >= max_nodes or retained_tokens + cost > max_tokens:
            omitted += 1
            continue
        retained.append(dict(result))
        retained_tokens += cost
    return retained, omitted


def build_sakg_mcp_server(
    graph: object | None = None,
    *,
    nodes: object | None = None,
    edges: object | None = None,
    tier: str = _DEFAULT_TIER,
) -> MCPServer:
    """Build a deny-by-default server exposing only ``tradeoff_precedents``."""
    if tier not in _TIERS:
        raise ValueError("tier must be SUMMARY or INDEX")
    node_snapshot, edge_snapshot = _snapshot(graph, nodes, edges)
    server = MCPServer("paeos-sakg", description="Read-only advisory SAKG projection")

    @server.tool(name="tradeoff_precedents", structured_output=True)
    def tradeoff_precedents_tool(
        subject: str,
        axes: list[str],
        namespace: str | None = None,
        min_confidence: float = 0.0,
        max_nodes: int = _DEFAULT_MAX_NODES,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> dict[str, object]:
        """Return ranked, advisory TradeOff precedents without any write capability."""
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("subject must be a non-empty string")
        max_nodes_value = _positive(max_nodes, "max_nodes")
        max_tokens_value = _positive(max_tokens, "max_tokens")
        try:
            raw = tradeoff_precedents(
                tuple(node for node in node_snapshot if node.get("type") in {None, "TradeOff"}),
                tuple(node for node in node_snapshot if node.get("type") in {None, "Decision"}),
                tuple(node for node in node_snapshot if node.get("type") in {None, "Outcome"}),
                edge_snapshot,
                axes,
                min_confidence=min_confidence,
                namespace=namespace,
            )
        except TradeoffPrecedentError as exc:
            raise ValueError(str(exc)) from exc
        results, omitted = _bounded(raw, max_nodes_value, max_tokens_value)
        return {
            "provenance": "sakg",
            "trust": "untrusted",
            "tier": tier,
            "method": "tradeoff_precedents",
            "subject": subject.strip(),
            "results": results,
            "truncated": omitted > 0,
            "omitted": omitted,
        }

    return server


build_server = build_sakg_mcp_server


def main() -> None:  # pragma: no cover - stdio launch is a deployment seam
    build_sakg_mcp_server().run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
