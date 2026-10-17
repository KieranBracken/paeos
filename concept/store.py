"""Append-only SQLite storage for the Concept OS graph."""

from __future__ import annotations

import json
import queue
import re
import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from concept.ids import (
    ConceptURI,
    IdentityCollisionError,
    JsonObject,
    JsonValue,
    canonical_json,
    content_hash,
    edge_uri,
    node_uri,
    outbox_uri,
    validate_concept_uri,
)
from concept.model import EDGE_FAMILIES, NODE_TYPES, EdgeEnvelope, NodeEnvelope, from_dict

__all__ = [
    "AppendReceipt",
    "CandidateOutboxEvent",
    "ConceptStore",
    "EdgeQuery",
    "IdentityCollisionError",
    "NodeQuery",
]

_NAMESPACE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,62}")
_OUTBOX_EVENT_TYPES = frozenset({"EMITTED", "DELIVERY_OBSERVED", "REJECTED", "SUPERSEDED"})
_READ_POOL_SIZE = 4


class StoreError(RuntimeError):
    """Base class for Concept OS store errors."""


@dataclass(frozen=True, slots=True)
class NodeQuery:
    """Stable filters for read-only node queries."""

    namespace: str
    node_type: str | None = None
    uri: str | None = None
    limit: int | None = None
    offset: int = 0


@dataclass(frozen=True, slots=True)
class EdgeQuery:
    """Stable filters for read-only edge queries."""

    namespace: str
    family: str | None = None
    relation: str | None = None
    source_uri: str | None = None
    target_uri: str | None = None
    limit: int | None = None
    offset: int = 0


@dataclass(frozen=True, slots=True)
class AppendReceipt:
    """The canonical URI set and physical insert counts for one append operation."""

    node_uris: tuple[str, ...]
    edge_uris: tuple[str, ...]
    inserted_node_count: int
    inserted_edge_count: int

    @property
    def node_count(self) -> int:
        return len(self.node_uris)

    @property
    def edge_count(self) -> int:
        return len(self.edge_uris)


@dataclass(frozen=True, slots=True)
class CandidateOutboxEvent:
    """Immutable candidate delivery observation accepted by the outbox boundary."""

    uri: ConceptURI | str
    namespace: str
    hypothesis_uri: ConceptURI | str
    event_type: str
    schema_version: int
    candidate: object
    recorded_at: str = ""

    def __post_init__(self) -> None:
        _validate_namespace(self.namespace)
        hypothesis = validate_concept_uri(_as_uri_text(self.hypothesis_uri, "hypothesis_uri"))
        if hypothesis.namespace != self.namespace or hypothesis.kind != "hypothesis":
            raise ValueError("outbox requires a same-namespace Hypothesis endpoint")
        if self.event_type not in _OUTBOX_EVENT_TYPES:
            raise ValueError(f"invalid outbox event type: {self.event_type}")
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version < 1
        ):
            raise ValueError("schema_version must be a positive integer")
        candidate = _json_ready(self.candidate)
        if not isinstance(candidate, Mapping):
            raise TypeError("candidate must be a JSON object")
        if self.recorded_at:
            _validate_recorded_at(self.recorded_at)
        if self.uri:
            parsed = validate_concept_uri(_as_uri_text(self.uri, "uri"))
            if parsed.namespace != self.namespace or parsed.kind != "outbox":
                raise ValueError("outbox URI must use the event namespace and outbox kind")

    @property
    def id(self) -> ConceptURI | str:
        """Alias for callers that use the node/edge envelope ``id`` spelling."""

        return self.uri

    @property
    def payload(self) -> object:
        """Alias for delivery-observation callers that call the candidate payload ``payload``."""

        return self.candidate

    def to_dict(self) -> dict[str, object]:
        return {
            "uri": _as_uri_text(self.uri, "uri"),
            "namespace": self.namespace,
            "hypothesis_uri": _as_uri_text(self.hypothesis_uri, "hypothesis_uri"),
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "candidate": _json_ready(self.candidate),
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class _PreparedNode:
    uri: str
    namespace: str
    node_type: str
    schema_version: int
    canonical_bytes: bytes
    full_hash: str
    recorded_at: str


@dataclass(frozen=True, slots=True)
class _PreparedEdge:
    uri: str
    namespace: str
    family: str
    relation: str
    source_uri: str
    target_uri: str
    schema_version: int
    canonical_bytes: bytes
    full_hash: str
    recorded_at: str


@dataclass(frozen=True, slots=True)
class _PreparedOutbox:
    uri: str
    namespace: str
    hypothesis_uri: str
    event_type: str
    schema_version: int
    canonical_bytes: bytes
    full_hash: str
    recorded_at: str


class _ReadOnlyConnectionPool:
    """Small pool of immutable SQLite URI connections."""

    def __init__(self, path: Path, size: int = _READ_POOL_SIZE) -> None:
        if size < 1:
            raise ValueError("read_pool_size must be positive")
        self._connections = tuple(_open_read_connection(path) for _ in range(size))
        self._available: queue.LifoQueue[sqlite3.Connection] = queue.LifoQueue(maxsize=size)
        for connection in self._connections:
            self._available.put(connection)

    @property
    def connections(self) -> tuple[sqlite3.Connection, ...]:
        return self._connections

    @contextmanager
    def checkout(self) -> Iterator[sqlite3.Connection]:
        connection = self._available.get()
        try:
            yield connection
        finally:
            self._available.put(connection)

    def close(self) -> None:
        for connection in self._connections:
            connection.close()


class ConceptStore:
    """Pure SQLite WAL graph store with append-only domain tables."""

    def __init__(self, database: str | Path, *, read_pool_size: int = _READ_POOL_SIZE) -> None:
        if isinstance(read_pool_size, bool) or not isinstance(read_pool_size, int) or read_pool_size < 1:
            raise ValueError("read_pool_size must be a positive integer")
        self._path = Path(database).expanduser().resolve()
        if self._path.name == ":memory:":
            raise ValueError("ConceptStore requires a durable filesystem database path")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._write_connection = _open_write_connection(self._path)
        self._write_lock = threading.RLock()
        try:
            self._create_schema()
            self._read_pool = _ReadOnlyConnectionPool(self._path, size=read_pool_size)
        except BaseException:
            self._write_connection.close()
            raise

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._read_pool.close()
        self._write_connection.close()

    def __enter__(self) -> ConceptStore:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def append_node(self, node: NodeEnvelope) -> str:
        prepared = _prepare_node(node)
        with self._transaction():
            self._append_node_row(prepared)
        return prepared.uri

    def append_edge(self, edge: EdgeEnvelope) -> str:
        prepared = _prepare_edge(edge)
        with self._transaction():
            self._append_edge_row(prepared)
        return prepared.uri

    def append_nodes_and_edges(
        self,
        nodes: Sequence[NodeEnvelope],
        edges: Sequence[EdgeEnvelope],
    ) -> AppendReceipt:
        prepared_nodes = sorted((_prepare_node(node) for node in nodes), key=_uri_sort_key)
        prepared_edges = sorted((_prepare_edge(edge) for edge in edges), key=_uri_sort_key)
        node_uris = _unique_uris(row.uri for row in prepared_nodes)
        edge_uris = _unique_uris(row.uri for row in prepared_edges)

        inserted_node_count = 0
        inserted_edge_count = 0
        with self._transaction():
            for row in prepared_nodes:
                inserted_node_count += int(self._append_node_row(row))
            for row in prepared_edges:
                inserted_edge_count += int(self._append_edge_row(row))
        return AppendReceipt(
            node_uris=node_uris,
            edge_uris=edge_uris,
            inserted_node_count=inserted_node_count,
            inserted_edge_count=inserted_edge_count,
        )

    def get_node(self, uri: str) -> NodeEnvelope | None:
        parsed = validate_concept_uri(uri)
        with self._read_pool.checkout() as connection:
            row = connection.execute(
                "SELECT uri, canonical_json, recorded_at FROM nodes WHERE uri = ?",
                (parsed.uri,),
            ).fetchone()
        return _node_from_row(row) if row is not None else None

    def iter_nodes(self, query: NodeQuery) -> Iterator[NodeEnvelope]:
        namespace, clauses, parameters, suffix = _compile_node_query(query)

        def _iterate() -> Iterator[NodeEnvelope]:
            sql = (
                "SELECT uri, canonical_json, recorded_at FROM nodes "
                f"WHERE namespace = ?{clauses} ORDER BY uri COLLATE BINARY{suffix}"
            )
            with self._read_pool.checkout() as connection:
                rows = connection.execute(sql, (namespace, *parameters))
                for row in rows:
                    yield _node_from_row(row)

        return _iterate()

    def iter_edges(self, query: EdgeQuery) -> Iterator[EdgeEnvelope]:
        namespace, clauses, parameters, suffix = _compile_edge_query(query)

        def _iterate() -> Iterator[EdgeEnvelope]:
            sql = (
                "SELECT uri, canonical_json, recorded_at FROM edges "
                f"WHERE namespace = ?{clauses} ORDER BY uri COLLATE BINARY{suffix}"
            )
            with self._read_pool.checkout() as connection:
                rows = connection.execute(sql, (namespace, *parameters))
                for row in rows:
                    yield _edge_from_row(row)

        return _iterate()

    def snapshot_hash(self, namespace: str) -> str:
        _validate_namespace(namespace)
        with self._read_pool.checkout() as connection:
            node_rows = connection.execute(
                "SELECT uri, content_hash FROM nodes "
                "WHERE namespace = ? ORDER BY uri COLLATE BINARY",
                (namespace,),
            ).fetchall()
            edge_rows = connection.execute(
                "SELECT uri, content_hash FROM edges "
                "WHERE namespace = ? ORDER BY uri COLLATE BINARY",
                (namespace,),
            ).fetchall()
        preimage: JsonObject = {
            "domain": "concept-os/graph-snapshot",
            "version": 1,
            "namespace": namespace,
            "nodes": [[str(row[0]), str(row[1])] for row in node_rows],
            "edges": [[str(row[0]), str(row[1])] for row in edge_rows],
        }
        return content_hash(canonical_json(preimage))

    def append_outbox_event(self, event: CandidateOutboxEvent | Mapping[str, object]) -> str:
        prepared = _prepare_outbox(event)
        if not self._has_hypothesis(prepared.namespace, prepared.hypothesis_uri):
            raise ValueError("outbox requires a same-namespace Hypothesis endpoint")
        with self._transaction():
            if not self._has_hypothesis_in_writer(
                prepared.namespace, prepared.hypothesis_uri
            ):
                raise ValueError("outbox requires a same-namespace Hypothesis endpoint")
            self._append_outbox_row(prepared)
        return prepared.uri

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._write_lock:
            self._write_connection.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._write_connection.execute("COMMIT")
            except BaseException:
                if self._write_connection.in_transaction:
                    self._write_connection.execute("ROLLBACK")
                raise

    def _create_schema(self) -> None:
        self._write_connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                uri TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                node_type TEXT NOT NULL CHECK (node_type IN (
                    'Concept', 'Analogy', 'Transformation', 'SemanticNeighborhood',
                    'InspirationHeuristic', 'Hypothesis'
                )),
                schema_version INTEGER NOT NULL CHECK (schema_version > 0),
                canonical_json BLOB NOT NULL,
                content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
                recorded_at TEXT NOT NULL
            ) STRICT;

            CREATE TABLE IF NOT EXISTS edges (
                uri TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                family TEXT NOT NULL CHECK (family IN (
                    'derivation', 'analogy', 'recombination',
                    'abstraction', 'exemplification', 'neighborhood'
                )),
                relation TEXT NOT NULL,
                source_uri TEXT NOT NULL REFERENCES nodes(uri),
                target_uri TEXT NOT NULL REFERENCES nodes(uri),
                schema_version INTEGER NOT NULL CHECK (schema_version > 0),
                canonical_json BLOB NOT NULL,
                content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
                recorded_at TEXT NOT NULL,
                CHECK (source_uri <> target_uri)
            ) STRICT;

            CREATE TABLE IF NOT EXISTS candidate_outbox (
                uri TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                hypothesis_uri TEXT NOT NULL REFERENCES nodes(uri),
                event_type TEXT NOT NULL CHECK (event_type IN (
                    'EMITTED', 'DELIVERY_OBSERVED', 'REJECTED', 'SUPERSEDED'
                )),
                schema_version INTEGER NOT NULL CHECK (schema_version > 0),
                canonical_json BLOB NOT NULL,
                content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
                recorded_at TEXT NOT NULL
            ) STRICT;

            CREATE INDEX IF NOT EXISTS nodes_type_idx
                ON nodes(namespace, node_type, uri);
            CREATE INDEX IF NOT EXISTS edges_out_idx
                ON edges(namespace, source_uri, family, relation, target_uri);
            CREATE INDEX IF NOT EXISTS edges_in_idx
                ON edges(namespace, target_uri, family, relation, source_uri);
            CREATE INDEX IF NOT EXISTS candidate_outbox_hypothesis_idx
                ON candidate_outbox(namespace, hypothesis_uri, recorded_at, uri);

            CREATE TRIGGER IF NOT EXISTS nodes_append_only_update
            BEFORE UPDATE ON nodes
            BEGIN
                SELECT RAISE(ABORT, 'append-only table');
            END;

            CREATE TRIGGER IF NOT EXISTS nodes_append_only_delete
            BEFORE DELETE ON nodes
            BEGIN
                SELECT RAISE(ABORT, 'append-only table');
            END;

            CREATE TRIGGER IF NOT EXISTS edges_append_only_update
            BEFORE UPDATE ON edges
            BEGIN
                SELECT RAISE(ABORT, 'append-only table');
            END;

            CREATE TRIGGER IF NOT EXISTS edges_append_only_delete
            BEFORE DELETE ON edges
            BEGIN
                SELECT RAISE(ABORT, 'append-only table');
            END;

            CREATE TRIGGER IF NOT EXISTS candidate_outbox_append_only_update
            BEFORE UPDATE ON candidate_outbox
            BEGIN
                SELECT RAISE(ABORT, 'append-only table');
            END;

            CREATE TRIGGER IF NOT EXISTS candidate_outbox_append_only_delete
            BEFORE DELETE ON candidate_outbox
            BEGIN
                SELECT RAISE(ABORT, 'append-only table');
            END;

            CREATE TRIGGER IF NOT EXISTS edges_endpoint_boundary_insert
            BEFORE INSERT ON edges
            WHEN NOT EXISTS (
                SELECT 1 FROM nodes AS source_node
                WHERE source_node.uri = NEW.source_uri
                  AND source_node.namespace = NEW.namespace
            ) OR NOT EXISTS (
                SELECT 1 FROM nodes AS target_node
                WHERE target_node.uri = NEW.target_uri
                  AND target_node.namespace = NEW.namespace
            )
            BEGIN
                SELECT RAISE(ABORT, 'edge endpoints must exist in the same namespace');
            END;

            CREATE TRIGGER IF NOT EXISTS candidate_outbox_namespace_hypothesis_insert
            BEFORE INSERT ON candidate_outbox
            WHEN NOT EXISTS (
                SELECT 1 FROM nodes AS hypothesis_node
                WHERE hypothesis_node.uri = NEW.hypothesis_uri
                  AND hypothesis_node.node_type = 'Hypothesis'
                  AND hypothesis_node.namespace = NEW.namespace
            )
            BEGIN
                SELECT RAISE(ABORT, 'outbox requires a same-namespace Hypothesis endpoint');
            END;
            """
        )

    def _append_node_row(self, row: _PreparedNode) -> bool:
        existing = self._write_connection.execute(
            "SELECT canonical_json, content_hash FROM nodes WHERE uri = ?",
            (row.uri,),
        ).fetchone()
        if existing is not None:
            _ensure_idempotent(
                row.uri,
                row.canonical_bytes,
                row.full_hash,
                bytes(existing[0]),
                str(existing[1]),
            )
            return False
        self._write_connection.execute(
            "INSERT INTO nodes "
            "(uri, namespace, node_type, schema_version, canonical_json, content_hash, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                row.uri,
                row.namespace,
                row.node_type,
                row.schema_version,
                row.canonical_bytes,
                row.full_hash,
                row.recorded_at,
            ),
        )
        return True

    def _append_edge_row(self, row: _PreparedEdge) -> bool:
        existing = self._write_connection.execute(
            "SELECT canonical_json, content_hash FROM edges WHERE uri = ?",
            (row.uri,),
        ).fetchone()
        if existing is not None:
            _ensure_idempotent(
                row.uri,
                row.canonical_bytes,
                row.full_hash,
                bytes(existing[0]),
                str(existing[1]),
            )
            return False
        self._write_connection.execute(
            "INSERT INTO edges "
            "(uri, namespace, family, relation, source_uri, target_uri, schema_version, "
            "canonical_json, content_hash, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row.uri,
                row.namespace,
                row.family,
                row.relation,
                row.source_uri,
                row.target_uri,
                row.schema_version,
                row.canonical_bytes,
                row.full_hash,
                row.recorded_at,
            ),
        )
        return True

    def _append_outbox_row(self, row: _PreparedOutbox) -> bool:
        existing = self._write_connection.execute(
            "SELECT canonical_json, content_hash FROM candidate_outbox WHERE uri = ?",
            (row.uri,),
        ).fetchone()
        if existing is not None:
            _ensure_idempotent(
                row.uri,
                row.canonical_bytes,
                row.full_hash,
                bytes(existing[0]),
                str(existing[1]),
            )
            return False
        self._write_connection.execute(
            "INSERT INTO candidate_outbox "
            "(uri, namespace, hypothesis_uri, event_type, schema_version, canonical_json, "
            "content_hash, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row.uri,
                row.namespace,
                row.hypothesis_uri,
                row.event_type,
                row.schema_version,
                row.canonical_bytes,
                row.full_hash,
                row.recorded_at,
            ),
        )
        return True

    def _has_hypothesis(self, namespace: str, uri: str) -> bool:
        with self._read_pool.checkout() as connection:
            row = connection.execute(
                "SELECT 1 FROM nodes WHERE uri = ? AND namespace = ? AND node_type = 'Hypothesis'",
                (uri, namespace),
            ).fetchone()
        return row is not None

    def _has_hypothesis_in_writer(self, namespace: str, uri: str) -> bool:
        row = self._write_connection.execute(
            "SELECT 1 FROM nodes WHERE uri = ? AND namespace = ? AND node_type = 'Hypothesis'",
            (uri, namespace),
        ).fetchone()
        return row is not None


def _open_write_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        str(path),
        isolation_level=None,
        check_same_thread=False,
        timeout=5.0,
    )
    connection.row_factory = sqlite3.Row
    journal_mode = str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
    if journal_mode != "wal":
        connection.close()
        raise StoreError(f"SQLite WAL could not be enabled; got {journal_mode!r}")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if connection.execute("PRAGMA synchronous").fetchone()[0] != 2:
        connection.close()
        raise StoreError("SQLite synchronous=FULL could not be verified")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        connection.close()
        raise StoreError("SQLite foreign_keys=ON could not be verified")
    if connection.execute("PRAGMA busy_timeout").fetchone()[0] != 5000:
        connection.close()
        raise StoreError("SQLite busy_timeout=5000 could not be verified")
    return connection


def _open_read_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"{path.as_uri()}?mode=ro",
        uri=True,
        isolation_level=None,
        check_same_thread=False,
        timeout=5.0,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
        connection.close()
        raise StoreError("read-only SQLite query_only=ON could not be verified")
    return connection


def _prepare_node(node: NodeEnvelope) -> _PreparedNode:
    if not isinstance(node, NodeEnvelope):
        raise TypeError("append_node requires a NodeEnvelope")
    data = _json_object(node.to_dict())
    preimage = dict(data)
    uri = _as_uri_text(preimage.pop("id"), "id")
    preimage.pop("recorded_at", None)
    canonical_bytes = canonical_json(cast(JsonValue, preimage))
    expected_uri = node_uri(node.namespace, node.type, cast(JsonObject, preimage))
    if uri != expected_uri:
        raise ValueError("node URI does not match its canonical identity preimage")
    return _PreparedNode(
        uri=uri,
        namespace=node.namespace,
        node_type=node.type,
        schema_version=node.schema_version,
        canonical_bytes=canonical_bytes,
        full_hash=content_hash(canonical_bytes),
        recorded_at=_storage_time(node.recorded_at),
    )


def _prepare_edge(edge: EdgeEnvelope) -> _PreparedEdge:
    if not isinstance(edge, EdgeEnvelope):
        raise TypeError("append_edge requires an EdgeEnvelope")
    source_uri = _as_uri_text(edge.source_uri, "source_uri")
    target_uri = _as_uri_text(edge.target_uri, "target_uri")
    source = validate_concept_uri(source_uri)
    target = validate_concept_uri(target_uri)
    if source.namespace != edge.namespace or target.namespace != edge.namespace:
        raise ValueError("edge endpoints must belong to the edge namespace")
    data = _json_object(edge.to_dict())
    preimage = dict(data)
    uri = _as_uri_text(preimage.pop("id"), "id")
    preimage.pop("recorded_at", None)
    canonical_bytes = canonical_json(cast(JsonValue, preimage))
    expected_uri = edge_uri(edge.namespace, cast(JsonObject, preimage))
    if uri != expected_uri:
        raise ValueError("edge URI does not match its canonical identity preimage")
    return _PreparedEdge(
        uri=uri,
        namespace=edge.namespace,
        family=edge.family,
        relation=edge.relation,
        source_uri=source_uri,
        target_uri=target_uri,
        schema_version=edge.schema_version,
        canonical_bytes=canonical_bytes,
        full_hash=content_hash(canonical_bytes),
        recorded_at=_storage_time(edge.recorded_at),
    )


def _prepare_outbox(event: CandidateOutboxEvent | Mapping[str, object]) -> _PreparedOutbox:
    raw = event.to_dict() if isinstance(event, CandidateOutboxEvent) else dict(event)
    namespace = raw.get("namespace")
    if not isinstance(namespace, str):
        raise ValueError("outbox namespace is required")
    _validate_namespace(namespace)
    hypothesis_uri = raw.get("hypothesis_uri")
    if not isinstance(hypothesis_uri, (str, ConceptURI)):
        raise ValueError("outbox hypothesis_uri is required")
    hypothesis = validate_concept_uri(_as_uri_text(hypothesis_uri, "hypothesis_uri"))
    if hypothesis.namespace != namespace or hypothesis.kind != "hypothesis":
        raise ValueError("outbox requires a same-namespace Hypothesis endpoint")
    event_type = raw.get("event_type")
    if not isinstance(event_type, str) or event_type not in _OUTBOX_EVENT_TYPES:
        raise ValueError(f"invalid outbox event type: {event_type!r}")
    schema_version = raw.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version < 1:
        raise ValueError("schema_version must be a positive integer")
    if "candidate" in raw:
        candidate = raw["candidate"]
    elif "payload" in raw:
        candidate = raw["payload"]
    else:
        raise ValueError("outbox candidate or payload is required")
    candidate = _json_ready(candidate)
    if not isinstance(candidate, Mapping):
        raise TypeError("outbox candidate must be a JSON object")
    preimage: JsonObject = {
        "namespace": namespace,
        "hypothesis_uri": hypothesis.uri,
        "event_type": event_type,
        "schema_version": schema_version,
        "candidate": cast(JsonValue, _json_ready(candidate)),
    }
    canonical_bytes = canonical_json(preimage)
    expected_uri = outbox_uri(namespace, preimage)
    provided_uri = raw.get("uri", raw.get("id", ""))
    if not isinstance(provided_uri, (str, ConceptURI)):
        raise TypeError("outbox uri must be a string")
    uri = _as_uri_text(provided_uri, "uri")
    if uri and uri != expected_uri:
        raise ValueError("outbox URI does not match its canonical identity preimage")
    recorded_at = raw.get("recorded_at", "")
    if not isinstance(recorded_at, str):
        raise TypeError("recorded_at must be a string")
    return _PreparedOutbox(
        uri=uri or expected_uri,
        namespace=namespace,
        hypothesis_uri=hypothesis.uri,
        event_type=event_type,
        schema_version=schema_version,
        canonical_bytes=canonical_bytes,
        full_hash=content_hash(canonical_bytes),
        recorded_at=_storage_time(recorded_at),
    )


def _compile_node_query(query: NodeQuery) -> tuple[str, str, tuple[object, ...], str]:
    if not isinstance(query, NodeQuery):
        raise TypeError("iter_nodes requires a NodeQuery")
    _validate_namespace(query.namespace)
    if query.node_type is not None and query.node_type not in NODE_TYPES:
        raise ValueError(f"invalid node_type: {query.node_type}")
    clauses: list[str] = []
    parameters: list[object] = []
    if query.node_type is not None:
        clauses.append(" AND node_type = ?")
        parameters.append(query.node_type)
    if query.uri is not None:
        parsed = validate_concept_uri(query.uri)
        if parsed.namespace != query.namespace:
            raise ValueError("query URI crosses the namespace boundary")
        clauses.append(" AND uri = ?")
        parameters.append(parsed.uri)
    suffix = _limit_offset(query.limit, query.offset)
    return query.namespace, "".join(clauses), tuple(parameters), suffix


def _compile_edge_query(query: EdgeQuery) -> tuple[str, str, tuple[object, ...], str]:
    if not isinstance(query, EdgeQuery):
        raise TypeError("iter_edges requires an EdgeQuery")
    _validate_namespace(query.namespace)
    if query.family is not None and query.family not in EDGE_FAMILIES:
        raise ValueError(f"invalid edge family: {query.family}")
    clauses: list[str] = []
    parameters: list[object] = []
    if query.family is not None:
        clauses.append(" AND family = ?")
        parameters.append(query.family)
    if query.relation is not None:
        clauses.append(" AND relation = ?")
        parameters.append(query.relation)
    for field_name, value in (("source_uri", query.source_uri), ("target_uri", query.target_uri)):
        if value is None:
            continue
        parsed = validate_concept_uri(value)
        if parsed.namespace != query.namespace:
            raise ValueError("query endpoint crosses the namespace boundary")
        clauses.append(f" AND {field_name} = ?")
        parameters.append(parsed.uri)
    suffix = _limit_offset(query.limit, query.offset)
    return query.namespace, "".join(clauses), tuple(parameters), suffix


def _limit_offset(limit: int | None, offset: int) -> str:
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        raise ValueError("query limit must be a non-negative integer")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("query offset must be a non-negative integer")
    if limit is None:
        return f" LIMIT -1 OFFSET {offset}"
    return f" LIMIT {limit} OFFSET {offset}"


def _node_from_row(row: sqlite3.Row) -> NodeEnvelope:
    data = _canonical_object(row["canonical_json"])
    data["id"] = row["uri"]
    data["recorded_at"] = row["recorded_at"]
    value = from_dict(data)
    if not isinstance(value, NodeEnvelope):
        raise StoreError("stored node canonical JSON did not decode to a NodeEnvelope")
    return value


def _edge_from_row(row: sqlite3.Row) -> EdgeEnvelope:
    data = _canonical_object(row["canonical_json"])
    data["id"] = row["uri"]
    data["recorded_at"] = row["recorded_at"]
    value = from_dict(data)
    if not isinstance(value, EdgeEnvelope):
        raise StoreError("stored edge canonical JSON did not decode to an EdgeEnvelope")
    return value


def _canonical_object(raw: bytes | str) -> dict[str, object]:
    value = json.loads(bytes(raw) if isinstance(raw, bytes) else raw)
    if not isinstance(value, dict):
        raise StoreError("stored canonical JSON must be an object")
    return {str(key): item for key, item in value.items()}


def _json_object(value: object) -> dict[str, object]:
    ready = _json_ready(value)
    if not isinstance(ready, dict):
        raise TypeError("envelope serialization must produce a JSON object")
    return ready


def _json_ready(value: object) -> object:
    if isinstance(value, ConceptURI):
        return value.uri
    if hasattr(value, "to_dict"):
        return _json_ready(cast(Any, value).to_dict())
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return {_json_ready(item) for item in value}
    return value


def _ensure_idempotent(
    uri: str,
    canonical_bytes: bytes,
    full_hash: str,
    existing_canonical_bytes: bytes,
    existing_full_hash: str,
) -> None:
    if canonical_bytes != existing_canonical_bytes or full_hash != existing_full_hash:
        raise IdentityCollisionError(
            f"identity collision for {uri}: canonical bytes or full SHA-256 differ"
        )


def _validate_namespace(namespace: str) -> None:
    if not isinstance(namespace, str) or _NAMESPACE_RE.fullmatch(namespace) is None:
        raise ValueError("namespace must match ^[a-z0-9][a-z0-9_-]{0,62}$")


def _validate_recorded_at(value: str) -> None:
    try:
        datetime.fromisoformat(value[:-1] if value.endswith("Z") else value)
    except ValueError as exc:
        raise ValueError(f"invalid recorded_at timestamp: {value}") from exc
    if not value.endswith("Z"):
        raise ValueError("recorded_at must be a UTC RFC3339 string ending in Z")


def _storage_time(value: str) -> str:
    if value:
        _validate_recorded_at(value)
        return value
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _as_uri_text(value: object, field_name: str) -> str:
    if isinstance(value, ConceptURI):
        return value.uri
    if isinstance(value, str):
        return value
    raise TypeError(f"{field_name} must be a Concept URI string")


def _uri_sort_key(row: _PreparedNode | _PreparedEdge) -> bytes:
    return row.uri.encode("utf-8")


def _unique_uris(uris: Iterator[str]) -> tuple[str, ...]:
    return tuple(sorted(set(uris), key=lambda uri: uri.encode("utf-8")))
