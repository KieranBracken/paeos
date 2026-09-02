"""Storage-boundary namespace isolation tests for I-STORE."""

import pytest

from sakg.store import GraphStore, NamespaceViolation


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



def test_each_store_sees_only_its_namespace(tmp_path) -> None:
    db = tmp_path / "graph.sqlite3"
    alpha = node("alpha", "6")
    beta = node("beta", "7")
    with GraphStore(db, "alpha") as alpha_store, GraphStore(db, "beta") as beta_store:
        alpha_store.append_node(alpha)
        beta_store.append_node(beta)
        assert alpha_store.nodes() == (alpha,)
        assert beta_store.nodes() == (beta,)
        with pytest.raises(NamespaceViolation):
            alpha_store.get_node(beta["id"])


def test_edge_endpoints_cannot_cross_namespace(tmp_path) -> None:
    db = tmp_path / "graph.sqlite3"
    alpha, beta = node("alpha", "8"), node("beta", "9")
    with GraphStore(db, "alpha") as alpha_store, GraphStore(db, "beta") as beta_store:
        alpha_store.append_node(alpha)
        beta_store.append_node(beta)
        foreign = edge("alpha", alpha["id"], beta["id"], "structural", "edge:foreign:1")
        with pytest.raises(NamespaceViolation):
            alpha_store.append_edge(foreign)


def test_malformed_store_namespace_fails_closed(tmp_path) -> None:
    with pytest.raises(NamespaceViolation):
        GraphStore(tmp_path / "graph.sqlite3", "../escape")
