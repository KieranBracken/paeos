"""Deterministic, budget-bounded SAKG projection engine.

Projection is read-only and advisory.  It ranks complete result structures, applies hard
node/token budgets by dropping whole results, and reports every omission explicitly.  Hashes
are over canonical JSON so a projection can be replayed from the same corpus and request.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

__all__ = [
    "ALLOWED_METHODS",
    "ALLOWED_TIERS",
    "BudgetedResults",
    "InvalidProjectionRequest",
    "ProjectionBudget",
    "ProjectionError",
    "ProjectionRequest",
    "ProjectionResponse",
    "apply_budget",
    "canonical_bytes",
    "canonical_hash",
    "enforce_budget",
    "estimate_tokens",
    "project",
    "project_nodes",
]

ALLOWED_METHODS = frozenset(
    {
        "query_architectures",
        "dependency_impact",
        "tradeoff_precedents",
        "pattern_retrieval",
        "memory_augment",
    }
)
ALLOWED_TIERS = frozenset({"SUMMARY", "INDEX", "COMPACT", "DIFF"})
RESPONSE_TIERS = frozenset({"SUMMARY", "INDEX"})
_STATUSES = frozenset({"canonical", "candidate", "refuted"})
_WORD = re.compile(r"[A-Za-z0-9_:-]+")


class ProjectionError(ValueError):
    """Base class for fail-closed projection errors."""


class InvalidProjectionRequest(ProjectionError):
    """A request does not satisfy the frozen projection contract."""


def canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as exc:
        raise ProjectionError("value is not canonical JSON") from exc


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InvalidProjectionRequest(f"{field} must be a positive integer")
    return value


def _text(value: object, field: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise InvalidProjectionRequest(f"{field} must be a non-empty string")
    return value


def _date(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidProjectionRequest(f"{field} must be RFC 3339 date-time") from exc
    return text


@dataclass(frozen=True, slots=True)
class ProjectionBudget:
    max_tokens: int
    max_nodes: int
    tier: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ProjectionBudget:
        if set(value) != {"max_tokens", "max_nodes", "tier"}:
            raise InvalidProjectionRequest("budget fields mismatch")
        tier = _text(value["tier"], "budget.tier")
        if tier not in ALLOWED_TIERS or tier == "FULL":
            raise InvalidProjectionRequest("budget.tier is not an advisory tier")
        return cls(
            max_tokens=_positive_int(value["max_tokens"], "budget.max_tokens"),
            max_nodes=_positive_int(value["max_nodes"], "budget.max_nodes"),
            tier=tier,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "max_tokens": self.max_tokens,
            "max_nodes": self.max_nodes,
            "tier": self.tier,
        }


@dataclass(frozen=True, slots=True)
class ProjectionRequest:
    method: str
    subject: str
    namespace: tuple[str, ...]
    budget: ProjectionBudget
    min_confidence: float
    as_of: str
    status: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ProjectionRequest:
        required = {"method", "subject", "namespace", "budget", "filters"}
        if set(value) != required:
            raise InvalidProjectionRequest("request fields mismatch")
        method = _text(value["method"], "method")
        if method not in ALLOWED_METHODS:
            raise InvalidProjectionRequest("unknown projection method")
        subject = _text(value["subject"], "subject")
        raw_namespaces = value["namespace"]
        if isinstance(raw_namespaces, str) or not isinstance(raw_namespaces, Sequence):
            raise InvalidProjectionRequest("namespace must be a non-empty array")
        namespaces = tuple(_text(item, "namespace item") for item in raw_namespaces)
        if not namespaces or len(set(namespaces)) != len(namespaces):
            raise InvalidProjectionRequest("namespace must be unique and non-empty")
        raw_budget = value["budget"]
        if not isinstance(raw_budget, Mapping):
            raise InvalidProjectionRequest("budget must be an object")
        raw_filters = value["filters"]
        if not isinstance(raw_filters, Mapping):
            raise InvalidProjectionRequest("filters must be an object")
        if set(raw_filters) != {"min_confidence", "as_of", "status"}:
            raise InvalidProjectionRequest("filters fields mismatch")
        confidence = raw_filters["min_confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise InvalidProjectionRequest("filters.min_confidence must be numeric")
        if not 0 <= confidence <= 1:
            raise InvalidProjectionRequest("filters.min_confidence must be between 0 and 1")
        raw_status = raw_filters["status"]
        if isinstance(raw_status, str) or not isinstance(raw_status, Sequence):
            raise InvalidProjectionRequest("filters.status must be an array")
        statuses = tuple(_text(item, "status item") for item in raw_status)
        if not statuses or len(set(statuses)) != len(statuses) or not set(statuses) <= _STATUSES:
            raise InvalidProjectionRequest("filters.status contains an unknown status")
        return cls(
            method=method,
            subject=subject,
            namespace=namespaces,
            budget=ProjectionBudget.from_mapping(cast(Mapping[str, object], raw_budget)),
            min_confidence=float(confidence),
            as_of=_date(raw_filters["as_of"], "filters.as_of"),
            status=statuses,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "subject": self.subject,
            "namespace": list(self.namespace),
            "budget": self.budget.to_dict(),
            "filters": {
                "min_confidence": self.min_confidence,
                "as_of": self.as_of,
                "status": list(self.status),
            },
        }


@dataclass(frozen=True, slots=True)
class BudgetedResults:
    retained: tuple[Mapping[str, object], ...]
    retained_tokens: int
    omitted: int
    truncated: bool


def _candidate_cost(candidate: Mapping[str, object]) -> int:
    explicit = candidate.get("estimated_tokens")
    if isinstance(explicit, int) and not isinstance(explicit, bool) and explicit > 0:
        return explicit
    return estimate_tokens(candidate)


def estimate_tokens(value: object) -> int:
    """Use a deterministic conservative four-bytes-per-token estimate."""
    return max(1, math.ceil(len(canonical_bytes(value)) / 4))


def enforce_budget(
    candidates: Iterable[Mapping[str, object]],
    budget: ProjectionBudget | Mapping[str, object],
) -> BudgetedResults:
    parsed = (
        budget if isinstance(budget, ProjectionBudget) else ProjectionBudget.from_mapping(budget)
    )
    retained: list[Mapping[str, object]] = []
    retained_tokens = 0
    omitted = 0
    for candidate in candidates:
        cost = _candidate_cost(candidate)
        if len(retained) >= parsed.max_nodes or retained_tokens + cost > parsed.max_tokens:
            omitted += 1
            continue
        retained.append(dict(candidate))
        retained_tokens += cost
    return BudgetedResults(tuple(retained), retained_tokens, omitted, omitted > 0)


apply_budget = enforce_budget


@dataclass(frozen=True, slots=True)
class ProjectionResponse:
    results: tuple[Mapping[str, object], ...]
    corpus_hash: str
    query_hash: str
    truncated: bool
    omitted: int
    tier: str
    sakg_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "results": [dict(item) for item in self.results],
            "provenance": {
                "sakg_version": self.sakg_version,
                "corpus_hash": self.corpus_hash,
                "query_hash": self.query_hash,
            },
            "truncated": self.truncated,
            "omitted": self.omitted,
            "trust": "untrusted",
            "tier": self.tier,
        }


def _records(source: object) -> tuple[Mapping[str, object], ...]:
    nodes_fn = getattr(source, "nodes", None)
    value = nodes_fn() if callable(nodes_fn) else source
    if isinstance(value, (Mapping, str, bytes)):
        raise ProjectionError("node source must be an iterable of objects")
    if not isinstance(value, Iterable):
        raise ProjectionError("node source must be iterable")
    result = tuple(value)
    if any(not isinstance(item, Mapping) for item in result):
        raise ProjectionError("node source contains a non-object")
    return cast(tuple[Mapping[str, object], ...], result)


def _summary(node: Mapping[str, object]) -> dict[str, object]:
    raw = node.get("node_summary", node)
    if not isinstance(raw, Mapping):
        raise ProjectionError("node_summary must be an object")
    required = {"id", "type", "namespace", "status", "label", "summary"}
    if not required <= set(raw):
        raise ProjectionError("node_summary is missing required fields")
    result = {key: raw[key] for key in required}
    if any(not isinstance(result[key], str) or not result[key] for key in required):
        raise ProjectionError("node_summary fields must be non-empty strings")
    if result["status"] not in _STATUSES:
        raise ProjectionError("node_summary status is unknown")
    return result


def _confidence(node: Mapping[str, object]) -> float:
    value = node.get("confidence", node.get("score", 0.0))
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ProjectionError("node confidence/score must be between 0 and 1")
    return float(value)


def _valid_at(node: Mapping[str, object], as_of: str) -> bool:
    point = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    start = node.get("valid_from")
    if isinstance(start, str) and point < datetime.fromisoformat(start.replace("Z", "+00:00")):
        return False
    end = node.get("valid_until")
    return not (
        isinstance(end, str) and point >= datetime.fromisoformat(end.replace("Z", "+00:00"))
    )


def _why(
    node: Mapping[str, object], request: ProjectionRequest, summary: Mapping[str, object]
) -> str:
    facets = node.get("facets")
    why_facet = facets.get("why") if isinstance(facets, Mapping) else None
    why_direct = node.get("why")
    if isinstance(why_facet, str) and why_facet:
        why: str = why_facet
    elif isinstance(why_direct, str) and why_direct:
        why = why_direct
    else:
        why = f"{request.method}: subject={request.subject} -> {summary['type']}:{summary['id']}"
    if len(why) > 1024:
        raise ProjectionError("why path exceeds 1024 characters")
    return why


def _ranked(
    nodes: Sequence[Mapping[str, object]], request: ProjectionRequest
) -> tuple[dict[str, object], ...]:
    subject_words = {word.lower() for word in _WORD.findall(request.subject)}
    ranked: list[tuple[float, str, dict[str, object], int]] = []
    for node in nodes:
        summary = _summary(node)
        if summary["namespace"] not in request.namespace:
            continue
        if summary["status"] not in request.status:
            continue
        confidence = _confidence(node)
        if confidence < request.min_confidence or not _valid_at(node, request.as_of):
            continue
        searchable = f"{summary['label']} {summary['summary']}".lower()
        hits = sum(1 for word in subject_words if word in searchable)
        lexical = hits / len(subject_words) if subject_words else 0.0
        score = min(1.0, 0.8 * confidence + 0.2 * lexical)
        result = {
            "node_summary": summary,
            "score": round(score, 12),
            "why": _why(node, request, summary),
        }
        ranked.append((score, cast(str, summary["id"]), result, _candidate_cost(node)))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return tuple({**result, "estimated_tokens": cost} for _, _, result, cost in ranked)


def _is_request(value: object) -> bool:
    return isinstance(value, Mapping) and "method" in value and "filters" in value


def project(
    first: Mapping[str, object] | Iterable[Mapping[str, object]],
    second: Mapping[str, object] | Iterable[Mapping[str, object]] | None = None,
    *,
    edges: Iterable[Mapping[str, object]] = (),
    sakg_version: str = "1.0.0",
) -> dict[str, object]:
    """Project nodes using either ``project(request, nodes)`` or ``project(nodes, request)``."""
    if _is_request(first):
        request_value, nodes_value = first, second
    elif _is_request(second):
        request_value, nodes_value = second, first
    else:
        raise InvalidProjectionRequest("a request mapping is required")
    if nodes_value is None:
        raise ProjectionError("node source is required")
    request = ProjectionRequest.from_mapping(cast(Mapping[str, object], request_value))
    nodes = _records(nodes_value)
    ranked = _ranked(nodes, request)
    budgeted = enforce_budget(ranked, request.budget)
    corpus = {"nodes": [dict(node) for node in nodes], "edges": [dict(edge) for edge in edges]}
    response_tier = request.budget.tier if request.budget.tier in RESPONSE_TIERS else "INDEX"
    return ProjectionResponse(
        results=tuple(
            {key: value for key, value in item.items() if key != "estimated_tokens"}
            for item in budgeted.retained
        ),
        corpus_hash=canonical_hash(corpus),
        query_hash=canonical_hash(request.to_dict()),
        truncated=budgeted.truncated,
        omitted=budgeted.omitted,
        tier=response_tier,
        sakg_version=_text(sakg_version, "sakg_version"),
    ).to_dict()


def project_nodes(
    nodes: Iterable[Mapping[str, object]],
    request: Mapping[str, object],
    *,
    edges: Iterable[Mapping[str, object]] = (),
    sakg_version: str = "1.0.0",
) -> dict[str, object]:
    return project(request, nodes, edges=edges, sakg_version=sakg_version)
