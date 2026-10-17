from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from sakg.store import GraphStore
from scripts.sakg_live_graph_index import index_repository


def _anchor(namespace: str, kind: str, suffix: str) -> dict[str, object]:
    digest = hashlib.sha256(f"{kind}:{suffix}".encode()).hexdigest()
    return {"id": f"sakg://{namespace}/{kind}/{suffix.upper():0>26}", "type": kind, "namespace": namespace,
            "facets": {"historical": {"milestone": suffix}}, "label": f"sealed {kind} {suffix}",
            "summary": "Task 22 Court-sealed historical authority anchor.",
            "provenance": {"origin": {"system": "task-22", "run_id": "r-task22"}, "author_kind": "ingest",
                           "ingested_at": "2026-09-04T00:00:00Z", "source_hash": digest},
            "evidence": [{"hash": digest, "uri": f"cas://task22/{suffix}", "kind": "decision",
                           "reverification": "re-run Task 22 admission verification"}], "status": "canonical",
            "confidence": 1.0, "valid_from": "2026-09-04T00:00:00Z", "valid_until": None,
            "falsifier": None, "coordinates": {"domain": ["paeos"]}}


def _source_tree(root: Path) -> None:
    for package in ("paeos", "kernel"):
        directory = root / package
        directory.mkdir(parents=True)
        (directory / "__init__.py").write_text("from dataclasses import dataclass\n", encoding="utf-8")
        for index in range(9):
            (directory / f"module_{index:02d}.py").write_text(
                "from dataclasses import dataclass\n"
                f"@dataclass\nclass Mechanism{index}:\n    value: int = {index}\n\n"
                f"def run_{index}(value: int) -> int:\n    return value + {index}\n", encoding="utf-8")


def test_live_index_emits_typed_entities_and_historical_bindings(tmp_path: Path) -> None:
    root, db = tmp_path / "source", tmp_path / "sakg.db"
    _source_tree(root)
    with GraphStore(db, "paeos-history") as store:
        store.append_node(_anchor("paeos-history", "Decision", "1"))
        store.append_node(_anchor("paeos-history", "Constraint", "2"))
    report = index_repository(root, db)
    assert report["nodes"] >= 50
    assert set(report["indexed_types"]) == {"Component", "Pattern", "Mechanism", "TaxonomyNode"}
    with GraphStore(db, "paeos-history") as store:
        nodes, edges = store.nodes(), store.edges()
    assert {node["type"] for node in nodes} >= {"Decision", "Constraint", "Component", "Pattern", "Mechanism", "TaxonomyNode"}
    assert any(edge["relation"] == "constrained_by" for edge in edges)
    assert any(edge["relation"] == "part_of" for edge in edges)


def test_replay_is_deterministic_and_append_only(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _source_tree(root)
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    assert index_repository(root, first) == index_repository(root, second)
    with GraphStore(first, "paeos-history") as store:
        before = (store.nodes(), store.edges())
    replay = index_repository(root, first)
    with GraphStore(first, "paeos-history") as store:
        after = (store.nodes(), store.edges())
    assert replay["nodes"] == len(after[0]) and before == after
    with sqlite3.connect(first) as connection:
        sql = " ".join(row[0] or "" for row in connection.execute("SELECT sql FROM sqlite_master WHERE type='trigger'"))
    assert "BEFORE UPDATE" in sql and "BEFORE DELETE" in sql
    assert "UPDATE" not in json.dumps(after) and "DELETE" not in json.dumps(after)


def test_default_operator_query_is_read_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with GraphStore() as store:
        assert store.query_nodes() == ()
