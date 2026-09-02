from __future__ import annotations

from sakg.extract import extract_nodes, extract_option


def test_rejected_l04_candidate_is_retained_as_an_option() -> None:
    source = {
        "kind": "l04",
        "name": "Rejected approach",
        "rejected": True,
        "rationale": "Fails the safety constraint.",
    }
    result = extract_option(source, namespace="demo")
    assert result.node is not None
    assert result.node["type"] == "Option"
    assert result.node["facets"]["decision_state"]["value"] == "rejected"
    assert result.node["facets"]["rejected"]["value"] is True


def test_rejected_option_is_not_filtered_from_batch_extraction() -> None:
    results = extract_nodes(
        ({"kind": "l04", "name": "Rejected", "decision_state": "rejected"},), namespace="demo"
    )
    assert len(results) == 1
    assert results[0].node is not None
    assert results[0].node["type"] == "Option"
