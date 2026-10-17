"""Test-only graph builders for typed traversal and neighborhood tests."""

from __future__ import annotations

from collections.abc import Mapping

from concept.ids import ConceptURI, edge_uri, node_uri
from concept.model import (
    AbstractionEdgePayload,
    Analogy,
    AnalogyEdgePayload,
    Concept,
    DerivationEdgePayload,
    EdgeEnvelope,
    ExemplificationEdgePayload,
    Hypothesis,
    NeighborhoodEdgePayload,
    NodeEnvelope,
    RecombinationEdgePayload,
    SemanticNeighborhood,
    Transformation,
)

RECORDED_AT = "2026-09-05T12:00:00Z"
PROVENANCE = "a" * 64


def _node(
    namespace: str,
    node_type: str,
    payload: object,
    *,
    recorded_at: str = RECORDED_AT,
) -> NodeEnvelope:
    preimage = {
        "namespace": namespace,
        "type": node_type,
        "schema_version": 1,
        "payload": payload.to_dict(),  # type: ignore[union-attr]
        "representations": [],
        "provenance_refs": [PROVENANCE],
    }
    return NodeEnvelope(
        id=node_uri(namespace, node_type, preimage),
        type=node_type,
        namespace=namespace,
        schema_version=1,
        payload=payload,
        representations=(),
        provenance_refs=(PROVENANCE,),
        recorded_at=recorded_at,
    )


def concept(label: str, *, namespace: str = "demo") -> NodeEnvelope:
    payload = Concept(label=label, description=f"Description of {label}.", domain_tags=("test",))
    return _node(namespace, "Concept", payload)


def analogy(label: str, *, namespace: str = "demo") -> NodeEnvelope:
    payload = Analogy(
        source_roles=(label,),
        target_roles=(f"{label}-target",),
        known_breaks=("not_yet_tested",),
    )
    return _node(namespace, "Analogy", payload)


def neighborhood(center: NodeEnvelope, *, namespace: str | None = None) -> NodeEnvelope:
    actual_namespace = namespace or center.namespace
    payload = SemanticNeighborhood(
        neighborhood_id=f"neighborhood-{center.id.token}",
        center_uri=center.id,
        distance_metric="typed-hop/v1",
        threshold="2",
        members=(),
    )
    return _node(actual_namespace, "SemanticNeighborhood", payload)


def hypothesis(label: str, *, namespace: str = "demo") -> NodeEnvelope:
    payload = Hypothesis(
        proposition=f"{label} is a bounded proposition.",
        scope="test systems",
        falsifiers=("the observation fails",),
    )
    return _node(namespace, "Hypothesis", payload)


def transformation(label: str, *, namespace: str = "demo") -> NodeEnvelope:
    payload = Transformation(
        operator_name=label,
        operator_version="1",
        input_signature={},
        output_signature={},
        implementation_ref="concept://demo/concept/00000000000000000000000000",
    )
    return _node(namespace, "Transformation", payload)


def edge(
    source: NodeEnvelope,
    target: NodeEnvelope,
    family: str,
    relation: str,
    *,
    edge_tag: str = "0",
) -> EdgeEnvelope:
    source_uri = source.id
    target_uri = target.id
    payload: object
    if family == "derivation":
        payload = DerivationEdgePayload(
            operator_uri=source_uri,
            trace_uri=target_uri,
            input_order=0,
        )
    elif family == "analogy":
        payload = AnalogyEdgePayload(role_name="role", correspondence_index=0)
    elif family == "recombination":
        payload = RecombinationEdgePayload(
            contribution_role="source",
            contribution_order=0,
            heuristic_trace_uri=source_uri,
            source_uris=(source_uri, target_uri),
        )
    elif family == "abstraction":
        payload = AbstractionEdgePayload(
            abstraction_operator_uri=source_uri,
            preserved_features=("feature",),
        )
    elif family == "exemplification":
        payload = ExemplificationEdgePayload(scope="test", source_provenance_ref=PROVENANCE)
    elif family == "neighborhood":
        payload = NeighborhoodEdgePayload(
            rank=1,
            component_distances={"graph": "0.10"},
            aggregate_distance="0.10",
            why=(),
        )
    else:
        raise AssertionError(f"unsupported test family: {family}")

    preimage = {
        "namespace": source.namespace,
        "family": family,
        "relation": relation,
        "source_uri": source_uri.uri,
        "target_uri": target_uri.uri,
        "schema_version": 1,
        "payload": payload.to_dict(),  # type: ignore[union-attr]
        "provenance_refs": [PROVENANCE],
    }
    return EdgeEnvelope(
        id=edge_uri(source.namespace, preimage),
        namespace=source.namespace,
        family=family,
        relation=relation,
        source_uri=source_uri,
        target_uri=target_uri,
        schema_version=1,
        payload=payload,
        provenance_refs=(PROVENANCE,),
        recorded_at=RECORDED_AT,
    )


def append_graph(store: object, nodes: tuple[NodeEnvelope, ...], edges: tuple[EdgeEnvelope, ...]) -> None:
    store.append_nodes_and_edges(nodes, edges)  # type: ignore[union-attr]


class MappingSnapshot:
    """Small cross-namespace snapshot double used where ConceptStore rejects such rows."""

    def __init__(
        self,
        nodes: tuple[NodeEnvelope, ...],
        edges: tuple[Mapping[str, object], ...],
        snapshot_hash: str = "b" * 64,
    ) -> None:
        self._nodes = {node.id.uri: node for node in nodes}
        self._edges = edges
        self._snapshot_hash = snapshot_hash

    def get_node(self, uri: str) -> NodeEnvelope | None:
        return self._nodes.get(uri)

    def iter_edges(self, query: object) -> tuple[Mapping[str, object], ...]:
        return self._edges

    def snapshot_hash(self, namespace: str) -> str:
        return self._snapshot_hash


def mapping_edge(
    edge_id: str,
    namespace: str,
    source_uri: ConceptURI | str,
    target_uri: ConceptURI | str,
    family: str = "derivation",
    relation: str = "derived_from",
) -> dict[str, object]:
    return {
        "id": edge_id,
        "namespace": namespace,
        "family": family,
        "relation": relation,
        "source_uri": source_uri.uri if isinstance(source_uri, ConceptURI) else source_uri,
        "target_uri": target_uri.uri if isinstance(target_uri, ConceptURI) else target_uri,
    }
