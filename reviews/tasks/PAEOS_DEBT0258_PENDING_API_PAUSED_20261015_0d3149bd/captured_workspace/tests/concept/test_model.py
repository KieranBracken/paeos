from dataclasses import FrozenInstanceError

import pytest
from concept.ids import ConceptURI
from concept.model import (
    Analogy,
    AnalogyEdgePayload,
    CandidateHypothesisEnvelope,
    Concept,
    DerivationEdgePayload,
    EdgeEnvelope,
    Hypothesis,
    NodeEnvelope,
    ScoreVector,
    SearchRequest,
    SearchResult,
    Transformation,
    ValidationError,
    from_dict,
)

NODE_URI = ConceptURI("concept://demo/concept/00000000000000000000000000", "demo", "concept", "00000000000000000000000000")
OTHER_NODE_URI = ConceptURI("concept://demo/concept/11111111111111111111111111", "demo", "concept", "11111111111111111111111111")
ANALOGY_URI = ConceptURI("concept://demo/analogy/00000000000000000000000000", "demo", "analogy", "00000000000000000000000000")
TRANSFORMATION_URI = ConceptURI("concept://demo/transformation/00000000000000000000000000", "demo", "transformation", "00000000000000000000000000")
TRACE_URI = ConceptURI("concept://demo/trace/11111111111111111111111111", "demo", "trace", "11111111111111111111111111")


def concept_node() -> NodeEnvelope:
    return NodeEnvelope(
        id=NODE_URI,
        type="Concept",
        namespace="demo",
        schema_version=1,
        payload=Concept(label="Feedback", description="A response loop.", domain_tags=("systems",)),
        representations=(),
        provenance_refs=("a" * 64,),
        recorded_at="2026-09-04T20:00:00Z",
    )


def test_node_envelope_is_frozen_and_round_trips() -> None:
    node = concept_node()
    assert from_dict(node.to_dict()) == node
    assert node.payload.domain_tags == ("systems",)
    with pytest.raises(FrozenInstanceError):
        node.namespace = "other"


def test_transformation_rejects_non_declarative_null_implementation() -> None:
    with pytest.raises(ValidationError):
        Transformation(
            operator_name="invert",
            operator_version="1",
            input_signature={},
            output_signature={},
            preconditions=("bounded",),
            postconditions=("bounded",),
            parameters_schema={},
            determinism="pure",
            implementation_ref=None,
        )


def test_analogy_requires_known_break_or_explicit_marker() -> None:
    with pytest.raises(ValidationError):
        Analogy(
            source_roles=("river",),
            target_roles=("network",),
            correspondences=(),
            preserved_relations=(),
            known_breaks=(),
            metric_snapshot={},
            heuristic_uri="concept://demo/inspiration-heuristic/00000000000000000000000000",
        )


def test_hypothesis_lifecycle_is_exploratory_closed_set() -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            proposition="A rule works.",
            scope="toy",
            assumptions=("fixed",),
            lineage=(),
            expected_observations=("output changes",),
            falsifiers=("output does not change",),
            lifecycle="validated",
            score_snapshot={},
        )


def test_edge_envelope_rejects_self_loops_and_direct_concept_analogy() -> None:
    with pytest.raises(ValidationError):
        EdgeEnvelope(
            id=ConceptURI("concept://demo/edge/00000000000000000000000000", "demo", "edge", "00000000000000000000000000"),
            namespace="demo",
            family="analogy",
            relation="has_source",
            source_uri=NODE_URI,
            target_uri=OTHER_NODE_URI,
            schema_version=1,
            payload=AnalogyEdgePayload(role_name="source", correspondence_index=0),
            provenance_refs=("b" * 64,),
            recorded_at="2026-09-04T20:00:00Z",
        )


def test_edge_envelope_round_trip() -> None:
    edge = EdgeEnvelope(
        id=ConceptURI("concept://demo/edge/00000000000000000000000000", "demo", "edge", "00000000000000000000000000"),
        namespace="demo",
        family="derivation",
        relation="derived_from",
        source_uri=NODE_URI,
        target_uri=TRANSFORMATION_URI,
        schema_version=1,
        payload=DerivationEdgePayload(operator_uri=TRANSFORMATION_URI, trace_uri=TRACE_URI, input_order=0),
        provenance_refs=("c" * 64,),
        recorded_at="2026-09-04T20:00:00Z",
    )
    assert from_dict(edge.to_dict()) == edge


def test_search_and_candidate_envelopes_are_non_evidentiary() -> None:
    request = SearchRequest(namespace="demo", query_text="feedback", anchor_uris=(NODE_URI,), seed=7)
    assert request.to_dict()["namespace"] == "demo"
    result = SearchResult(
        query_hash="a" * 64,
        graph_snapshot_hash="b" * 64,
        algorithm_versions={},
        heuristic_versions={},
        seeds={},
        budgets_requested={},
        budgets_consumed={},
        results=(),
        rejected_by_reason={},
        errors=(),
        omitted=0,
        truncated=False,
    )
    assert "confidence" not in result.to_dict()
    scores = ScoreVector("0.8", "0.7", "0.6", "0.5", "0.1", "1.0")
    candidate = CandidateHypothesisEnvelope(
        envelope_id=ConceptURI("concept://demo/outbox/00000000000000000000000000", "demo", "outbox", "00000000000000000000000000"),
        schema_version=1,
        hypothesis_uri=ConceptURI("concept://demo/hypothesis/00000000000000000000000000", "demo", "hypothesis", "00000000000000000000000000"),
        proposition="A rule reduces oscillation.",
        scope="toy systems",
        assumptions=("fixed sampling",),
        expected_observations=("amplitude decreases",),
        falsifiers=("amplitude increases",),
        source_refs=(NODE_URI,),
        replay_manifest={"query_hash": "a" * 64},
        score_vectors=scores,
        graph_snapshot_hash="c" * 64,
        content_hashes=("d" * 64,),
        requested_evaluation_kind="bounded_experiment",
    )
    assert candidate.to_dict()["authority"] == "exploratory"
    assert candidate.to_dict()["score_vectors"]["evidentiary"] is False

