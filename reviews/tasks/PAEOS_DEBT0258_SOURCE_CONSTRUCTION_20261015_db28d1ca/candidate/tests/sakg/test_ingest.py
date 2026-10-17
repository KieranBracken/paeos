from __future__ import annotations

import json
from hashlib import sha256

from kernel.cas import CAS, FilesystemCasStore
from runtime.emission.outbox import PostSealOutbox
from sakg.ingest import ingest_outbox
from sakg.store import GraphStore

EVIDENCE = sha256(b"i-ingest-evidence").hexdigest()
NODE_ID = "sakg://demo/Decision/01J00000000000000000000001"


def node() -> dict[str, object]:
    return {
        "id": NODE_ID,
        "type": "Decision",
        "namespace": "demo",
        "facets": {"question": {"value": "Which candidate is safe?"}},
        "label": "A candidate decision",
        "summary": "A node pulled from a sealed outbox bundle.",
        "provenance": {
            "origin": {"system": "test", "run_id": "i-ingest"},
            "author_kind": "agent",
            "ingested_at": "2026-09-02T12:00:00Z",
            "source_hash": sha256(b"source").hexdigest(),
        },
        "evidence": [
            {
                "hash": EVIDENCE,
                "uri": "cas://evidence",
                "kind": "test",
                "reverification": "rerun ingest",
            }
        ],
        "status": "candidate",
        "confidence": 0.5,
        "valid_from": "2026-09-02T12:00:00Z",
        "valid_until": None,
        "falsifier": None,
        "coordinates": {"domain": ["systems"]},
    }


def fixture(tmp_path):
    cas = CAS(FilesystemCasStore(tmp_path / "cas"))
    payload = {"namespace": "demo", "nodes": [node()]}
    bundle_hash = cas.put(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    outbox = PostSealOutbox(tmp_path / "outbox.jsonl")
    outbox.write_after_seal(
        {
            "bundle_id": "bundle-i-ingest",
            "goal_id": "g-i-ingest",
            "namespace": "demo",
            "artifact_bundle_hash": bundle_hash,
            "evidence_refs": [EVIDENCE],
        },
        goal_state="integrated",
        seal_sequence=4,
        l16_sequence=5,
        emitted_at="2026-09-02T12:00:00Z",
    )
    return cas, outbox


def test_pull_ingest_lands_a_candidate_in_the_producing_namespace(tmp_path) -> None:
    cas, outbox = fixture(tmp_path)
    with GraphStore(tmp_path / "graph.sqlite3", "demo") as store:
        report = ingest_outbox(outbox, store, cas)
        assert report.to_dict() == {
            "records_seen": 1,
            "bundles_read": 1,
            "nodes_appended": 1,
            "nodes_replayed": 0,
            "nodes_total": 1,
            "promoted": 0,
        }
        assert store.get_node(NODE_ID)["status"] == "candidate"
        assert store.get_node(NODE_ID)["namespace"] == "demo"


def test_compact_emission_node_is_hydrated_to_the_universal_envelope(tmp_path) -> None:
    base = node()
    compact = {
        key: base[key]
        for key in ("id", "type", "label", "summary", "facets", "evidence", "provenance", "status")
    }
    compact["facets"] = {"question": "Which candidate is safe?"}
    compact["provenance"] = {
        "origin": {"system": "bundle", "run_id": "compact"},
        "source_hash": base["provenance"]["source_hash"],
    }
    cas = CAS(FilesystemCasStore(tmp_path / "cas"))
    payload = {
        "bundle_id": "sakg-bundle:compact",
        "schema_version": "paeos.sakg.emission-bundle/v1",
        "goal_id": "g-compact",
        "sealed_at": "2026-09-02T12:00:00Z",
        "namespace": "demo",
        "producer": {"system": "paeos", "version": "0.1"},
        "nodes": [compact],
    }
    bundle_hash = cas.put(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    outbox = PostSealOutbox(tmp_path / "outbox.jsonl")
    outbox.write_after_seal(
        {
            "bundle_id": "bundle-compact",
            "goal_id": "g-compact",
            "namespace": "demo",
            "artifact_bundle_hash": bundle_hash,
            "evidence_refs": [EVIDENCE],
        },
        goal_state="integrated",
        seal_sequence=1,
        l16_sequence=2,
        emitted_at="2026-09-02T12:00:00Z",
    )
    with GraphStore(tmp_path / "graph.sqlite3", "demo") as store:
        ingest_outbox(outbox, store, cas)
        stored = store.get_node(NODE_ID)
        assert stored["status"] == "candidate"
        assert stored["facets"]["question"] == {"value": "Which candidate is safe?"}
        assert stored["provenance"]["author_kind"] == "ingest"
        assert stored["confidence"] == 0.0
