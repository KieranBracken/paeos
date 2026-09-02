from __future__ import annotations

from sakg.ingest import ingest_outbox
from sakg.store import GraphStore

from tests.sakg.test_ingest import fixture, NODE_ID


def test_re_reading_the_same_outbox_is_idempotent(tmp_path) -> None:
    cas, outbox = fixture(tmp_path)
    with GraphStore(tmp_path / "graph.sqlite3", "demo") as store:
        first = ingest_outbox(outbox, store, cas)
        second = ingest_outbox(outbox, store, cas)
        assert first.nodes_appended == 1
        assert second.nodes_appended == 0
        assert second.nodes_replayed == 1
        assert len(store.nodes()) == 1
        assert store.get_node(NODE_ID)["status"] == "candidate"
