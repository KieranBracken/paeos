from __future__ import annotations

from collections.abc import Sequence

from concept.ids import ConceptURI, edge_uri, node_uri
from concept.model import (
    Analogy,
    AnalogyEdgePayload,
    Concept,
    DerivationEdgePayload,
    EdgeEnvelope,
    Hypothesis,
    NodeEnvelope,
    RecombinationEdgePayload,
)
from concept.store import ConceptStore

PROVENANCE = "a" * 64
RECORDED_AT = "2026-09-05T12:00:00Z"


def concept(
    label: str,
    *,
    namespace: str = "demo",
    domain_tags: tuple[str, ...] = ("test",),
    vector: Sequence[float] | None = None,
) -> NodeEnvelope:
    payload = Concept(label=label, description=f"Description of {label}.", domain_tags=domain_tags)
    representations: tuple[object, ...] = ()
    if vector is not None:
        representations = ({"kind": "vector_ref", "values": list(vector)},)
    return _node(namespace, "Concept", payload, representations=representations)


def hypothesis(
    proposition: str,
    *,
    namespace: str = "demo",
    lifecycle: str = "candidate",
) -> NodeEnvelope:
    payload = Hypothesis(
        proposition=proposition,
        scope="test systems",
        assumptions=("bounded input",),
        expected_observations=("the result is observable",),
        falsifiers=("the result is absent",),
        lifecycle=lifecycle,
    )
    return _node(namespace, "Hypothesis", payload)


def analogy_node(*, namespace: str = "demo") -> NodeEnvelope:
    payload = Analogy(
        source_roles=("source",),
        target_roles=("target",),
        known_breaks=("not_yet_tested",),
    )
    return _node(namespace, "Analogy", payload)


def edge(
    source: NodeEnvelope,
    target: NodeEnvelope,
    *,
    family: str = "derivation",
    relation: str = "derived_from",
    role_name: str = "role",
    correspondence_index: int = 0,
    contribution_order: int = 0,
) -> EdgeEnvelope:
    if family == "derivation":
        payload: object = DerivationEdgePayload(
            operator_uri=source.id,
            trace_uri=target.id,
            input_order=contribution_order,
        )
    elif family == "analogy":
        payload = AnalogyEdgePayload(
            role_name=role_name,
            correspondence_index=correspondence_index,
        )
    elif family == "recombination":
        payload = RecombinationEdgePayload(
            contribution_role=role_name,
            contribution_order=contribution_order,
            heuristic_trace_uri=source.id,
            source_uris=(source.id, target.id),
        )
    else:
        raise AssertionError(f"unsupported family {family}")
    preimage = {
        "namespace": source.namespace,
        "family": family,
        "relation": relation,
        "source_uri": uri_text(source.id),
        "target_uri": uri_text(target.id),
        "schema_version": 1,
        "payload": payload.to_dict(),  # type: ignore[union-attr]
        "provenance_refs": [PROVENANCE],
    }
    return EdgeEnvelope(
        id=edge_uri(source.namespace, preimage),
        namespace=source.namespace,
        family=family,
        relation=relation,
        source_uri=source.id,
        target_uri=target.id,
        schema_version=1,
        payload=payload,
        provenance_refs=(PROVENANCE,),
        recorded_at=RECORDED_AT,
    )


def _node(
    namespace: str,
    node_type: str,
    payload: object,
    *,
    representations: tuple[object, ...] = (),
) -> NodeEnvelope:
    preimage = {
        "namespace": namespace,
        "type": node_type,
        "schema_version": 1,
        "payload": payload.to_dict(),  # type: ignore[union-attr]
        "representations": list(representations),
        "provenance_refs": [PROVENANCE],
    }
    return NodeEnvelope(
        id=node_uri(namespace, node_type, preimage),
        type=node_type,
        namespace=namespace,
        schema_version=1,
        payload=payload,
        representations=representations,
        provenance_refs=(PROVENANCE,),
        recorded_at=RECORDED_AT,
    )


def append(store: ConceptStore, nodes: Sequence[NodeEnvelope], edges: Sequence[EdgeEnvelope] = ()) -> None:
    store.append_nodes_and_edges(tuple(nodes), tuple(edges))


def uri_text(value: ConceptURI | str) -> str:
    return value.uri if isinstance(value, ConceptURI) else value
