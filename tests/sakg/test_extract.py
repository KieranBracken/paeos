from __future__ import annotations

from hashlib import sha256

import pytest
from sakg.extract import extract_artifact, extract_evidence_ref, extract_nodes
from sakg.store import validate_node_envelope

EVIDENCE = sha256(b"extract-evidence").hexdigest()


@pytest.mark.parametrize(
    ("kind", "node_type"),
    (
        ("l06", "TradeOff"),
        ("l04", "Option"),
        ("l08", "Component"),
        ("l11", "Constraint"),
        ("decision-graph", "Decision"),
        ("scar-graph", "Scar"),
    ),
)
def test_layer_artifacts_extract_to_universal_typed_nodes(kind: str, node_type: str) -> None:
    result = extract_artifact(
        {
            "kind": kind,
            "name": "Example",
            "summary": "A stable extraction.",
            "evidence": [EVIDENCE],
        },
        namespace="demo",
        evidence_hashes=(EVIDENCE,),
    )
    assert result.node is not None
    assert result.node["type"] == node_type
    assert result.node["status"] == "candidate"
    validate_node_envelope(result.node, "demo")


def test_cas_hashes_become_evidence_ref_nodes_and_sequence_is_deterministic() -> None:
    first = extract_evidence_ref(EVIDENCE, namespace="demo")
    second = extract_nodes(({"kind": "cas_hash", "hash": EVIDENCE},), namespace="demo")
    assert first.node == second[0].node
    assert first.node is not None and first.node["type"] == "EvidenceRef"
    validate_node_envelope(first.node, "demo")
