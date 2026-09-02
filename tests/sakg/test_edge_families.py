"""Eight §4.4 edge families and edge-as-object semantics."""

from hashlib import sha256

import pytest
from sakg.store import EDGE_FAMILIES, EdgeFamilyError, GraphStore


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


def test_all_eight_edge_families_are_registered_and_persisted(tmp_path) -> None:
    assert len(EDGE_FAMILIES) == 8
    with GraphStore(tmp_path / "graph.sqlite3", "demo-project") as store:
        source, target = node(suffix="0"), node(suffix="a")
        store.append_node(source)
        store.append_node(target)
        for index, family in enumerate(EDGE_FAMILIES):
            store.append_edge(
                edge("demo-project", source["id"], target["id"], family, f"edge:{family}:{index}")
            )
        assert tuple(sorted(item["family"] for item in store.edges())) == tuple(
            sorted(EDGE_FAMILIES)
        )
        assert all(
            "properties" in item and "family_owned" in item["properties"] for item in store.edges()
        )


def test_unknown_edge_family_is_rejected(tmp_path) -> None:
    source, target = node(suffix="b"), node(suffix="c")
    with GraphStore(tmp_path / "graph.sqlite3", "demo-project") as store:
        store.append_node(source)
        store.append_node(target)
        with pytest.raises(EdgeFamilyError):
            store.append_edge(
                edge("demo-project", source["id"], target["id"], "invented", "edge:bad:1")
            )


def test_properties_are_not_promoted_to_endpoint_columns(tmp_path) -> None:
    source, target = node(suffix="d"), node(suffix="e")
    with GraphStore(tmp_path / "graph.sqlite3", "demo-project") as store:
        store.append_node(source)
        store.append_node(target)
        record = edge("demo-project", source["id"], target["id"], "tradeoff", "edge:tradeoff:1")
        result = store.append_edge(record)
        persisted = store.get_edge(result)
        assert persisted["properties"] == {
            "confidence": 0.75,
            "axis": "fixture",
            "family_owned": True,
        }
        assert "confidence" not in persisted
