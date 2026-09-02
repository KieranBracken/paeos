import sqlite3
from hashlib import sha256

import pytest
from sakg.store import AppendOnlyViolation, DuplicateIdentity, GraphStore


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



def test_delete_is_explicitly_rejected_and_history_remains(tmp_path) -> None:
    original = node()
    with GraphStore(tmp_path / "graph.sqlite3", "demo-project") as store:
        store.append_node(original)
        with pytest.raises(AppendOnlyViolation):
            store.delete_node(original["id"])
        assert store.get_node(original["id"]) == original


def test_supersession_appends_new_version_without_mutating_old(tmp_path) -> None:
    original = node()
    replacement = node(suffix="5")
    with GraphStore(tmp_path / "graph.sqlite3", "demo-project") as store:
        store.append_node(original)
        store.supersede_node(replacement, original["id"])
        assert store.get_node(original["id"]) == original
        supersedes_dict = {"node_id": original["id"]}
        assert store.get_node(replacement["id"])["facets"]["supersedes"] == supersedes_dict
        assert len(store.nodes()) == 2


def test_conflicting_identity_cannot_overwrite_existing_row(tmp_path) -> None:
    original = node()
    changed = dict(original)
    changed["label"] = "tampered"
    with GraphStore(tmp_path / "graph.sqlite3", "demo-project") as store:
        store.append_node(original)
        with pytest.raises(DuplicateIdentity):
            store.append_node(changed)


def test_sqlite_triggers_reject_direct_update_and_delete(tmp_path) -> None:
    db = tmp_path / "graph.sqlite3"
    original = node()
    with GraphStore(db, "demo-project") as store:
        store.append_node(original)
        with pytest.raises(sqlite3.IntegrityError):
            store._db.execute(
                "UPDATE nodes SET payload = payload WHERE node_id = ?",
                (original["id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            store._db.execute("DELETE FROM nodes WHERE node_id = ?", (original["id"],))
