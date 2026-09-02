from __future__ import annotations

from sakg.ingest import ingest_outbox, promotion_eligible
from sakg.store import GraphStore

from tests.sakg.test_ingest import fixture, NODE_ID, node


def test_frequency_does_not_promote_a_candidate(tmp_path) -> None:
    cas, outbox = fixture(tmp_path)
    with GraphStore(tmp_path / "graph.sqlite3", "demo") as store:
        reports = [ingest_outbox(outbox, store, cas) for _ in range(5)]
        assert sum(report.promoted for report in reports) == 0
        stored = store.get_node(NODE_ID)
        assert stored["status"] == "candidate"
        assert not promotion_eligible(stored, ())
