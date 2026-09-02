"""Focused persistence and §4.2 envelope tests for I-STORE."""

from sakg.store import Edge, EnvelopeValidationError, GraphStore, NamespaceViolation


from hashlib import sha256


def node(namespace: str = "demo-project", suffix: str = "1") -> dict[str, object]:
    return {
        "id": f"sakg://{namespace}/Decision/01J00000000000000000000{suffix.upper()}01",
        "type": "Decision",
        "namespace": namespace,
        "facets": {"origin": {"kind": "fixture"}},
        "label": "A stored decision",
        "summary": "A universal envelope fixture persisted by the graph store.",
        "provenance": {
            "origin": {"system": "test", "run_id": "i-store-test"},
            "author_kind": "agent",
            "ingested_at": "2026-09-02T12:00:00Z",
            "source_hash": sha256(b"fixture").hexdigest(),
        },
        "evidence": [
            {
                "hash": sha256(b"evidence").hexdigest(),
                "uri": "cas://fixture/evidence",
                "kind": "test",
                "reverification": "rerun the focused store test",
            }
        ],
        "status": "candidate",
        "confidence": 0.5,
        "valid_from": "2026-09-02T12:00:00Z",
        "valid_until": None,
        "falsifier": None,
        "coordinates": {"domain": ["systems"]},
    }


def edge(namespace: str, source: str, target: str, family: str, edge_id: str) -> dict[str, object]:
    return {
        "edge_id": edge_id,
        "namespace": namespace,
        "source": source,
        "target": target,
        "family": family,
        "relation": "relates_to",
        "properties": {"confidence": 0.75, "axis": "fixture", "family_owned": True},
        "evidence": [],
        "created_at": "2026-09-02T12:00:00Z",
    }



def test_node_round_trip_and_restart(tmp_path) -> None:
    db = tmp_path / "graph.sqlite3"
    original = node()
    with GraphStore(db, "demo-project") as store:
        assert store.append_node(original) == original["id"]
        assert store.get_node(original["id"]) == original
    with GraphStore(db, "demo-project") as reopened:
        assert reopened.nodes() == (original,)


def test_envelope_validation_rejects_missing_or_cross_namespace_fields(tmp_path) -> None:
    original = node()
    with GraphStore(tmp_path / "graph.sqlite3", "demo-project") as store:
        malformed = dict(original)
        malformed.pop("confidence")
        try:
            store.append_node(malformed)
        except EnvelopeValidationError:
            pass
        else:
            raise AssertionError("missing §4.2 field was accepted")
        foreign = node("other-project", "2")
        try:
            store.append_node(foreign)
        except NamespaceViolation:
            pass
        else:
            raise AssertionError("cross-namespace node was accepted")


def test_edge_round_trip_preserves_edge_object_properties(tmp_path) -> None:
    with GraphStore(tmp_path / "graph.sqlite3", "demo-project") as store:
        source, target = node(suffix="3"), node(suffix="4")
        store.append_node(source)
        store.append_node(target)
        record = edge("demo-project", source["id"], target["id"], "dependency", "edge:dependency:1")
        assert store.append_edge(record) == "edge:dependency:1"
        assert store.get_edge("edge:dependency:1") == record
        assert store.edges("dependency")[0]["properties"] == record["properties"]


def test_idempotent_replay_accepts_identical_content(tmp_path) -> None:
    original = node()
    with GraphStore(tmp_path / "graph.sqlite3", "demo-project") as store:
        assert store.put_node(original) == store.put_node(original)
        assert len(store.nodes()) == 1
