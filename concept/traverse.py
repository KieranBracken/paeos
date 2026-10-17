"""Bounded, typed graph traversal and reproducible neighborhood snapshots."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Collection, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol, cast

from concept.ids import ConceptURI, canonical_json, content_hash, node_uri, validate_concept_uri
from concept.model import EDGE_FAMILIES, EdgeEnvelope, NodeEnvelope, SemanticNeighborhood
from concept.store import ConceptStore, EdgeQuery

__all__ = [
    "BOTH",
    "EDGE_FAMILIES",
    "INCOMING",
    "OUTGOING",
    "CrossNamespaceDenied",
    "Direction",
    "NamespaceReadPolicy",
    "TraversalCycleError",
    "TraversalError",
    "TraversalPath",
    "TraversalRequest",
    "TraversalResult",
    "TraversalStep",
    "materialize_neighborhood",
    "traverse",
]


class Direction(StrEnum):
    """The permitted orientation for each traversed edge."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    BOTH = "both"


INCOMING = Direction.INCOMING
OUTGOING = Direction.OUTGOING
BOTH = Direction.BOTH

_RELATIONS_BY_FAMILY: dict[str, frozenset[str]] = {
    "derivation": frozenset({"derived_from", "supersedes", "specializes_from"}),
    "analogy": frozenset({"has_source", "has_target", "refines"}),
    "recombination": frozenset({"contributes_to", "combined_as"}),
    "abstraction": frozenset({"abstracts_to", "generalizes_to"}),
    "exemplification": frozenset({"exemplifies", "counterexample_to"}),
    "neighborhood": frozenset({"contains"}),
}
_ALL_RELATIONS = frozenset().union(*_RELATIONS_BY_FAMILY.values())
_NONTRANSITIVE_FAMILIES = frozenset({"analogy", "neighborhood"})
_NAMESPACE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,62}")


class TraversalError(ValueError):
    """Base class for fail-closed traversal errors."""


class CrossNamespaceDenied(TraversalError):
    """A root or edge crosses a namespace without an explicit read policy."""


class TraversalCycleError(TraversalError):
    """A derivation or supersession path contains a directed cycle."""

    def __init__(self, cycle: Iterable[ConceptURI | str]) -> None:
        self.cycle = tuple(cycle)
        super().__init__("derivation/supersession cycle: " + " -> ".join(_uri_text(uri) for uri in self.cycle))


@dataclass(frozen=True, slots=True)
class NamespaceReadPolicy:
    """Explicit permission for a namespace to read another namespace."""

    namespace: str
    readable_namespaces: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        _validate_namespace(self.namespace, "read policy namespace")
        object.__setattr__(self, "readable_namespaces", frozenset(self.readable_namespaces))

    def allows(self, namespace: str) -> bool:
        return namespace == self.namespace or "*" in self.readable_namespaces or namespace in self.readable_namespaces


ReadPolicy = (
    NamespaceReadPolicy
    | Mapping[str, object]
    | Collection[str]
    | str
    | None
)


@dataclass(frozen=True, slots=True)
class TraversalStep:
    """One directed hop, including the edge and relation that justified it."""

    node_uri: ConceptURI | str
    edge_uri: ConceptURI | str
    source_uri: ConceptURI | str
    target_uri: ConceptURI | str
    family: str
    relation: str
    direction: Direction

    @property
    def uri(self) -> ConceptURI | str:
        return self.node_uri

    def to_dict(self) -> dict[str, object]:
        return {
            "uri": _uri_text(self.node_uri),
            "edge_uri": _uri_text(self.edge_uri),
            "source_uri": _uri_text(self.source_uri),
            "target_uri": _uri_text(self.target_uri),
            "family": self.family,
            "relation": self.relation,
            "direction": cast(Direction, self.direction).value,
        }


@dataclass(frozen=True, slots=True)
class TraversalPath:
    """Complete, ordered explanation for a returned node or edge."""

    node_uris: tuple[ConceptURI | str, ...]
    edge_uris: tuple[ConceptURI | str, ...]
    steps: tuple[TraversalStep, ...] = field(default_factory=tuple)
    reason: str = ""

    @property
    def nodes(self) -> tuple[ConceptURI | str, ...]:
        return self.node_uris

    @property
    def edges(self) -> tuple[ConceptURI | str, ...]:
        return self.edge_uris

    def to_dict(self) -> dict[str, object]:
        return {
            "node_uris": [_uri_text(uri) for uri in self.node_uris],
            "edge_uris": [_uri_text(uri) for uri in self.edge_uris],
            "steps": [step.to_dict() for step in self.steps],
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class TraversalRequest:
    """Immutable constraints for one bounded typed traversal."""

    namespace: str
    roots: tuple[ConceptURI | str, ...] = field(default_factory=tuple)
    direction: Direction | str = Direction.OUTGOING
    families: tuple[str, ...] = field(default_factory=tuple)
    relations: tuple[str, ...] = field(default_factory=tuple)
    max_hops: int = 1
    max_expansions: int = 100
    max_results: int = 100
    read_policy: ReadPolicy = None
    disclosure_filters: ReadPolicy = None
    max_serialized_bytes: int | None = None
    family_allow_list: tuple[str, ...] | None = None
    relation_allow_list: tuple[str, ...] | None = None
    allowed_families: tuple[str, ...] | None = None
    allowed_relations: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        _validate_namespace(self.namespace)
        if not isinstance(self.direction, Direction):
            try:
                object.__setattr__(self, "direction", Direction(self.direction))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"unknown traversal direction: {self.direction!r}") from exc

        roots = tuple(_ensure_uri(uri, "root") for uri in self.roots)
        object.__setattr__(self, "roots", _unique_sorted(roots))

        families = self.family_allow_list
        if families is None:
            families = self.allowed_families
        if families is None:
            families = self.families
        normalized_families = _normalize_allow_list(families, EDGE_FAMILIES, "edge family")
        if not normalized_families:
            normalized_families = EDGE_FAMILIES
        object.__setattr__(self, "families", normalized_families)
        object.__setattr__(self, "family_allow_list", normalized_families)
        object.__setattr__(self, "allowed_families", normalized_families)

        relations = self.relation_allow_list
        if relations is None:
            relations = self.allowed_relations
        if relations is None:
            relations = self.relations
        normalized_relations = _normalize_allow_list(relations, _ALL_RELATIONS, "relation")
        object.__setattr__(self, "relations", normalized_relations)
        object.__setattr__(self, "relation_allow_list", normalized_relations)
        object.__setattr__(self, "allowed_relations", normalized_relations)

        for field_name in ("max_hops", "max_expansions", "max_results"):
            _validate_budget(getattr(self, field_name), field_name)
        if self.max_serialized_bytes is not None:
            _validate_budget(self.max_serialized_bytes, "max_serialized_bytes")
        if self.read_policy is not None:
            object.__setattr__(self, "read_policy", _freeze(self.read_policy))
        if self.disclosure_filters is not None:
            object.__setattr__(self, "disclosure_filters", _freeze(self.disclosure_filters))

    @property
    def effective_read_policy(self) -> ReadPolicy:
        return self.read_policy if self.read_policy is not None else self.disclosure_filters

    def to_dict(self) -> dict[str, object]:
        return {
            "namespace": self.namespace,
            "roots": [_uri_text(uri) for uri in self.roots],
            "direction": cast(Direction, self.direction).value,
            "families": list(self.families),
            "relations": list(self.relations),
            "max_hops": self.max_hops,
            "max_expansions": self.max_expansions,
            "max_results": self.max_results,
            "read_policy": _thaw(self.effective_read_policy),
            "max_serialized_bytes": self.max_serialized_bytes,
        }


@dataclass(frozen=True, slots=True)
class TraversalResult:
    """Immutable URI result, path explanations, and exact budget consumption."""

    namespace: str
    roots: tuple[ConceptURI | str, ...]
    nodes: tuple[ConceptURI | str, ...]
    edges: tuple[ConceptURI | str, ...]
    why: Mapping[str, TraversalPath]
    edge_why: Mapping[str, TraversalPath]
    graph_snapshot_hash: str
    budgets_requested: Mapping[str, int]
    budgets_consumed: Mapping[str, int]
    omitted: int = 0
    truncated: bool = False
    request: TraversalRequest | None = None
    query_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "roots", tuple(self.roots))
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(self, "why", _URIPathMap(self.why))
        object.__setattr__(self, "edge_why", _URIPathMap(self.edge_why))
        object.__setattr__(self, "budgets_requested", MappingProxyType(dict(self.budgets_requested)))
        object.__setattr__(self, "budgets_consumed", MappingProxyType(dict(self.budgets_consumed)))

    @property
    def node_uris(self) -> tuple[ConceptURI | str, ...]:
        return self.nodes

    @property
    def edge_uris(self) -> tuple[ConceptURI | str, ...]:
        return self.edges

    @property
    def paths(self) -> Mapping[str, TraversalPath]:
        return self.why

    @property
    def steps(self) -> int:
        return self.budgets_consumed["steps"]

    @property
    def nodes_consumed(self) -> int:
        return self.budgets_consumed["nodes"]

    @property
    def edges_consumed(self) -> int:
        return self.budgets_consumed["edges"]

    @property
    def member_uris(self) -> tuple[ConceptURI | str, ...]:
        roots = {_uri_text(uri) for uri in self.roots}
        return tuple(uri for uri in self.nodes if _uri_text(uri) not in roots)

    def to_dict(self) -> dict[str, object]:
        return {
            "namespace": self.namespace,
            "roots": [_uri_text(uri) for uri in self.roots],
            "nodes": [_uri_text(uri) for uri in self.nodes],
            "edges": [_uri_text(uri) for uri in self.edges],
            "why": {key: path.to_dict() for key, path in self.why.items()},
            "edge_why": {key: path.to_dict() for key, path in self.edge_why.items()},
            "graph_snapshot_hash": self.graph_snapshot_hash,
            "budgets_requested": dict(self.budgets_requested),
            "budgets_consumed": dict(self.budgets_consumed),
            "omitted": self.omitted,
            "truncated": self.truncated,
            "query_hash": self.query_hash,
        }


class _Snapshot(Protocol):
    def iter_edges(self, query: EdgeQuery) -> Iterable[EdgeEnvelope | Mapping[str, object]]: ...

    def snapshot_hash(self, namespace: str) -> str: ...


class _URIPathMap(Mapping[str, TraversalPath]):
    """Read-only explanation map accepting either URI text or ConceptURI keys."""

    __slots__ = ("_data",)

    def __init__(self, paths: Mapping[str, TraversalPath]) -> None:
        self._data = MappingProxyType(dict(paths))

    def __getitem__(self, key: str | ConceptURI) -> TraversalPath:
        return self._data[_uri_text(key)]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


@dataclass(frozen=True, slots=True)
class _QueuedPath:
    uri: ConceptURI
    path: TraversalPath
    ancestry: tuple[ConceptURI, ...]
    last_family: str | None = None


def traverse(snapshot: ConceptStore, request: TraversalRequest) -> TraversalResult:
    """Walk a read snapshot in stable BFS order under explicit typed budgets."""

    if not isinstance(request, TraversalRequest):
        raise TypeError("traverse requires a TraversalRequest")
    allowed_families = frozenset(request.families or EDGE_FAMILIES)
    allowed_relations = frozenset(request.relations)
    _validate_roots(request, snapshot)
    raw_edges = tuple(_iter_snapshot_edges(snapshot, request.namespace))
    edges = tuple(sorted(raw_edges, key=_edge_sort_key))
    _validate_edges(edges)

    graph_hash = _snapshot_hash(snapshot, request.namespace, edges)
    query_hash = content_hash(canonical_json(cast(Any, request.to_dict())))
    roots = cast(tuple[ConceptURI, ...], request.roots)
    node_order: list[ConceptURI | str] = list(roots)
    edge_order: list[ConceptURI | str] = []
    seen_nodes = {_uri_text(uri) for uri in roots}
    seen_edges: set[str] = set()
    why: dict[str, TraversalPath] = {}
    edge_why: dict[str, TraversalPath] = {}
    queue: deque[_QueuedPath] = deque()
    for root in roots:
        path = TraversalPath(node_uris=(root,), edge_uris=(), reason="root anchor")
        why[root.uri] = path
        queue.append(_QueuedPath(uri=root, path=path, ancestry=(root,)))

    expansions = 0
    steps = 0
    omitted = 0
    truncated = False
    while queue:
        current = queue.popleft()
        depth = len(current.path.edge_uris)
        if depth >= request.max_hops:
            continue
        for edge_value in edges:
            oriented = _orient_edge(edge_value, current.uri, cast(Direction, request.direction))
            if oriented is None:
                continue
            edge_id, source, target, family, relation, neighbor, direction = oriented
            if family not in allowed_families:
                continue
            if allowed_relations and relation not in allowed_relations:
                continue
            if relation not in _RELATIONS_BY_FAMILY.get(family, frozenset()):
                raise TraversalError(f"unknown relation {relation!r} for edge family {family!r}")
            if current.last_family == family and family in _NONTRANSITIVE_FAMILIES:
                continue
            if not _namespace_allowed(request, source.namespace, target.namespace):
                if source.namespace != target.namespace:
                    raise CrossNamespaceDenied(
                        f"read policy does not permit {source.namespace} -> {target.namespace}"
                    )
                continue
            if family == "derivation" and neighbor in current.ancestry:
                cycle_start = current.ancestry.index(neighbor)
                raise TraversalCycleError((*current.ancestry[cycle_start:], neighbor))
            if neighbor.uri in seen_nodes:
                continue
            if expansions >= request.max_expansions:
                truncated = True
                omitted += 1
                continue
            if len(node_order) - len(roots) >= request.max_results:
                truncated = True
                omitted += 1
                continue

            step = TraversalStep(
                node_uri=neighbor,
                edge_uri=edge_id,
                source_uri=source.uri,
                target_uri=target.uri,
                family=family,
                relation=relation,
                direction=direction,
            )
            path = TraversalPath(
                node_uris=(*current.path.node_uris, neighbor),
                edge_uris=(*current.path.edge_uris, edge_id),
                steps=(*current.path.steps, step),
                reason=f"matched allow-listed {family}/{relation} path",
            )
            expansions += 1
            steps += 1
            seen_nodes.add(neighbor.uri)
            node_order.append(neighbor)
            why[neighbor.uri] = path
            edge_id_text = _uri_text(edge_id)
            if edge_id_text not in seen_edges:
                seen_edges.add(edge_id_text)
                edge_order.append(edge_id)
                edge_why[edge_id_text] = path
            queue.append(
                _QueuedPath(
                    uri=neighbor,
                    path=path,
                    ancestry=(*current.ancestry, neighbor),
                    last_family=family,
                )
            )

    budgets_requested = {
        "max_hops": request.max_hops,
        "max_expansions": request.max_expansions,
        "max_results": request.max_results,
    }
    budgets_consumed = {
        "steps": steps,
        "nodes": len(node_order),
        "edges": len(edge_order),
        "expansions": expansions,
    }
    return TraversalResult(
        namespace=request.namespace,
        roots=roots,
        nodes=tuple(node_order),
        edges=tuple(edge_order),
        why=why,
        edge_why=edge_why,
        graph_snapshot_hash=graph_hash,
        budgets_requested=budgets_requested,
        budgets_consumed=budgets_consumed,
        omitted=omitted,
        truncated=truncated,
        request=request,
        query_hash=query_hash,
    )


def materialize_neighborhood(store: ConceptStore, result: TraversalResult) -> ConceptURI:
    """Persist a deterministic SemanticNeighborhood for a traversal result.

    Members are admitted in traversal order.  A member is either fully represented or omitted;
    there is no partial serialization of a member under ``max_serialized_bytes``.
    """

    if not isinstance(result, TraversalResult):
        raise TypeError("materialize_neighborhood requires a TraversalResult")
    if not result.roots:
        raise ValueError("a neighborhood requires at least one traversal root")
    request = result.request
    max_bytes = request.max_serialized_bytes if request is not None else None
    members: list[dict[str, object]] = []
    omitted = result.omitted
    for rank, uri in enumerate(result.member_uris, start=1):
        path = result.why[_uri_text(uri)]
        member = {
            "uri": _uri_text(uri),
            "rank": rank,
            "component_distances": {"graph": f"{len(path.edge_uris):.6f}"},
            "aggregate_distance": f"{len(path.edge_uris):.6f}",
            "why": [
                {
                    "uri": _uri_text(step.node_uri),
                    "family": step.family,
                    "relation": step.relation,
                }
                for step in path.steps
            ],
        }
        if max_bytes is not None:
            candidate = tuple((*members, member))
            if len(canonical_json(cast(Any, list(candidate)))) > max_bytes:
                omitted += 1
                continue
        members.append(member)

    payload = SemanticNeighborhood(
        neighborhood_id=result.query_hash,
        center_uri=result.roots[0],
        distance_metric="typed-hop/v1",
        threshold=str(request.max_hops if request is not None else 0),
        members=tuple(members),
        anchor_uris=tuple(result.roots),
        metric_versions={"graph": "v1"},
        weights={"graph": "1.00"},
        filters={
            "direction": (
                cast(Direction, request.direction).value
                if request is not None
                else Direction.OUTGOING.value
            ),
            "families": list(request.families) if request is not None else list(EDGE_FAMILIES),
            "relations": list(request.relations) if request is not None else [],
        },
        budget={
            "max_nodes": request.max_results if request is not None else len(members),
            "max_serialized_bytes": max_bytes,
        },
        omitted=omitted,
        truncated=bool(result.truncated or omitted > result.omitted),
        graph_snapshot_hash=result.graph_snapshot_hash,
        query_hash=result.query_hash,
    )
    preimage: dict[str, object] = {
        "namespace": result.namespace,
        "type": "SemanticNeighborhood",
        "schema_version": 1,
        "payload": payload.to_dict(),
        "representations": [],
        "provenance_refs": [result.graph_snapshot_hash],
    }
    identity = node_uri(result.namespace, "SemanticNeighborhood", cast(Any, preimage))
    node = NodeEnvelope(
        id=identity,
        type="SemanticNeighborhood",
        namespace=result.namespace,
        schema_version=1,
        payload=payload,
        representations=(),
        provenance_refs=(result.graph_snapshot_hash,),
        recorded_at="1970-01-01T00:00:00Z",
    )
    store.append_node(node)
    return cast(ConceptURI, node.id)


def _validate_roots(request: TraversalRequest, snapshot: ConceptStore) -> None:
    roots = cast(tuple[ConceptURI, ...], request.roots)
    for root in roots:
        if not _namespace_allowed(request, request.namespace, root.namespace):
            raise CrossNamespaceDenied(
                f"read policy does not permit {request.namespace} -> {root.namespace} root"
            )
        get_node = getattr(snapshot, "get_node", None)
        if callable(get_node) and get_node(root.uri) is None:
            raise TraversalError(f"root node is not present in snapshot: {root.uri}")


def _iter_snapshot_edges(
    snapshot: ConceptStore,
    namespace: str,
) -> Iterable[EdgeEnvelope | Mapping[str, object]]:
    try:
        return snapshot.iter_edges(EdgeQuery(namespace=namespace))
    except (AttributeError, TypeError):
        edges = getattr(snapshot, "edges", None)
        if callable(edges):
            return cast(Iterable[EdgeEnvelope | Mapping[str, object]], edges())
        if isinstance(edges, Iterable):
            return edges
        raise TraversalError("snapshot does not expose an edge iterator") from None


def _snapshot_hash(
    snapshot: ConceptStore,
    namespace: str,
    edges: Iterable[EdgeEnvelope | Mapping[str, object]],
) -> str:
    snapshot_hash = getattr(snapshot, "snapshot_hash", None)
    if callable(snapshot_hash):
        return str(snapshot_hash(namespace))
    preimage = {
        "namespace": namespace,
        "edges": [_edge_to_dict(edge) for edge in edges],
    }
    return content_hash(canonical_json(cast(Any, preimage)))


def _orient_edge(
    edge_value: EdgeEnvelope | Mapping[str, object],
    current: ConceptURI,
    direction: Direction,
) -> tuple[ConceptURI | str, ConceptURI, ConceptURI, str, str, ConceptURI, Direction] | None:
    source = _edge_endpoint(edge_value, "source_uri")
    target = _edge_endpoint(edge_value, "target_uri")
    family = _edge_field(edge_value, "family")
    relation = _edge_field(edge_value, "relation")
    edge_id = _edge_identifier(edge_value)
    if direction in (Direction.OUTGOING, Direction.BOTH) and source == current:
        return edge_id, source, target, family, relation, target, Direction.OUTGOING
    if direction in (Direction.INCOMING, Direction.BOTH) and target == current:
        return edge_id, source, target, family, relation, source, Direction.INCOMING
    return None


def _edge_endpoint(edge: EdgeEnvelope | Mapping[str, object], field_name: str) -> ConceptURI:
    return _ensure_uri(_edge_field(edge, field_name), field_name)


def _edge_field(edge: EdgeEnvelope | Mapping[str, object], field_name: str) -> str:
    value: object = (
        edge.get(field_name) if isinstance(edge, Mapping) else getattr(edge, field_name, None)
    )
    if isinstance(value, ConceptURI):
        return value.uri
    if not isinstance(value, str) or not value:
        raise TraversalError(f"edge {field_name} must be a non-empty string")
    return value


def _edge_identifier(edge: EdgeEnvelope | Mapping[str, object]) -> ConceptURI | str:
    value: object = edge.get("id") if isinstance(edge, Mapping) else getattr(edge, "id", None)
    if isinstance(value, ConceptURI):
        return value
    if isinstance(value, str) and value:
        return value
    raise TraversalError("edge id must be a non-empty string or ConceptURI")


def _optional_edge_field(edge: EdgeEnvelope | Mapping[str, object], field_name: str) -> str | None:
    value: object = edge.get(field_name) if isinstance(edge, Mapping) else getattr(edge, field_name, None)
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    raise TraversalError(f"edge {field_name} must be a non-empty string when present")


def _edge_sort_key(edge: EdgeEnvelope | Mapping[str, object]) -> tuple[str, str, str, str, str]:
    return (
        _edge_field(edge, "id"),
        _edge_field(edge, "family"),
        _edge_field(edge, "relation"),
        _edge_field(edge, "source_uri"),
        _edge_field(edge, "target_uri"),
    )


def _edge_to_dict(edge: EdgeEnvelope | Mapping[str, object]) -> dict[str, object]:
    if isinstance(edge, Mapping):
        return {str(key): value for key, value in edge.items()}
    return edge.to_dict()


def _validate_edges(edges: Iterable[EdgeEnvelope | Mapping[str, object]]) -> None:
    for edge in edges:
        family = _edge_field(edge, "family")
        relation = _edge_field(edge, "relation")
        if family not in EDGE_FAMILIES:
            raise TraversalError(f"unknown edge family in snapshot: {family!r}")
        if relation not in _RELATIONS_BY_FAMILY[family]:
            raise TraversalError(f"unknown relation {relation!r} for edge family {family!r}")
        source = _edge_endpoint(edge, "source_uri")
        target = _edge_endpoint(edge, "target_uri")
        edge_namespace = _optional_edge_field(edge, "namespace")
        if edge_namespace is not None and edge_namespace not in {source.namespace, target.namespace}:
            raise TraversalError("edge namespace does not match either endpoint namespace")


def _namespace_allowed(request: TraversalRequest, source: str, target: str) -> bool:
    if source == target:
        return True
    policy = request.effective_read_policy
    if policy is None:
        return False
    if isinstance(policy, NamespaceReadPolicy):
        return policy.namespace == source and policy.allows(target)
    if isinstance(policy, str):
        return policy in {"*", "allow_all"}
    if isinstance(policy, Collection) and not isinstance(policy, Mapping):
        return target in policy or "*" in policy
    if not isinstance(policy, Mapping):
        return False
    source_entry = policy.get(source)
    target_entry = policy.get(target)
    if source_entry is not None and target_entry is not None:
        return _policy_entry_allows(source_entry, target) and _policy_entry_allows(target_entry, source)
    if source_entry is not None:
        return _policy_entry_allows(source_entry, target)
    if target_entry is not None:
        return target_entry is True or _policy_entry_allows(target_entry, source)
    return _policy_entry_allows(policy, target)


def _policy_entry_allows(entry: object, peer: str) -> bool:
    if entry is True:
        return True
    if isinstance(entry, NamespaceReadPolicy):
        return entry.allows(peer)
    if isinstance(entry, str):
        return entry == peer or entry == "*"
    if isinstance(entry, Mapping):
        for key in ("read", "readable_namespaces", "allow", "allow_namespaces", "share_with", "accept_from"):
            if key in entry and _policy_entry_allows(entry[key], peer):
                return True
        return False
    if isinstance(entry, Collection):
        return peer in entry or "*" in entry
    return False


def _normalize_allow_list(
    values: Iterable[str] | None,
    allowed: Collection[str],
    label: str,
) -> tuple[str, ...]:
    normalized = tuple(sorted(set(values or ())))
    unknown = [value for value in normalized if value not in allowed]
    if unknown:
        raise ValueError(f"unknown {label}: {unknown[0]}")
    return normalized


def _validate_budget(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")


def _validate_namespace(value: str, label: str = "namespace") -> None:
    if not isinstance(value, str) or _NAMESPACE_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must match ^[a-z0-9][a-z0-9_-]{{0,62}}$")


def _ensure_uri(value: ConceptURI | str, field_name: str) -> ConceptURI:
    if isinstance(value, ConceptURI):
        return value
    if isinstance(value, str):
        try:
            return validate_concept_uri(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid Concept URI") from exc
    raise TypeError(f"{field_name} must be a ConceptURI or URI string")


def _uri_text(value: ConceptURI | str) -> str:
    return value.uri if isinstance(value, ConceptURI) else value


def _unique_sorted(values: Iterable[ConceptURI]) -> tuple[ConceptURI, ...]:
    unique = {value.uri: value for value in values}
    return tuple(unique[key] for key in sorted(unique))


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_thaw(item) for item in value]
    if isinstance(value, ConceptURI):
        return value.uri
    if isinstance(value, NamespaceReadPolicy):
        return {value.namespace: sorted(value.readable_namespaces)}
    return value
