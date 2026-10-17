"""Frozen ontology models, envelopes, and validators for Concept OS."""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from concept.ids import ConceptURI, validate_concept_uri

__all__ = [
    "EDGE_FAMILIES",
    "NODE_TYPES",
    "REPRESENTATION_KINDS",
    "AbstractionEdgePayload",
    "Analogy",
    "AnalogyEdgePayload",
    "CandidateHypothesisEnvelope",
    "Concept",
    "DerivationEdgePayload",
    "EdgeEnvelope",
    "ExemplificationEdgePayload",
    "Hypothesis",
    "InspirationHeuristic",
    "NeighborhoodEdgePayload",
    "NodeEnvelope",
    "RecombinationEdgePayload",
    "ScoreVector",
    "SearchRequest",
    "SearchResult",
    "SemanticNeighborhood",
    "Transformation",
    "ValidationError",
    "from_dict",
    "to_dict",
]

NODE_TYPES: tuple[str, ...] = (
    "Concept",
    "Analogy",
    "Transformation",
    "SemanticNeighborhood",
    "InspirationHeuristic",
    "Hypothesis",
)

EDGE_FAMILIES: tuple[str, ...] = (
    "derivation",
    "analogy",
    "recombination",
    "abstraction",
    "exemplification",
    "neighborhood",
)

REPRESENTATION_KINDS: tuple[str, ...] = (
    "symbolic",
    "structural",
    "exemplar_refs",
    "vector_ref",
    "probabilistic_ref",
    "procedural_affordance",
    "source_ref",
)

_FORBIDDEN_TRUTH_LIFECYCLES: frozenset[str] = frozenset(
    {"validated", "proven", "canonical", "accepted", "verified", "ground_truth"}
)

_ALLOWED_HYPOTHESIS_LIFECYCLES: frozenset[str] = frozenset(
    {"draft", "exploratory", "candidate", "exported", "dismissed", "superseded"}
)


class ValidationError(ValueError):
    """Raised when an ontology model invariant fails validation."""


def _uri_str(val: ConceptURI | str) -> str:
    if isinstance(val, ConceptURI):
        return val.uri
    return str(val)

def _ensure_concept_uri(val: ConceptURI | str) -> ConceptURI:
    if isinstance(val, ConceptURI):
        return val
    if isinstance(val, str):
        return validate_concept_uri(val)
    raise ValidationError(f"Expected ConceptURI or valid URI string, got: {type(val).__name__}")


def _freeze(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool, bytes)) or value is None:
        return value
    if isinstance(value, ConceptURI):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (dict, MappingProxyType)):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    return value


def _thaw(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, ConceptURI):
        return value.uri
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    if isinstance(value, (dict, MappingProxyType)):
        return {str(k): _thaw(v) for k, v in value.items()}
    return value


def _validate_rfc3339(ts: str) -> None:
    if not isinstance(ts, str) or not ts.endswith("Z"):
        raise ValidationError(f"Invalid timestamp format (must end in Z): {ts}")
    raw = ts[:-1]
    try:
        datetime.datetime.fromisoformat(raw)
    except Exception as exc:
        raise ValidationError(f"Invalid RFC3339 timestamp: {ts}") from exc


@dataclass(frozen=True, slots=True)
class Concept:
    label: str
    description: str
    domain_tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValidationError("Concept label cannot be empty")
        object.__setattr__(self, "domain_tags", tuple(self.domain_tags))

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "description": self.description,
            "domain_tags": list(self.domain_tags),
        }


@dataclass(frozen=True, slots=True)
class Transformation:
    operator_name: str
    operator_version: str
    input_signature: Mapping[str, Any]
    output_signature: Mapping[str, Any]
    preconditions: tuple[str, ...] = field(default_factory=tuple)
    postconditions: tuple[str, ...] = field(default_factory=tuple)
    parameters_schema: Mapping[str, Any] = field(default_factory=dict)
    determinism: str = "pure"
    implementation_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.operator_name.strip():
            raise ValidationError("Transformation operator_name cannot be empty")
        if self.implementation_ref is None:
            raise ValidationError("Non-declarative null implementation_ref is forbidden")
        object.__setattr__(self, "input_signature", _freeze(self.input_signature))
        object.__setattr__(self, "output_signature", _freeze(self.output_signature))
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
        object.__setattr__(self, "postconditions", tuple(self.postconditions))
        object.__setattr__(self, "parameters_schema", _freeze(self.parameters_schema))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_name": self.operator_name,
            "operator_version": self.operator_version,
            "input_signature": _thaw(self.input_signature),
            "output_signature": _thaw(self.output_signature),
            "preconditions": list(self.preconditions),
            "postconditions": list(self.postconditions),
            "parameters_schema": _thaw(self.parameters_schema),
            "determinism": self.determinism,
            "implementation_ref": self.implementation_ref,
        }


@dataclass(frozen=True, slots=True)
class Analogy:
    source_roles: tuple[str, ...]
    target_roles: tuple[str, ...]
    correspondences: tuple[Any, ...] = field(default_factory=tuple)
    preserved_relations: tuple[Any, ...] = field(default_factory=tuple)
    known_breaks: tuple[str, ...] = field(default_factory=tuple)
    metric_snapshot: Mapping[str, Any] = field(default_factory=dict)
    heuristic_uri: ConceptURI | str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_roles", tuple(self.source_roles))
        object.__setattr__(self, "target_roles", tuple(self.target_roles))
        object.__setattr__(self, "correspondences", _freeze(self.correspondences))
        object.__setattr__(self, "preserved_relations", _freeze(self.preserved_relations))
        object.__setattr__(self, "known_breaks", tuple(self.known_breaks))
        object.__setattr__(self, "metric_snapshot", _freeze(self.metric_snapshot))
        if self.heuristic_uri:
            object.__setattr__(self, "heuristic_uri", _ensure_concept_uri(self.heuristic_uri))

        if not self.known_breaks and "not_yet_tested" not in self.known_breaks:
            raise ValidationError("Analogy requires known break or explicit 'not_yet_tested' marker")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_roles": list(self.source_roles),
            "target_roles": list(self.target_roles),
            "correspondences": _thaw(self.correspondences),
            "preserved_relations": _thaw(self.preserved_relations),
            "known_breaks": list(self.known_breaks),
            "metric_snapshot": _thaw(self.metric_snapshot),
            "heuristic_uri": _uri_str(self.heuristic_uri) if self.heuristic_uri else "",
        }


@dataclass(frozen=True, slots=True)
class Hypothesis:
    proposition: str
    scope: str
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    lineage: tuple[Any, ...] = field(default_factory=tuple)
    expected_observations: tuple[str, ...] = field(default_factory=tuple)
    falsifiers: tuple[str, ...] = field(default_factory=tuple)
    lifecycle: str = "draft"
    score_snapshot: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.lifecycle in _FORBIDDEN_TRUTH_LIFECYCLES or self.lifecycle not in _ALLOWED_HYPOTHESIS_LIFECYCLES:
            raise ValidationError(
                f"Hypothesis lifecycle '{self.lifecycle}' is forbidden; truth lifecycles are strictly banned."
            )
        if not self.proposition.strip():
            raise ValidationError("Hypothesis proposition cannot be empty")
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "lineage", _freeze(self.lineage))
        object.__setattr__(self, "expected_observations", tuple(self.expected_observations))
        object.__setattr__(self, "falsifiers", tuple(self.falsifiers))
        object.__setattr__(self, "score_snapshot", _freeze(self.score_snapshot))

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposition": self.proposition,
            "scope": self.scope,
            "assumptions": list(self.assumptions),
            "lineage": _thaw(self.lineage),
            "expected_observations": list(self.expected_observations),
            "falsifiers": list(self.falsifiers),
            "lifecycle": self.lifecycle,
            "score_snapshot": _thaw(self.score_snapshot),
        }


@dataclass(frozen=True, slots=True)
class SemanticNeighborhood:
    neighborhood_id: str = ""
    center_uri: ConceptURI | str | None = None
    distance_metric: str = ""
    threshold: str = ""
    members: tuple[Any, ...] = field(default_factory=tuple)
    anchor_uris: tuple[ConceptURI | str, ...] = field(default_factory=tuple)
    metric_versions: Mapping[str, Any] = field(default_factory=dict)
    weights: Mapping[str, Any] = field(default_factory=dict)
    filters: Mapping[str, Any] = field(default_factory=dict)
    budget: Mapping[str, Any] = field(default_factory=dict)
    omitted: int = 0
    truncated: bool = False
    graph_snapshot_hash: str = ""
    query_hash: str = ""

    def __post_init__(self) -> None:
        if self.center_uri is None:
            if not self.anchor_uris:
                raise ValidationError("SemanticNeighborhood requires a center or anchor URI")
            center_uri = _ensure_concept_uri(self.anchor_uris[0])
        else:
            center_uri = _ensure_concept_uri(self.center_uri)
        object.__setattr__(self, "center_uri", center_uri)
        object.__setattr__(self, "members", _freeze(self.members))
        object.__setattr__(
            self,
            "anchor_uris",
            tuple(_ensure_concept_uri(uri) for uri in (self.anchor_uris or (center_uri,))),
        )
        object.__setattr__(self, "metric_versions", _freeze(self.metric_versions))
        object.__setattr__(self, "weights", _freeze(self.weights))
        object.__setattr__(self, "filters", _freeze(self.filters))
        object.__setattr__(self, "budget", _freeze(self.budget))
        if isinstance(self.omitted, bool) or not isinstance(self.omitted, int) or self.omitted < 0:
            raise ValidationError("SemanticNeighborhood omitted must be a non-negative integer")

    def to_dict(self) -> dict[str, Any]:
        has_snapshot_metadata = bool(
            self.metric_versions
            or self.weights
            or self.filters
            or self.budget
            or self.omitted
            or self.truncated
            or self.graph_snapshot_hash
            or self.query_hash
        )
        if has_snapshot_metadata:
            return {
                "anchor_uris": [_uri_str(uri) for uri in self.anchor_uris],
                "metric_versions": _thaw(self.metric_versions),
                "weights": _thaw(self.weights),
                "filters": _thaw(self.filters),
                "budget": _thaw(self.budget),
                "members": _thaw(self.members),
                "omitted": self.omitted,
                "truncated": self.truncated,
                "graph_snapshot_hash": self.graph_snapshot_hash,
                "query_hash": self.query_hash,
            }
        return {
            "neighborhood_id": self.neighborhood_id,
            "center_uri": _uri_str(self.center_uri) if self.center_uri is not None else None,
            "distance_metric": self.distance_metric,
            "threshold": self.threshold,
            "members": _thaw(self.members),
        }


@dataclass(frozen=True, slots=True)
class InspirationHeuristic:
    name: str
    heuristic_version: str
    family: str
    procedure_descriptor: Mapping[str, Any]
    applicability_criteria: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "procedure_descriptor", _freeze(self.procedure_descriptor))
        object.__setattr__(self, "applicability_criteria", tuple(self.applicability_criteria))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "heuristic_version": self.heuristic_version,
            "family": self.family,
            "procedure_descriptor": _thaw(self.procedure_descriptor),
            "applicability_criteria": list(self.applicability_criteria),
        }


_NODE_PAYLOAD_MAP = {
    "Concept": Concept,
    "Analogy": Analogy,
    "Transformation": Transformation,
    "SemanticNeighborhood": SemanticNeighborhood,
    "InspirationHeuristic": InspirationHeuristic,
    "Hypothesis": Hypothesis,
}


@dataclass(frozen=True, slots=True)
class NodeEnvelope:
    id: ConceptURI | str
    type: str
    namespace: str
    schema_version: int
    payload: Any
    representations: tuple[Any, ...] = field(default_factory=tuple)
    provenance_refs: tuple[str, ...] = field(default_factory=tuple)
    recorded_at: str = ""

    def __post_init__(self) -> None:
        uri = _ensure_concept_uri(self.id)
        object.__setattr__(self, "id", uri)

        if self.type not in NODE_TYPES:
            raise ValidationError(f"Invalid node type '{self.type}'. Must be one of {NODE_TYPES}")

        expected_cls = _NODE_PAYLOAD_MAP.get(self.type)
        assert expected_cls is not None
        if not isinstance(self.payload, expected_cls):  # type: ignore[arg-type]
            raise ValidationError(f"Payload for type '{self.type}' must be an instance of {expected_cls.__name__}")

        if uri.namespace != self.namespace:
            raise ValidationError(f"Node URI namespace '{uri.namespace}' does not match '{self.namespace}'")

        if self.schema_version < 1:
            raise ValidationError("schema_version must be >= 1")

        if not self.provenance_refs:
            raise ValidationError("provenance_refs cannot be empty")

        if self.recorded_at:
            _validate_rfc3339(self.recorded_at)

        object.__setattr__(self, "representations", _freeze(self.representations))
        object.__setattr__(self, "provenance_refs", tuple(self.provenance_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": _uri_str(self.id),
            "type": self.type,
            "namespace": self.namespace,
            "schema_version": self.schema_version,
            "payload": self.payload.to_dict() if hasattr(self.payload, "to_dict") else _thaw(self.payload),
            "representations": _thaw(self.representations),
            "provenance_refs": list(self.provenance_refs),
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class AnalogyEdgePayload:
    role_name: str
    correspondence_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_name": self.role_name,
            "correspondence_index": self.correspondence_index,
        }


@dataclass(frozen=True, slots=True)
class DerivationEdgePayload:
    operator_uri: ConceptURI | str
    trace_uri: ConceptURI | str
    input_order: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "operator_uri", _ensure_concept_uri(self.operator_uri))
        object.__setattr__(self, "trace_uri", _ensure_concept_uri(self.trace_uri))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_uri": _uri_str(self.operator_uri),
            "trace_uri": _uri_str(self.trace_uri),
            "input_order": self.input_order,
        }


@dataclass(frozen=True, slots=True)
class RecombinationEdgePayload:
    contribution_role: str
    contribution_order: int
    heuristic_trace_uri: ConceptURI | str
    source_uris: tuple[ConceptURI | str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "heuristic_trace_uri", _ensure_concept_uri(self.heuristic_trace_uri))
        object.__setattr__(self, "source_uris", tuple(_ensure_concept_uri(u) for u in self.source_uris))
        if len(self.source_uris) < 2:
            raise ValidationError("Recombination requires at least two distinct source URIs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contribution_role": self.contribution_role,
            "contribution_order": self.contribution_order,
            "heuristic_trace_uri": _uri_str(self.heuristic_trace_uri),
            "source_uris": [_uri_str(u) for u in self.source_uris],
        }


@dataclass(frozen=True, slots=True)
class AbstractionEdgePayload:
    abstraction_operator_uri: ConceptURI | str
    preserved_features: tuple[str, ...]
    lost_features: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "abstraction_operator_uri", _ensure_concept_uri(self.abstraction_operator_uri))
        object.__setattr__(self, "preserved_features", tuple(self.preserved_features))
        object.__setattr__(self, "lost_features", tuple(self.lost_features))

    def to_dict(self) -> dict[str, Any]:
        return {
            "abstraction_operator_uri": _uri_str(self.abstraction_operator_uri),
            "preserved_features": list(self.preserved_features),
            "lost_features": list(self.lost_features),
        }


@dataclass(frozen=True, slots=True)
class ExemplificationEdgePayload:
    scope: str
    source_provenance_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "source_provenance_ref": self.source_provenance_ref,
        }


@dataclass(frozen=True, slots=True)
class NeighborhoodEdgePayload:
    rank: int
    component_distances: Mapping[str, str]
    aggregate_distance: str
    why: tuple[Any, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_distances", _freeze(self.component_distances))
        object.__setattr__(self, "why", _freeze(self.why))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "component_distances": _thaw(self.component_distances),
            "aggregate_distance": self.aggregate_distance,
            "why": _thaw(self.why),
        }


_EDGE_PAYLOAD_MAP = {
    "derivation": DerivationEdgePayload,
    "analogy": AnalogyEdgePayload,
    "recombination": RecombinationEdgePayload,
    "abstraction": AbstractionEdgePayload,
    "exemplification": ExemplificationEdgePayload,
    "neighborhood": NeighborhoodEdgePayload,
}


@dataclass(frozen=True, slots=True)
class EdgeEnvelope:
    id: ConceptURI | str
    namespace: str
    family: str
    relation: str
    source_uri: ConceptURI | str
    target_uri: ConceptURI | str
    schema_version: int
    payload: Any
    provenance_refs: tuple[str, ...] = field(default_factory=tuple)
    recorded_at: str = ""

    def __post_init__(self) -> None:
        uri = _ensure_concept_uri(self.id)
        src = _ensure_concept_uri(self.source_uri)
        tgt = _ensure_concept_uri(self.target_uri)

        object.__setattr__(self, "id", uri)
        object.__setattr__(self, "source_uri", src)
        object.__setattr__(self, "target_uri", tgt)

        if str(src) == str(tgt):
            raise ValidationError("Self-loops are forbidden across all Concept OS edges")

        if self.family not in EDGE_FAMILIES:
            raise ValidationError(f"Invalid edge family '{self.family}'. Must be one of {EDGE_FAMILIES}")

        expected_cls = _EDGE_PAYLOAD_MAP.get(self.family)
        assert expected_cls is not None
        if not isinstance(self.payload, expected_cls):  # type: ignore[arg-type]
            raise ValidationError(f"Payload for family '{self.family}' must be an instance of {expected_cls.__name__}")

        if self.family == "analogy":
            if src.kind == "concept" and tgt.kind == "concept":
                raise ValidationError("Direct Concept-to-Concept analogy edges are forbidden")
            if self.relation in ("has_source", "has_target") and src.kind != "analogy":
                raise ValidationError("Analogy has_source/has_target edge requires an Analogy source node")

        if uri.namespace != self.namespace:
            raise ValidationError(f"Edge URI namespace '{uri.namespace}' does not match '{self.namespace}'")

        if not self.provenance_refs:
            raise ValidationError("provenance_refs cannot be empty")

        if self.recorded_at:
            _validate_rfc3339(self.recorded_at)

        object.__setattr__(self, "provenance_refs", tuple(self.provenance_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": _uri_str(self.id),
            "namespace": self.namespace,
            "family": self.family,
            "relation": self.relation,
            "source_uri": _uri_str(self.source_uri),
            "target_uri": _uri_str(self.target_uri),
            "schema_version": self.schema_version,
            "payload": self.payload.to_dict() if hasattr(self.payload, "to_dict") else _thaw(self.payload),
            "provenance_refs": list(self.provenance_refs),
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class SearchRequest:
    namespace: str
    query_text: str = ""
    anchor_uris: tuple[ConceptURI | str, ...] = field(default_factory=tuple)
    seed: int = 0
    disclosure_policy: str = "same_namespace"
    desired_output_kinds: tuple[str, ...] = ("Concept",)
    required_edge_families: tuple[str, ...] = ()
    forbidden_edge_families: tuple[str, ...] = ()
    required_relations: tuple[str, ...] = ()
    forbidden_relations: tuple[str, ...] = ()
    constraints: Mapping[str, Any] = field(default_factory=dict)
    representation_requirements: tuple[str, ...] = ()
    algorithm_allow_list: tuple[Any, ...] = field(default_factory=tuple)
    budgets: Mapping[str, int] = field(default_factory=lambda: {"max_expansions": 10, "max_results": 2, "max_hops": 2, "max_tokens": 100})
    ranking_weights: Mapping[str, str] = field(default_factory=lambda: {"relevance": "0.50", "novelty": "0.50"})
    score_versions: Mapping[str, str] = field(default_factory=lambda: {"relevance": "v1", "novelty": "v1"})

    def __post_init__(self) -> None:
        if "confidence" in self.ranking_weights:
            raise ValidationError("Forbidden 'confidence' field present in ranking weights")
        object.__setattr__(self, "anchor_uris", tuple(_ensure_concept_uri(u) for u in self.anchor_uris))
        object.__setattr__(self, "desired_output_kinds", tuple(self.desired_output_kinds))
        object.__setattr__(self, "required_edge_families", tuple(self.required_edge_families))
        object.__setattr__(self, "forbidden_edge_families", tuple(self.forbidden_edge_families))
        object.__setattr__(self, "required_relations", tuple(self.required_relations))
        object.__setattr__(self, "forbidden_relations", tuple(self.forbidden_relations))
        object.__setattr__(self, "constraints", _freeze(self.constraints))
        object.__setattr__(self, "representation_requirements", tuple(self.representation_requirements))
        object.__setattr__(self, "algorithm_allow_list", _freeze(self.algorithm_allow_list))
        object.__setattr__(self, "budgets", _freeze(self.budgets))
        object.__setattr__(self, "ranking_weights", _freeze(self.ranking_weights))
        object.__setattr__(self, "score_versions", _freeze(self.score_versions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_text": self.query_text,
            "anchor_uris": [_uri_str(u) for u in self.anchor_uris],
            "namespace": self.namespace,
            "disclosure_policy": self.disclosure_policy,
            "desired_output_kinds": list(self.desired_output_kinds),
            "required_edge_families": list(self.required_edge_families),
            "forbidden_edge_families": list(self.forbidden_edge_families),
            "required_relations": list(self.required_relations),
            "forbidden_relations": list(self.forbidden_relations),
            "constraints": _thaw(self.constraints),
            "representation_requirements": list(self.representation_requirements),
            "algorithm_allow_list": _thaw(self.algorithm_allow_list),
            "budgets": _thaw(self.budgets),
            "seed": self.seed,
            "ranking_weights": _thaw(self.ranking_weights),
            "score_versions": _thaw(self.score_versions),
        }


@dataclass(frozen=True, slots=True)
class SearchResult:
    query_hash: str
    graph_snapshot_hash: str
    algorithm_versions: Mapping[str, str] = field(default_factory=dict)
    heuristic_versions: Mapping[str, str] = field(default_factory=dict)
    seeds: Mapping[str, int] = field(default_factory=dict)
    budgets_requested: Mapping[str, int] = field(default_factory=dict)
    budgets_consumed: Mapping[str, int] = field(default_factory=dict)
    results: tuple[Any, ...] = field(default_factory=tuple)
    rejected_by_reason: Mapping[str, int] = field(default_factory=dict)
    errors: tuple[Any, ...] = field(default_factory=tuple)
    omitted: int = 0
    truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "algorithm_versions", _freeze(self.algorithm_versions))
        object.__setattr__(self, "heuristic_versions", _freeze(self.heuristic_versions))
        object.__setattr__(self, "seeds", _freeze(self.seeds))
        object.__setattr__(self, "budgets_requested", _freeze(self.budgets_requested))
        object.__setattr__(self, "budgets_consumed", _freeze(self.budgets_consumed))
        object.__setattr__(self, "results", _freeze(self.results))
        object.__setattr__(self, "rejected_by_reason", _freeze(self.rejected_by_reason))
        object.__setattr__(self, "errors", _freeze(self.errors))

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_hash": self.query_hash,
            "graph_snapshot_hash": self.graph_snapshot_hash,
            "algorithm_versions": _thaw(self.algorithm_versions),
            "heuristic_versions": _thaw(self.heuristic_versions),
            "seeds": _thaw(self.seeds),
            "budgets_requested": _thaw(self.budgets_requested),
            "budgets_consumed": _thaw(self.budgets_consumed),
            "results": _thaw(self.results),
            "rejected_by_reason": _thaw(self.rejected_by_reason),
            "errors": _thaw(self.errors),
            "omitted": self.omitted,
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class ScoreVector:
    relevance: str = "0.0"
    novelty: str = "0.0"
    coherence: str = "0.0"
    diversity_contribution: str = "0.0"
    cost: str = "0.0"
    provenance_completeness: str = "1.0"

    def to_dict(self) -> dict[str, str]:
        return {
            "relevance": self.relevance,
            "novelty": self.novelty,
            "coherence": self.coherence,
            "diversity_contribution": self.diversity_contribution,
            "cost": self.cost,
            "provenance_completeness": self.provenance_completeness,
        }


@dataclass(frozen=True, slots=True)
class CandidateHypothesisEnvelope:
    envelope_id: ConceptURI | str
    schema_version: int
    hypothesis_uri: ConceptURI | str
    proposition: str
    scope: str
    assumptions: tuple[str, ...]
    expected_observations: tuple[str, ...]
    falsifiers: tuple[str, ...]
    source_refs: tuple[ConceptURI | str, ...]
    replay_manifest: Mapping[str, Any]
    score_vectors: ScoreVector
    graph_snapshot_hash: str
    content_hashes: tuple[str, ...]
    requested_evaluation_kind: str = "bounded_experiment"
    proposal_kind: str = "exploratory_hypothesis"
    authority: str = "exploratory"
    trust: str = "untrusted_candidate"

    def __post_init__(self) -> None:
        object.__setattr__(self, "envelope_id", _ensure_concept_uri(self.envelope_id))
        object.__setattr__(self, "hypothesis_uri", _ensure_concept_uri(self.hypothesis_uri))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "expected_observations", tuple(self.expected_observations))
        object.__setattr__(self, "falsifiers", tuple(self.falsifiers))
        object.__setattr__(self, "source_refs", tuple(_ensure_concept_uri(u) for u in self.source_refs))
        object.__setattr__(self, "replay_manifest", _freeze(self.replay_manifest))
        object.__setattr__(self, "content_hashes", tuple(self.content_hashes))

        if not self.falsifiers:
            raise ValidationError("CandidateHypothesis requires at least one explicit falsifier")

    def to_dict(self) -> dict[str, Any]:
        comps = self.score_vectors.to_dict() if hasattr(self.score_vectors, "to_dict") else _thaw(self.score_vectors)
        return {
            "envelope_id": _uri_str(self.envelope_id),
            "schema_version": self.schema_version,
            "proposal_kind": self.proposal_kind,
            "authority": "exploratory",
            "trust": self.trust,
            "hypothesis_uri": _uri_str(self.hypothesis_uri),
            "proposition": self.proposition,
            "scope": self.scope,
            "assumptions": list(self.assumptions),
            "expected_observations": list(self.expected_observations),
            "falsifiers": list(self.falsifiers),
            "source_refs": [_uri_str(u) for u in self.source_refs],
            "replay_manifest": _thaw(self.replay_manifest),
            "score_vectors": {
                "evidentiary": False,
                "components": comps,
            },
            "graph_snapshot_hash": self.graph_snapshot_hash,
            "content_hashes": list(self.content_hashes),
            "requested_evaluation_kind": self.requested_evaluation_kind,
        }


def to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not serializable with to_dict")


def from_dict(d: Mapping[str, Any]) -> Any:
    if not isinstance(d, (dict, MappingProxyType)):
        raise TypeError(f"from_dict expects Mapping, got {type(d).__name__}")

    # NodeEnvelope
    if "type" in d and d["type"] in NODE_TYPES:
        node_type = str(d["type"])
        raw_payload = d["payload"]
        payload_cls = _NODE_PAYLOAD_MAP[node_type]
        payload = payload_cls(**raw_payload) if isinstance(raw_payload, dict) else raw_payload
        return NodeEnvelope(
            id=d["id"],
            type=node_type,
            namespace=d["namespace"],
            schema_version=d["schema_version"],
            payload=payload,
            representations=tuple(d.get("representations", ())),
            provenance_refs=tuple(d.get("provenance_refs", ())),
            recorded_at=d.get("recorded_at", ""),
        )

    # EdgeEnvelope
    if "family" in d and d["family"] in EDGE_FAMILIES:
        family = str(d["family"])
        raw_payload = d["payload"]
        payload_cls = _EDGE_PAYLOAD_MAP[family]
        payload = payload_cls(**raw_payload) if isinstance(raw_payload, dict) else raw_payload
        return EdgeEnvelope(
            id=d["id"],
            namespace=d["namespace"],
            family=family,
            relation=d["relation"],
            source_uri=d["source_uri"],
            target_uri=d["target_uri"],
            schema_version=d["schema_version"],
            payload=payload,
            provenance_refs=tuple(d.get("provenance_refs", ())),
            recorded_at=d.get("recorded_at", ""),
        )

    # SearchRequest
    if "desired_output_kinds" in d and "budgets" in d:
        return SearchRequest(
            namespace=d["namespace"],
            query_text=d.get("query_text", ""),
            anchor_uris=tuple(d.get("anchor_uris", ())),
            seed=d.get("seed", 0),
            disclosure_policy=d.get("disclosure_policy", "same_namespace"),
            desired_output_kinds=tuple(d.get("desired_output_kinds", ("Concept",))),
            required_edge_families=tuple(d.get("required_edge_families", ())),
            forbidden_edge_families=tuple(d.get("forbidden_edge_families", ())),
            required_relations=tuple(d.get("required_relations", ())),
            forbidden_relations=tuple(d.get("forbidden_relations", ())),
            constraints=dict(d.get("constraints", {})),
            representation_requirements=tuple(d.get("representation_requirements", ())),
            algorithm_allow_list=tuple(d.get("algorithm_allow_list", ())),
            budgets=dict(d.get("budgets", {})),
            ranking_weights=dict(d.get("ranking_weights", {})),
            score_versions=dict(d.get("score_versions", {})),
        )

    # CandidateHypothesisEnvelope
    if "hypothesis_uri" in d and "proposal_kind" in d:
        score_data = d.get("score_vectors", {})
        comps = score_data.get("components", {}) if isinstance(score_data, dict) else {}
        scores = ScoreVector(**comps)
        return CandidateHypothesisEnvelope(
            envelope_id=d["envelope_id"],
            schema_version=d["schema_version"],
            hypothesis_uri=d["hypothesis_uri"],
            proposition=d["proposition"],
            scope=d["scope"],
            assumptions=tuple(d.get("assumptions", ())),
            expected_observations=tuple(d.get("expected_observations", ())),
            falsifiers=tuple(d.get("falsifiers", ())),
            source_refs=tuple(d.get("source_refs", ())),
            replay_manifest=dict(d.get("replay_manifest", {})),
            score_vectors=scores,
            graph_snapshot_hash=d["graph_snapshot_hash"],
            content_hashes=tuple(d.get("content_hashes", ())),
            requested_evaluation_kind=d.get("requested_evaluation_kind", "bounded_experiment"),
            proposal_kind=d.get("proposal_kind", "exploratory_hypothesis"),
            authority=d.get("authority", "exploratory"),
            trust=d.get("trust", "untrusted_candidate"),
        )

    raise ValueError(f"Unable to deserialize dict into recognized Concept OS model: {list(d.keys())}")
