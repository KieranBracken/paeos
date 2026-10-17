from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kae.citation_pipeline import CasReferenceError, CitationLinkError, extract_citations, ingest_citations
from sakg.store import GraphStore


class MemoryCAS:
    def __init__(self, content: bytes) -> None:
        self.digest = hashlib.sha256(content).hexdigest()
        self.content = content

    def get(self, digest: str) -> bytes:
        if digest != self.digest:
            raise KeyError(digest)
        return self.content


def _node(namespace: str, kind: str, suffix: str) -> dict[str, object]:
    digest = hashlib.sha256(f"{kind}:{suffix}".encode()).hexdigest()
    return {
        "id": f"sakg://{namespace}/{kind}/{suffix.upper():0>26}", "type": kind, "namespace": namespace,
        "facets": {"source": {"value": "task22"}}, "label": f"{kind} {suffix}", "summary": "sealed historical anchor",
        "provenance": {"origin": {"system": "task22", "run_id": "r"}, "author_kind": "ingest",
                       "ingested_at": "2026-09-04T00:00:00Z", "source_hash": digest},
        "evidence": [{"hash": digest, "uri": f"cas://{digest}", "kind": "decision",
                       "reverification": "re-run historical admission"}], "status": "canonical", "confidence": 1.0,
        "valid_from": "2026-09-04T00:00:00Z", "valid_until": None, "falsifier": None,
        "coordinates": {"domain": ["paeos"]},
    }


def test_byte_exact_citations_mint_refs_and_typed_links(tmp_path: Path) -> None:
    content = b"Intro\n[1] RFC 9110 Section 5\nREFERENCE: Unicode caf\xc3\xa9\nTail\n"
    cas = MemoryCAS(content)
    db = tmp_path / "sakg.db"
    with GraphStore(db, "paeos-history") as store:
        decision, constraint = _node("paeos-history", "Decision", "1"), _node("paeos-history", "Constraint", "2")
        store.append_node(decision)
        store.append_node(constraint)
        report = ingest_citations(cas, [{"cas_hash": cas.digest, "uri": "rfc://9110", "decision_ids": [decision["id"]], "constraint_ids": [constraint["id"]]}], store)
        refs = [node for node in store.nodes() if node["type"] == "EvidenceRef"]
        edges = store.edges()
    assert report.to_dict() == {"sources_seen": 1, "citations_seen": 2, "nodes_appended": 2, "nodes_replayed": 0, "nodes_total": 2, "edges_appended": 4, "edges_replayed": 0, "edges_total": 4}
    assert refs[0]["facets"]["anchor"]["byte_start"] == content.index(b"RFC")
    assert refs[1]["facets"]["anchor"]["citation_hash"] == hashlib.sha256(b"Unicode caf\xc3\xa9").hexdigest()
    assert {edge["relation"] for edge in edges} == {"justified_by", "evidence"}
    assert all(edge["family"] in {"causal", "constraint"} for edge in edges)


def test_replay_is_idempotent_and_deterministic(tmp_path: Path) -> None:
    content = b"CITATION: first\n[2] second\n"
    cas = MemoryCAS(content)
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    with GraphStore(first, "paeos-history") as store:
        first_report = ingest_citations(cas, [{"cas_hash": cas.digest, "uri": "paper://x"}], store)
        second_report = ingest_citations(cas, [{"cas_hash": cas.digest, "uri": "paper://x"}], store)
        snapshot = (store.nodes(), store.edges())
    with GraphStore(second, "paeos-history") as store:
        other_report = ingest_citations(cas, [{"cas_hash": cas.digest, "uri": "paper://x"}], store)
        assert snapshot != ((), ())
        assert other_report == first_report
    assert first_report.nodes_appended == 2 and first_report.nodes_replayed == 0
    assert second_report.nodes_appended == 0 and second_report.nodes_replayed == 2


def test_missing_or_corrupt_cas_fails_closed() -> None:
    content = b"[1] valid\n"
    cas = MemoryCAS(content)
    with pytest.raises(CasReferenceError):
        extract_citations(cas, {"cas_hash": "0" * 64, "uri": "paper://missing"})
    with pytest.raises(CasReferenceError):
        extract_citations(lambda _digest: b"tampered", {"cas_hash": cas.digest, "uri": "paper://bad"})


def test_foreign_linkage_is_rejected(tmp_path: Path) -> None:
    content = b"[1] source\n"
    cas = MemoryCAS(content)
    with GraphStore(tmp_path / "sakg.db", "paeos-history") as store:
        with pytest.raises(CitationLinkError):
            ingest_citations(cas, [{"cas_hash": cas.digest, "decision_ids": ["sakg://other/Decision/00000000000000000000000000"]}], store)
