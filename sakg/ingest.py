"""Pull-based candidate ingestion for post-seal PAEOS outbox bundles.

Only CAS-addressed bundles are read.  Every node is validated against the producing
outbox namespace, is required to carry evidence bound to the outbox references, and
lands in the graph store as ``candidate``.  Re-reading an unchanged outbox is a no-op
at the storage layer; no frequency or replay count can promote a node.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from runtime.emission.outbox import OutboxRecord, PostSealOutbox

from sakg.store import GraphStore, validate_node_envelope

__all__ = [
    "EvidenceBindingError",
    "IngestError",
    "IngestIntegrityError",
    "IngestNamespaceError",
    "IngestReport",
    "IngestStatusError",
    "OutboxIngestor",
    "ingest",
    "ingest_outbox",
    "is_promotion_eligible",
    "promotion_eligible",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class IngestError(ValueError):
    """Base class for fail-closed outbox ingestion errors."""


class IngestIntegrityError(IngestError):
    """The CAS bundle or node is malformed or unavailable."""


class IngestNamespaceError(IngestError):
    """A node or bundle attempts to cross the producing namespace boundary."""


class IngestStatusError(IngestError):
    """An upstream node is not a candidate and cannot be silently downgraded."""


class EvidenceBindingError(IngestIntegrityError):
    """A candidate's evidence is absent or not bound to the outbox references."""


class CasReader(Protocol):
    def get(self, key: str) -> bytes: ...


StoreTarget = GraphStore | Mapping[str, GraphStore] | Callable[[str], GraphStore]


@dataclass(frozen=True, slots=True)
class IngestReport:
    """Accounting for one pull operation; ``promoted`` is structurally always zero."""

    records_seen: int
    bundles_read: int
    nodes_appended: int
    nodes_replayed: int
    promoted: int = 0

    @property
    def nodes_total(self) -> int:
        return self.nodes_appended + self.nodes_replayed

    def to_dict(self) -> dict[str, int]:
        return {
            "records_seen": self.records_seen,
            "bundles_read": self.bundles_read,
            "nodes_appended": self.nodes_appended,
            "nodes_replayed": self.nodes_replayed,
            "nodes_total": self.nodes_total,
            "promoted": self.promoted,
        }


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise IngestIntegrityError(f"{field} must be a lowercase SHA-256 hash")
    return value


def _reader_get(reader: CasReader | Callable[[str], bytes], digest: str) -> bytes:
    try:
        value = reader(digest) if callable(reader) else reader.get(digest)
    except Exception as exc:  # CAS implementations expose provider-specific miss errors.
        raise IngestIntegrityError(f"CAS bundle {digest} is unavailable") from exc
    if not isinstance(value, bytes):
        raise IngestIntegrityError("CAS reader returned non-byte content")
    return value


def _store_for(target: StoreTarget, namespace: str) -> GraphStore:
    if isinstance(target, GraphStore):
        if target.namespace != namespace:
            raise IngestNamespaceError(
                "store namespace "
                f"{target.namespace!r} does not match outbox namespace {namespace!r}"
            )
        return target
    if isinstance(target, Mapping):
        try:
            store = target[namespace]
        except KeyError as exc:
            raise IngestNamespaceError(
                f"no graph store is bound to namespace {namespace!r}"
            ) from exc
    else:
        store = target(namespace)
    if not isinstance(store, GraphStore) or store.namespace != namespace:
        raise IngestNamespaceError("namespace resolver returned an incorrectly bound graph store")
    return store


def _bundle_nodes(raw: bytes, record: OutboxRecord) -> list[Mapping[str, object]]:
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IngestIntegrityError(f"bundle {record.artifact_bundle_hash} is not JSON") from exc
    if not isinstance(decoded, Mapping):
        raise IngestIntegrityError("CAS bundle must be an object")
    bundle_namespace = decoded.get("namespace")
    if bundle_namespace is not None and bundle_namespace != record.namespace:
        raise IngestNamespaceError("bundle namespace differs from producing outbox namespace")
    nodes = decoded.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise IngestIntegrityError("CAS bundle must contain a non-empty nodes array")
    if any(not isinstance(item, Mapping) for item in nodes):
        raise IngestIntegrityError("CAS bundle nodes must be objects")
    return list(nodes)


def _candidate_node(
    node: Mapping[str, object],
    record: OutboxRecord,
) -> dict[str, object]:
    candidate = dict(node)
    status = candidate.get("status", "candidate")
    if status != "candidate":
        raise IngestStatusError("ingest accepts candidate nodes only; it never rewrites status")
    candidate["status"] = "candidate"
    node_namespace = candidate.get("namespace", record.namespace)
    if node_namespace != record.namespace:
        raise IngestNamespaceError("node namespace differs from producing outbox namespace")
    candidate["namespace"] = record.namespace
    facets = candidate.get("facets")
    if not isinstance(facets, Mapping):
        raise IngestIntegrityError("candidate facets must be an object")
    # The emission-bundle contract permits compact scalar facet values.  Hydrate them
    # explicitly into the §4.2 envelope shape without discarding source information.
    candidate["facets"] = {
        str(key): dict(value) if isinstance(value, Mapping) else {"value": value}
        for key, value in facets.items()
    }
    provenance = candidate.get("provenance")
    if not isinstance(provenance, Mapping):
        raise IngestIntegrityError("candidate provenance must be an object")
    hydrated_provenance = dict(provenance)
    hydrated_provenance.setdefault("author_kind", "ingest")
    hydrated_provenance.setdefault("ingested_at", record.emitted_at)
    candidate["provenance"] = hydrated_provenance
    candidate.setdefault("confidence", 0.0)
    candidate.setdefault("valid_from", record.emitted_at)
    candidate.setdefault("valid_until", None)
    candidate.setdefault("falsifier", None)
    candidate.setdefault("coordinates", {})
    evidence = candidate.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise EvidenceBindingError("candidate has no evidence references")
    bound_hashes = set(record.evidence_refs)
    for index, item in enumerate(evidence):
        if not isinstance(item, Mapping):
            raise EvidenceBindingError(f"candidate evidence[{index}] is not an object")
        digest = _hash(item.get("hash"), f"candidate evidence[{index}].hash")
        if digest not in bound_hashes:
            raise EvidenceBindingError(
                f"candidate evidence[{index}] is not bound to the producing outbox record"
            )
    try:
        validate_node_envelope(candidate, record.namespace)
    except Exception as exc:
        raise IngestIntegrityError(
            "candidate does not satisfy the universal node envelope"
        ) from exc
    return candidate


def is_promotion_eligible(node: Mapping[str, object], evidence_hashes: Sequence[str]) -> bool:
    """Pure guard used by callers: ingestion itself can never promote a node."""
    if node.get("status") != "candidate":
        return False
    evidence = node.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return False
    allowed = set(evidence_hashes)
    return all(
        isinstance(item, Mapping)
        and isinstance(item.get("hash"), str)
        and item["hash"] in allowed
        for item in evidence
    )


promotion_eligible = is_promotion_eligible


class OutboxIngestor:
    """Pull immutable outbox references into one or more namespace-bound stores."""

    def __init__(
        self,
        outbox: PostSealOutbox | str | Path,
        store: StoreTarget,
        cas: CasReader | Callable[[str], bytes],
    ) -> None:
        self.outbox = outbox if isinstance(outbox, PostSealOutbox) else PostSealOutbox(outbox)
        self.store = store
        self.cas = cas

    def ingest(self) -> IngestReport:
        records = self.outbox.records()
        appended = 0
        replayed = 0
        for record in records:
            store = _store_for(self.store, record.namespace)
            bundle = _reader_get(self.cas, record.artifact_bundle_hash)
            nodes = [_candidate_node(node, record) for node in _bundle_nodes(bundle, record)]
            # Validate every node and existing identity before writing any node from this
            # bundle: malformed or conflicting bundles cannot leave partial projections.
            pending: list[dict[str, object]] = []
            for node in nodes:
                node_id = str(node["id"])
                prior = store.get_node(node_id)
                if prior is not None:
                    if prior != node:
                        raise IngestIntegrityError(
                            f"candidate identity {node_id!r} conflicts with history"
                        )
                    replayed += 1
                else:
                    pending.append(node)
            for node in pending:
                store.append_node(node)
                appended += 1
        return IngestReport(len(records), len(records), appended, replayed)


def ingest_outbox(
    outbox: PostSealOutbox | str | Path,
    store: StoreTarget,
    cas: CasReader | Callable[[str], bytes],
) -> IngestReport:
    """Read all sealed outbox records and append candidate nodes idempotently."""
    return OutboxIngestor(outbox, store, cas).ingest()


def ingest(
    outbox: PostSealOutbox | str | Path,
    store: StoreTarget,
    cas: CasReader | Callable[[str], bytes],
) -> IngestReport:
    """Short alias for :func:`ingest_outbox`."""
    return ingest_outbox(outbox, store, cas)
