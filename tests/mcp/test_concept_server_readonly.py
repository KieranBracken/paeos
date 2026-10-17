from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest
from concept.mcp_server import build_concept_mcp_server
from mcp.server.mcpserver.exceptions import ToolError

from tests.mcp._fixtures import seed_graph

FORBIDDEN_NAMES = ("create", "append", "update", "delete", "promote", "validate", "execute", "export")


def test_forbidden_mutation_names_are_absent_and_rejected(tmp_path: Path) -> None:
    seeded = seed_graph(tmp_path / "graph.db")
    server = build_concept_mcp_server(seeded.database)
    try:
        names = {tool.name for tool in asyncio.run(server.list_tools())}
        assert not names.intersection(FORBIDDEN_NAMES)
        for name in FORBIDDEN_NAMES:
            with pytest.raises(ToolError):
                asyncio.run(server.call_tool(name, {}))
    finally:
        server.close()


def test_sqlite_connection_is_mode_ro_and_query_only(tmp_path: Path) -> None:
    seeded = seed_graph(tmp_path / "graph.db")
    server = build_concept_mcp_server(seeded.database)
    try:
        snapshot = cast(Any, server)._snapshot
        connection = cast(sqlite3.Connection, snapshot._connection)
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert connection.execute("PRAGMA database_list").fetchone()[2] == str(seeded.database)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("INSERT INTO nodes(uri) VALUES ('blocked')")
    finally:
        server.close()


def test_server_has_no_writer_or_outbox_capability_surface(tmp_path: Path) -> None:
    seeded = seed_graph(tmp_path / "graph.db")
    server = build_concept_mcp_server(seeded.database)
    try:
        assert not any("write" in name.lower() for name in vars(server))
        assert not any("outbox" in name.lower() for name in vars(server))
        assert not hasattr(cast(Any, server)._snapshot, "append_node")
        assert not hasattr(cast(Any, server)._snapshot, "append_outbox_event")
    finally:
        server.close()


def test_data_and_snapshot_hash_are_read_in_one_transaction(tmp_path: Path) -> None:
    seeded = seed_graph(tmp_path / "graph.db")
    server = build_concept_mcp_server(seeded.database)
    try:
        snapshot = cast(Any, server)._snapshot
        connection = cast(sqlite3.Connection, snapshot._connection)
        observed_transaction_states: list[bool] = []
        original_snapshot_hash = snapshot.snapshot_hash

        def snapshot_hash_in_transaction(namespace: str) -> str:
            observed_transaction_states.append(connection.in_transaction)
            return original_snapshot_hash(namespace)

        snapshot.snapshot_hash = snapshot_hash_in_transaction
        response = asyncio.run(
            server.call_tool("concept_get", {"uri": seeded.root_uri})
        )
        assert response.is_error is False
        assert observed_transaction_states == [True]
    finally:
        server.close()


def test_hypothesis_data_and_snapshot_hash_are_read_in_one_transaction(tmp_path: Path) -> None:
    seeded = seed_graph(tmp_path / "graph.db")
    server = build_concept_mcp_server(seeded.database)
    try:
        snapshot = cast(Any, server)._snapshot
        connection = cast(sqlite3.Connection, snapshot._connection)
        observed_transaction_states: list[bool] = []
        original_snapshot_hash = snapshot.snapshot_hash

        def snapshot_hash_in_transaction(namespace: str) -> str:
            observed_transaction_states.append(connection.in_transaction)
            return original_snapshot_hash(namespace)

        snapshot.snapshot_hash = snapshot_hash_in_transaction
        response = asyncio.run(
            server.call_tool("concept_hypothesis_get", {"uri": seeded.hypothesis_uri})
        )
        assert response.is_error is False
        assert observed_transaction_states == [True]
    finally:
        server.close()
