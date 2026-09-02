"""Corpus and query hashes are stable and change when inputs change."""

from __future__ import annotations

from sakg.project import project

REQUEST = {
    "method": "pattern_retrieval",
    "subject": "safe restart",
    "namespace": ["demo"],
    "budget": {"max_tokens": 500, "max_nodes": 4, "tier": "SUMMARY"},
    "filters": {"min_confidence": 0, "as_of": "2026-09-02T00:00:00Z", "status": ["canonical"]},
}
NODE = {
    "id": "sakg://demo/Pattern/01ARZ3NDEKTSV4RRFFQ69G5F01",
    "type": "Pattern",
    "namespace": "demo",
    "status": "canonical",
    "label": "Safe restart",
    "summary": "Restart from immutable state",
    "confidence": 0.95,
}


def test_hashes_are_reproducible_and_input_bound() -> None:
    first = project(REQUEST, (NODE,))
    second = project(REQUEST, (NODE,))
    assert first == second
    changed_request = {**REQUEST, "subject": "unsafe restart"}
    changed_corpus = {**NODE, "summary": "A different restart"}
    assert (
        project(changed_request, (NODE,))["provenance"]["query_hash"]
        != first["provenance"]["query_hash"]
    )
    assert (
        project(REQUEST, (changed_corpus,))["provenance"]["corpus_hash"]
        != first["provenance"]["corpus_hash"]
    )
