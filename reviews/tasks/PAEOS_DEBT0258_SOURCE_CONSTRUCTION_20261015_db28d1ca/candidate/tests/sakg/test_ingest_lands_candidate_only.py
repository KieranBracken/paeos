from __future__ import annotations

from sakg.ingest import ingest_outbox
from sakg.store import GraphStore
from tests.sakg.test_ingest import NODE_ID, fixture


def test_replay_never_changes_candidate_status(tmp_path) -> None:
    cas, outbox = fixture(tmp_path)
    with GraphStore(tmp_path / "graph.sqlite3", "demo") as store:
        ingest_outbox(outbox, store, cas)
        ingest_outbox(outbox, store, cas)
        assert store.get_node(NODE_ID)["status"] == "candidate"
