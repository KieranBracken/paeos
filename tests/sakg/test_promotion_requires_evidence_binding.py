from __future__ import annotations

import json
from hashlib import sha256

import pytest
from kernel.cas import CAS, FilesystemCasStore
from runtime.emission.outbox import PostSealOutbox
from sakg.ingest import EvidenceBindingError, ingest_outbox, promotion_eligible
from sakg.store import GraphStore
from tests.sakg.test_ingest import node


def test_unbound_candidate_evidence_is_rejected_before_append(tmp_path) -> None:
    cas = CAS(FilesystemCasStore(tmp_path / "cas"))
    payload = {"namespace": "demo", "nodes": [node()]}
    bundle_hash = cas.put(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    outbox = PostSealOutbox(tmp_path / "outbox.jsonl")
    outbox.write_after_seal(
        {
            "bundle_id": "bundle-unbound",
            "goal_id": "g-unbound",
            "namespace": "demo",
            "artifact_bundle_hash": bundle_hash,
            "evidence_refs": [sha256(b"different").hexdigest()],
        },
        goal_state="integrated",
        seal_sequence=1,
        l16_sequence=2,
        emitted_at="2026-09-02T12:00:00Z",
    )
    with GraphStore(tmp_path / "graph.sqlite3", "demo") as store:
        with pytest.raises(EvidenceBindingError):
            ingest_outbox(outbox, store, cas)
        assert store.nodes() == ()
    assert not promotion_eligible(node(), ())
