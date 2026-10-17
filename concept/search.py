"""Deterministic, bounded multi-arm search over the Concept OS graph."""

from __future__ import annotations

import math
import random
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Protocol, cast

from concept.ids import ConceptURI, canonical_json, content_hash
from concept.inspiration import (
    Proposal,
    ProposalResult,
    propose_analogies,
    propose_recombinations,
    score_novelty,
)
from concept.model import (
    EDGE_FAMILIES,
    NODE_TYPES,
    NodeEnvelope,
    ScoreVector,
    SearchRequest,
    ValidationError,
)
from concept.store import ConceptStore, EdgeQuery, NodeQuery
from concept.traverse import OUTGOING, TraversalRequest, traverse

__all__ = [
    "AnalogySearchArm",
    "CompiledSearchRequest",
    "RankedSearchItem",
    "SearchArm",
    "SearchArmResult",
    "SearchBudget",
    "SearchCandidate",
    "SearchOrchestra",
    "SearchRequest",
    "SearchResult",
    "SeededRandomWalkSearchArm",
    "TraversalSearchArm",
    "compile_query",
]

_ARM_SPECS: tuple[tuple[str, str], ...] = (
    ("traversal", "v1"),
    ("seeded-random-walk", "v1"),
)
_SCORE_COMPONENTS: tuple[str, ...] = (
    "relevance",
    "novelty",
    "coherence",
    "diversity_contribution",
    "cost",
    "provenance_completeness",
)
_RELATIONS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    "derivation": ("derived_from", "supersedes", "specializes_from"),
    "analogy": ("has_source", "has_target", "refines"),
    "recombination": ("contributes_to", "combined_as"),
    "abstraction": ("abstracts_to", "generalizes_to"),
    "exemplification": ("exemplifies", "counterexample_to"),
    "neighborhood": ("contains",),
}
_ALL_RELATIONS: tuple[str, ...] = tuple(
    sorted({relation for relations in _RELATIONS_BY_FAMILY.values() for relation in relations})
)
_NAMESPACE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
_TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)
_SCALE = Decimal("0.000001")


class SearchSnapshot(Protocol):
    """Read-only graph snapshot required by search arms."""

    def get_node(self, uri: str) -> NodeEnvelope | None: ...

    def iter_nodes(self, query: NodeQuery) -> Iterable[NodeEnvelope]: ...

    def iter_edges(self, query: EdgeQuery) -> Iterable[Any]: ...

    def snapshot_hash(self, namespace: str) -> str: ...


@dataclass(frozen=True, slots=True)
class SearchBudget:
    """One immutable arm allocation."""

    max_expansions: int
    max_results: int
    max_hops: int
    max_tokens: int

    def __post_init__(self) -> None:
        for name in ("max_expansions", "max_results", "max_hops", "max_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    def to_dict(self) -> dict[str, int]:
        return {
            "max_expansions": self.max_expansions,
            "max_results": self.max_results,
            "max_hops": self.max_hops,
            "max_tokens": self.max_tokens,
        }


@dataclass(frozen=True, slots=True)
class CompiledSearchRequest:
    """Canonical query plus explicit constraints and immutable arm allocations."""

    request: SearchRequest
    query_hash: str
    original_query_text: str
    anchor_uris: tuple[str, ...]
    constraints: Mapping[str, Any]
    arm_allocations: Mapping[str, SearchBudget]
    algorithm_allow_list: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchor_uris", tuple(self.anchor_uris))
        object.__setattr__(self, "constraints", MappingProxyType(dict(self.constraints)))
        object.__setattr__(self, "arm_allocations", MappingProxyType(dict(self.arm_allocations)))
        object.__setattr__(self, "algorithm_allow_list", tuple(self.algorithm_allow_list))

    @property
    def namespace(self) -> str:
        return self.request.namespace

    @property
    def seed(self) -> int:
        return self.request.seed

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_hash": self.query_hash,
            "original_query_text": self.original_query_text,
            "anchor_uris": list(self.anchor_uris),
            "constraints": _jsonable(self.constraints),
            "arm_allocations": {
                name: budget.to_dict() for name, budget in self.arm_allocations.items()
            },
            "algorithm_allow_list": [
                {"name": name, "version": version}
                for name, version in self.algorithm_allow_list
            ],
            "request": self.request.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    """A whole candidate and the arm/generator trace that produced it."""

    candidate: Any
    candidate_uri: str = ""
    arm_name: str = ""
    arm_version: str = ""
    why: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    cost: int = 1
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        uri = self.candidate_uri or _candidate_uri(self.candidate)
        if not uri:
            raise ValueError("search candidates require a Concept URI")
        if isinstance(self.cost, bool) or not isinstance(self.cost, int) or self.cost < 0:
            raise ValueError("candidate cost must be a non-negative integer")
        object.__setattr__(self, "candidate_uri", uri)
        object.__setattr__(self, "why", tuple(dict(item) for item in self.why))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_uri": self.candidate_uri,
            "arm_name": self.arm_name,
            "arm_version": self.arm_version,
            "candidate": _jsonable(self.candidate),
            "why": [_jsonable(item) for item in self.why],
            "cost": self.cost,
            "metadata": _jsonable(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SearchArmResult:
    """Complete, bounded output from one arm, including explicit degradation."""

    candidates: tuple[SearchCandidate | Any, ...] = field(default_factory=tuple)
    paths: Mapping[str, Any] = field(default_factory=dict)
    budgets_requested: Mapping[str, int] = field(default_factory=dict)
    budgets_consumed: Mapping[str, int] = field(default_factory=dict)
    rejected_items: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    truncated: bool = False
    errors: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    omitted: int = 0
    seed: int = 0

    def __post_init__(self) -> None:
        normalized: list[SearchCandidate] = []
        for candidate in self.candidates:
            if isinstance(candidate, SearchCandidate):
                normalized.append(candidate)
            else:
                normalized.append(SearchCandidate(candidate=candidate))
        object.__setattr__(self, "candidates", tuple(normalized))
        object.__setattr__(self, "paths", MappingProxyType(dict(self.paths)))
        object.__setattr__(self, "budgets_requested", MappingProxyType(dict(self.budgets_requested)))
        object.__setattr__(self, "budgets_consumed", MappingProxyType(dict(self.budgets_consumed)))
        object.__setattr__(self, "rejected_items", tuple(dict(item) for item in self.rejected_items))
        object.__setattr__(self, "errors", tuple(dict(item) for item in self.errors))
        if isinstance(self.omitted, bool) or not isinstance(self.omitted, int) or self.omitted < 0:
            raise ValueError("omitted must be a non-negative integer")

    @property
    def path_explanations(self) -> Mapping[str, Any]:
        return self.paths

    @property
    def rejected(self) -> tuple[Mapping[str, Any], ...]:
        return self.rejected_items

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [_jsonable(candidate) for candidate in self.candidates],
            "paths": {key: _jsonable(value) for key, value in self.paths.items()},
            "budgets_requested": dict(self.budgets_requested),
            "budgets_consumed": dict(self.budgets_consumed),
            "rejected_items": [_jsonable(item) for item in self.rejected_items],
            "truncated": self.truncated,
            "errors": [_jsonable(item) for item in self.errors],
            "omitted": self.omitted,
            "seed": self.seed,
        }


class SearchArm(Protocol):
    """Pure protocol for one deterministic search strategy."""

    name: str
    version: str

    def search(
        self,
        request: CompiledSearchRequest,
        snapshot: SearchSnapshot,
        budget: SearchBudget,
        seed: int,
    ) -> SearchArmResult: ...


@dataclass(frozen=True, slots=True)
class RankedSearchItem:
    """A ranked candidate with all non-evidentiary score components exposed."""

    candidate_uri: str
    rank: int
    score_components: ScoreVector
    why: tuple[Mapping[str, Any], ...]
    candidate: Any = field(compare=False, repr=False)
    arm_name: str = field(default="", compare=False)
    arm_version: str = field(default="", compare=False)
    scalar_score: str = field(default="0.000000", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "why", tuple(dict(item) for item in self.why))

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_uri": self.candidate_uri,
            "rank": self.rank,
            "score_components": self.score_components.to_dict(),
            "why": [_jsonable(item) for item in self.why],
        }


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Stable search response and replayable manifest."""

    query_hash: str
    graph_snapshot_hash: str
    algorithm_versions: Mapping[str, str]
    heuristic_versions: Mapping[str, str]
    seeds: Mapping[str, int]
    budgets_requested: Mapping[str, int]
    budgets_consumed: Mapping[str, int]
    results: tuple[RankedSearchItem, ...] = field(default_factory=tuple)
    rejected_by_reason: Mapping[str, int] = field(default_factory=dict)
    errors: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    omitted: int = 0
    truncated: bool = False
    arm_results: Mapping[str, SearchArmResult] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "algorithm_versions",
            "heuristic_versions",
            "seeds",
            "budgets_requested",
            "budgets_consumed",
            "rejected_by_reason",
            "arm_results",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))
        object.__setattr__(self, "results", tuple(self.results))
        object.__setattr__(self, "errors", tuple(dict(error) for error in self.errors))
        if isinstance(self.omitted, bool) or not isinstance(self.omitted, int) or self.omitted < 0:
            raise ValueError("omitted must be a non-negative integer")

    @property
    def replay_manifest(self) -> dict[str, Any]:
        why: dict[str, Any] = {}
        for arm_result in self.arm_results.values():
            for candidate in arm_result.candidates:
                why.setdefault(candidate.candidate_uri, [_jsonable(path) for path in candidate.why])
        return {
            "query_hash": self.query_hash,
            "graph_snapshot_hash": self.graph_snapshot_hash,
            "algorithm_versions": dict(self.algorithm_versions),
            "heuristic_versions": dict(self.heuristic_versions),
            "seeds": dict(self.seeds),
            "budgets_requested": dict(self.budgets_requested),
            "budgets_consumed": dict(self.budgets_consumed),
            "rejected_by_reason": dict(self.rejected_by_reason),
            "omitted": self.omitted,
            "truncated": self.truncated,
            "why": why,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_hash": self.query_hash,
            "graph_snapshot_hash": self.graph_snapshot_hash,
            "algorithm_versions": dict(self.algorithm_versions),
            "heuristic_versions": dict(self.heuristic_versions),
            "seeds": dict(self.seeds),
            "budgets_requested": dict(self.budgets_requested),
            "budgets_consumed": dict(self.budgets_consumed),
            "results": [item.to_dict() for item in self.results],
            "rejected_by_reason": dict(self.rejected_by_reason),
            "errors": [_jsonable(error) for error in self.errors],
            "omitted": self.omitted,
            "truncated": self.truncated,
        }


class TraversalSearchArm:
    """Stable breadth-first arm backed by :mod:`concept.traverse`."""

    name = "traversal"
    version = "v1"

    def search(
        self,
        request: CompiledSearchRequest,
        snapshot: SearchSnapshot,
        budget: SearchBudget,
        seed: int,
    ) -> SearchArmResult:
        explicit_roots = bool(request.anchor_uris)
        roots = request.anchor_uris or _matching_roots(request, snapshot)
        if not roots:
            return SearchArmResult(
                budgets_requested=budget.to_dict(),
                rejected_items=({"reason": "no_matching_root"},),
                truncated=False,
                seed=seed,
            )

        families = _allowed_families(request)
        relations = _allowed_relations(request)
        if not families:
            return SearchArmResult(
                budgets_requested=budget.to_dict(),
                rejected_items=({"reason": "no_allowed_edge_family"},),
                seed=seed,
            )
        traversal_request = TraversalRequest(
            namespace=request.namespace,
            roots=roots,
            direction=OUTGOING,
            families=families,
            relations=relations,
            max_hops=budget.max_hops,
            max_expansions=budget.max_expansions,
            max_results=max(budget.max_results, len(roots)) if not explicit_roots else budget.max_results,
            read_policy=request.request.disclosure_policy,
        )
        traversal_result = traverse(cast(ConceptStore, snapshot), traversal_request)
        root_set = set(request.anchor_uris)
        candidates: list[SearchCandidate] = []
        rejected: list[Mapping[str, Any]] = []
        paths: dict[str, Any] = {}
        for raw_uri in traversal_result.nodes:
            uri = _uri_text(raw_uri)
            if explicit_roots and uri in root_set:
                continue
            node = snapshot.get_node(uri)
            if node is None:
                rejected.append({"reason": "missing_candidate", "candidate_uri": uri})
                continue
            path = traversal_result.why[uri]
            path_dict = path.to_dict()
            if not _candidate_matches(request, node, path_dict):
                rejected.append({"reason": _rejection_reason(request, node), "candidate_uri": uri})
                continue
            paths[uri] = path
            candidates.append(
                SearchCandidate(
                    candidate=node,
                    candidate_uri=uri,
                    arm_name=self.name,
                    arm_version=self.version,
                    why=(path_dict,),
                    cost=max(1, len(path.edge_uris)),
                    metadata={"kind": "traversal", "hops": len(path.edge_uris)},
                )
            )

        admitted, budget_rejections, token_count, token_omitted = _limit_arm_candidates(
            candidates, budget
        )
        rejected.extend(budget_rejections)
        consumed = dict(traversal_result.budgets_consumed)
        consumed["tokens"] = token_count
        consumed["results"] = len(admitted)
        consumed["hops"] = max((len(path.edge_uris) for path in paths.values()), default=0)
        consumed["expansions"] = min(consumed.get("expansions", 0), budget.max_expansions)
        return SearchArmResult(
            candidates=tuple(admitted),
            paths={item.candidate_uri: paths[item.candidate_uri] for item in admitted},
            budgets_requested=budget.to_dict(),
            budgets_consumed=consumed,
            rejected_items=tuple(rejected),
            truncated=traversal_result.truncated or bool(budget_rejections),
            omitted=traversal_result.omitted + token_omitted,
            seed=seed,
        )


class SeededRandomWalkSearchArm:
    """Seeded diversity arm using local analogy and recombination proposers."""

    name = "seeded-random-walk"
    version = "v1"

    def search(
        self,
        request: CompiledSearchRequest,
        snapshot: SearchSnapshot,
        budget: SearchBudget,
        seed: int,
    ) -> SearchArmResult:
        if budget.max_expansions == 0 or budget.max_results == 0:
            return SearchArmResult(
                budgets_requested=budget.to_dict(),
                rejected_items=({"reason": "budget_exhausted"},),
                seed=seed,
            )
        concepts = sorted(
            (node for node in snapshot.iter_nodes(NodeQuery(namespace=request.namespace)) if node.type == "Concept"),
            key=lambda node: _uri_text(node.id),
        )
        rng = random.Random(seed)
        anchor_concepts = [
            node for uri in request.anchor_uris for node in (snapshot.get_node(uri),) if node is not None and node.type == "Concept"
        ]
        ordered: list[NodeEnvelope] = []
        seen: set[str] = set()
        for node in anchor_concepts:
            uri = _uri_text(node.id)
            if uri not in seen:
                seen.add(uri)
                ordered.append(node)
        remainder = [node for node in concepts if _uri_text(node.id) not in seen]
        rng.shuffle(remainder)
        ordered.extend(remainder)
        rejected: list[Mapping[str, Any]] = []
        desired = set(request.request.desired_output_kinds)
        proposal: ProposalResult
        proposal_request: dict[str, Any] = {
            "namespace": request.namespace,
            "constraints": request.request.constraints,
            "source_uris": tuple(_uri_text(node.id) for node in ordered[: max(2, min(len(ordered), 4))]),
            "scope": request.request.query_text or "local concept graph",
        }
        if "Analogy" in desired:
            if len(ordered) < 2:
                return SearchArmResult(
                    budgets_requested=budget.to_dict(),
                    rejected_items=({"reason": "insufficient_source_pairs"},),
                    seed=seed,
                )
            proposal_request["source_uris"] = (_uri_text(ordered[0].id),)
            proposal_request["target_uris"] = (_uri_text(ordered[1].id),)
            proposal = propose_analogies(snapshot, proposal_request, budget=budget.max_expansions, seed=seed)
        elif desired.intersection({"Concept", "Hypothesis"}):
            output_kind = "Hypothesis" if "Hypothesis" in desired and "Concept" not in desired else "Concept"
            proposal_request["output_kind"] = output_kind
            if len(ordered) < 2:
                return SearchArmResult(
                    budgets_requested=budget.to_dict(),
                    rejected_items=({"reason": "insufficient_source_pairs"},),
                    seed=seed,
                )
            proposal = propose_recombinations(
                snapshot,
                proposal_request,
                budget=budget.max_expansions,
                seed=seed,
            )
        else:
            return SearchArmResult(
                budgets_requested=budget.to_dict(),
                rejected_items=({"reason": "unsupported_output_kind"},),
                seed=seed,
            )

        rejected.extend(proposal.rejected_traces)
        candidates: list[SearchCandidate] = []
        paths: dict[str, Any] = {}
        for generated in proposal.proposals[: budget.max_results]:
            node = generated.node
            trace = _jsonable(generated.trace)
            if not _candidate_matches(request, node, trace):
                rejected.append({"reason": _rejection_reason(request, node), "candidate_uri": _uri_text(node.id)})
                continue
            uri = _uri_text(node.id)
            paths[uri] = trace
            candidates.append(
                SearchCandidate(
                    candidate=node,
                    candidate_uri=uri,
                    arm_name=self.name,
                    arm_version=self.version,
                    why=(cast(Mapping[str, Any], trace),),
                    cost=max(1, proposal.budget_consumed),
                    metadata={"kind": str(generated.trace.get("kind", "inspiration")), "seed": seed},
                )
            )
        admitted, budget_rejections, token_count, token_omitted = _limit_arm_candidates(candidates, budget)
        rejected.extend(budget_rejections)
        return SearchArmResult(
            candidates=tuple(admitted),
            paths={item.candidate_uri: paths[item.candidate_uri] for item in admitted},
            budgets_requested=budget.to_dict(),
            budgets_consumed={
                "proposals": min(proposal.budget_consumed, budget.max_expansions),
                "expansions": min(proposal.budget_consumed, budget.max_expansions),
                "results": len(admitted),
                "tokens": token_count,
                "hops": 0,
            },
            rejected_items=tuple(rejected),
            truncated=bool(budget_rejections) or len(proposal.proposals) > len(admitted),
            omitted=token_omitted + max(0, len(proposal.proposals) - len(admitted)),
            seed=seed,
        )


AnalogySearchArm = SeededRandomWalkSearchArm


class SearchOrchestra:
    """Coordinate fixed arm allocations, deterministic ranking, and replay output."""

    def __init__(self, snapshot: SearchSnapshot | ConceptStore, arms: Sequence[SearchArm] | None = None) -> None:
        self.snapshot = snapshot
        selected = tuple(arms) if arms is not None else (TraversalSearchArm(), SeededRandomWalkSearchArm())
        if not selected:
            raise ValueError("SearchOrchestra requires at least one arm")
        identities = [(str(arm.name), str(arm.version)) for arm in selected]
        if len(set(identities)) != len(identities):
            raise ValueError("SearchOrchestra arm names and versions must be unique")
        self.arms = tuple(sorted(selected, key=lambda arm: (str(arm.name), str(arm.version))))

    def search(self, request: SearchRequest | dict[str, Any]) -> SearchResult:
        raw_request = _coerce_request(request)
        configured_specs = tuple((str(arm.name), str(arm.version)) for arm in self.arms)
        if raw_request.algorithm_allow_list:
            requested_specs = set(_normalize_arm_specs(raw_request.algorithm_allow_list))
            specs = tuple(spec for spec in configured_specs if spec in requested_specs)
        else:
            specs = configured_specs
        compiled = _compile(raw_request, specs)
        allow = set(compiled.algorithm_allow_list)
        selected_arms = tuple(
            arm for arm in self.arms if (str(arm.name), str(arm.version)) in allow
        )
        arm_results: dict[str, SearchArmResult] = {}
        errors: list[Mapping[str, Any]] = []
        all_candidates: list[SearchCandidate] = []
        rejected: list[Mapping[str, Any]] = []
        for index, arm in enumerate(selected_arms):
            identity = (str(arm.name), str(arm.version))
            budget = compiled.arm_allocations.get(identity[0])
            if budget is None:
                budget = SearchBudget(0, 0, compiled.request.budgets["max_hops"], 0)
            arm_seed = compiled.seed + index
            try:
                result = arm.search(compiled, self.snapshot, budget, arm_seed)
                if not isinstance(result, SearchArmResult):
                    raise TypeError("search arm returned an invalid result type")
            except Exception as exc:
                error = {
                    "arm_name": identity[0],
                    "arm_version": identity[1],
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
                result = SearchArmResult(
                    budgets_requested=budget.to_dict(),
                    errors=(error,),
                    truncated=True,
                    seed=arm_seed,
                )
                errors.append(error)
            else:
                errors.extend(result.errors)
            arm_result = _rebind_arm_result(result, identity, budget)
            arm_results[identity[0]] = arm_result
            rejected.extend(arm_result.rejected_items)
            all_candidates.extend(arm_result.candidates)

        unique_candidates: list[SearchCandidate] = []
        seen_uris: set[str] = set()
        merge_order = sorted(
            all_candidates,
            key=lambda item: (item.arm_name, item.arm_version, item.candidate_uri),
        )
        for candidate in merge_order:
            if candidate.candidate_uri in seen_uris:
                rejected.append({"reason": "duplicate_candidate", "candidate_uri": candidate.candidate_uri})
                continue
            seen_uris.add(candidate.candidate_uri)
            unique_candidates.append(candidate)

        ranked = _rank_candidates(unique_candidates, compiled, self.snapshot)
        final_results, final_omitted, final_truncated, final_tokens = _enforce_result_budget(
            ranked, compiled.request.budgets["max_results"], compiled.request.budgets["max_tokens"]
        )
        rejected_counts = _count_rejections(rejected)
        consumed = _consumed_budgets(arm_results, compiled.request.budgets, len(final_results), final_tokens)
        omitted = sum(result.omitted for result in arm_results.values()) + final_omitted
        truncated = final_truncated or any(result.truncated for result in arm_results.values()) or bool(omitted)
        algorithm_versions = {name: version for name, version in compiled.algorithm_allow_list}
        heuristic_versions = {
            "relevance": "relevance/v1",
            "novelty": "novelty/v1",
            "diversity": "diversity/v1",
            "ranking": "ranking/v1",
        }
        heuristic_versions.update({str(key): str(value) for key, value in compiled.request.score_versions.items()})
        seeds = {name: compiled.seed + index for index, (name, _version) in enumerate(compiled.algorithm_allow_list)}
        return SearchResult(
            query_hash=compiled.query_hash,
            graph_snapshot_hash=str(self.snapshot.snapshot_hash(compiled.namespace)),
            algorithm_versions=algorithm_versions,
            heuristic_versions=heuristic_versions,
            seeds=seeds,
            budgets_requested=dict(compiled.request.budgets),
            budgets_consumed=consumed,
            results=tuple(final_results),
            rejected_by_reason=rejected_counts,
            errors=tuple(errors),
            omitted=omitted,
            truncated=truncated,
            arm_results=arm_results,
        )


def compile_query(request: SearchRequest | dict[str, Any]) -> CompiledSearchRequest:
    """Compile a request into a canonical query and fixed default arm allocations."""

    return _compile(_coerce_request(request), None)


def _compile(request: SearchRequest, arm_specs: Sequence[tuple[str, str]] | None) -> CompiledSearchRequest:
    if not isinstance(request.namespace, str) or _NAMESPACE_RE.fullmatch(request.namespace) is None:
        raise ValidationError("namespace must match the Concept OS namespace grammar")
    if not isinstance(request.query_text, str):
        raise ValidationError("query_text must be a string")
    if not request.query_text and not request.anchor_uris:
        raise ValidationError("search requires query_text or anchor_uris")
    if set(request.required_edge_families) & set(request.forbidden_edge_families):
        raise ValidationError("an edge family cannot be both required and forbidden")
    if set(request.required_relations) & set(request.forbidden_relations):
        raise ValidationError("a relation cannot be both required and forbidden")
    if not set(request.desired_output_kinds).issubset(NODE_TYPES):
        raise ValidationError("desired_output_kinds contains an unknown node type")
    if not set(request.required_edge_families).issubset(EDGE_FAMILIES):
        raise ValidationError("required_edge_families contains an unknown family")
    if not set(request.forbidden_edge_families).issubset(EDGE_FAMILIES):
        raise ValidationError("forbidden_edge_families contains an unknown family")
    if not set(request.required_relations).issubset(_ALL_RELATIONS):
        raise ValidationError("required_relations contains an unknown relation")
    if not set(request.forbidden_relations).issubset(_ALL_RELATIONS):
        raise ValidationError("forbidden_relations contains an unknown relation")
    if any(_uri_namespace(_uri_text(uri)) != request.namespace for uri in request.anchor_uris):
        raise ValidationError("anchor URI namespace must match request namespace")
    budgets = _request_budgets(request)
    specs = _normalize_arm_specs(request.algorithm_allow_list) if arm_specs is None else tuple(arm_specs)
    specs = tuple(dict.fromkeys(specs))
    if not specs:
        raise ValidationError("at least one search arm must be allow-listed")
    allocations = {
        name: SearchBudget(
            max_expansions=_split_budget(budgets["max_expansions"], len(specs), index),
            max_results=_split_budget(budgets["max_results"], len(specs), index),
            max_hops=budgets["max_hops"],
            max_tokens=_split_budget(budgets["max_tokens"], len(specs), index),
        )
        for index, (name, _version) in enumerate(specs)
    }
    constraints = dict(request.constraints)
    constraints.update({
        "namespace": request.namespace,
        "disclosure_policy": request.disclosure_policy,
        "desired_output_kinds": tuple(request.desired_output_kinds),
        "required_edge_families": tuple(request.required_edge_families),
        "forbidden_edge_families": tuple(request.forbidden_edge_families),
        "required_relations": tuple(request.required_relations),
        "forbidden_relations": tuple(request.forbidden_relations),
        "representation_requirements": tuple(request.representation_requirements),
    })
    canonical_request = request.to_dict()
    if request.algorithm_allow_list:
        canonical_request["algorithm_allow_list"] = [
            {"name": name, "version": version}
            for name, version in _normalize_arm_specs(request.algorithm_allow_list)
        ]
    query_hash = content_hash(canonical_json(cast(Any, canonical_request)))
    return CompiledSearchRequest(
        request=request,
        query_hash=query_hash,
        original_query_text=request.query_text,
        anchor_uris=tuple(_uri_text(uri) for uri in request.anchor_uris),
        constraints=constraints,
        arm_allocations=allocations,
        algorithm_allow_list=specs,
    )


def _coerce_request(request: SearchRequest | dict[str, Any]) -> SearchRequest:
    if isinstance(request, SearchRequest):
        return request
    if isinstance(request, dict):
        return SearchRequest(**request)
    raise TypeError("search request must be SearchRequest or dict")


def _normalize_arm_specs(values: Sequence[Any]) -> tuple[tuple[str, str], ...]:
    if not values:
        return _ARM_SPECS
    specs: list[tuple[str, str]] = []
    for value in values:
        if isinstance(value, Mapping):
            name = value.get("name")
            version = value.get("version")
        elif isinstance(value, Sequence) and not isinstance(value, str) and len(value) == 2:
            name, version = value
        else:
            raise ValidationError("algorithm_allow_list entries require name and version")
        if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
            raise ValidationError("algorithm_allow_list entries require non-empty name and version")
        specs.append((name, version))
    if len(set(specs)) != len(specs):
        raise ValidationError("algorithm_allow_list cannot contain duplicate arm identities")
    return tuple(specs)


def _request_budgets(request: SearchRequest) -> dict[str, int]:
    required = ("max_expansions", "max_results", "max_hops", "max_tokens")
    result: dict[str, int] = {}
    for name in required:
        value = request.budgets.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValidationError(f"budgets.{name} must be a positive integer")
        result[name] = value
    return result


def _split_budget(total: int, count: int, index: int) -> int:
    return total // count + int(index < total % count)


def _allowed_families(request: CompiledSearchRequest) -> tuple[str, ...]:
    required = tuple(request.request.required_edge_families)
    if required:
        return tuple(sorted(required))
    forbidden = set(request.request.forbidden_edge_families)
    return tuple(sorted(set(EDGE_FAMILIES) - forbidden))


def _allowed_relations(request: CompiledSearchRequest) -> tuple[str, ...]:
    required = tuple(request.request.required_relations)
    if required:
        return tuple(sorted(required))
    forbidden = set(request.request.forbidden_relations)
    return tuple(relation for relation in _ALL_RELATIONS if relation not in forbidden)


def _matching_roots(request: CompiledSearchRequest, snapshot: SearchSnapshot) -> tuple[str, ...]:
    tokens = set(_TOKEN_RE.findall(request.original_query_text.casefold()))
    matches: list[str] = []
    for node in snapshot.iter_nodes(NodeQuery(namespace=request.namespace)):
        if not tokens or tokens.issubset(set(_TOKEN_RE.findall(_node_text(node).casefold()))):
            matches.append(_uri_text(node.id))
    return tuple(sorted(matches))


def _candidate_matches(request: CompiledSearchRequest, candidate: NodeEnvelope, trace: Mapping[str, Any]) -> bool:
    if candidate.namespace != request.namespace or candidate.type not in request.request.desired_output_kinds:
        return False
    representations = {
        str(item.get("kind"))
        for item in candidate.representations
        if isinstance(item, Mapping) and isinstance(item.get("kind"), str)
    }
    if not set(request.request.representation_requirements).issubset(representations):
        return False
    required_tags = request.request.constraints.get("required_domain_tags", ())
    candidate_tags = set(getattr(candidate.payload, "domain_tags", ()))
    if not set(required_tags).issubset(candidate_tags):
        return False
    forbidden_tags = request.request.constraints.get("forbidden_domain_tags", ())
    if candidate_tags.intersection(set(forbidden_tags)):
        return False
    trace_families = {
        str(step.get("family")) for step in _trace_steps(trace) if isinstance(step, Mapping)
    }
    trace_relations = {
        str(step.get("relation")) for step in _trace_steps(trace) if isinstance(step, Mapping)
    }
    return (
        (not request.request.required_edge_families or set(request.request.required_edge_families).issubset(trace_families))
        and (not request.request.required_relations or set(request.request.required_relations).issubset(trace_relations))
    )


def _rejection_reason(request: CompiledSearchRequest, candidate: NodeEnvelope) -> str:
    if candidate.type not in request.request.desired_output_kinds:
        return "undesired_output_kind"
    if candidate.namespace != request.namespace:
        return "namespace_disclosure"
    if request.request.representation_requirements:
        return "missing_representation"
    if request.request.constraints.get("required_domain_tags"):
        return "missing_required_domain_tag"
    if request.request.required_relations:
        return "missing_required_relation"
    return "constraint_mismatch"


def _trace_steps(trace: Mapping[str, Any]) -> Sequence[Any]:
    steps = trace.get("steps", ())
    return steps if isinstance(steps, Sequence) and not isinstance(steps, str) else ()


def _limit_arm_candidates(
    candidates: Sequence[SearchCandidate], budget: SearchBudget
) -> tuple[tuple[SearchCandidate, ...], tuple[Mapping[str, Any], ...], int, int]:
    admitted: list[SearchCandidate] = []
    rejected: list[Mapping[str, Any]] = []
    tokens = 0
    omitted = 0
    for candidate in candidates:
        if len(admitted) >= budget.max_results:
            rejected.append({"reason": "arm_result_budget_exceeded", "candidate_uri": candidate.candidate_uri})
            omitted += 1
            continue
        cost = _estimate_tokens(candidate.to_dict())
        if tokens + cost > budget.max_tokens:
            rejected.append({"reason": "serialized_budget_exceeded", "candidate_uri": candidate.candidate_uri})
            omitted += 1
            continue
        admitted.append(candidate)
        tokens += cost
    return tuple(admitted), tuple(rejected), tokens, omitted


def _rebind_arm_result(result: SearchArmResult, identity: tuple[str, str], budget: SearchBudget) -> SearchArmResult:
    raw_candidates = tuple(
        SearchCandidate(
            candidate=item.candidate,
            candidate_uri=item.candidate_uri,
            arm_name=identity[0],
            arm_version=identity[1],
            why=item.why,
            cost=item.cost,
            metadata=item.metadata,
        )
        for item in result.candidates
    )
    candidates, budget_rejections, token_count, budget_omitted = _limit_arm_candidates(raw_candidates, budget)
    consumed = {str(key): max(0, int(value)) for key, value in result.budgets_consumed.items()}
    for key, limit in (("expansions", budget.max_expansions), ("results", budget.max_results), ("tokens", budget.max_tokens)):
        if key in consumed:
            consumed[key] = min(consumed[key], limit)
    consumed.setdefault("results", len(candidates))
    consumed.setdefault("tokens", token_count)
    requested = dict(result.budgets_requested) or budget.to_dict()
    return SearchArmResult(
        candidates=candidates,
        paths={item.candidate_uri: result.paths[item.candidate_uri] for item in candidates if item.candidate_uri in result.paths},
        budgets_requested=requested,
        budgets_consumed=consumed,
        rejected_items=(*result.rejected_items, *budget_rejections),
        truncated=result.truncated or bool(budget_rejections),
        errors=result.errors,
        omitted=result.omitted + budget_omitted,
        seed=result.seed,
    )


def _rank_candidates(
    candidates: Sequence[SearchCandidate], request: CompiledSearchRequest, snapshot: SearchSnapshot
) -> tuple[RankedSearchItem, ...]:
    first_arm: set[str] = set()
    scored: list[tuple[Decimal, tuple[str, str, str], RankedSearchItem]] = []
    for candidate in sorted(candidates, key=lambda item: (item.arm_name, item.arm_version, item.candidate_uri)):
        relevance = _relevance(candidate, request)
        novelty = float(score_novelty(candidate.candidate, snapshot).novelty_score)
        coherence = _bounded_float(candidate.metadata.get("coherence", 1.0))
        diversity = 1.0 if candidate.arm_name not in first_arm else 0.25
        first_arm.add(candidate.arm_name)
        cost = min(1.0, candidate.cost / max(1, request.request.budgets["max_expansions"]))
        node = _candidate_node(candidate.candidate)
        provenance = 1.0 if node is not None and node.provenance_refs and candidate.why else 0.0
        vector = ScoreVector(
            relevance=_score_string(relevance),
            novelty=_score_string(novelty),
            coherence=_score_string(coherence),
            diversity_contribution=_score_string(diversity),
            cost=_score_string(cost),
            provenance_completeness=_score_string(provenance),
        )
        scalar = _scalar_score(vector, request.request.ranking_weights)
        item = RankedSearchItem(
            candidate_uri=candidate.candidate_uri,
            rank=0,
            score_components=vector,
            why=candidate.why,
            candidate=candidate.candidate,
            arm_name=candidate.arm_name,
            arm_version=candidate.arm_version,
            scalar_score=_decimal_string(scalar),
        )
        scored.append((scalar, (candidate.arm_name, candidate.arm_version, candidate.candidate_uri), item))
    scored.sort(key=lambda entry: (-entry[0], entry[1][0], entry[1][1], entry[1][2]))
    return tuple(
        RankedSearchItem(
            candidate_uri=item.candidate_uri,
            rank=index,
            score_components=item.score_components,
            why=item.why,
            candidate=item.candidate,
            arm_name=item.arm_name,
            arm_version=item.arm_version,
            scalar_score=item.scalar_score,
        )
        for index, (_score, _key, item) in enumerate(scored, start=1)
    )


def _scalar_score(vector: ScoreVector, weights: Mapping[str, Any]) -> Decimal:
    values = vector.to_dict()
    total = Decimal("0")
    for name in _SCORE_COMPONENTS:
        weight = _decimal(weights.get(name, "0"))
        value = _decimal(values[name])
        total += -value * weight if name == "cost" else value * weight
    return total


def _enforce_result_budget(
    ranked: Sequence[RankedSearchItem], max_results: int, max_tokens: int
) -> tuple[tuple[RankedSearchItem, ...], int, bool, int]:
    selected: list[RankedSearchItem] = []
    omitted = 0
    tokens = 0
    truncated = False
    for item in ranked:
        if len(selected) >= max_results:
            omitted += 1
            truncated = True
            continue
        item_tokens = _estimate_tokens(item.to_dict())
        if tokens + item_tokens > max_tokens:
            omitted += 1
            truncated = True
            continue
        selected.append(item)
        tokens += item_tokens
    return tuple(selected), omitted, truncated, tokens


def _consumed_budgets(
    arm_results: Mapping[str, SearchArmResult], requested: Mapping[str, int], result_count: int, tokens: int
) -> dict[str, int]:
    expansions = sum(min(int(result.budgets_consumed.get("expansions", 0)), requested["max_expansions"]) for result in arm_results.values())
    arm_tokens = sum(int(result.budgets_consumed.get("tokens", 0)) for result in arm_results.values())
    hops = max((int(result.budgets_consumed.get("hops", 0)) for result in arm_results.values()), default=0)
    consumed_tokens = min(max(tokens, arm_tokens), requested["max_tokens"])
    return {
        "max_expansions": min(expansions, requested["max_expansions"]),
        "max_results": result_count,
        "max_hops": min(hops, requested["max_hops"]),
        "max_tokens": consumed_tokens,
        "expansions": min(expansions, requested["max_expansions"]),
        "results": result_count,
        "tokens": consumed_tokens,
    }


def _count_rejections(items: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = str(item.get("reason", "unspecified"))
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _candidate_node(candidate: Any) -> NodeEnvelope | None:
    if isinstance(candidate, NodeEnvelope):
        return candidate
    if isinstance(candidate, Proposal):
        return candidate.node
    node = getattr(candidate, "node", None)
    return node if isinstance(node, NodeEnvelope) else None


def _candidate_uri(candidate: Any) -> str:
    node = _candidate_node(candidate)
    if node is not None:
        return _uri_text(node.id)
    raw = getattr(candidate, "candidate_uri", getattr(candidate, "id", getattr(candidate, "uri", "")))
    return _uri_text(raw) if raw else ""


def _node_text(node: NodeEnvelope) -> str:
    payload = node.payload
    values = [getattr(payload, name, "") for name in ("label", "description", "proposition", "scope")]
    return " ".join(str(value) for value in values if value)


def _relevance(candidate: SearchCandidate, request: CompiledSearchRequest) -> float:
    tokens = _TOKEN_RE.findall(request.original_query_text.casefold())
    if not tokens:
        return 0.5
    node = _candidate_node(candidate.candidate)
    if node is None:
        return 0.0
    words = set(_TOKEN_RE.findall(_node_text(node).casefold()))
    return sum(token in words for token in tokens) / len(tokens)


def _bounded_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return min(1.0, max(0.0, float(value)))


def _score_string(value: float) -> str:
    decimal = Decimal(str(_bounded_float(value))).quantize(_SCALE, rounding=ROUND_HALF_UP)
    return format(decimal, "f")


def _decimal(value: Any) -> Decimal:
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"ranking weight must be numeric: {value!r}") from exc
    if not decimal.is_finite():
        raise ValidationError("ranking weight must be finite")
    return decimal


def _decimal_string(value: Decimal) -> str:
    return format(value.quantize(_SCALE, rounding=ROUND_HALF_UP), "f")


def _estimate_tokens(value: Any) -> int:
    encoded = canonical_json(cast(Any, _jsonable(value)))
    return max(1, math.ceil(len(encoded) / 16))


def _jsonable(value: Any) -> Any:
    if isinstance(value, ConceptURI):
        return value.uri
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def _uri_text(value: ConceptURI | str) -> str:
    return value.uri if isinstance(value, ConceptURI) else str(value)


def _uri_namespace(uri: str) -> str:
    return uri.removeprefix("concept://").split("/", 1)[0]
