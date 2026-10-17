"""KAE citation ingestion with byte-exact CAS anchoring.

External documents enter the graph only through a verified SHA-256 CAS address.  Citation
spans are represented as candidate ``EvidenceRef`` nodes; immutable Task 22 Decisions and
Constraints are never rewritten, only linked by deterministic edges.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from sakg.store import Edge, GraphStore

NAMESPACE = "paeos-history"
INGESTED_AT = "2026-09-04T00:00:00Z"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_CITATION = re.compile(
    rb"(?m)^[ \t]*(?:\[\d+\]|(?:CITATION|REFERENCE)[ \t]*[:#])[ \t]*(?P<body>[^\r\n]+?)[ \t]*(?:\r?\n|$)"
)
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class CitationPipelineError(ValueError):
    """A source, CAS blob, citation, or linkage failed closed validation."""


class CasReferenceError(CitationPipelineError):
    """The supplied CAS address is missing, malformed, or content-mismatched."""


class CitationLinkError(CitationPipelineError):
    """A requested Decision/Constraint linkage is absent or crosses a namespace."""


@dataclass(frozen=True, slots=True)
class CitationSpan:
    cas_hash: str
    uri: str
    byte_start: int
    byte_end: int
    line_start: int
    line_end: int
    citation_hash: str
    text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "cas_hash": self.cas_hash,
            "uri": self.uri,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "citation_hash": self.citation_hash,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class CitationIngestReport:
    sources_seen: int
    citations_seen: int
    nodes_appended: int
    nodes_replayed: int
    edges_appended: int
    edges_replayed: int

    @property
    def nodes_total(self) -> int:
        return self.nodes_appended + self.nodes_replayed

    @property
    def edges_total(self) -> int:
        return self.edges_appended + self.edges_replayed

    def to_dict(self) -> dict[str, int]:
        return {
            "sources_seen": self.sources_seen,
            "citations_seen": self.citations_seen,
            "nodes_appended": self.nodes_appended,
            "nodes_replayed": self.nodes_replayed,
            "nodes_total": self.nodes_total,
            "edges_appended": self.edges_appended,
            "edges_replayed": self.edges_replayed,
            "edges_total": self.edges_total,
        }


def _id(namespace: str, kind: str, key: str) -> str:
    number = int.from_bytes(hashlib.sha256(f"{namespace}:{kind}:{key}".encode()).digest()[:16], "big")
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        number, remainder = divmod(number, 32)
        chars[index] = _ALPHABET[remainder]
    return f"sakg://{namespace}/{kind}/{''.join(chars)}"


def _edge(namespace: str, source: str, target: str, family: str, relation: str, key: str) -> Edge:
    edge_key = hashlib.sha256(f"{family}:{relation}:{key}".encode()).hexdigest()[:32]
    return Edge(
        edge_id=f"edge:task24:{edge_key}", namespace=namespace, source=source, target=target,
        family=family, relation=relation,
        properties={"origin": "kae-citation-pipeline", "deterministic": True},
        evidence=(), created_at=INGESTED_AT,
    )


def _read_cas(cas: object, digest: str) -> bytes:
    if not isinstance(digest, str) or _HASH.fullmatch(digest) is None:
        raise CasReferenceError("cas_hash must be a lowercase SHA-256 address")
    try:
        if hasattr(cas, "get"):
            content = cas.get(digest)  # type: ignore[attr-defined]
        elif hasattr(cas, "read"):
            content = cas.read(digest)  # type: ignore[attr-defined]
        elif callable(cas):
            content = cas(digest)
        else:
            raise TypeError("CAS reader must expose get/read or be callable")
    except Exception as exc:
        raise CasReferenceError(f"CAS reference is unavailable: {digest}") from exc
    if not isinstance(content, bytes) or hashlib.sha256(content).hexdigest() != digest:
        raise CasReferenceError(f"CAS content does not match address: {digest}")
    return content


def extract_citations(cas: object, source: Mapping[str, object]) -> tuple[CitationSpan, ...]:
    """Read one manifest source and return byte-anchored citation spans in stable order."""
    digest = source.get("cas_hash", source.get("hash"))
    if not isinstance(digest, str) or _HASH.fullmatch(digest) is None:
        raise CasReferenceError("source.cas_hash must be a lowercase SHA-256 address")
    uri = source.get("uri", f"cas://{digest}")
    if not isinstance(uri, str) or not uri.strip():
        raise CitationPipelineError("source.uri must be non-empty")
    content = _read_cas(cas, digest)
    try:
        matches = list(_CITATION.finditer(content))
        spans: list[CitationSpan] = []
        for match in matches:
            start, end = match.span("body")
            raw = content[start:end]
            text = raw.decode("utf-8")
            spans.append(CitationSpan(
                cas_hash=digest, uri=uri, byte_start=start, byte_end=end,
                line_start=content.count(b"\n", 0, start) + 1,
                line_end=content.count(b"\n", 0, max(start, end - 1)) + 1,
                citation_hash=hashlib.sha256(raw).hexdigest(), text=text,
            ))
    except UnicodeDecodeError as exc:
        raise CitationPipelineError("citation span is not valid UTF-8") from exc
    return tuple(spans)


def _linked_nodes(store: GraphStore, source: Mapping[str, object], namespace: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    requested_decisions = source.get("decision_ids", ())
    requested_constraints = source.get("constraint_ids", ())
    if requested_decisions is not None and not isinstance(requested_decisions, (list, tuple)):
        raise CitationLinkError("decision_ids must be an array")
    if requested_constraints is not None and not isinstance(requested_constraints, (list, tuple)):
        raise CitationLinkError("constraint_ids must be an array")

    def resolve(raw: object, expected: str) -> list[dict[str, object]]:
        values = list(raw) if isinstance(raw, (list, tuple)) and raw else []
        if not values:
            return sorted((node for node in store.nodes() if node["type"] == expected), key=lambda node: str(node["id"]))[:1]
        result: list[dict[str, object]] = []
        for value in values:
            if not isinstance(value, str) or not value.startswith(f"sakg://{namespace}/{expected}/"):
                raise CitationLinkError(f"{expected} linkage crosses namespace or type")
            node = store.get_node(value)
            if node is None or node["type"] != expected:
                raise CitationLinkError(f"linked {expected} is absent: {value}")
            result.append(node)
        return sorted(result, key=lambda node: str(node["id"]))

    return resolve(requested_decisions, "Decision"), resolve(requested_constraints, "Constraint")


def ingest_citations(cas: object, sources: Iterable[Mapping[str, object]], store: GraphStore,
                     *, namespace: str = NAMESPACE) -> CitationIngestReport:
    """Ingest all citation spans from CAS manifests into an append-only GraphStore."""
    manifests = sorted((dict(source) for source in sources), key=lambda source: (
        str(source.get("cas_hash", source.get("hash", ""))), str(source.get("uri", ""))))
    nodes_appended = nodes_replayed = edges_appended = edges_replayed = citations_seen = 0
    for source in manifests:
        spans = extract_citations(cas, source)
        decisions, constraints = _linked_nodes(store, source, namespace)
        for span in spans:
            key = f"{span.cas_hash}:{span.byte_start}:{span.byte_end}:{span.citation_hash}"
            node = {
                "id": _id(namespace, "EvidenceRef", key), "type": "EvidenceRef", "namespace": namespace,
                "facets": {"cas": {"hash": span.cas_hash, "uri": span.uri},
                           "anchor": {"byte_start": span.byte_start, "byte_end": span.byte_end,
                                      "line_start": span.line_start, "line_end": span.line_end,
                                      "citation_hash": span.citation_hash},
                           "citation": {"text": span.text}},
                "label": f"Citation {span.cas_hash[:12]}:{span.byte_start}-{span.byte_end}",
                "summary": "Byte-anchored citation extracted from an immutable CAS document.",
                "provenance": {"origin": {"system": "kae", "run_id": "task-24-kae-cas-citations"},
                               "author_kind": "ingest", "ingested_at": INGESTED_AT,
                               "source_hash": span.cas_hash},
                "evidence": [{"hash": span.cas_hash, "uri": f"cas://{span.cas_hash}", "kind": "source",
                              "reverification": "re-read the exact CAS bytes and verify the anchor hash"}],
                "status": "candidate", "confidence": 0.8, "valid_from": INGESTED_AT,
                "valid_until": None, "falsifier": None,
                "coordinates": {"domain": ["external-knowledge"], "source": [span.uri]},
            }
            existed = store.get_node(str(node["id"])) is not None
            store.append_node(node)
            if existed:
                nodes_replayed += 1
            else:
                nodes_appended += 1
            citations_seen += 1
            for target in decisions:
                edge = _edge(namespace, str(node["id"]), str(target["id"]), "causal", "justified_by", key + str(target["id"]))
                edge_existed = store.get_edge(edge.edge_id) is not None
                store.append_edge(edge)
                edges_replayed += int(edge_existed)
                edges_appended += int(not edge_existed)
            for target in constraints:
                edge = _edge(namespace, str(node["id"]), str(target["id"]), "constraint", "evidence", key + str(target["id"]))
                edge_existed = store.get_edge(edge.edge_id) is not None
                store.append_edge(edge)
                edges_replayed += int(edge_existed)
                edges_appended += int(not edge_existed)
    return CitationIngestReport(len(manifests), citations_seen, nodes_appended, nodes_replayed,
                                edges_appended, edges_replayed)


def ingest_manifest(cas: object, manifest_path: str | Path, store: GraphStore,
                    *, namespace: str = NAMESPACE) -> CitationIngestReport:
    """Load a JSON array of CAS source manifests and ingest it."""
    import json
    try:
        raw = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CitationPipelineError("citation manifest is unreadable JSON") from exc
    if not isinstance(raw, list) or any(not isinstance(item, Mapping) for item in raw):
        raise CitationPipelineError("citation manifest must be an array of source objects")
    return ingest_citations(cas, raw, store, namespace=namespace)


__all__ = ["CasReferenceError", "CitationIngestReport", "CitationLinkError", "CitationPipelineError", "CitationSpan", "extract_citations", "ingest_citations", "ingest_manifest"]
