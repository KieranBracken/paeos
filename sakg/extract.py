"""Deterministic PAEOS artifact-to-node extraction.

The extractor is intentionally independent of the runtime and graph store.  It turns
layer artifacts into universal SAKG envelopes while returning an explicit gap ledger;
fields which cannot be mapped are never silently discarded.  Extraction is pure: IDs,
source hashes, timestamps, and JSON serialization are deterministic for the same input.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "ExtractionError",
    "ExtractionGap",
    "ExtractionResult",
    "canonical_json",
    "extract_artifact",
    "extract_component",
    "extract_constraint",
    "extract_decision",
    "extract_evidence_ref",
    "extract_nodes",
    "extract_option",
    "extract_scar",
    "extract_tradeoff",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_ID = re.compile(
    r"^sakg://[^/]+/(?:Decision|Option|Constraint|TradeOff|Component|Scar|EvidenceRef)/"
    r"[0-9A-HJKMNP-TV-Z]{26}$"
)
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_INGESTED_AT = "2026-09-02T00:00:00Z"
_TYPE_BY_KIND = {
    "l06": "TradeOff",
    "tradeoff": "TradeOff",
    "trade_off": "TradeOff",
    "matrix": "TradeOff",
    "l04": "Option",
    "option": "Option",
    "candidate": "Option",
    "l08": "Component",
    "component": "Component",
    "design": "Component",
    "l11": "Constraint",
    "constraint": "Constraint",
    "contract": "Constraint",
    "decision": "Decision",
    "decision_graph": "Decision",
    "scar": "Scar",
    "scar_graph": "Scar",
    "evidence": "EvidenceRef",
    "evidence_ref": "EvidenceRef",
    "cas_hash": "EvidenceRef",
    "cas_hashes": "EvidenceRef",
}
_KIND_ALIASES = {
    "TradeOff": "l06",
    "Option": "l04",
    "Component": "l08",
    "Constraint": "l11",
    "Decision": "decision",
    "Scar": "scar",
    "EvidenceRef": "evidence_ref",
}
_KNOWN_FIELDS = {
    "TradeOff": ("axes", "approaches", "risks", "decision", "matrix"),
    "Option": ("name", "title", "description", "decision_state", "rejected", "rationale"),
    "Component": ("name", "description", "interface", "dependencies", "data_flow"),
    "Constraint": ("name", "rule", "forbidden", "acceptance", "rollback"),
    "Decision": ("question", "decision", "options", "rationale", "selected"),
    "Scar": ("lesson", "detection", "failure", "severity", "remediation"),
    "EvidenceRef": ("hash", "uri", "kind", "reverification"),
}
_METADATA_FIELDS = frozenset(
    {
        "id",
        "node_id",
        "namespace",
        "source_kind",
        "kind",
        "type",
        "label",
        "summary",
        "status",
        "confidence",
        "valid_from",
        "valid_until",
        "falsifier",
        "coordinates",
        "provenance",
        "evidence",
        "evidence_hashes",
        "source_hash",
        "author_kind",
        "origin",
        "ingested_at",
        "artifact",
        "data",
        "payload",
        "raw",
        "cas_hash",
        "cas_hashes",
    }
)


class ExtractionError(ValueError):
    """Raised when an artifact cannot be identified or a CAS reference is malformed."""


@dataclass(frozen=True, slots=True)
class ExtractionGap:
    """A source field which was absent, invalid, or not representable in the envelope."""

    path: str
    reason: str
    required: bool = False

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "reason": self.reason, "required": self.required}


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """One typed node plus explicit extraction gaps."""

    node: dict[str, object] | None
    gaps: tuple[ExtractionGap, ...]
    source_kind: str

    @property
    def complete(self) -> bool:
        return not self.gaps

    def to_dict(self) -> dict[str, object]:
        return {
            "node": self.node,
            "gaps": [gap.to_dict() for gap in self.gaps],
            "source_kind": self.source_kind,
        }


def canonical_json(value: object) -> bytes:
    """Return deterministic compact UTF-8 JSON bytes for evidence hashing."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ExtractionError("value is not canonical JSON") from exc


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _kind(value: object) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ExtractionError("source_kind must identify an artifact")
    normalized = value.strip().lower().replace("-", "_")
    node_type = _TYPE_BY_KIND.get(normalized)
    if node_type is None:
        node_type = value if value in _KIND_ALIASES else None
        normalized = _KIND_ALIASES.get(value, normalized)
    if node_type is None:
        raise ExtractionError(f"unsupported artifact kind: {value}")
    return normalized, node_type


def _crockford_id(namespace: str, node_type: str, source_hash: str) -> str:
    digest = hashlib.sha256(f"{namespace}:{node_type}:{source_hash}".encode()).digest()
    number = int.from_bytes(digest[:16], "big")
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        number, remainder = divmod(number, 32)
        chars[index] = _ALPHABET[remainder]
    return f"sakg://{namespace}/{node_type}/{''.join(chars)}"


def _hash_source(source: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(dict(source))).hexdigest()


def _read(source: Mapping[str, object], *names: str) -> tuple[object | None, str | None]:
    for name in names:
        if name in source and source[name] is not None:
            return source[name], name
    return None, None


def _facet(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(value)
    return {"value": value}


def _valid_hash(value: object) -> str | None:
    return value if isinstance(value, str) and _SHA256.fullmatch(value) else None


def _evidence(
    source: Mapping[str, object],
    extra_hashes: Sequence[str],
    gaps: list[ExtractionGap],
) -> list[dict[str, object]]:
    raw, _ = _read(source, "evidence", "evidence_hashes")
    values: list[object] = []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        values.extend(raw)
    values.extend(extra_hashes)
    refs: list[dict[str, object]] = []
    for index, item in enumerate(values):
        if isinstance(item, Mapping):
            digest = _valid_hash(item.get("hash"))
            kind = _text(item.get("kind")) or "artifact"
            uri = _text(item.get("uri")) or (f"cas://{digest}" if digest else None)
            reverification = _text(item.get("reverification")) or "re-run the source extraction"
        else:
            digest = _valid_hash(item)
            kind = "artifact"
            uri = f"cas://{digest}" if digest else None
            reverification = "re-run the source extraction"
        if digest is None or uri is None:
            gaps.append(
                ExtractionGap(
                    f"evidence[{index}]",
                    "CAS evidence reference is not a lowercase SHA-256",
                    True,
                )
            )
            continue
        refs.append({"hash": digest, "uri": uri, "kind": kind, "reverification": reverification})
    if not refs:
        gaps.append(
            ExtractionGap("evidence", "no verifiable CAS evidence reference was supplied", True)
        )
    return refs


def _base_node(
    source: Mapping[str, object],
    *,
    source_kind: str,
    node_type: str,
    namespace: str,
    node_id: str | None,
    evidence_hashes: Sequence[str],
) -> tuple[dict[str, object], list[ExtractionGap]]:
    if _NAMESPACE.fullmatch(namespace) is None:
        raise ExtractionError("namespace is malformed")
    gaps: list[ExtractionGap] = []
    source_hash = _valid_hash(source.get("source_hash")) or _hash_source(source)
    if "source_hash" in source and _valid_hash(source.get("source_hash")) is None:
        gaps.append(
            ExtractionGap(
                "source_hash",
                "invalid source hash; canonical source hash was derived",
                True,
            )
        )
    chosen_id = node_id or (_text(source.get("id")) or _text(source.get("node_id")))
    if chosen_id is None:
        chosen_id = _crockford_id(namespace, node_type, source_hash)
        gaps.append(
            ExtractionGap("id", "node id absent; deterministic id derived from source hash")
        )
    if _ID.fullmatch(chosen_id) is None or not chosen_id.startswith(
        f"sakg://{namespace}/{node_type}/"
    ):
        gaps.append(
            ExtractionGap(
                "id",
                "supplied id is invalid for this namespace/type; deterministic id used",
                True,
            )
        )
        chosen_id = _crockford_id(namespace, node_type, source_hash)

    label_value, _ = _read(source, "label", "title", "name", "subject", "question")
    label = _text(label_value)
    if label is None:
        label = f"{node_type} extracted artifact"
        gaps.append(ExtractionGap("label", "no source label/title/name could be extracted"))
    label = label[:160]
    summary_value, _ = _read(source, "summary", "description", "rationale", "lesson", "rule")
    summary = _text(summary_value) or ""
    if summary_value is None:
        gaps.append(ExtractionGap("summary", "no source summary/description could be extracted"))
    if len(summary) > 280:
        summary = summary[:280]
        gaps.append(
            ExtractionGap("summary", "source summary exceeded the envelope limit and was bounded")
        )

    provenance_value, _ = _read(source, "provenance")
    provenance = dict(provenance_value) if isinstance(provenance_value, Mapping) else {}
    origin_value = provenance.get("origin", source.get("origin"))
    origin = dict(origin_value) if isinstance(origin_value, Mapping) else {}
    system = _text(origin.get("system")) or "paeos.sakg.extract"
    run_id = _text(origin.get("run_id")) or f"extract-{source_kind}"
    author_kind = (
        _text(provenance.get("author_kind")) or _text(source.get("author_kind")) or "ingest"
    )
    if author_kind not in {"human", "agent", "ingest", "inferred"}:
        gaps.append(
            ExtractionGap("provenance.author_kind", "unknown author kind; ingest used", True)
        )
        author_kind = "ingest"
    ingested_at = (
        _text(provenance.get("ingested_at")) or _text(source.get("ingested_at")) or _INGESTED_AT
    )
    if "ingested_at" not in provenance and "ingested_at" not in source:
        gaps.append(
            ExtractionGap(
                "provenance.ingested_at",
                "ingestion timestamp absent; deterministic epoch used",
            )
        )
    if "origin" not in provenance and "origin" not in source:
        gaps.append(ExtractionGap("provenance.origin", "origin absent; extractor identity used"))

    status = _text(source.get("status")) or "candidate"
    if status not in {"candidate", "canonical", "superseded", "refuted"}:
        gaps.append(ExtractionGap("status", "unknown status; candidate used"))
        status = "candidate"
    confidence = source.get("confidence", 0.0)
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        gaps.append(ExtractionGap("confidence", "missing or invalid confidence; 0.0 used"))
        confidence = 0.0
    elif "confidence" not in source:
        gaps.append(ExtractionGap("confidence", "confidence absent; explicit zero retained"))
    valid_from = _text(source.get("valid_from")) or _INGESTED_AT
    valid_until_value = source.get("valid_until")
    valid_until = (
        valid_until_value if valid_until_value is None or _text(valid_until_value) else None
    )
    if "valid_from" not in source:
        gaps.append(ExtractionGap("valid_from", "validity start absent; deterministic epoch used"))
    if "falsifier" not in source:
        gaps.append(ExtractionGap("falsifier", "falsifier absent; explicit null retained"))
    falsifier_value = source.get("falsifier")
    falsifier = falsifier_value if falsifier_value is None or _text(falsifier_value) else None
    coordinates_value = source.get("coordinates")
    coordinates: dict[str, object] = (
        dict(coordinates_value) if isinstance(coordinates_value, Mapping) else {}
    )
    if "coordinates" not in source:
        gaps.append(ExtractionGap("coordinates", "coordinates absent; empty object retained"))

    facets: dict[str, dict[str, object]] = {"source_kind": {"value": source_kind}}
    for field in _KNOWN_FIELDS[node_type]:
        if field in source:
            facets[field] = _facet(source[field])
    if node_type == "Option":
        rejected = bool(source.get("rejected", False)) or (
            str(source.get("decision_state", "")).lower() == "rejected"
        )
        if rejected:
            facets["decision_state"] = {"value": "rejected"}
            facets["rejected"] = {"value": True}
    for field in source:
        if field not in _METADATA_FIELDS and field not in _KNOWN_FIELDS[node_type]:
            gaps.append(
                ExtractionGap(f"source.{field}", "field is not mapped by this typed extractor")
            )
    node = {
        "id": chosen_id,
        "type": node_type,
        "namespace": namespace,
        "facets": facets,
        "label": label,
        "summary": summary,
        "provenance": {
            "origin": {"system": system, "run_id": run_id},
            "author_kind": author_kind,
            "ingested_at": ingested_at,
            "source_hash": source_hash,
        },
        "evidence": _evidence(source, evidence_hashes, gaps),
        "status": status,
        "confidence": confidence,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "falsifier": falsifier,
        "coordinates": dict(coordinates),
    }
    return node, gaps


def extract_artifact(
    source: Mapping[str, object],
    *,
    source_kind: str | None = None,
    kind: str | None = None,
    namespace: str = "default",
    node_id: str | None = None,
    evidence_hashes: Sequence[str] = (),
) -> ExtractionResult:
    """Extract one layer artifact into a typed envelope and gap ledger."""
    if not isinstance(source, Mapping):
        raise ExtractionError("source must be a mapping")
    selected_kind = (
        source_kind
        or kind
        or _text(source.get("source_kind"))
        or _text(source.get("kind"))
        or _text(source.get("type"))
    )
    normalized_kind, node_type = _kind(selected_kind)
    payload = source
    nested = source.get("artifact") or source.get("data")
    if isinstance(nested, Mapping):
        payload = dict(nested)
        for key in _METADATA_FIELDS:
            if key in source and key not in payload:
                payload[key] = source[key]
    node, gaps = _base_node(
        payload,
        source_kind=normalized_kind,
        node_type=node_type,
        namespace=namespace,
        node_id=node_id,
        evidence_hashes=evidence_hashes,
    )
    return ExtractionResult(node=node, gaps=tuple(gaps), source_kind=normalized_kind)


def extract_evidence_ref(
    cas_hash: str | Mapping[str, object],
    *,
    namespace: str = "default",
    kind: str = "artifact",
    uri: str | None = None,
    reverification: str = "re-run the source extraction",
) -> ExtractionResult:
    """Turn a CAS SHA-256 into an EvidenceRef node; invalid hashes fail closed."""
    source: dict[str, object] = (
        dict(cas_hash) if isinstance(cas_hash, Mapping) else {"hash": cas_hash}
    )
    digest = _valid_hash(source.get("hash") or source.get("cas_hash"))
    if digest is None:
        raise ExtractionError("EvidenceRef requires a lowercase SHA-256 hash")
    source.update(
        {
            "source_kind": "evidence_ref",
            "label": f"Evidence {digest[:12]}",
            "summary": "CAS-addressed extraction evidence",
            "hash": digest,
            "uri": uri or f"cas://{digest}",
            "kind": kind,
            "reverification": reverification,
            "evidence": [digest],
        }
    )
    return extract_artifact(source, namespace=namespace, evidence_hashes=(digest,))


def _wrapper(source: Mapping[str, object], node_type: str, **kwargs: Any) -> ExtractionResult:
    return extract_artifact(source, source_kind=_KIND_ALIASES[node_type], **kwargs)


def extract_tradeoff(source: Mapping[str, object], **kwargs: Any) -> ExtractionResult:
    return _wrapper(source, "TradeOff", **kwargs)


def extract_option(source: Mapping[str, object], **kwargs: Any) -> ExtractionResult:
    return _wrapper(source, "Option", **kwargs)


def extract_component(source: Mapping[str, object], **kwargs: Any) -> ExtractionResult:
    return _wrapper(source, "Component", **kwargs)


def extract_constraint(source: Mapping[str, object], **kwargs: Any) -> ExtractionResult:
    return _wrapper(source, "Constraint", **kwargs)


def extract_decision(source: Mapping[str, object], **kwargs: Any) -> ExtractionResult:
    return _wrapper(source, "Decision", **kwargs)


def extract_scar(source: Mapping[str, object], **kwargs: Any) -> ExtractionResult:
    return _wrapper(source, "Scar", **kwargs)


def extract_nodes(
    artifacts: Sequence[Mapping[str, object]],
    *,
    namespace: str = "default",
    evidence_hashes: Sequence[str] = (),
) -> tuple[ExtractionResult, ...]:
    """Extract a deterministic sequence, retaining rejected options as nodes."""
    results: list[ExtractionResult] = []
    for item in artifacts:
        selected = (
            _text(item.get("source_kind")) or _text(item.get("kind")) or _text(item.get("type"))
        )
        if selected is not None and _kind(selected)[1] == "EvidenceRef":
            digest = item.get("hash") or item.get("cas_hash")
            if isinstance(digest, str):
                results.append(extract_evidence_ref(digest, namespace=namespace))
                continue
        results.append(extract_artifact(item, namespace=namespace, evidence_hashes=evidence_hashes))
    return tuple(results)
