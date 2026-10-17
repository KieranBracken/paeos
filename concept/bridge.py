"""Candidate-only, append-only boundary for exporting Concept OS hypotheses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from concept.ids import (
    ConceptURI,
    JsonObject,
    JsonValue,
    canonical_json,
    content_hash,
    outbox_uri,
    validate_concept_uri,
)
from concept.model import CandidateHypothesisEnvelope, Hypothesis, NodeEnvelope, ScoreVector
from concept.store import CandidateOutboxEvent, ConceptStore

__all__ = [
    "CandidateExportBoundaryError",
    "MissingFalsifierError",
    "TruthBearingStatusForbiddenError",
    "build_candidate_envelope",
    "emit_candidate",
]

_SCHEMA_VERSION = 1
_SCORE_FIELDS = frozenset(
    {"relevance", "novelty", "coherence", "diversity_contribution", "cost", "provenance_completeness"}
)
_TRUTH_STATUSES = frozenset(
    {"validated", "proven", "canonical", "accepted", "verified", "ground_truth", "promoted"}
)


class CandidateExportBoundaryError(ValueError):
    """Base error for an export that cannot cross the candidate boundary."""


class MissingFalsifierError(CandidateExportBoundaryError):
    """Raised when a hypothesis has no explicit falsifier."""


class TruthBearingStatusForbiddenError(CandidateExportBoundaryError):
    """Raised when a proposal is labeled with a truth-bearing status."""


def build_candidate_envelope(
    store: ConceptStore,
    hypothesis_uri: str,
    evaluation_kind: str,
    *,
    source_concept_uris: Sequence[str] = (),
    source_analogy_uris: Sequence[str] = (),
    source_transformation_uris: Sequence[str] = (),
    sakg_reference_uris: Sequence[str] = (),
    source_refs: Sequence[str] | None = None,
    replay_manifest: Mapping[str, Any] | None = None,
    search_result: Any | None = None,
    generator_trace: Any | None = None,
    score_vectors: Mapping[str, Any] | ScoreVector | None = None,
    graph_snapshot_hash: str | None = None,
    content_hashes: Sequence[str] = (),
    proposal_status: str = "candidate_proposal",
    proposal_kind: str | None = None,
    status: str | None = None,
) -> CandidateHypothesisEnvelope:
    """Construct a deterministic proposal from a stored Hypothesis and replay metadata."""

    _require_status(proposal_kind if proposal_kind is not None else status or proposal_status)
    if not isinstance(evaluation_kind, str) or not evaluation_kind.strip():
        raise CandidateExportBoundaryError("requested evaluation kind is required")
    hypothesis = _load_hypothesis(store, hypothesis_uri)
    payload = hypothesis.payload
    if not isinstance(payload, Hypothesis):
        raise CandidateExportBoundaryError("hypothesis endpoint has an invalid payload")
    if not payload.scope.strip():
        raise CandidateExportBoundaryError("hypothesis scope is required")
    if not payload.assumptions:
        raise CandidateExportBoundaryError("hypothesis assumptions are required")
    if not payload.expected_observations:
        raise CandidateExportBoundaryError("expected observations are required")
    if not payload.falsifiers:
        raise MissingFalsifierError("candidate export requires at least one falsifier")

    hypothesis_id = validate_concept_uri(_uri_text(hypothesis.id))
    namespace = hypothesis_id.namespace
    categories: dict[str, Sequence[str]] = {
        "concept_uris": tuple(source_concept_uris),
        "analogy_uris": tuple(source_analogy_uris),
        "transformation_uris": tuple(source_transformation_uris),
    }
    if source_refs is not None:
        categories["source_uris"] = tuple(source_refs)
    local_sources = _validate_sources(store, namespace, categories)
    if not local_sources:
        lineage = tuple(uri for uri in payload.lineage if isinstance(uri, str) and uri.startswith("concept://"))
        local_sources = _validate_sources(store, namespace, {"source_uris": lineage})
    if not local_sources:
        raise CandidateExportBoundaryError("candidate export requires local provenance references")
    sakg_refs = _opaque_refs(sakg_reference_uris, "SAKG")
    if not sakg_refs:
        raise CandidateExportBoundaryError("candidate export requires a SAKG reference")

    snapshot = str(graph_snapshot_hash or store.snapshot_hash(namespace))
    manifest = _manifest(
        store,
        hypothesis,
        snapshot,
        replay_manifest=replay_manifest,
        search_result=search_result,
        generator_trace=generator_trace,
        sakg_refs=sakg_refs,
        categories=categories,
    )
    scores = _scores(score_vectors)
    _reject_confidence(manifest)
    hashes = tuple(content_hashes) or _source_hashes(store, hypothesis, local_sources)
    _validate_hashes(hashes)
    data: JsonObject = {
        "namespace": namespace,
        "schema_version": _SCHEMA_VERSION,
        "hypothesis_uri": hypothesis_id.uri,
        "proposition": payload.proposition,
        "scope": payload.scope,
        "assumptions": list(payload.assumptions),
        "expected_observations": list(payload.expected_observations),
        "falsifiers": list(payload.falsifiers),
        "source_refs": list(local_sources),
        "replay_manifest": cast(JsonValue, _jsonable(manifest)),
        "score_vectors": {"evidentiary": False, "components": cast(JsonValue, scores.to_dict())},
        "graph_snapshot_hash": snapshot,
        "content_hashes": list(hashes),
        "requested_evaluation_kind": evaluation_kind,
        "proposal_kind": "candidate_proposal",
        "authority": "exploratory",
        "trust": "untrusted_candidate",
    }
    return CandidateHypothesisEnvelope(
        envelope_id=outbox_uri(namespace, data),
        schema_version=_SCHEMA_VERSION,
        hypothesis_uri=hypothesis_id,
        proposition=payload.proposition,
        scope=payload.scope,
        assumptions=tuple(payload.assumptions),
        expected_observations=tuple(payload.expected_observations),
        falsifiers=tuple(payload.falsifiers),
        source_refs=tuple(local_sources),
        replay_manifest=cast(Mapping[str, Any], _jsonable(manifest)),
        score_vectors=scores,
        graph_snapshot_hash=snapshot,
        content_hashes=hashes,
        requested_evaluation_kind=evaluation_kind,
        proposal_kind="candidate_proposal",
        authority="exploratory",
        trust="untrusted_candidate",
    )


def emit_candidate(store: ConceptStore, envelope: CandidateHypothesisEnvelope) -> str:
    """Append one EMITTED event; ConceptStore supplies byte-identical idempotence."""

    if not isinstance(envelope, CandidateHypothesisEnvelope):
        raise TypeError("emit_candidate requires CandidateHypothesisEnvelope")
    if envelope.schema_version != _SCHEMA_VERSION:
        raise CandidateExportBoundaryError("unsupported candidate envelope schema version")
    _require_status(envelope.proposal_kind)
    if envelope.authority != "exploratory" or envelope.trust != "untrusted_candidate":
        raise TruthBearingStatusForbiddenError("candidate authority and trust are fixed exploratory values")
    if not envelope.falsifiers:
        raise MissingFalsifierError("candidate export requires at least one falsifier")
    candidate = cast(dict[str, object], _jsonable(envelope.to_dict()))
    _reject_confidence(candidate)
    hypothesis = validate_concept_uri(_uri_text(envelope.hypothesis_uri))
    event_data: JsonObject = {
        "namespace": hypothesis.namespace,
        "hypothesis_uri": hypothesis.uri,
        "event_type": "EMITTED",
        "schema_version": _SCHEMA_VERSION,
        "candidate": cast(JsonValue, candidate),
    }
    event = CandidateOutboxEvent(
        uri=outbox_uri(hypothesis.namespace, event_data),
        namespace=hypothesis.namespace,
        hypothesis_uri=hypothesis,
        event_type="EMITTED",
        schema_version=_SCHEMA_VERSION,
        candidate=candidate,
    )
    return store.append_outbox_event(event)


def _load_hypothesis(store: ConceptStore, uri: str) -> NodeEnvelope:
    try:
        parsed = validate_concept_uri(uri)
    except (TypeError, ValueError) as exc:
        raise CandidateExportBoundaryError("hypothesis URI is invalid") from exc
    if parsed.kind != "hypothesis":
        raise CandidateExportBoundaryError("candidate export requires a Hypothesis URI")
    node = store.get_node(parsed.uri)
    if node is None or node.type != "Hypothesis":
        raise CandidateExportBoundaryError("hypothesis endpoint is unavailable")
    return node


def _validate_sources(store: ConceptStore, namespace: str, categories: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    expected = {"concept_uris": "Concept", "analogy_uris": "Analogy", "transformation_uris": "Transformation"}
    result: list[str] = []
    for category, uris in categories.items():
        for raw_uri in uris:
            try:
                parsed = validate_concept_uri(raw_uri)
            except (TypeError, ValueError) as exc:
                raise CandidateExportBoundaryError(f"invalid source URI: {raw_uri!r}") from exc
            if parsed.namespace != namespace:
                raise CandidateExportBoundaryError("source URI crosses the namespace boundary")
            node = store.get_node(parsed.uri)
            if node is None:
                raise CandidateExportBoundaryError(f"source URI is unavailable: {parsed.uri}")
            wanted = expected.get(category)
            if wanted is not None and node.type != wanted:
                raise CandidateExportBoundaryError(f"{category} requires {wanted} nodes, got {node.type}")
            if parsed.uri not in result:
                result.append(parsed.uri)
    return tuple(result)


def _opaque_refs(values: Sequence[str], label: str) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip() or "://" not in value:
            raise CandidateExportBoundaryError(f"{label} references must be non-empty URI strings")
        if value not in result:
            result.append(value)
    return tuple(result)


def _manifest(
    store: ConceptStore,
    hypothesis: NodeEnvelope,
    snapshot: str,
    *,
    replay_manifest: Mapping[str, Any] | None,
    search_result: Any | None,
    generator_trace: Any | None,
    sakg_refs: Sequence[str],
    categories: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    manifest: dict[str, Any] = {}
    if search_result is not None:
        candidate = getattr(search_result, "replay_manifest", None)
        if isinstance(candidate, Mapping):
            manifest.update(_jsonable(candidate))
    if replay_manifest is not None:
        manifest.update(_jsonable(replay_manifest))
    if manifest.get("graph_snapshot_hash") not in (None, snapshot):
        raise CandidateExportBoundaryError("replay manifest snapshot does not match graph snapshot")
    manifest["graph_snapshot_hash"] = snapshot
    manifest.setdefault("query_hash", content_hash(canonical_json({"hypothesis_uri": _uri_text(hypothesis.id)})))
    manifest.setdefault("algorithm_versions", {"candidate-bridge": "v1"})
    manifest.setdefault("seeds", {"candidate-bridge": 0})
    why = manifest.get("why_paths", manifest.get("why"))
    if not why:
        why = {_uri_text(hypothesis.id): [{"kind": "lineage", "source_uris": list(getattr(hypothesis.payload, "lineage", ())), "relation": "candidate_provenance"}]}
    manifest["why_paths"] = _jsonable(why)
    manifest.setdefault("why", _jsonable(why))
    manifest["source_uris"] = {key: list(values) for key, values in categories.items() if key != "source_uris"}
    manifest["sakg_reference_uris"] = list(sakg_refs)
    manifest["generator_trace"] = _jsonable(generator_trace) if generator_trace is not None else []
    return manifest


def _source_hashes(store: ConceptStore, hypothesis: NodeEnvelope, source_uris: Sequence[str]) -> tuple[str, ...]:
    hashes: list[str] = []
    for uri in (_uri_text(hypothesis.id), *source_uris):
        node = store.get_node(uri)
        if node is None:
            raise CandidateExportBoundaryError(f"source disappeared during export: {uri}")
        data = node.to_dict()
        data.pop("id", None)
        data.pop("recorded_at", None)
        hashes.append(content_hash(canonical_json(cast(JsonValue, data))))
    return tuple(hashes)


def _scores(value: Mapping[str, Any] | ScoreVector | None) -> ScoreVector:
    if value is None:
        return ScoreVector()
    if isinstance(value, ScoreVector):
        return value
    raw: Mapping[str, Any] = value.get("components", value) if isinstance(value, Mapping) else {}
    _reject_confidence(raw)
    unknown = set(raw) - _SCORE_FIELDS - {"evidentiary"}
    if unknown:
        raise CandidateExportBoundaryError(f"unknown score vector fields: {sorted(unknown)}")
    return ScoreVector(**cast(Any, {field: str(raw[field]) for field in _SCORE_FIELDS if field in raw}))


def _require_status(status: str) -> None:
    if status != "candidate_proposal" or status in _TRUTH_STATUSES:
        raise TruthBearingStatusForbiddenError("only candidate_proposal may cross the boundary")


def _validate_hashes(values: Sequence[str]) -> None:
    for value in values:
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise CandidateExportBoundaryError("content hashes must be lowercase SHA-256 strings")


def _reject_confidence(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() == "confidence":
                raise CandidateExportBoundaryError("confidence is not an admissible candidate field")
            _reject_confidence(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _reject_confidence(item)


def _jsonable(value: Any) -> Any:
    if isinstance(value, ConceptURI):
        return value.uri
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise CandidateExportBoundaryError(f"non-serializable candidate value: {type(value).__name__}")


def _uri_text(value: ConceptURI | str) -> str:
    return value.uri if isinstance(value, ConceptURI) else value
