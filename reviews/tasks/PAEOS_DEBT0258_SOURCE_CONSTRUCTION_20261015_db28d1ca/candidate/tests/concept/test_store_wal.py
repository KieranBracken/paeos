from __future__ import annotations

import sqlite3

import pytest
from concept.store import ConceptStore, NodeQuery

from tests.concept._store_fixtures import concept_node


def test_writer_configures_required_sqlite_pragmas(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    assert store._write_connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert store._write_connection.execute("PRAGMA synchronous").fetchone()[0] == 2
    assert store._write_connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert store._write_connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_read_pool_uses_read_only_query_only_connections(tmp_path) -> None:
    store = ConceptStore(tmp_path / "concept.db")
    store.append_node(concept_node("read-only"))
    connections = store._read_pool.connections
    assert connections
    for connection in connections:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("CREATE TABLE forbidden_write(value TEXT)")
    assert list(store.iter_nodes(NodeQuery(namespace="demo")))


def test_wal_file_is_created_for_durable_database(tmp_path) -> None:
    path = tmp_path / "concept.db"
    store = ConceptStore(path)
    store.append_node(concept_node("wal"))
    assert path.with_name(path.name + "-wal").exists() or path.with_name(path.name + "-shm").exists()
