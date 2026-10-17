"""Durable, append-only SAKG graph storage.

The store accepts only the universal §4.2 node envelope and keeps every write in an
append-only SQLite log.  Supersession is represented by a new node whose facets point
to the prior node; historical rows are never updated or deleted.  Edges are first-class
objects: relation metadata stays under ``properties`` rather than being flattened into
the endpoint rows.
"""

from __future__ import annotations

import copy
import json
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "EDGE_FAMILIES",
    "AppendOnlyViolation",
    "DuplicateIdentity",
    "Edge",
    "EdgeFamilyError",
    "EnvelopeValidationError",
    "GraphStore",
    "NamespaceViolation",
    "SAKGStore",
    "Store",
    "StoreError",
]


EDGE_FAMILIES: tuple[str, ...] = (
    "structural",
    "dependency",
    "causal",
    "optimization",
    "constraint",
    "tradeoff",
    "problem",
    "similarity",
)
_EDGE_FAMILY_SET = frozenset(EDGE_FAMILIES)
_NODE_ID = re.compile(
    r"^sakg://[^/]+/(?:Decision|Problem|Option|Constraint|Objective|TradeOff|Mechanism|Pattern|Component|Outcome|Scar|EvidenceRef|TaxonomyNode)/[0-9A-HJKMNP-TV-Z]{26}$"
)
_NAMESPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_EVIDENCE_KINDS = frozenset({"artifact", "test", "report", "observation", "decision", "source"})
_NODE_TYPES = frozenset(
    {
        "Decision",
        "Problem",
        "Option",
        "Constraint",
        "Objective",
        "TradeOff",
        "Mechanism",
        "Pattern",
        "Component",
        "Outcome",
        "Scar",
        "EvidenceRef",
        "TaxonomyNode",
    }
)
_STATUSES = frozenset({"candidate", "canonical", "superseded", "refuted"})
_AUTHOR_KINDS = frozenset({"human", "agent", "ingest", "inferred"})


class StoreError(Exception):
    """Base class for fail-closed graph-store errors."""


class EnvelopeValidationError(StoreError, ValueError):
    """A node does not satisfy the universal §4.2 envelope."""


class NamespaceViolation(StoreError, ValueError):
    """An object or query attempts to cross the store's namespace boundary."""


class DuplicateIdentity(StoreError, ValueError):
    """An append would reuse an identity with different content."""


class AppendOnlyViolation(StoreError, RuntimeError):
    """A destructive mutation was requested from an append-only store."""


class EdgeFamilyError(StoreError, ValueError):
    """An edge does not name one of the eight registered edge families."""


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise EnvelopeValidationError("object is not JSON serializable") from exc


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise EnvelopeValidationError(f"{field_name} must be an object")
    return value


def _as_text(value: object, field_name: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise EnvelopeValidationError(f"{field_name} must be a non-empty string")
    return value


def _check_datetime(value: object, field_name: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    text = _as_text(value, field_name)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EnvelopeValidationError(f"{field_name} must be RFC 3339 date-time") from exc


def _check_evidence(value: object, field_name: str) -> None:
    if not isinstance(value, list):
        raise EnvelopeValidationError(f"{field_name} must be an array")
    for index, item in enumerate(value):
        evidence = _as_mapping(item, f"{field_name}[{index}]")
        required = {"hash", "uri", "kind", "reverification"}
        if not required.issubset(evidence):
            raise EnvelopeValidationError(f"{field_name}[{index}] is missing a required field")
        digest = _as_text(evidence["hash"], f"{field_name}[{index}].hash")
        if _HASH.fullmatch(digest) is None:
            raise EnvelopeValidationError(f"{field_name}[{index}].hash is not SHA-256")
        kind = _as_text(evidence["kind"], f"{field_name}[{index}].kind")
        if kind not in _EVIDENCE_KINDS:
            raise EnvelopeValidationError(f"{field_name}[{index}].kind is unknown")
        _as_text(evidence["uri"], f"{field_name}[{index}].uri")
        _as_text(evidence["reverification"], f"{field_name}[{index}].reverification")


def validate_node_envelope(node: Mapping[str, object], namespace: str | None = None) -> None:
    """Validate the complete §4.2 envelope before it reaches SQLite."""
    required = {
        "id",
        "type",
        "namespace",
        "facets",
        "label",
        "summary",
        "provenance",
        "evidence",
        "status",
        "confidence",
        "valid_from",
        "valid_until",
        "falsifier",
        "coordinates",
    }
    if set(node) != required:
        missing = sorted(required - set(node))
        extra = sorted(set(node) - required)
        raise EnvelopeValidationError(f"envelope fields mismatch; missing={missing}, extra={extra}")
    node_id = _as_text(node["id"], "id")
    if _NODE_ID.fullmatch(node_id) is None:
        raise EnvelopeValidationError("id is not a typed SAKG identifier")
    node_type = _as_text(node["type"], "type")
    if node_type not in _NODE_TYPES:
        raise EnvelopeValidationError("type is not in the universal vocabulary")
    object_namespace = _as_text(node["namespace"], "namespace")
    if _NAMESPACE.fullmatch(object_namespace) is None:
        raise EnvelopeValidationError("namespace is malformed")
    id_namespace = node_id.split("/", 3)[2]
    if id_namespace != object_namespace:
        raise NamespaceViolation("node id and envelope namespace differ")
    if namespace is not None and object_namespace != namespace:
        raise NamespaceViolation(
            f"object belongs to namespace {object_namespace!r}, not {namespace!r}"
        )
    facets = _as_mapping(node["facets"], "facets")
    if any(not isinstance(value, Mapping) for value in facets.values()):
        raise EnvelopeValidationError("every facets value must be an object")
    label = _as_text(node["label"], "label")
    if len(label) > 160:
        raise EnvelopeValidationError("label exceeds 160 characters")
    summary = node["summary"]
    if not isinstance(summary, str) or len(summary) > 280:
        raise EnvelopeValidationError("summary must be a string of at most 280 characters")
    provenance = _as_mapping(node["provenance"], "provenance")
    provenance_required = {"origin", "author_kind", "ingested_at", "source_hash"}
    if set(provenance) != provenance_required:
        raise EnvelopeValidationError("provenance fields mismatch")
    origin = _as_mapping(provenance["origin"], "provenance.origin")
    if set(origin) != {"system", "run_id"}:
        raise EnvelopeValidationError("provenance.origin fields mismatch")
    _as_text(origin["system"], "provenance.origin.system")
    _as_text(origin["run_id"], "provenance.origin.run_id")
    author_kind = _as_text(provenance["author_kind"], "provenance.author_kind")
    if author_kind not in _AUTHOR_KINDS:
        raise EnvelopeValidationError("unknown provenance author_kind")
    _check_datetime(provenance["ingested_at"], "provenance.ingested_at")
    source_hash = _as_text(provenance["source_hash"], "provenance.source_hash")
    if _HASH.fullmatch(source_hash) is None:
        raise EnvelopeValidationError("provenance.source_hash is not SHA-256")
    _check_evidence(node["evidence"], "evidence")
    status = _as_text(node["status"], "status")
    if status not in _STATUSES:
        raise EnvelopeValidationError("unknown node status")
    confidence = node["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        raise EnvelopeValidationError("confidence must be a number between 0 and 1")
    _check_datetime(node["valid_from"], "valid_from")
    _check_datetime(node["valid_until"], "valid_until", nullable=True)
    if node["falsifier"] is not None and not isinstance(node["falsifier"], str):
        raise EnvelopeValidationError("falsifier must be a string or null")
    coordinates = _as_mapping(node["coordinates"], "coordinates")
    for key, values in coordinates.items():
        _as_text(key, "coordinate key")
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value for value in values
        ):
            raise EnvelopeValidationError("coordinates must map to non-empty string arrays")


@dataclass(frozen=True, slots=True)
class Edge:
    """An edge-as-object; relation metadata is never flattened into a node."""

    edge_id: str
    namespace: str
    source: str
    target: str
    family: str
    relation: str
    properties: Mapping[str, object] = field(default_factory=dict)
    evidence: tuple[Mapping[str, object], ...] = ()
    created_at: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "edge_id": self.edge_id,
            "namespace": self.namespace,
            "source": self.source,
            "target": self.target,
            "family": self.family,
            "relation": self.relation,
            "properties": dict(self.properties),
            "evidence": [dict(item) for item in self.evidence],
            "created_at": self.created_at or _now(),
        }


def _normalise_edge(value: Edge | Mapping[str, object], namespace: str) -> dict[str, object]:
    data = value.to_dict() if isinstance(value, Edge) else dict(value)
    required = {
        "edge_id",
        "namespace",
        "source",
        "target",
        "family",
        "relation",
        "properties",
        "evidence",
        "created_at",
    }
    if set(data) != required:
        raise EnvelopeValidationError("edge fields mismatch")
    edge_namespace = _as_text(data["namespace"], "edge.namespace")
    if edge_namespace != namespace:
        raise NamespaceViolation("edge namespace does not match the store")
    edge_id = _as_text(data["edge_id"], "edge.edge_id")
    source = _as_text(data["source"], "edge.source")
    target = _as_text(data["target"], "edge.target")
    for endpoint in (source, target):
        if _NODE_ID.fullmatch(endpoint) is None or endpoint.split("/", 3)[2] != namespace:
            raise NamespaceViolation("edge endpoint crosses the store namespace")
    family = _as_text(data["family"], "edge.family")
    if family not in _EDGE_FAMILY_SET:
        raise EdgeFamilyError(f"unknown edge family: {family}")
    _as_text(data["relation"], "edge.relation")
    properties = _as_mapping(data["properties"], "edge.properties")
    if not isinstance(data["evidence"], list):
        raise EnvelopeValidationError("edge.evidence must be an array")
    _check_evidence(data["evidence"], "edge.evidence")
    _check_datetime(data["created_at"], "edge.created_at")
    return {
        "edge_id": edge_id,
        "namespace": edge_namespace,
        "source": source,
        "target": target,
        "family": family,
        "relation": str(data["relation"]),
        "properties": dict(properties),
        "evidence": list(data["evidence"]),
        "created_at": str(data["created_at"]),
    }


class GraphStore:
    """Namespace-scoped SQLite graph store with append-only enforcement."""

    def __init__(self, path: str | Path = "sakg.db", namespace: str = "paeos-history") -> None:
        if _NAMESPACE.fullmatch(namespace) is None:
            raise NamespaceViolation("store namespace is malformed")
        self.namespace = namespace
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
            database = str(self.path)
        else:
            database = ":memory:"
        # Each append is a durable event.  Autocommit prevents a process/session
        # close from silently rolling back a successful append.
        self._db = sqlite3.connect(database, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                namespace TEXT NOT NULL,
                node_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                appended_at TEXT NOT NULL,
                PRIMARY KEY (namespace, node_id)
            );
            CREATE TABLE IF NOT EXISTS edges (
                namespace TEXT NOT NULL,
                edge_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                family TEXT NOT NULL,
                relation TEXT NOT NULL,
                payload TEXT NOT NULL,
                appended_at TEXT NOT NULL,
                PRIMARY KEY (namespace, edge_id),
                FOREIGN KEY (namespace, source_id) REFERENCES nodes(namespace, node_id),
                FOREIGN KEY (namespace, target_id) REFERENCES nodes(namespace, node_id)
            );
            CREATE TRIGGER IF NOT EXISTS nodes_append_only_update
                BEFORE UPDATE ON nodes BEGIN SELECT RAISE(ABORT, 'nodes are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS nodes_append_only_delete
                BEFORE DELETE ON nodes BEGIN SELECT RAISE(ABORT, 'nodes are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS edges_append_only_update
                BEFORE UPDATE ON edges BEGIN SELECT RAISE(ABORT, 'edges are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS edges_append_only_delete
                BEFORE DELETE ON edges BEGIN SELECT RAISE(ABORT, 'edges are append-only'); END;
            CREATE INDEX IF NOT EXISTS edges_namespace_family ON edges(namespace, family);
            """
        )

    def append_node(self, node: Mapping[str, object]) -> str:
        validate_node_envelope(node, self.namespace)
        node_id = str(node["id"])
        payload = _canonical(node)
        row = self._db.execute(
            "SELECT payload FROM nodes WHERE namespace = ? AND node_id = ?",
            (self.namespace, node_id),
        ).fetchone()
        if row is not None:
            if str(row["payload"]) == payload:
                return node_id
            raise DuplicateIdentity(f"node identity already contains different content: {node_id}")
        self._db.execute(
            "INSERT INTO nodes(namespace, node_id, payload, appended_at) VALUES (?, ?, ?, ?)",
            (self.namespace, node_id, payload, _now()),
        )
        return node_id

    put_node = append_node

    def supersede_node(self, node: Mapping[str, object], previous_id: str) -> str:
        previous = self.get_node(previous_id)
        if previous is None:
            raise StoreError(f"cannot supersede missing node: {previous_id}")
        candidate = copy.deepcopy(dict(node))
        facets = dict(_as_mapping(candidate.get("facets"), "facets"))
        facets["supersedes"] = {"node_id": previous_id}
        candidate["facets"] = facets
        return self.append_node(candidate)

    def get_node(self, node_id: str) -> dict[str, object] | None:
        self._assert_id_namespace(node_id)
        row = self._db.execute(
            "SELECT payload FROM nodes WHERE namespace = ? AND node_id = ?",
            (self.namespace, node_id),
        ).fetchone()
        return None if row is None else dict(json.loads(str(row["payload"])))

    def nodes(self) -> tuple[dict[str, object], ...]:
        rows = self._db.execute(
            "SELECT payload FROM nodes WHERE namespace = ? ORDER BY node_id", (self.namespace,)
        ).fetchall()
        return tuple(dict(json.loads(str(row["payload"]))) for row in rows)

    def query_nodes(self, node_type: str | None = None) -> tuple[dict[str, object], ...]:
        """Read-only operator query over the append-only node projection."""
        values = self.nodes()
        if node_type is None:
            return values
        if node_type not in _NODE_TYPES:
            raise ValueError(f"unknown node type: {node_type}")
        return tuple(node for node in values if node["type"] == node_type)

    def append_edge(self, edge: Edge | Mapping[str, object]) -> str:
        data = _normalise_edge(edge, self.namespace)
        edge_id = str(data["edge_id"])
        for endpoint in (str(data["source"]), str(data["target"])):
            if self.get_node(endpoint) is None:
                raise StoreError(f"edge endpoint is not present in this namespace: {endpoint}")
        payload = _canonical(data)
        row = self._db.execute(
            "SELECT payload FROM edges WHERE namespace = ? AND edge_id = ?",
            (self.namespace, edge_id),
        ).fetchone()
        if row is not None:
            if str(row["payload"]) == payload:
                return edge_id
            raise DuplicateIdentity(f"edge identity already contains different content: {edge_id}")
        self._db.execute(
            "INSERT INTO edges(namespace, edge_id, source_id, target_id, family, relation, "
            "payload, appended_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.namespace,
                edge_id,
                data["source"],
                data["target"],
                data["family"],
                data["relation"],
                payload,
                _now(),
            ),
        )
        return edge_id

    put_edge = append_edge

    def get_edge(self, edge_id: str) -> dict[str, object] | None:
        row = self._db.execute(
            "SELECT payload FROM edges WHERE namespace = ? AND edge_id = ?",
            (self.namespace, edge_id),
        ).fetchone()
        return None if row is None else dict(json.loads(str(row["payload"])))

    def edges(self, family: str | None = None) -> tuple[dict[str, object], ...]:
        if family is not None and family not in _EDGE_FAMILY_SET:
            raise EdgeFamilyError(f"unknown edge family: {family}")
        if family is None:
            rows = self._db.execute(
                "SELECT payload FROM edges WHERE namespace = ? ORDER BY edge_id", (self.namespace,)
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT payload FROM edges WHERE namespace = ? AND family = ? ORDER BY edge_id",
                (self.namespace, family),
            ).fetchall()
        return tuple(dict(json.loads(str(row["payload"]))) for row in rows)

    def delete_node(self, node_id: str) -> None:
        self._assert_id_namespace(node_id)
        raise AppendOnlyViolation("nodes cannot be deleted; append a superseding node instead")

    def delete_edge(self, edge_id: str) -> None:
        raise AppendOnlyViolation("edges cannot be deleted")

    def _assert_id_namespace(self, node_id: str) -> None:
        if _NODE_ID.fullmatch(node_id) is None:
            raise NamespaceViolation("malformed or untyped node identifier")
        if node_id.split("/", 3)[2] != self.namespace:
            raise NamespaceViolation("node identifier crosses the store namespace")

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> GraphStore:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


SAKGStore = GraphStore
Store = GraphStore
