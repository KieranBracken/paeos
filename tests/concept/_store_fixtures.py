from __future__ import annotations

from collections.abc import Mapping

from concept.ids import ConceptURI, edge_uri, node_uri, outbox_uri
from concept.model import (
    Concept,
    DerivationEdgePayload,
    EdgeEnvelope,
    Hypothesis,
    NodeEnvelope,
)
from concept.store import CandidateOutboxEvent

RECORDED_AT = "2026-09-04T20:00:00Z"
PROVENANCE = "a" * 64


def concept_node(
    label: str,
    *,
    namespace: str = "demo",
    recorded_at: str = RECORDED_AT,
) -> NodeEnvelope:
    payload = Concept(label=label, description=f"Description of {label}.", domain_tags=("test",))
    preimage: dict[str, object] = {
        "namespace": namespace,
        "type": "Concept",
        "schema_version": 1,
        "payload": payload.to_dict(),
        "representations": [],
        "provenance_refs": [PROVENANCE],
    }
    return NodeEnvelope(
        id=node_uri(namespace, "Concept", preimage),
        type="Concept",
        namespace=namespace,
        schema_version=1,
        payload=payload,
        representations=(),
        provenance_refs=(PROVENANCE,),
        recorded_at=recorded_at,
    )


def hypothesis_node(
    proposition: str = "A bounded rule reduces oscillation.",
    *,
    namespace: str = "demo",
) -> NodeEnvelope:
    payload = Hypothesis(
        proposition=proposition,
        scope="toy systems",
        assumptions=("fixed sampling",),
        lineage=(),
        expected_observations=("amplitude decreases",),
        falsifiers=("amplitude increases",),
        lifecycle="candidate",
        score_snapshot={"novelty": "0.80"},
    )
    preimage: dict[str, object] = {
        "namespace": namespace,
        "type": "Hypothesis",
        "schema_version": 1,
        "payload": payload.to_dict(),
        "representations": [],
        "provenance_refs": [PROVENANCE],
    }
    return NodeEnvelope(
        id=node_uri(namespace, "Hypothesis", preimage),
        type="Hypothesis",
        namespace=namespace,
        schema_version=1,
        payload=payload,
        representations=(),
        provenance_refs=(PROVENANCE,),
        recorded_at=RECORDED_AT,
    )


def derivation_edge(source: NodeEnvelope, target: NodeEnvelope) -> EdgeEnvelope:
    source_uri = source.id.uri
    target_uri = target.id.uri
    payload = DerivationEdgePayload(
        operator_uri=source_uri,
        trace_uri=target_uri,
        input_order=0,
    )
    preimage: dict[str, object] = {
        "namespace": source.namespace,
        "family": "derivation",
        "relation": "derived_from",
        "source_uri": source_uri,
        "target_uri": target_uri,
        "schema_version": 1,
        "payload": payload.to_dict(),
        "provenance_refs": [PROVENANCE],
    }
    return EdgeEnvelope(
        id=edge_uri(source.namespace, preimage),
        namespace=source.namespace,
        family="derivation",
        relation="derived_from",
        source_uri=source_uri,
        target_uri=target_uri,
        schema_version=1,
        payload=payload,
        provenance_refs=(PROVENANCE,),
        recorded_at=RECORDED_AT,
    )


def outbox_event(
    hypothesis: NodeEnvelope,
    *,
    candidate: Mapping[str, object] | None = None,
    namespace: str | None = None,
    event_type: str = "EMITTED",
) -> CandidateOutboxEvent:
    event_namespace = namespace or hypothesis.namespace
    event_candidate = dict(candidate or {"proposal": "test"})
    preimage: dict[str, object] = {
        "namespace": event_namespace,
        "hypothesis_uri": hypothesis.id.uri,
        "event_type": event_type,
        "schema_version": 1,
        "candidate": event_candidate,
    }
    return CandidateOutboxEvent(
        uri=outbox_uri(event_namespace, preimage),
        namespace=event_namespace,
        hypothesis_uri=hypothesis.id.uri,
        event_type=event_type,
        schema_version=1,
        candidate=event_candidate,
        recorded_at=RECORDED_AT,
    )


def typed_uri(uri: str) -> ConceptURI:
    parts = uri.removeprefix("concept://").split("/")
    return ConceptURI(uri, parts[0], parts[1], parts[2])
