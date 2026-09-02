"""Deterministic, policy-gated traversal over the eight SAKG edge families.

This module only walks already-materialized edges.  It performs no ranking, synthesis, or
recommendation.  Dependency edges are checked as a directed graph and reject cycles;
``analogous_to`` is deliberately a one-hop relation; and a cross-namespace edge requires
explicit disclosure by both the source and target namespaces.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .store import EDGE_FAMILIES

__all__ = [
    "CrossNamespaceDenied",
    "DependencyCycleError",
    "DisclosurePolicy",
    "TraversalError",
    "TraversalStep",
    "append_edge_checked",
    "cross_namespace_allowed",
    "dependency_is_acyclic",
    "traverse",
    "traverse_analogous",
    "typed_walk",
    "validate_dependency_acyclic",
    "walk",
    "walk_ids",
]

_FAMILIES = frozenset(EDGE_FAMILIES)


class TraversalError(ValueError):
    """Base class for fail-closed traversal errors."""


class DependencyCycleError(TraversalError):
    """A dependency edge would make the directed dependency graph cyclic."""

    def __init__(self, cycle: Sequence[str]) -> None:
        self.cycle = tuple(cycle)
        super().__init__("dependency cycle: " + " -> ".join(self.cycle))


class CrossNamespaceDenied(TraversalError):
    """A cross-namespace edge lacks bilateral disclosure."""


@dataclass(frozen=True, slots=True)
class DisclosurePolicy:
    """The minimum bilateral disclosure contract for one namespace."""

    namespace: str
    share_with: frozenset[str] = frozenset()
    accept_from: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class TraversalStep:
    """One reached node and the edge that reached it."""

    node_id: str
    depth: int
    edge_id: str
    family: str
    relation: str


@runtime_checkable
class _EdgeStore(Protocol):
    def edges(self, family: str | None = None) -> tuple[dict[str, object], ...]: ...

    def append_edge(self, edge: Mapping[str, object]) -> str: ...


def _edges(
    source: Iterable[Mapping[str, object]] | _EdgeStore,
) -> tuple[Mapping[str, object], ...]:
    if isinstance(source, _EdgeStore):
        return tuple(source.edges())
    if isinstance(source, Iterable):
        return tuple(source)
    return ()


def _field(edge: Mapping[str, object], key: str) -> str:
    value = edge.get(key)
    if not isinstance(value, str) or not value:
        raise TraversalError(f"edge {key} must be a non-empty string")
    return value


def _namespace(node_id: str) -> str:
    parts = node_id.split("/", 3)
    if len(parts) < 4 or not node_id.startswith("sakg://"):
        raise TraversalError(f"malformed node identifier: {node_id!r}")
    return parts[2]


def _policy_namespace(policy: DisclosurePolicy | Mapping[str, object]) -> str:
    if isinstance(policy, DisclosurePolicy):
        return policy.namespace
    namespace = policy.get("namespace")
    if not isinstance(namespace, str) or not namespace:
        raise CrossNamespaceDenied("disclosure policy has no namespace")
    return namespace


def _peer_set(policy: DisclosurePolicy | Mapping[str, object], key: str) -> frozenset[str]:
    values: object
    if isinstance(policy, DisclosurePolicy):
        values = policy.share_with if key == "share_with" else policy.accept_from
    else:
        values = policy.get(key, ())
    if values is True:
        return frozenset({"*"})
    if isinstance(values, str):
        return frozenset({values})
    if isinstance(values, Collection):
        return frozenset(value for value in values if isinstance(value, str))
    return frozenset()


def _allows(policy: DisclosurePolicy | Mapping[str, object], key: str, peer: str) -> bool:
    peers = _peer_set(policy, key)
    return "*" in peers or peer in peers


def cross_namespace_allowed(
    source_policy: DisclosurePolicy | Mapping[str, object],
    target_policy: DisclosurePolicy | Mapping[str, object],
) -> bool:
    """Return true only when source outbound and target inbound disclosure both exist."""
    source = _policy_namespace(source_policy)
    target = _policy_namespace(target_policy)
    if source == target:
        return True
    return _allows(source_policy, "share_with", target) and _allows(
        target_policy, "accept_from", source
    )


def _policies_allow(
    source_id: str,
    target_id: str,
    policies: Mapping[str, DisclosurePolicy | Mapping[str, object]] | None,
) -> bool:
    source = _namespace(source_id)
    target = _namespace(target_id)
    if source == target:
        return True
    if policies is None or source not in policies or target not in policies:
        return False
    return cross_namespace_allowed(policies[source], policies[target])


def validate_dependency_acyclic(edges: Iterable[Mapping[str, object]]) -> None:
    """Reject any directed cycle formed by ``dependency`` family edges."""
    graph: dict[str, set[str]] = {}
    for edge in edges:
        if _field(edge, "family") != "dependency":
            continue
        source = _field(edge, "source")
        target = _field(edge, "target")
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set())
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(node: str) -> None:
        if node in visiting:
            start = path.index(node)
            raise DependencyCycleError((*path[start:], node))
        if node in visited:
            return
        visiting.add(node)
        path.append(node)
        for target in sorted(graph[node]):
            visit(target)
        path.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)


def dependency_is_acyclic(edges: Iterable[Mapping[str, object]]) -> bool:
    try:
        validate_dependency_acyclic(edges)
    except DependencyCycleError:
        return False
    return True


def append_edge_checked(store: _EdgeStore, edge: Mapping[str, object]) -> str:
    """Validate the complete dependency projection before an append-only store write."""
    existing = list(_edges(store))
    existing.append(edge)
    validate_dependency_acyclic(existing)
    return store.append_edge(edge)


def walk_ids(
    source: Iterable[Mapping[str, object]] | _EdgeStore,
    start_id: str,
    family: str,
    *,
    relation: str | None = None,
    max_depth: int | None = None,
    disclosure_policies: Mapping[str, DisclosurePolicy | Mapping[str, object]] | None = None,
) -> tuple[str, ...]:
    """Return reached node IDs in deterministic breadth-first order.

    ``analogous_to`` is never expanded transitively: relation-filtered walks stop after one hop.
    Cross-namespace edges fail closed unless bilateral policies are supplied and allow them.
    """
    if family not in _FAMILIES:
        raise TraversalError(f"unknown edge family: {family}")
    if max_depth is not None and max_depth < 1:
        return ()
    edges = _edges(source)
    reached: list[str] = []
    seen = {start_id}
    queue: deque[tuple[str, int]] = deque(((start_id, 0),))
    while queue:
        current, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        candidates: list[tuple[str, str, str, Mapping[str, object]]] = []
        for edge in edges:
            if _field(edge, "family") != family or _field(edge, "source") != current:
                continue
            edge_relation = _field(edge, "relation")
            if relation is not None and edge_relation != relation:
                continue
            target = _field(edge, "target")
            if not _policies_allow(current, target, disclosure_policies):
                if _namespace(current) != _namespace(target):
                    raise CrossNamespaceDenied(
                        f"{_namespace(current)} has no bilateral disclosure with"
                        f" {_namespace(target)}"
                    )
                continue
            candidates.append((_field(edge, "edge_id"), target, edge_relation, edge))
        for _edge_id, target, _edge_relation, _edge in sorted(candidates):
            if target in seen:
                continue
            seen.add(target)
            reached.append(target)
            if not (family == "similarity" and relation == "analogous_to"):
                queue.append((target, depth + 1))
    return tuple(reached)


def walk(
    source: Iterable[Mapping[str, object]] | _EdgeStore,
    start_id: str,
    family: str,
    **kwargs: object,
) -> tuple[str, ...]:
    """Compatibility alias for ``walk_ids``."""
    return walk_ids(source, start_id, family, **kwargs)  # type: ignore[arg-type]


traverse = walk_ids


def traverse_analogous(
    source: Iterable[Mapping[str, object]] | _EdgeStore,
    start_id: str,
    *,
    disclosure_policies: Mapping[str, DisclosurePolicy | Mapping[str, object]] | None = None,
) -> tuple[str, ...]:
    """Traverse direct ``analogous_to`` edges only; never compute a transitive closure."""
    return walk_ids(
        source,
        start_id,
        "similarity",
        relation="analogous_to",
        max_depth=1,
        disclosure_policies=disclosure_policies,
    )


def typed_walk(
    source: Iterable[Mapping[str, object]] | _EdgeStore,
    nodes: Iterable[Mapping[str, object]],
    start_id: str,
    family: str,
    *,
    target_type: str | None = None,
    **kwargs: object,
) -> tuple[Mapping[str, object], ...]:
    """Walk edges and return only reached typed node envelopes, without judgment or ranking."""
    node_map = {str(node["id"]): node for node in nodes if isinstance(node.get("id"), str)}
    ids = walk_ids(source, start_id, family, **kwargs)  # type: ignore[arg-type]
    result = []
    for node_id in ids:
        node = node_map.get(node_id)
        if node is None:
            continue
        if target_type is not None and node.get("type") != target_type:
            continue
        result.append(node)
    return tuple(result)
