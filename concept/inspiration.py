"""Local graph inspiration mathematics for Concept OS.

This module is deliberately a pure, read-only proposer/scorer boundary.  It does not ingest
external material, call a provider, write to a store, or alter the lifecycle of a candidate.
"""

from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from concept.ids import ConceptURI, edge_uri, node_uri
from concept.model import (
    EDGE_FAMILIES,
    Analogy,
    AnalogyEdgePayload,
    Concept,
    EdgeEnvelope,
    Hypothesis,
    InspirationHeuristic,
    NodeEnvelope,
    RecombinationEdgePayload,
)
from concept.store import EdgeQuery, NodeQuery

__all__ = [
    "DistanceResult",
    "InspirationHeuristic",
    "NoveltyResult",
    "Proposal",
    "ProposalResult",
    "SerendipityResult",
    "distance",
    "propose_analogies",
    "propose_recombinations",
    "score_novelty",
    "score_serendipity",
]

_COMPONENTS = ("graph", "vector", "structural")
_NOVELTY_COMPONENTS = (
    "distance",
    "structural_surprise",
    "domain_span",
    "recombination_rarity",
    "duplication_penalty",
)
_DEFAULT_DISTANCE_WEIGHTS = {"graph": 1.0, "vector": 1.0, "structural": 1.0}
_DEFAULT_NOVELTY_WEIGHTS = {
    "distance": 1.0,
    "structural_surprise": 1.0,
    "domain_span": 1.0,
    "recombination_rarity": 1.0,
}
_DEFAULT_PROVENANCE = "0" * 64
_DEFAULT_RECORDED_AT = "1970-01-01T00:00:00Z"


class _Snapshot(Protocol):
    def get_node(self, uri: str) -> NodeEnvelope | None: ...

    def iter_nodes(self, query: NodeQuery) -> Iterable[NodeEnvelope]: ...

    def iter_edges(self, query: EdgeQuery) -> Iterable[EdgeEnvelope]: ...

    def snapshot_hash(self, namespace: str) -> str: ...


@dataclass(frozen=True, slots=True)
class DistanceResult:
    aggregate_distance: float | None
    graph_distance: float | None
    vector_distance: float | None
    structural_distance: float | None
    missing_components: tuple[str, ...] = ()
    graph_unreachable: bool = False
    unscorable: bool = False
    weights_used: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "missing_components", tuple(self.missing_components))
        object.__setattr__(self, "weights_used", dict(self.weights_used))


@dataclass(frozen=True, slots=True)
class Proposal:
    """A reified proposal containing its node and membership edges."""

    node: NodeEnvelope
    edges: tuple[EdgeEnvelope, ...] = ()
    trace: Mapping[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> ConceptURI:
        return cast(ConceptURI, self.node.id)

    @property
    def type(self) -> str:
        return self.node.type

    @property
    def payload(self) -> Any:
        return self.node.payload

    @property
    def envelope(self) -> NodeEnvelope:
        return self.node

    @property
    def node_envelope(self) -> NodeEnvelope:
        return self.node

    def __getitem__(self, key: str) -> Any:
        if key == "node":
            return self.node
        if key == "edges":
            return self.edges
        if key == "trace":
            return self.trace
        return self.node.to_dict()[key]


@dataclass(frozen=True, slots=True)
class ProposalResult:
    proposals: tuple[Proposal, ...] = ()
    rejected_traces: tuple[Mapping[str, Any], ...] = ()
    budget_consumed: int = 0
    seed: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposals", tuple(self.proposals))
        object.__setattr__(self, "rejected_traces", tuple(dict(trace) for trace in self.rejected_traces))


@dataclass(frozen=True, slots=True)
class NoveltyResult:
    novelty_score: float
    components: dict[str, float]
    missing_components: tuple[str, ...]
    weights: dict[str, float]
    heuristic_version: str
    snapshot_hash: str
    nearest_comparators: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "novelty_score", _round_score(self.novelty_score))
        object.__setattr__(self, "components", dict(self.components))
        object.__setattr__(self, "missing_components", tuple(self.missing_components))
        object.__setattr__(self, "weights", dict(self.weights))
        object.__setattr__(self, "nearest_comparators", tuple(self.nearest_comparators))


@dataclass(frozen=True, slots=True)
class SerendipityResult:
    serendipity_score: float | None
    relevance: float
    novelty: float
    coherence: float
    provenance_completeness: float
    unscorable: bool

    def __post_init__(self) -> None:
        for name in ("relevance", "novelty", "coherence", "provenance_completeness"):
            object.__setattr__(self, name, _round_score(getattr(self, name)))
        if self.serendipity_score is not None:
            object.__setattr__(self, "serendipity_score", _round_score(self.serendipity_score))


def distance(
    left: Any,
    right: Any,
    snapshot: _Snapshot,
    metric_set: Mapping[str, Any] | None = None,
) -> DistanceResult:
    """Score graph, vector, and typed-neighbor distances with explicit availability."""

    metrics = dict(metric_set or {})
    left_node = _resolve_node(left, snapshot)
    right_node = _resolve_node(right, snapshot)
    left_uri = _node_uri(left, left_node)
    right_uri = _node_uri(right, right_node)
    graph_value: float | None = None
    graph_unreachable = False
    if left_uri is not None and right_uri is not None:
        graph_value, graph_unreachable = _graph_distance(
            left_uri,
            right_uri,
            snapshot,
            metrics,
        )
    vector_value = _vector_distance(left_node or left, right_node or right)
    structural_value: float | None = None
    if left_uri is not None and right_uri is not None:
        structural_value = _structural_distance(left_uri, right_uri, snapshot, metrics)

    values = {
        "graph": graph_value,
        "vector": vector_value,
        "structural": structural_value,
    }
    missing = tuple(key for key in _COMPONENTS if values[key] is None)
    weights = _distance_weights(metrics)
    available_weights = {key: weight for key, weight in weights.items() if values[key] is not None and weight > 0}
    total_weight = sum(available_weights.values())
    if total_weight <= 0:
        return DistanceResult(
            aggregate_distance=None,
            graph_distance=_rounded_or_none(graph_value),
            vector_distance=_rounded_or_none(vector_value),
            structural_distance=_rounded_or_none(structural_value),
            missing_components=missing,
            graph_unreachable=graph_unreachable,
            unscorable=True,
            weights_used={},
        )
    normalized = {key: _round_score(weight / total_weight) for key, weight in available_weights.items()}
    aggregate = sum(cast(float, values[key]) * weight for key, weight in available_weights.items()) / total_weight
    return DistanceResult(
        aggregate_distance=_round_score(aggregate),
        graph_distance=_rounded_or_none(graph_value),
        vector_distance=_rounded_or_none(vector_value),
        structural_distance=_rounded_or_none(structural_value),
        missing_components=missing,
        graph_unreachable=graph_unreachable,
        unscorable=False,
        weights_used=normalized,
    )


def propose_analogies(
    snapshot: _Snapshot,
    request: Any,
    budget: int = 10,
    seed: int = 0,
) -> ProposalResult:
    """Create explicit, reified, non-transitive analogy proposals."""

    _validate_budget(budget)
    namespace = _request_namespace(request, snapshot)
    source_uris, source_explicit = _request_uris(request, "source_uris")
    target_uris, target_explicit = _request_uris(request, "target_uris")
    if not source_uris:
        source_uris = _request_uris(request, "source_nodes")[0]
        source_explicit = False
    if not target_uris:
        target_uris = _request_uris(request, "target_nodes")[0]
        target_explicit = False
    concepts = _concept_nodes(snapshot, namespace)
    rng = random.Random(seed)
    if not source_uris and concepts:
        source_uris = (_node_id_text(rng.choice(concepts)),)
    if not target_uris and concepts:
        target_choices = [_node_id_text(node) for node in concepts if _node_id_text(node) not in source_uris]
        if target_choices:
            target_uris = (rng.choice(target_choices),)
    if not source_explicit and not target_explicit:
        source_uris, target_uris = _seeded_pair_sets(concepts, rng)

    rejected: list[Mapping[str, Any]] = []
    if not source_uris or not target_uris:
        rejected.append({"reason": "insufficient_source_or_target", "seed": seed})
        return ProposalResult(rejected_traces=tuple(rejected), budget_consumed=1 if budget else 0, seed=seed)
    if budget == 0:
        return ProposalResult(rejected_traces=({"reason": "budget_exhausted"},), seed=seed)

    sources = tuple(_node_for_uri(snapshot, uri) for uri in source_uris)
    targets = tuple(_node_for_uri(snapshot, uri) for uri in target_uris)
    if any(node is None for node in sources + targets):
        rejected.append({"reason": "unknown_endpoint", "source_uris": source_uris, "target_uris": target_uris})
        return ProposalResult(rejected_traces=tuple(rejected), budget_consumed=1, seed=seed)
    source_nodes = tuple(node for node in sources if node is not None)
    target_nodes = tuple(node for node in targets if node is not None)
    if any(node.type != "Concept" for node in source_nodes + target_nodes):
        rejected.append({"reason": "nontransitive_analogy_input", "detail": "analogy nodes cannot be chained as proof"})
        return ProposalResult(rejected_traces=tuple(rejected), budget_consumed=1, seed=seed)
    if len(source_nodes) != len(target_nodes):
        rejected.append(
            {
                "reason": "source_target_arity_mismatch",
                "source_count": len(source_nodes),
                "target_count": len(target_nodes),
            }
        )
        return ProposalResult(rejected_traces=tuple(rejected), budget_consumed=1, seed=seed)

    correspondences = tuple(
        {
            "source_uri": _node_id_text(source),
            "target_uri": _node_id_text(target),
            "source_role": f"source_{index}",
            "target_role": f"target_{index}",
        }
        for index, (source, target) in enumerate(zip(source_nodes, target_nodes, strict=False))
    )
    if not correspondences:
        rejected.append({"reason": "empty_correspondence", "seed": seed})
        return ProposalResult(rejected_traces=tuple(rejected), budget_consumed=1, seed=seed)
    preserved = _preserved_relations(source_nodes, target_nodes, snapshot)
    known_breaks = tuple(_request_value(request, "known_breaks", ())) or ("not_yet_tested",)
    graph_hash = _snapshot_hash(snapshot, namespace)
    payload = Analogy(
        source_roles=tuple(f"source_{index}" for index in range(len(correspondences))),
        target_roles=tuple(f"target_{index}" for index in range(len(correspondences))),
        correspondences=correspondences,
        preserved_relations=preserved,
        known_breaks=known_breaks,
        metric_snapshot=_analogy_metric_snapshot(source_nodes, target_nodes, snapshot),
        heuristic_uri=_heuristic_uri(namespace, "analogy/v1"),
    )
    node = _make_node(snapshot, namespace, "Analogy", payload, graph_hash)
    membership_edges = tuple(
        _make_analogy_edge(node, target, "has_source" if index < len(sources) else "has_target", index)
        for index, target in enumerate(source_nodes + target_nodes)
    )
    proposal = Proposal(
        node=node,
        edges=membership_edges,
        trace={
            "kind": "analogy",
            "seed": seed,
            "source_uris": source_uris,
            "target_uris": target_uris,
            "preserved_relations": preserved,
            "known_breaks": known_breaks,
            "non_transitive": True,
        },
    )
    return ProposalResult(proposals=(proposal,), budget_consumed=1, seed=seed)


def propose_recombinations(
    snapshot: _Snapshot,
    request: Any,
    budget: int = 10,
    seed: int = 0,
) -> ProposalResult:
    """Create a bounded two-or-more-source recombination without mutating the graph."""

    _validate_budget(budget)
    namespace = _request_namespace(request, snapshot)
    requested, _explicit = _request_uris(request, "source_uris")
    if not requested:
        requested, _explicit = _request_uris(request, "source_nodes")
    concepts = _concept_nodes(snapshot, namespace)
    if not requested:
        requested = tuple(_node_id_text(node) for node in concepts)
    if budget == 0:
        return ProposalResult(rejected_traces=({"reason": "budget_exhausted"},), seed=seed)
    if len(set(requested)) < 2:
        return ProposalResult(
            rejected_traces=({"reason": "requires_two_distinct_sources", "source_uris": requested},),
            budget_consumed=1,
            seed=seed,
        )
    source_nodes = tuple(_node_for_uri(snapshot, uri) for uri in requested)
    if any(node is None for node in source_nodes):
        return ProposalResult(
            rejected_traces=({"reason": "unknown_source", "source_uris": requested},),
            budget_consumed=1,
            seed=seed,
        )
    source_nodes_present = tuple(node for node in source_nodes if node is not None)
    if any(node.type not in {"Concept", "Transformation"} for node in source_nodes_present):
        return ProposalResult(
            rejected_traces=({"reason": "unsupported_source_type", "source_uris": requested},),
            budget_consumed=1,
            seed=seed,
        )
    constraints = _request_mapping(request, "constraints")
    constraint_reason = _hard_constraint_failure(source_nodes_present, snapshot, constraints)
    if constraint_reason is not None:
        return ProposalResult(
            rejected_traces=({"reason": constraint_reason, "source_uris": requested},),
            budget_consumed=1,
            seed=seed,
        )
    ordered_sources = _order_by_intermediate_distance(source_nodes_present, snapshot, seed)
    graph_hash = _snapshot_hash(snapshot, namespace)
    output_kind = str(_request_value(request, "output_kind", "Hypothesis"))
    if output_kind == "Concept":
        tags = tuple(sorted({tag for node in ordered_sources for tag in getattr(node.payload, "domain_tags", ())}))
        payload: Concept | Hypothesis = Concept(
            label="Recombination of " + " + ".join(_node_label(node) for node in ordered_sources),
            description="Exploratory recombination generated from ordered local graph contributions.",
            domain_tags=tags,
        )
    else:
        proposition = " and ".join(_node_label(node) for node in ordered_sources) + " may combine."
        payload = Hypothesis(
            proposition=proposition,
            scope=str(_request_value(request, "scope", "local concept graph")),
            assumptions=("source contributions remain ordered",),
            lineage=tuple(_node_id_text(node) for node in ordered_sources),
            expected_observations=("the combined pattern is inspectable",),
            falsifiers=("the contributions are incompatible under evaluation",),
            lifecycle="candidate",
            score_snapshot={
                "relevance": "0.0",
                "novelty": "0.0",
                "coherence": "0.0",
                "diversity_contribution": "0.0",
                "cost": "0.0",
                "provenance_completeness": "0.0",
            },
        )
    output = _make_node(snapshot, namespace, output_kind if output_kind in {"Concept", "Hypothesis"} else "Hypothesis", payload, graph_hash)
    recombination_edges = tuple(
        _make_recombination_edge(output, source, ordered_sources, index)
        for index, source in enumerate(ordered_sources)
    )
    proposal = Proposal(
        node=output,
        edges=recombination_edges,
        trace={
            "kind": "recombination",
            "heuristic_version": "recombination/v1",
            "source_uris": tuple(_node_id_text(node) for node in ordered_sources),
            "ordered_contribution_roles": tuple(f"contribution_{index}" for index in range(len(ordered_sources))),
            "seed": seed,
        },
    )
    return ProposalResult(proposals=(proposal,), budget_consumed=1, seed=seed)


def score_novelty(
    candidate: Any,
    snapshot: _Snapshot,
    heuristic: InspirationHeuristic | Mapping[str, Any] | None = None,
) -> NoveltyResult:
    """Score exploratory novelty; this function has no lifecycle or persistence authority."""

    config = _heuristic_config(heuristic)
    namespace = _candidate_namespace(candidate, snapshot)
    candidate_node = _resolve_node(candidate, snapshot)
    comparators = _novelty_comparators(snapshot, namespace) if namespace else ()
    candidate_uri = _node_uri(candidate, candidate_node)
    comparators = tuple(node for node in comparators if _node_id_text(node) != candidate_uri)
    nearest: list[tuple[float, str]] = []
    values: dict[str, float] = {}
    explicit_distance = _numeric_value(candidate, "distance")
    if explicit_distance is not None:
        values["distance"] = _clamp(explicit_distance)
    elif candidate_node is not None and comparators:
        for comparator in comparators:
            result = distance(candidate_node, comparator, snapshot)
            if result.aggregate_distance is not None:
                nearest.append((result.aggregate_distance, _node_id_text(comparator)))
        if nearest:
            nearest.sort(key=lambda item: (item[0], item[1]))
            values["distance"] = _clamp(nearest[0][0])
    for name in _NOVELTY_COMPONENTS[1:]:
        direct = _numeric_value(candidate, name)
        if direct is not None:
            values[name] = _clamp(direct)
    if "structural_surprise" not in values:
        derived = _derived_structural_surprise(candidate, snapshot, namespace)
        if derived is not None:
            values["structural_surprise"] = derived
    if "domain_span" not in values:
        derived = _derived_domain_span(candidate_node)
        if derived is not None:
            values["domain_span"] = derived
    if "recombination_rarity" not in values:
        derived = _derived_recombination_rarity(candidate, snapshot, namespace)
        if derived is not None:
            values["recombination_rarity"] = derived
    if "duplication_penalty" not in values:
        derived = _derived_duplication_penalty(candidate if candidate_node is None else candidate_node, comparators)
        if derived is not None:
            values["duplication_penalty"] = derived

    missing = tuple(name for name in _NOVELTY_COMPONENTS if name not in values)
    raw_weights = _novelty_weights(config)
    available = {
        name: raw_weights.get(name, 0.0)
        for name in _NOVELTY_COMPONENTS[:-1]
        if name in values and raw_weights.get(name, 0.0) > 0
    }
    weight_total = sum(available.values())
    if weight_total:
        weighted_mean = sum(values[name] * weight for name, weight in available.items()) / weight_total
        result_weights = {name: _round_score(weight / weight_total) for name, weight in available.items()}
    else:
        weighted_mean = 0.0
        result_weights = {}
    duplication_weight = _numeric_config(config, "duplication_weight", 0.0)
    novelty_score = _clamp(weighted_mean - duplication_weight * values.get("duplication_penalty", 0.0))
    output_weights = dict(result_weights)
    output_weights["duplication_weight"] = _round_score(duplication_weight)
    return NoveltyResult(
        novelty_score=_round_score(novelty_score),
        components={name: _round_score(value) for name, value in values.items()},
        missing_components=missing,
        weights=output_weights,
        heuristic_version=str(_request_value(config, "heuristic_version", "novelty/v1")),
        snapshot_hash=_snapshot_hash(snapshot, namespace) if namespace else "",
        nearest_comparators=tuple(uri for _, uri in nearest[:5]),
    )


def score_serendipity(
    candidate: Any,
    query: Any,
    heuristic: InspirationHeuristic | Mapping[str, Any] | None = None,
) -> SerendipityResult:
    """Project relevance and novelty through coherence and provenance completeness."""

    config = _heuristic_config(heuristic)
    relevance = _first_numeric(candidate, query, config, key="relevance")
    novelty = _first_numeric(candidate, query, config, key="novelty")
    coherence = _first_numeric(candidate, query, config, key="coherence")
    provenance = _first_numeric(candidate, query, config, key="provenance_completeness")
    relevance_value = _clamp(relevance) if relevance is not None else 0.0
    novelty_value = _clamp(novelty) if novelty is not None else 0.0
    coherence_value = _clamp(coherence) if coherence is not None else 0.0
    provenance_value = _clamp(provenance) if provenance is not None else 0.0
    unscorable = relevance is None or novelty is None
    score = None if unscorable else _round_score(math.sqrt(relevance_value * novelty_value) * coherence_value * provenance_value)
    return SerendipityResult(
        serendipity_score=score,
        relevance=relevance_value,
        novelty=novelty_value,
        coherence=coherence_value,
        provenance_completeness=provenance_value,
        unscorable=unscorable,
    )


def _graph_distance(
    left_uri: str,
    right_uri: str,
    snapshot: _Snapshot,
    metrics: Mapping[str, Any],
) -> tuple[float, bool]:
    if left_uri == right_uri:
        return 0.0, False
    allowed_families = _string_set(metrics.get("graph_families"), EDGE_FAMILIES)
    allowed_relations = _string_set(metrics.get("graph_relations"), ())
    adjacency: dict[str, set[str]] = {}
    for item in snapshot.iter_edges(EdgeQuery(namespace=_uri_namespace(left_uri))):
        family = str(_edge_value(item, "family", ""))
        relation = str(_edge_value(item, "relation", ""))
        if family not in allowed_families or (allowed_relations and relation not in allowed_relations):
            continue
        source = _uri_text(_edge_value(item, "source_uri", ""))
        target = _uri_text(_edge_value(item, "target_uri", ""))
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set()).add(source)
    queue: deque[tuple[str, int]] = deque([(left_uri, 0)])
    seen = {left_uri}
    while queue:
        current, hops = queue.popleft()
        for neighbor in sorted(adjacency.get(current, ())):
            if neighbor == right_uri:
                tau = _positive_float(metrics.get("tau", 3.0), 3.0)
                return _clamp(1.0 - math.exp(-float(hops + 1) / tau)), False
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, hops + 1))
    return 1.0, True


def _vector_distance(left: Any, right: Any) -> float | None:
    left_vector = _extract_vector(left)
    right_vector = _extract_vector(right)
    if left_vector is None or right_vector is None or len(left_vector) != len(right_vector) or not left_vector:
        return None
    left_norm = math.sqrt(sum(value * value for value in left_vector))
    right_norm = math.sqrt(sum(value * value for value in right_vector))
    if left_norm == 0.0 or right_norm == 0.0:
        return None
    cosine = sum(a * b for a, b in zip(left_vector, right_vector, strict=True)) / (left_norm * right_norm)
    return _clamp((1.0 - cosine) / 2.0)


def _structural_distance(left_uri: str, right_uri: str, snapshot: _Snapshot, metrics: Mapping[str, Any]) -> float | None:
    left_signature = _neighbor_signature(left_uri, snapshot)
    right_signature = _neighbor_signature(right_uri, snapshot)
    if not left_signature and not right_signature:
        return None
    weights = _structural_signature_weights(metrics)
    keys = set(left_signature) | set(right_signature)
    intersection = sum(min(left_signature.get(key, 0.0), right_signature.get(key, 0.0)) * weights.get(key, 1.0) for key in keys)
    union = sum(max(left_signature.get(key, 0.0), right_signature.get(key, 0.0)) * weights.get(key, 1.0) for key in keys)
    if union == 0.0:
        return None
    return _clamp(1.0 - intersection / union)


def _neighbor_signature(uri: str, snapshot: _Snapshot) -> dict[tuple[str, str], float]:
    signature: dict[tuple[str, str], float] = {}
    for item in snapshot.iter_edges(EdgeQuery(namespace=_uri_namespace(uri))):
        source = _uri_text(_edge_value(item, "source_uri", ""))
        target = _uri_text(_edge_value(item, "target_uri", ""))
        if uri not in {source, target}:
            continue
        key = (str(_edge_value(item, "family", "")), str(_edge_value(item, "relation", "")))
        signature[key] = signature.get(key, 0.0) + 1.0
    return signature


def _distance_weights(metrics: Mapping[str, Any]) -> dict[str, float]:
    if "weights" in metrics and isinstance(metrics["weights"], Mapping):
        raw = metrics["weights"]
        return {
            name: _positive_float(raw.get(name, raw.get(f"{name}_distance", 0.0)), 0.0)
            for name in _COMPONENTS
        }
    if any(name in metrics or f"{name}_distance" in metrics for name in _COMPONENTS):
        return {
            name: _positive_float(metrics.get(name, metrics.get(f"{name}_distance", 0.0)), 0.0)
            for name in _COMPONENTS
        }
    return dict(_DEFAULT_DISTANCE_WEIGHTS)


def _structural_signature_weights(metrics: Mapping[str, Any]) -> dict[tuple[str, str], float]:
    raw = metrics.get("structural_weights", {})
    if not isinstance(raw, Mapping):
        return {}
    weights: dict[tuple[str, str], float] = {}
    for key, value in raw.items():
        if isinstance(key, tuple) and len(key) == 2:
            weights[(str(key[0]), str(key[1]))] = _positive_float(value, 1.0)
        elif isinstance(key, str) and ":" in key:
            family, relation = key.split(":", 1)
            weights[(family, relation)] = _positive_float(value, 1.0)
    return weights


def _make_node(snapshot: _Snapshot, namespace: str, node_type: str, payload: Any, provenance: str) -> NodeEnvelope:
    provenance_ref = provenance if len(provenance) == 64 else _DEFAULT_PROVENANCE
    preimage: dict[str, Any] = {
        "namespace": namespace,
        "type": node_type,
        "schema_version": 1,
        "payload": payload.to_dict(),
        "representations": [],
        "provenance_refs": [provenance_ref],
    }
    return NodeEnvelope(
        id=node_uri(namespace, node_type, cast(Any, preimage)),
        type=node_type,
        namespace=namespace,
        schema_version=1,
        payload=payload,
        representations=(),
        provenance_refs=(provenance_ref,),
        recorded_at=_DEFAULT_RECORDED_AT,
    )


def _make_analogy_edge(analogy: NodeEnvelope, target: NodeEnvelope, relation: str, index: int) -> EdgeEnvelope:
    payload = AnalogyEdgePayload(role_name=relation, correspondence_index=index)
    return _make_edge(analogy, target, "analogy", relation, payload)


def _make_recombination_edge(output: NodeEnvelope, source: NodeEnvelope, sources: Sequence[NodeEnvelope], index: int) -> EdgeEnvelope:
    payload = RecombinationEdgePayload(
        contribution_role=f"contribution_{index}",
        contribution_order=index,
        heuristic_trace_uri=_heuristic_uri(source.namespace, "recombination/v1"),
        source_uris=tuple(item.id for item in sources),
    )
    return _make_edge(source, output, "recombination", "contributes_to", payload)


def _make_edge(source: NodeEnvelope, target: NodeEnvelope, family: str, relation: str, payload: Any) -> EdgeEnvelope:
    provenance_ref = source.provenance_refs[0] if source.provenance_refs else _DEFAULT_PROVENANCE
    preimage: dict[str, Any] = {
        "namespace": source.namespace,
        "family": family,
        "relation": relation,
        "source_uri": _node_id_text(source),
        "target_uri": _node_id_text(target),
        "schema_version": 1,
        "payload": payload.to_dict(),
        "provenance_refs": [provenance_ref],
    }
    return EdgeEnvelope(
        id=edge_uri(source.namespace, cast(Any, preimage)),
        namespace=source.namespace,
        family=family,
        relation=relation,
        source_uri=source.id,
        target_uri=target.id,
        schema_version=1,
        payload=payload,
        provenance_refs=(provenance_ref,),
        recorded_at=_DEFAULT_RECORDED_AT,
    )


def _preserved_relations(sources: Sequence[NodeEnvelope], targets: Sequence[NodeEnvelope], snapshot: _Snapshot) -> tuple[str, ...]:
    values: list[str] = []
    for source, target in zip(sources, targets, strict=False):
        source_signatures = set(_neighbor_signature(_node_id_text(source), snapshot))
        target_signatures = set(_neighbor_signature(_node_id_text(target), snapshot))
        for family, relation in sorted(source_signatures & target_signatures):
            values.append(f"{family}:{relation}")
    return tuple(values)


def _analogy_metric_snapshot(
    sources: Sequence[NodeEnvelope],
    targets: Sequence[NodeEnvelope],
    snapshot: _Snapshot,
) -> dict[str, str]:
    values: dict[str, list[float]] = {"aggregate_distance": [], "graph_distance": [], "vector_distance": [], "structural_distance": []}
    for source, target in zip(sources, targets, strict=False):
        result = distance(source, target, snapshot)
        for name in values:
            value = getattr(result, name)
            if value is not None:
                values[name].append(value)
    return {
        name: _decimal_text(sum(measures) / len(measures))
        for name, measures in values.items()
        if measures
    }


def _heuristic_uri(namespace: str, version: str) -> str:
    preimage: dict[str, Any] = {
        "namespace": namespace,
        "type": "InspirationHeuristic",
        "schema_version": 1,
        "payload": {"name": version, "version": version},
        "representations": [],
        "provenance_refs": [_DEFAULT_PROVENANCE],
    }
    return node_uri(namespace, "InspirationHeuristic", cast(Any, preimage))


def _hard_constraint_failure(nodes: Sequence[NodeEnvelope], snapshot: _Snapshot, constraints: Mapping[str, Any]) -> str | None:
    if not constraints:
        return None
    uris = tuple(_node_id_text(node) for node in nodes)
    pairs = constraints.get("incompatible_pairs", ())
    for pair in pairs if isinstance(pairs, Sequence) else ():
        if isinstance(pair, Sequence) and len(pair) >= 2 and all(_uri_text(item) in uris for item in pair[:2]):
            return "incompatible_hard_constraint"
    required_tags = constraints.get("required_domain_tags", ())
    if required_tags:
        tags = {tag for node in nodes for tag in getattr(node.payload, "domain_tags", ())}
        if not set(required_tags).issubset(tags):
            return "missing_required_domain_tag"
    max_distance = constraints.get("max_distance")
    if isinstance(max_distance, int | float) and len(nodes) >= 2:
        for left_index, left in enumerate(nodes[:-1]):
            for right in nodes[left_index + 1 :]:
                result = distance(left, right, snapshot)
                if result.aggregate_distance is not None and result.aggregate_distance > max_distance:
                    return "maximum_distance_exceeded"
    return None


def _order_by_intermediate_distance(nodes: Sequence[NodeEnvelope], snapshot: _Snapshot, seed: int) -> tuple[NodeEnvelope, ...]:
    shuffled = list(nodes)
    random.Random(seed).shuffle(shuffled)
    if len(shuffled) <= 2:
        return tuple(shuffled)
    band_center = 0.5
    scored: list[tuple[float, str, NodeEnvelope]] = []
    first = shuffled[0]
    for node in shuffled[1:]:
        result = distance(first, node, snapshot)
        value = result.aggregate_distance if result.aggregate_distance is not None else 1.0
        scored.append((abs(value - band_center), _node_id_text(node), node))
    scored.sort(key=lambda item: (item[0], item[1]))
    return (first, *(item[2] for item in scored))


def _seeded_pair_sets(nodes: Sequence[NodeEnvelope], rng: random.Random) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if len(nodes) < 2:
        return (), ()
    order = list(nodes)
    rng.shuffle(order)
    midpoint = max(1, len(order) // 2)
    sources = tuple(_node_id_text(node) for node in order[:midpoint])
    targets = tuple(_node_id_text(node) for node in order[midpoint:] or order[-1:])
    return sources, targets


def _concept_nodes(snapshot: _Snapshot, namespace: str) -> tuple[NodeEnvelope, ...]:
    return tuple(node for node in snapshot.iter_nodes(NodeQuery(namespace=namespace)) if node.type == "Concept")


def _novelty_comparators(snapshot: _Snapshot, namespace: str) -> tuple[NodeEnvelope, ...]:
    return tuple(
        node
        for node in snapshot.iter_nodes(NodeQuery(namespace=namespace))
        if node.type in {"Concept", "Hypothesis"}
    )


def _resolve_node(value: Any, snapshot: _Snapshot) -> NodeEnvelope | None:
    if isinstance(value, NodeEnvelope):
        return value
    uri = _node_uri(value, None)
    if uri is not None:
        return snapshot.get_node(uri)
    return None


def _node_for_uri(snapshot: _Snapshot, uri: str) -> NodeEnvelope | None:
    return snapshot.get_node(uri)


def _node_uri(value: Any, node: NodeEnvelope | None) -> str | None:
    if node is not None:
        return _node_id_text(node)
    if isinstance(value, ConceptURI):
        return value.uri
    if isinstance(value, str) and value.startswith("concept://"):
        return value
    raw = _request_value(value, "id", None)
    if raw is None:
        raw = _request_value(value, "uri", None)
    if isinstance(raw, ConceptURI):
        return raw.uri
    return raw if isinstance(raw, str) and raw.startswith("concept://") else None


def _request_namespace(request: Any, snapshot: _Snapshot) -> str:
    namespace = _request_value(request, "namespace", None)
    if isinstance(namespace, str) and namespace:
        return namespace
    anchors, _ = _request_uris(request, "anchor_uris")
    if anchors:
        return _uri_namespace(anchors[0])
    nodes = tuple(snapshot.iter_nodes(NodeQuery(namespace="demo", limit=1)))
    return nodes[0].namespace if nodes else "demo"


def _candidate_namespace(candidate: Any, snapshot: _Snapshot) -> str:
    namespace = _request_value(candidate, "namespace", None)
    if isinstance(namespace, str) and namespace:
        return namespace
    uri = _node_uri(candidate, _resolve_node(candidate, snapshot))
    if uri is not None:
        return _uri_namespace(uri)
    nodes = tuple(snapshot.iter_nodes(NodeQuery(namespace="demo", limit=1)))
    return nodes[0].namespace if nodes else "demo"


def _request_uris(request: Any, key: str) -> tuple[tuple[str, ...], bool]:
    raw = _request_value(request, key, ())
    if isinstance(raw, (str, ConceptURI)):
        raw = (raw,)
    if not isinstance(raw, Sequence):
        return (), False
    values = tuple(_uri_text(item) for item in raw if _uri_text(item))
    return values, bool(values)


def _request_mapping(value: Any, key: str) -> Mapping[str, Any]:
    raw = _request_value(value, key, {})
    return raw if isinstance(raw, Mapping) else {}


def _request_value(value: Any, key: str, default: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    if isinstance(value, InspirationHeuristic) and key == "heuristic_version":
        return value.heuristic_version
    if hasattr(value, key):
        return getattr(value, key)
    if hasattr(value, "to_dict"):
        raw = value.to_dict()
        if isinstance(raw, Mapping):
            return raw.get(key, default)
    return default


def _heuristic_config(heuristic: InspirationHeuristic | Mapping[str, Any] | None) -> Mapping[str, Any]:
    if heuristic is None:
        return {}
    if isinstance(heuristic, InspirationHeuristic):
        descriptor = dict(heuristic.procedure_descriptor)
        descriptor.setdefault("heuristic_version", heuristic.heuristic_version)
        return descriptor
    return heuristic


def _novelty_weights(config: Mapping[str, Any]) -> dict[str, float]:
    raw = config.get("weights", config)
    if not isinstance(raw, Mapping):
        raw = _DEFAULT_NOVELTY_WEIGHTS
    return {
        name: _nonnegative_float(raw.get(name, _DEFAULT_NOVELTY_WEIGHTS.get(name, 1.0)), 1.0)
        for name in _NOVELTY_COMPONENTS[:-1]
    }


def _numeric_config(config: Mapping[str, Any], key: str, default: float) -> float:
    value = config.get(key, default)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default


def _numeric_value(value: Any, key: str) -> float | None:
    raw = _request_value(value, key, None)
    if raw is None and key == "novelty":
        raw = _request_value(value, "novelty_score", None)
    if raw is None and key == "relevance":
        raw = _request_value(value, "relevance_score", None)
    if raw is None and isinstance(value, NodeEnvelope):
        raw = _request_value(value.payload, key, None)
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, str):
        parsed: float | None = None
        try:
            parsed = float(raw)
        except ValueError:
            parsed = None
        return parsed
    return None


def _first_numeric(*values: Any, key: str) -> float | None:
    for value in values:
        found = _numeric_value(value, key)
        if found is not None:
            return found
    return None


def _derived_structural_surprise(candidate: Any, snapshot: _Snapshot, namespace: str) -> float | None:
    signature = _request_value(candidate, "relation_signature", None)
    if not signature:
        return None
    comparable = _concept_nodes(snapshot, namespace)
    matches = sum(1 for node in comparable if _request_value(node, "relation_signature", None) == signature)
    return _clamp(1.0 - matches / max(1, len(comparable)))


def _derived_domain_span(node: NodeEnvelope | None) -> float | None:
    if node is None:
        return None
    tags = tuple(getattr(node.payload, "domain_tags", ()))
    return _clamp(len(set(tags)) / 4.0)


def _derived_recombination_rarity(candidate: Any, snapshot: _Snapshot, namespace: str) -> float | None:
    sources = _candidate_field(candidate, "source_uris", ())
    if not isinstance(sources, Sequence) or isinstance(sources, str):
        sources = _candidate_field(candidate, "lineage", ())
    if not isinstance(sources, Sequence) or isinstance(sources, str):
        return None
    source_signature = tuple(_uri_text(source) for source in sources)
    if len(source_signature) < 2 or len(set(source_signature)) != len(source_signature):
        return None
    operator_signature = _candidate_operator_signature(candidate)
    observed: set[tuple[tuple[str, ...], str, str]] = set()
    for item in snapshot.iter_edges(EdgeQuery(namespace=namespace, family="recombination")):
        payload = _edge_value(item, "payload", {})
        observed_sources = _request_value(payload, "source_uris", ())
        if not isinstance(observed_sources, Sequence) or isinstance(observed_sources, str):
            continue
        observed_signature = tuple(_uri_text(source) for source in observed_sources)
        if observed_signature != source_signature:
            continue
        observed_operator = _uri_text(_request_value(payload, "heuristic_trace_uri", ""))
        expected_operator = (
            _heuristic_uri(namespace, operator_signature)
            if operator_signature and not operator_signature.startswith("concept://")
            else operator_signature
        )
        if operator_signature and observed_operator != expected_operator:
            continue
        observed.add((observed_signature, observed_operator, _uri_text(_edge_value(item, "target_uri", ""))))
    return _clamp(1.0 / (1.0 + len(observed)))


def _derived_duplication_penalty(node: Any, comparators: Sequence[NodeEnvelope]) -> float | None:
    if node is None:
        return None
    label = _node_label(node)
    if not label:
        return None
    return 1.0 if any(_node_label(other) == label for other in comparators) else 0.0


def _candidate_field(candidate: Any, key: str, default: Any) -> Any:
    value = _request_value(candidate, key, None)
    if value not in (None, (), [], ""):
        return value
    trace = _request_value(candidate, "trace", {})
    return _request_value(trace, key, default)


def _candidate_operator_signature(candidate: Any) -> str:
    for key in ("operator_uri", "operator", "heuristic_trace_uri", "heuristic_version"):
        value = _candidate_field(candidate, key, None)
        if value not in (None, ""):
            return _uri_text(value)
    return ""


def _extract_vector(value: Any) -> tuple[float, ...] | None:
    raw = _request_value(value, "vector", None)
    if raw is None:
        raw = _request_value(value, "embedding", None)
    if raw is None:
        raw = _request_value(value, "values", None)
    if raw is None:
        representations = _request_value(value, "representations", ())
        if isinstance(representations, Sequence):
            for representation in representations:
                found = _extract_vector(representation)
                if found is not None:
                    return found
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return None
    if not raw:
        return None
    values: list[float] = []
    for item in raw:
        if not isinstance(item, int | float) or isinstance(item, bool):
            return None
        values.append(float(item))
    return tuple(values)


def _snapshot_hash(snapshot: _Snapshot, namespace: str) -> str:
    return str(snapshot.snapshot_hash(namespace))


def _edge_value(edge: Any, key: str, default: Any) -> Any:
    if isinstance(edge, Mapping):
        return edge.get(key, default)
    return getattr(edge, key, default)


def _node_label(node: Any) -> str:
    payload = getattr(node, "payload", None)
    source = payload if payload is not None else node
    for key in ("label", "proposition", "operator_name"):
        value = _request_value(source, key, "")
        if isinstance(value, str) and value:
            return value
    return _node_id_text(node) if isinstance(node, NodeEnvelope) else ""


def _node_id_text(node: NodeEnvelope) -> str:
    return _uri_text(node.id)


def _uri_text(value: Any) -> str:
    if isinstance(value, ConceptURI):
        return value.uri
    return str(value)


def _uri_namespace(uri: str) -> str:
    parts = uri.split("/")
    return parts[2] if len(parts) > 2 else "demo"


def _string_set(value: Any, default: Iterable[str]) -> frozenset[str]:
    if isinstance(value, str):
        return frozenset((value,))
    if isinstance(value, Iterable):
        return frozenset(str(item) for item in value)
    return frozenset(default)


def _positive_float(value: Any, default: float) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool) and float(value) > 0:
        return float(value)
    return default


def _nonnegative_float(value: Any, default: float) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool) and float(value) >= 0:
        return float(value)
    return default


def _round_score(value: float) -> float:
    return round(float(value), 6)


def _decimal_text(value: float) -> str:
    return f"{_round_score(value):.6f}"


def _rounded_or_none(value: float | None) -> float | None:
    return _round_score(value) if value is not None else None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _validate_budget(budget: int) -> None:
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ValueError("budget must be a non-negative integer")
