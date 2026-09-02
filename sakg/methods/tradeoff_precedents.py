"""S2 tradeoff precedent query over typed SAKG graph objects.

The method is deliberately read-only: it matches every requested axis on TradeOff nodes,
follows an explicit ``resolves_to`` edge to a Decision, then joins only a realized Outcome
through a ``realized_as`` edge.  Missing or malformed links are skipped fail-closed, and the
returned ``why`` path makes the three-hop evidence chain visible to callers.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, cast

__all__ = [
    "TradeoffPrecedentError",
    "execute",
    "find_tradeoff_precedents",
    "query_tradeoff_precedents",
    "run",
    "tradeoff_precedents",
]

_AXIS_RE = re.compile(r"^[a-z0-9][a-z0-9 _:-]*$")


class TradeoffPrecedentError(ValueError):
    """Raised when a tradeoff query or graph input is malformed."""


def _records(value: object, label: str) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if hasattr(value, "nodes"):
        source = cast(Any, value)
        value = source.nodes() if callable(source.nodes) else value
    if isinstance(value, Mapping):
        if "id" in value or "node_id" in value or "type" in value:
            return (cast(Mapping[str, object], value),)
        values = tuple(value.values())
    else:
        if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
            raise TradeoffPrecedentError(f"{label} must be an iterable of objects")
        values = tuple(value)
    if any(not isinstance(item, Mapping) for item in values):
        raise TradeoffPrecedentError(f"{label} contains a non-object")
    return cast(tuple[Mapping[str, object], ...], values)


def _edge_records(value: object) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if hasattr(value, "edges"):
        source = cast(Any, value)
        value = source.edges() if callable(source.edges) else value
    if isinstance(value, Mapping):
        if "source" in value or "target" in value or "edge_id" in value:
            return (cast(Mapping[str, object], value),)
        values = tuple(value.values())
    else:
        if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
            raise TradeoffPrecedentError("edges must be an iterable of objects")
        values = tuple(value)
    if any(not isinstance(item, Mapping) and not hasattr(item, "source") for item in values):
        raise TradeoffPrecedentError("edges contains a non-object")
    result: list[Mapping[str, object]] = []
    for item in values:
        if isinstance(item, Mapping):
            result.append(item)
        else:
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


def _id(node: Mapping[str, object]) -> str | None:
    value = node.get("id", node.get("node_id"))
    return value if isinstance(value, str) and value else None


def _type(node: Mapping[str, object]) -> str | None:
    value = node.get("type")
    if isinstance(value, str) and value:
        return value
    node_id = _id(node)
    if node_id and "/" in node_id:
        parts = node_id.split("/")
        if len(parts) >= 4:
            return parts[-2]
    return None


def _namespace(node: Mapping[str, object]) -> str | None:
    value = node.get("namespace")
    if isinstance(value, str) and value:
        return value
    node_id = _id(node)
    if node_id and node_id.startswith("sakg://"):
        parts = node_id.split("/")
        return parts[2] if len(parts) > 2 else None
    return None


def _axis_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().lower().split())
    return text if text and _AXIS_RE.fullmatch(text) else None


def _axes(node: Mapping[str, object]) -> frozenset[str]:
    containers: list[Mapping[str, object]] = [node]
    for name in ("facets", "coordinates", "data", "payload"):
        candidate = node.get(name)
        if isinstance(candidate, Mapping):
            containers.append(candidate)
    raw_values: list[object] = []
    for container in containers:
        for key in ("axes", "axis", "dimensions", "tradeoff_axes"):
            raw = container.get(key)
            if isinstance(raw, Mapping):
                raw_values.extend(raw.keys())
            elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
                raw_values.extend(raw)
            elif raw is not None:
                raw_values.append(raw)
    normalized = {_axis_text(item) for item in raw_values}
    return frozenset(item for item in normalized if item is not None)


def _field(node: Mapping[str, object], name: str) -> object | None:
    if name in node:
        return node[name]
    for container_name in ("facets", "coordinates", "data", "payload"):
        container = node.get(container_name)
        if isinstance(container, Mapping) and name in container:
            return container[name]
    return None


def _score(*nodes: Mapping[str, object], edge: Mapping[str, object] | None = None) -> float:
    candidates: list[object] = []
    for node in nodes:
        candidates.extend(_field(node, key) for key in ("score", "relevance", "confidence"))
    if edge is not None:
        properties = edge.get("properties")
        if isinstance(properties, Mapping):
            candidates.extend(properties.get(key) for key in ("score", "relevance", "confidence"))
    for candidate in candidates:
        if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
            continue
        value = float(candidate)
        if math.isfinite(value) and 0 <= value <= 1:
            return value
    return 1.0


def _endpoint(edge: Mapping[str, object], name: str) -> str | None:
    for key in (name, "from" if name == "source" else "to", f"{name}_id"):
        value = edge.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _relation(edge: Mapping[str, object]) -> str:
    value = edge.get("relation", "")
    return value.strip().lower().replace("-", "_") if isinstance(value, str) else ""


def _family(edge: Mapping[str, object]) -> str:
    value = edge.get("family", "")
    return value.strip().lower() if isinstance(value, str) else ""


def _is_resolving(edge: Mapping[str, object]) -> bool:
    relation = _relation(edge)
    return "resolv" in relation and (
        "decision" in relation or relation in {"resolves_to", "resolves_to_decision"}
    )


def _is_realization(edge: Mapping[str, object]) -> bool:
    relation = _relation(edge)
    return "realized_as" in relation or ("realiz" in relation and "outcome" in relation)


def _query_axes(axes: Sequence[str]) -> tuple[str, ...]:
    if isinstance(axes, (str, bytes, bytearray)):
        raise TradeoffPrecedentError("axes must contain at least two strings")
    normalized = tuple(_axis_text(axis) for axis in axes)
    if len(normalized) < 2 or any(axis is None for axis in normalized):
        raise TradeoffPrecedentError("axes must contain at least two valid strings")
    result = cast(tuple[str, ...], normalized)
    if len(set(result)) != len(result):
        raise TradeoffPrecedentError("axes must be unique")
    return result


def tradeoff_precedents(
    tradeoffs: object,
    decisions: object,
    outcomes: object,
    edges: object,
    axes: Sequence[str],
    *,
    min_confidence: float = 0.0,
    namespace: str | None = None,
) -> tuple[dict[str, object], ...]:
    """Return ranked TradeOff -> Decision -> realized Outcome precedent records.

    All links are directed and explicit.  A malformed node, a missing hop, a non-realized
    outcome, or a namespace mismatch simply cannot become a result; no inference is invented.
    """
    query_axes = _query_axes(axes)
    if (
        isinstance(min_confidence, bool)
        or not isinstance(min_confidence, (int, float))
        or not 0 <= min_confidence <= 1
    ):
        raise TradeoffPrecedentError("min_confidence must be between 0 and 1")
    tradeoff_nodes = _records(tradeoffs, "tradeoffs")
    decision_nodes = _records(decisions, "decisions")
    outcome_nodes = _records(outcomes, "outcomes")
    edge_nodes = _edge_records(edges)
    decision_by_id = {
        node_id: node
        for node in decision_nodes
        if (node_id := _id(node)) is not None and (_type(node) in {None, "Decision"})
    }
    outcome_by_id = {
        node_id: node
        for node in outcome_nodes
        if (node_id := _id(node)) is not None and (_type(node) in {None, "Outcome"})
    }
    results: dict[tuple[str, str], dict[str, object]] = {}
    for tradeoff in tradeoff_nodes:
        tradeoff_id = _id(tradeoff)
        if tradeoff_id is None or _type(tradeoff) not in {None, "TradeOff"}:
            continue
        if namespace is not None and _namespace(tradeoff) != namespace:
            continue
        if not set(query_axes) <= _axes(tradeoff):
            continue
        resolving_edges = tuple(
            edge
            for edge in edge_nodes
            if _endpoint(edge, "source") == tradeoff_id
            and _is_resolving(edge)
            and (decision_id := _endpoint(edge, "target")) in decision_by_id
        )
        for resolving in resolving_edges:
            decision_id = _endpoint(resolving, "target")
            if decision_id is None:
                continue
            decision = decision_by_id[decision_id]
            if namespace is not None and _namespace(decision) != namespace:
                continue
            realizations = tuple(
                edge
                for edge in edge_nodes
                if _endpoint(edge, "source") == decision_id
                and _is_realization(edge)
                and (outcome_id := _endpoint(edge, "target")) in outcome_by_id
            )
            for realization in realizations:
                outcome_id = _endpoint(realization, "target")
                if outcome_id is None:
                    continue
                outcome = outcome_by_id[outcome_id]
                status = _field(outcome, "status")
                summary = _field(outcome, "summary")
                if status != "realized" or not isinstance(summary, str) or not summary.strip():
                    continue
                if namespace is not None and _namespace(outcome) != namespace:
                    continue
                score = _score(tradeoff, decision, outcome, edge=resolving)
                if score < float(min_confidence):
                    continue
                result: dict[str, object] = {
                    "decision_id": decision_id,
                    "score": score,
                    "why": [
                        f"TradeOff axes matched: {','.join(query_axes)}",
                        "TradeOff resolves_to Decision",
                        "Decision realized_as Outcome",
                    ],
                    "outcome": {"id": outcome_id, "status": "realized", "summary": summary.strip()},
                }
                key = (decision_id, outcome_id)
                prior = results.get(key)
                prior_score = prior.get("score") if prior is not None else None
                if prior is None or (
                    isinstance(prior_score, (int, float)) and score > float(prior_score)
                ):
                    results[key] = result

    def result_key(item: dict[str, object]) -> tuple[float, str, str]:
        score_value = item.get("score")
        outcome_value = item.get("outcome")
        outcome_id = outcome_value.get("id") if isinstance(outcome_value, Mapping) else ""
        return (
            -float(score_value) if isinstance(score_value, (int, float)) else 0.0,
            str(item.get("decision_id", "")),
            str(outcome_id),
        )

    return tuple(
        sorted(
            results.values(),
            key=result_key,
        )
    )


def execute(request: Mapping[str, object], nodes: object, edges: object) -> dict[str, object]:
    """Execute a request-shaped query and return an advisory, untrusted response."""
    if request.get("method") != "tradeoff_precedents":
        raise TradeoffPrecedentError("method must be tradeoff_precedents")
    raw_axes = request.get("axes")
    if not isinstance(raw_axes, Sequence) or isinstance(raw_axes, (str, bytes, bytearray)):
        raise TradeoffPrecedentError("request.axes must be an array")
    records = _records(nodes, "nodes")
    tradeoffs = tuple(node for node in records if _type(node) in {None, "TradeOff"})
    decisions = tuple(node for node in records if _type(node) in {None, "Decision"})
    outcomes = tuple(node for node in records if _type(node) in {None, "Outcome"})
    result = tradeoff_precedents(
        tradeoffs, decisions, outcomes, edges, cast(Sequence[str], raw_axes)
    )
    return {"results": [dict(item) for item in result], "trust": "untrusted", "tier": "SUMMARY"}


query_tradeoff_precedents = execute
run = execute
find_tradeoff_precedents = tradeoff_precedents
