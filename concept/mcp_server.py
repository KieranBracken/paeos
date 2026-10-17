"""Structurally read-only MCP query surface for Concept OS.

The public server deliberately closes over one typed SQLite read snapshot.  Tool handlers receive
only JSON query values; they never receive a store writer, an outbox emitter, SQL, a path, or an
implementation reference.  Every result is advisory and is wrapped in the same candidate envelope.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any, Self, cast
from urllib.parse import quote

from mcp.server import MCPServer  # pyright: ignore[reportMissingImports]

from concept.ids import ConceptURI, canonical_json, content_hash, validate_concept_uri
from concept.model import EdgeEnvelope, NodeEnvelope, SearchRequest, from_dict
from concept.search import SearchOrchestra
from concept.store import EdgeQuery, NodeQuery
from concept.traverse import (
    EDGE_FAMILIES,
    OUTGOING,
    TraversalError,
    TraversalRequest,
    TraversalResult,
    traverse,
)

__all__ = [
    "ConceptMCPServer",
    "build_concept_mcp_server",
    "build_server",
    "main",
]

_TOOL_NAMES = (
    "concept_get",
    "concept_search",
    "concept_neighborhood",
    "concept_path",
    "concept_hypothesis_get",
)
_FORBIDDEN_TOOL_NAMES = frozenset(
    {"create", "append", "update", "delete", "promote", "validate", "execute", "export"}
)
_READONLY_SCHEMA = frozenset({"nodes", "edges", "candidate_outbox"})
_DEFAULT_TRAVERSAL_BUDGETS: dict[str, int] = {
    "max_hops": 2,
    "max_expansions": 100,
    "max_results": 100,
    "max_serialized_bytes": 65536,
}
_BUDGET_KEYS = frozenset(_DEFAULT_TRAVERSAL_BUDGETS)
_SEARCH_BUDGET_KEYS = frozenset(
    {"max_expansions", "max_results", "max_hops", "max_tokens"}
)
_MAX_TRAVERSAL_BUDGETS: dict[str, int] = {
    "max_hops": 32,
    "max_expansions": 10_000,
    "max_results": 1_000,
    "max_serialized_bytes": 1_000_000,
}
_MAX_SEARCH_BUDGETS: dict[str, int] = {
    "max_expansions": 10_000,
    "max_results": 1_000,
    "max_hops": 32,
    "max_tokens": 100_000,
}
_UNAVAILABLE_HASH = content_hash(
    canonical_json({"domain": "concept-os/mcp-store-unavailable", "version": 1})
)
_LOGGER = logging.getLogger(__name__)


class StoreUnavailable(RuntimeError):
    """A read-only graph snapshot cannot currently be queried."""


class _BudgetExceeded(ValueError):
    """A request exceeds the MCP server's finite resource ceiling."""


class _NamespaceDisclosureDenied(ValueError):
    """A client attempted to widen the server's same-namespace policy."""


class _ReadOnlySnapshot:
    """Typed, parameterized read facade over one SQLite ``mode=ro`` connection."""

    def __init__(self, database: str | Path) -> None:
        self._connection: sqlite3.Connection | None = None
        self._availability_error: str | None = None
        self._read_lock = threading.RLock()
        connection: sqlite3.Connection | None = None
        try:
            database_path = Path(database).expanduser().resolve()
            database_uri = f"file:{quote(str(database_path), safe='/')}?mode=ro"
            connection = sqlite3.connect(database_uri, uri=True, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            query_only = connection.execute("PRAGMA query_only").fetchone()
            if query_only is None or int(query_only[0]) != 1:
                raise StoreUnavailable("read-only SQLite query_only=ON could not be verified")
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if not _READONLY_SCHEMA.issubset(tables):
                raise StoreUnavailable("Concept OS read schema is unavailable")
            self._connection = connection
        except (OSError, sqlite3.Error, StoreUnavailable, TypeError, ValueError) as exc:
            if connection is not None:
                connection.close()
            self._availability_error = type(exc).__name__
            _LOGGER.debug("Concept OS MCP store unavailable: %s", self._availability_error)

    @property
    def available(self) -> bool:
        return self._connection is not None

    def close(self) -> None:
        with self._read_lock:
            connection, self._connection = self._connection, None
            if connection is not None:
                connection.close()

    @contextmanager
    def read_scope(self) -> Iterator[None]:
        """Serialize one logical query and pin its reads to one SQLite snapshot."""

        with self._read_lock:
            connection = self._connection
            if connection is None:
                raise StoreUnavailable("read-only graph snapshot is unavailable")
            try:
                connection.execute("BEGIN")
                yield
            except sqlite3.Error as exc:
                raise StoreUnavailable("read-only graph snapshot is unavailable") from exc
            finally:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")

    def _execute(self, statement: str, parameters: Sequence[object] = ()) -> sqlite3.Cursor:
        connection = self._connection
        if connection is None:
            raise StoreUnavailable("read-only graph snapshot is unavailable")
        try:
            return connection.execute(statement, tuple(parameters))
        except sqlite3.Error as exc:
            raise StoreUnavailable("read-only graph snapshot is unavailable") from exc

    def get_node(self, uri: str) -> NodeEnvelope | None:
        row = self._execute(
            "SELECT uri, canonical_json, recorded_at FROM nodes WHERE uri = ?",
            (uri,),
        ).fetchone()
        return _node_from_row(row) if row is not None else None

    def get_edge(self, uri: str) -> EdgeEnvelope | None:
        row = self._execute(
            "SELECT uri, canonical_json, recorded_at FROM edges WHERE uri = ?",
            (uri,),
        ).fetchone()
        return _edge_from_row(row) if row is not None else None

    def iter_nodes(self, query: NodeQuery) -> Iterable[NodeEnvelope]:
        if not isinstance(query, NodeQuery):
            raise TypeError("read-only node queries require NodeQuery")
        clauses = ["namespace = ?"]
        parameters: list[object] = [query.namespace]
        if query.node_type is not None:
            clauses.append("node_type = ?")
            parameters.append(query.node_type)
        if query.uri is not None:
            clauses.append("uri = ?")
            parameters.append(query.uri)
        statement = (
            "SELECT uri, canonical_json, recorded_at FROM nodes WHERE "
            + " AND ".join(clauses)
            + " ORDER BY uri COLLATE BINARY"
        )
        if query.limit is not None:
            statement += " LIMIT ? OFFSET ?"
            parameters.extend((query.limit, query.offset))
        elif query.offset:
            statement += " LIMIT -1 OFFSET ?"
            parameters.append(query.offset)
        rows = self._execute(statement, parameters).fetchall()
        return tuple(_node_from_row(row) for row in rows)

    def iter_edges(self, query: EdgeQuery) -> Iterable[EdgeEnvelope]:
        if not isinstance(query, EdgeQuery):
            raise TypeError("read-only edge queries require EdgeQuery")
        clauses = ["namespace = ?"]
        parameters: list[object] = [query.namespace]
        for field_name in ("family", "relation", "source_uri", "target_uri"):
            value = getattr(query, field_name)
            if value is not None:
                clauses.append(f"{field_name} = ?")
                parameters.append(value)
        statement = (
            "SELECT uri, canonical_json, recorded_at FROM edges WHERE "
            + " AND ".join(clauses)
            + " ORDER BY uri COLLATE BINARY"
        )
        if query.limit is not None:
            statement += " LIMIT ? OFFSET ?"
            parameters.extend((query.limit, query.offset))
        elif query.offset:
            statement += " LIMIT -1 OFFSET ?"
            parameters.append(query.offset)
        rows = self._execute(statement, parameters).fetchall()
        return tuple(_edge_from_row(row) for row in rows)

    def iter_outbox(self, namespace: str, hypothesis_uri: str) -> tuple[dict[str, object], ...]:
        rows = self._execute(
            "SELECT uri, canonical_json, recorded_at FROM candidate_outbox "
            "WHERE namespace = ? AND hypothesis_uri = ? "
            "ORDER BY recorded_at COLLATE BINARY, uri COLLATE BINARY",
            (namespace, hypothesis_uri),
        ).fetchall()
        observations: list[dict[str, object]] = []
        for row in rows:
            data = _canonical_object(row["canonical_json"])
            data.update({"uri": row["uri"], "recorded_at": row["recorded_at"]})
            observations.append(data)
        return tuple(observations)

    def snapshot_hash(self, namespace: str) -> str:
        node_rows = self._execute(
            "SELECT uri, content_hash FROM nodes "
            "WHERE namespace = ? ORDER BY uri COLLATE BINARY",
            (namespace,),
        ).fetchall()
        edge_rows = self._execute(
            "SELECT uri, content_hash FROM edges "
            "WHERE namespace = ? ORDER BY uri COLLATE BINARY",
            (namespace,),
        ).fetchall()
        preimage = {
            "domain": "concept-os/graph-snapshot",
            "version": 1,
            "namespace": namespace,
            "nodes": [[str(row[0]), str(row[1])] for row in node_rows],
            "edges": [[str(row[0]), str(row[1])] for row in edge_rows],
        }
        return content_hash(canonical_json(cast(Any, preimage)))


class ConceptMCPServer(MCPServer):  # pyright: ignore[misc]
    """MCP server with a closeable read-only Concept OS snapshot."""

    def __init__(self, snapshot: _ReadOnlySnapshot) -> None:
        super().__init__(
            "concept-os-readonly",
            description="Exploratory, structurally read-only Concept OS query surface",
        )
        self._snapshot = snapshot
        _register_tools(self)

    def close(self) -> None:
        self._snapshot.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def build_concept_mcp_server(database: str | Path) -> ConceptMCPServer:
    """Build a server with exactly five read-only query tools."""

    return ConceptMCPServer(_ReadOnlySnapshot(database))


build_server = build_concept_mcp_server


def _register_tools(server: ConceptMCPServer) -> None:
    @server.tool(name="concept_get", structured_output=True)
    def concept_get(uri: str) -> dict[str, object]:
        try:
            parsed = validate_concept_uri(uri)
        except (TypeError, ValueError):
            return _error_envelope("InvalidConceptURI", None)
        query_hash = _query_hash({"tool": "concept_get", "uri": parsed.uri})
        try:
            with server._snapshot.read_scope():
                record = _get_record(server._snapshot, parsed)
                return _envelope(
                    server._snapshot,
                    parsed.namespace,
                    query_hash,
                    [record] if record is not None else [],
                )
        except StoreUnavailable:
            return _error_envelope("StoreUnavailable", query_hash)
        except (TypeError, ValueError):
            return _error_envelope("InvalidConceptURI", query_hash)

    @server.tool(name="concept_search", structured_output=True)
    def concept_search(request: dict[str, object]) -> dict[str, object]:
        try:
            raw_request = _json_object(request)
            namespace = _request_namespace(raw_request)
            query_hash = _query_hash(raw_request)
            search_request = SearchRequest(**cast(Any, raw_request))
            _validate_search_request(search_request)
            with server._snapshot.read_scope():
                result = SearchOrchestra(server._snapshot).search(search_request)
                data = result.to_dict()
                result_rows = cast(list[dict[str, object]], data.pop("results"))
                response = _envelope(
                    server._snapshot,
                    namespace,
                    result.query_hash,
                    result_rows,
                    truncated=result.truncated,
                    omitted=result.omitted,
                )
                response["orchestra"] = data
                return response
        except (StoreUnavailable, sqlite3.Error):
            return _error_envelope("StoreUnavailable", locals().get("query_hash"))
        except _BudgetExceeded:
            return _error_envelope("BudgetExceeded", locals().get("query_hash"))
        except _NamespaceDisclosureDenied:
            return _error_envelope("NamespaceDisclosureError", locals().get("query_hash"))
        except (TypeError, KeyError):
            return _error_envelope("SchemaValidationError", locals().get("query_hash"))
        except ValueError as exc:
            error_type = "InvalidNamespace" if "namespace" in str(exc).lower() else "SchemaValidationError"
            return _error_envelope(error_type, locals().get("query_hash"))

    @server.tool(name="concept_neighborhood", structured_output=True)
    def concept_neighborhood(
        uri: str,
        budgets: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return _neighborhood_query(server._snapshot, uri, budgets)

    @server.tool(name="concept_path", structured_output=True)
    def concept_path(
        source_uri: str,
        target_uri: str,
        budgets: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return _path_query(server._snapshot, source_uri, target_uri, budgets)

    @server.tool(name="concept_hypothesis_get", structured_output=True)
    def concept_hypothesis_get(uri: str) -> dict[str, object]:
        try:
            parsed = validate_concept_uri(uri)
        except (TypeError, ValueError):
            return _error_envelope("InvalidConceptURI", None)
        query_hash = _query_hash({"tool": "concept_hypothesis_get", "uri": parsed.uri})
        if parsed.kind != "hypothesis":
            return _error_envelope("InvalidHypothesisURI", query_hash, namespace=parsed.namespace)
        try:
            with server._snapshot.read_scope():
                node = server._snapshot.get_node(parsed.uri)
                if node is None:
                    return _envelope(server._snapshot, parsed.namespace, query_hash, [])
                if node.type != "Hypothesis":
                    return _error_envelope(
                        "InvalidHypothesisURI", query_hash, namespace=parsed.namespace
                    )
                payload = cast(Any, node.payload)
                result = {
                    "hypothesis": node.to_dict(),
                    "lineage": _json_value(payload.lineage),
                    "score_snapshot": _json_value(payload.score_snapshot),
                    "export_observations": list(
                        server._snapshot.iter_outbox(parsed.namespace, parsed.uri)
                    ),
                }
                return _envelope(server._snapshot, parsed.namespace, query_hash, [result])
        except StoreUnavailable:
            return _error_envelope("StoreUnavailable", query_hash)

    # Defensive registration assertion: keeping the allow-list local makes accidental expansion
    # fail at construction rather than silently widening the public boundary.
    registered = tuple(tool.name for tool in server._tool_manager.list_tools())
    if registered != _TOOL_NAMES or set(registered) & _FORBIDDEN_TOOL_NAMES:
        raise RuntimeError("Concept OS MCP tool allow-list invariant failed")


def _neighborhood_query(
    snapshot: _ReadOnlySnapshot,
    uri: str,
    budgets: Mapping[str, object] | None,
) -> dict[str, object]:
    try:
        parsed = validate_concept_uri(uri)
        budget = _traversal_budgets(budgets)
        with snapshot.read_scope():
            query = TraversalRequest(
                namespace=parsed.namespace,
                roots=(parsed,),
                direction=OUTGOING,
                families=EDGE_FAMILIES,
                max_hops=budget["max_hops"],
                max_expansions=budget["max_expansions"],
                max_results=budget["max_results"],
                max_serialized_bytes=budget["max_serialized_bytes"],
            )
            result = traverse(cast(Any, snapshot), query)
            query_hash = result.query_hash
            payload, extra_omitted = _neighborhood_payload(snapshot, result, budget)
            return _envelope(
                snapshot,
                parsed.namespace,
                query_hash,
                [payload],
                truncated=result.truncated or extra_omitted > 0,
                omitted=result.omitted + extra_omitted,
            )
    except StoreUnavailable:
        return _error_envelope("StoreUnavailable", locals().get("query_hash"))
    except _BudgetExceeded:
        return _error_envelope("BudgetExceeded", locals().get("query_hash"), namespace=_safe_namespace(uri))
    except TraversalError:
        return _error_envelope("MissingEndpoint", locals().get("query_hash"), namespace=_safe_namespace(uri))
    except (TypeError, ValueError):
        return _error_envelope(
            "InvalidConceptURI" if not _looks_like_concept_uri(uri) else "SchemaValidationError",
            locals().get("query_hash"),
            namespace=_safe_namespace(uri),
        )


def _path_query(
    snapshot: _ReadOnlySnapshot,
    source_uri: str,
    target_uri: str,
    budgets: Mapping[str, object] | None,
) -> dict[str, object]:
    query_hash: str | None = None
    try:
        source = validate_concept_uri(source_uri)
        target = validate_concept_uri(target_uri)
        if source.namespace != target.namespace:
            return _error_envelope("NamespaceDisclosureError", None)
        budget = _traversal_budgets(budgets)
        with snapshot.read_scope():
            query = TraversalRequest(
                namespace=source.namespace,
                roots=(source,),
                direction=OUTGOING,
                families=EDGE_FAMILIES,
                max_hops=budget["max_hops"],
                max_expansions=budget["max_expansions"],
                max_results=budget["max_results"],
            )
            traversal_result = traverse(cast(Any, snapshot), query)
            query_hash = _query_hash(
                {
                    "tool": "concept_path",
                    "source_uri": source.uri,
                    "target_uri": target.uri,
                    "budgets": budget,
                }
            )
            path = traversal_result.why.get(target.uri)
            if path is None:
                return _envelope(
                    snapshot,
                    source.namespace,
                    query_hash,
                    [],
                    truncated=traversal_result.truncated,
                    omitted=traversal_result.omitted,
                )
            path_payload = {
                "source_uri": source.uri,
                "target_uri": target.uri,
                "why": path.to_dict(),
                "budgets_requested": dict(traversal_result.budgets_requested),
                "budgets_consumed": dict(traversal_result.budgets_consumed),
            }
            if budget["max_serialized_bytes"] < len(canonical_json(cast(Any, path_payload))):
                return _envelope(
                    snapshot,
                    source.namespace,
                    query_hash,
                    [],
                    truncated=True,
                    omitted=traversal_result.omitted + 1,
                    error={"type": "BudgetExceeded", "message": "path exceeds serialized budget"},
                )
            return _envelope(
                snapshot,
                source.namespace,
                query_hash,
                [path_payload],
                truncated=traversal_result.truncated,
                omitted=traversal_result.omitted,
            )
    except StoreUnavailable:
        return _error_envelope("StoreUnavailable", query_hash)
    except _BudgetExceeded:
        return _error_envelope("BudgetExceeded", query_hash, namespace=_safe_namespace(source_uri))
    except TraversalError:
        return _error_envelope("MissingEndpoint", query_hash, namespace=_safe_namespace(source_uri))
    except (TypeError, ValueError):
        return _error_envelope(
            "InvalidConceptURI" if not _looks_like_concept_uri(source_uri) else "SchemaValidationError",
            query_hash,
        )


def _neighborhood_payload(
    snapshot: _ReadOnlySnapshot,
    result: TraversalResult,
    budget: Mapping[str, int],
) -> tuple[dict[str, object], int]:
    members: list[dict[str, object]] = []
    why: dict[str, object] = {}
    omitted = 0
    serialized = 0
    for raw_uri in result.member_uris:
        member_uri = _uri_text(raw_uri)
        node = snapshot.get_node(member_uri)
        path = result.why.get(member_uri)
        if node is None or path is None:
            omitted += 1
            continue
        member = {"uri": member_uri, "node": node.to_dict(), "why": path.to_dict()}
        cost = len(canonical_json(cast(Any, member)))
        if serialized + cost > budget["max_serialized_bytes"]:
            omitted += 1
            continue
        serialized += cost
        members.append(member)
        why[member_uri] = path.to_dict()
    payload = {
        "type": "SemanticNeighborhood",
        "center_uri": _uri_text(result.roots[0]),
        "members": members,
        "why": why,
        "graph_snapshot_hash": result.graph_snapshot_hash,
        "query_hash": result.query_hash,
        "budgets_requested": dict(result.budgets_requested),
        "budgets_consumed": dict(result.budgets_consumed),
        "omitted": result.omitted + omitted,
        "truncated": result.truncated or omitted > 0,
    }
    return payload, omitted


def _get_record(snapshot: _ReadOnlySnapshot, parsed: ConceptURI) -> dict[str, object] | None:
    if parsed.kind == "edge":
        record = snapshot.get_edge(parsed.uri)
    elif parsed.kind in {"outbox"}:
        return None
    else:
        record = snapshot.get_node(parsed.uri)
    return record.to_dict() if record is not None else None


def _traversal_budgets(budgets: Mapping[str, object] | None) -> dict[str, int]:
    if budgets is None:
        return dict(_DEFAULT_TRAVERSAL_BUDGETS)
    if not isinstance(budgets, Mapping):
        raise TypeError("budgets must be an object")
    unknown = set(budgets) - _BUDGET_KEYS
    if unknown:
        raise ValueError("unknown budget field")
    result = dict(_DEFAULT_TRAVERSAL_BUDGETS)
    for name, value in budgets.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"budgets.{name} must be a non-negative integer")
        if value > _MAX_TRAVERSAL_BUDGETS[name]:
            raise _BudgetExceeded(f"budgets.{name} exceeds the server ceiling")
        result[name] = value
    return result


def _validate_search_request(request: SearchRequest) -> None:
    if request.disclosure_policy != "same_namespace":
        raise _NamespaceDisclosureDenied("MCP only permits same_namespace disclosure")
    budgets = request.budgets
    if not isinstance(budgets, Mapping):
        raise TypeError("search budgets must be an object")
    unknown = set(budgets) - _SEARCH_BUDGET_KEYS
    if unknown:
        raise ValueError("unknown search budget field")
    for name in _SEARCH_BUDGET_KEYS:
        value = budgets.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"budgets.{name} must be a positive integer")
        if value > _MAX_SEARCH_BUDGETS[name]:
            raise _BudgetExceeded(f"budgets.{name} exceeds the server ceiling")


def _envelope(
    snapshot: _ReadOnlySnapshot,
    namespace: str,
    query_hash: str | None,
    results: Iterable[Mapping[str, object]],
    *,
    truncated: bool = False,
    omitted: int = 0,
    error: Mapping[str, object] | None = None,
) -> dict[str, object]:
    try:
        graph_hash = snapshot.snapshot_hash(namespace)
    except StoreUnavailable:
        return _error_envelope("StoreUnavailable", query_hash, namespace=namespace)
    response: dict[str, object] = {
        "authority": "exploratory",
        "trust": "untrusted_candidate",
        "graph_snapshot_hash": graph_hash,
        "query_hash": query_hash,
        "truncated": bool(truncated),
        "omitted": max(0, int(omitted)),
        "results": [dict(result) for result in results],
    }
    if error is not None:
        response["error"] = dict(error)
    return response


def _error_envelope(
    error_type: str,
    query_hash: str | None,
    *,
    namespace: str | None = None,
    message: str | None = None,
) -> dict[str, object]:
    response: dict[str, object] = {
        "authority": "exploratory",
        "trust": "untrusted_candidate",
        "graph_snapshot_hash": _UNAVAILABLE_HASH,
        "query_hash": query_hash,
        "truncated": False,
        "omitted": 0,
        "results": [],
        "error": {
            "type": error_type,
            "message": message or _safe_error_message(error_type),
        },
    }
    if namespace is not None:
        response["namespace"] = namespace
    return response


def _safe_error_message(error_type: str) -> str:
    return {
        "InvalidConceptURI": "the URI is not a valid Concept OS URI",
        "InvalidHypothesisURI": "the URI does not name a Hypothesis",
        "InvalidNamespace": "the namespace is invalid",
        "NamespaceDisclosureError": "cross-namespace disclosure is not permitted",
        "MissingEndpoint": "the requested endpoint is absent",
        "SchemaValidationError": "the query does not satisfy the tool schema",
        "StoreUnavailable": "the Concept OS read snapshot is unavailable",
        "BudgetExceeded": "the requested budget cannot contain one whole result",
    }.get(error_type, "the query could not be completed")


def _request_namespace(request: Mapping[str, object]) -> str:
    namespace = request.get("namespace")
    if not isinstance(namespace, str):
        raise ValueError("namespace is required")
    parsed = validate_concept_uri(f"concept://{namespace}/concept/00000000000000000000000000")
    return parsed.namespace


def _query_hash(value: Mapping[str, object]) -> str | None:
    try:
        return content_hash(canonical_json(cast(Any, value)))
    except (TypeError, ValueError) as exc:
        _LOGGER.debug("Concept OS MCP query hash unavailable: %s", type(exc).__name__)
        return None


def _json_object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("query must be a JSON object")
    _json_value(value)
    return value


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError("query values must be JSON data")


def _canonical_object(raw: bytes | str) -> dict[str, object]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise StoreUnavailable("stored record is not an object")
    return {str(key): item for key, item in value.items()}


def _node_from_row(row: sqlite3.Row) -> NodeEnvelope:
    data = _canonical_object(row["canonical_json"])
    data.update({"id": row["uri"], "recorded_at": row["recorded_at"]})
    value = from_dict(data)
    if not isinstance(value, NodeEnvelope):
        raise StoreUnavailable("stored node is not a node envelope")
    return value


def _edge_from_row(row: sqlite3.Row) -> EdgeEnvelope:
    data = _canonical_object(row["canonical_json"])
    data.update({"id": row["uri"], "recorded_at": row["recorded_at"]})
    value = from_dict(data)
    if not isinstance(value, EdgeEnvelope):
        raise StoreUnavailable("stored edge is not an edge envelope")
    return value


def _uri_text(value: ConceptURI | str) -> str:
    return value.uri if isinstance(value, ConceptURI) else value


def _looks_like_concept_uri(value: object) -> bool:
    return isinstance(value, str) and value.startswith("concept://")


def _safe_namespace(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return validate_concept_uri(value).namespace
    except (TypeError, ValueError) as exc:
        _LOGGER.debug("Concept OS MCP namespace unavailable: %s", type(exc).__name__)
        return None


def main() -> None:  # pragma: no cover - stdio deployment seam
    raise RuntimeError("build_concept_mcp_server(database) is required before running the MCP transport")


if __name__ == "__main__":  # pragma: no cover
    main()
