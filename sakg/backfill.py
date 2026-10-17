"""Deterministic, append-only backfill of historical Outcome nodes.

Historical debt and incident records are useful memory, but they are not equivalent to
automatically observed outcomes.  This module therefore requires an explicit Decision URI,
marks every generated node ``hand_attributed`` and ``evidence_derived=False``, and preserves
the source markdown hash as a source EvidenceRef.  Records without a Decision binding become
explicit gaps and never produce an unbound Outcome.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .store import Edge, GraphStore

__all__ = [
    "BackfillError",
    "BackfillGap",
    "BackfillRecord",
    "BackfillResult",
    "backfill_historical_outcomes",
    "backfill_outcomes",
    "build_outcome_node",
    "discover_historical_records",
    "discover_records",
    "parse_historical_record",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DECISION = re.compile(r"^sakg://[^/]+/Decision/[0-9A-HJKMNP-TV-Z]{26}$")
_ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DEFAULT_TIME = "2026-09-02T00:00:00Z"


class BackfillError(ValueError):
    """A source cannot be safely represented as a historical Outcome."""


@dataclass(frozen=True, slots=True)
class BackfillGap:
    """A source record that was retained but could not yield a bound node."""

    path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class BackfillRecord:
    """Parsed debt/incident markdown and its explicit Decision binding."""

    path: Path
    record_id: str
    record_type: str
    source_hash: str
    decision_id: str | None
    binding_method: str | None
    fields: Mapping[str, str]
    gaps: tuple[BackfillGap, ...] = ()


@dataclass(frozen=True, slots=True)
class BackfillResult:
    """Nodes, binding edges, and explicit gaps emitted by one deterministic run."""

    nodes: tuple[dict[str, object], ...]
    edges: tuple[dict[str, object], ...]
    gaps: tuple[BackfillGap, ...]
    scanned: int

    @property
    def produced(self) -> int:
        return len(self.nodes)

    def to_dict(self) -> dict[str, object]:
        return {
            "scanned": self.scanned,
            "produced": self.produced,
            "nodes": list(self.nodes),
            "edges": list(self.edges),
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


def _crockford_id(seed: str) -> str:
    number = int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:16], "big")
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        number, remainder = divmod(number, 32)
        chars[index] = _ID_ALPHABET[remainder]
    return "".join(chars)


def _section(text: str, labels: Sequence[str]) -> str:
    label = "|".join(re.escape(item) for item in labels)
    match = re.search(rf"^##\s+(?:\d+\.\s*)?(?:{label})\s*$", text, re.I | re.M)
    if match is None:
        return ""
    tail = text[match.end() :]
    stop = re.search(r"^##\s+", tail, re.M)
    body = tail[: stop.start()] if stop else tail
    lines = [line.strip() for line in body.splitlines()]
    return " ".join(line for line in lines if line and not line.startswith("#")).strip()


def _field(text: str, names: Sequence[str]) -> str:
    for name in names:
        match = re.search(rf"^\s*(?:[-*]\s*)?{re.escape(name)}\s*:\s*(.+?)\s*$", text, re.I | re.M)
        if match:
            return match.group(1).strip().strip('`"')
    return ""


def _record_type(path: Path) -> str:
    name = path.name.upper()
    if name.startswith("DEBT-"):
        return "debt"
    if "INCIDENT" in name or name.startswith("REMAND-"):
        return "incident"
    return "historical"


def _decision_from_text(text: str) -> tuple[str | None, str | None]:
    explicit = _field(text, ("decision_id", "Decision ID", "bound_decision"))
    candidate = explicit or next(
        iter(re.findall(r"sakg://[^\s`\]\[)]+/Decision/[0-9A-HJKMNP-TV-Z]{26}", text)), ""
    )
    if candidate and _DECISION.fullmatch(candidate):
        return candidate, "explicit" if explicit else "source-reference"
    return None, None


def parse_historical_record(
    path: str | Path, *, decision_bindings: Mapping[str, str] | None = None
) -> BackfillRecord:
    source = Path(path)
    raw = source.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    record_id = source.stem
    decision_id, method = _decision_from_text(text)
    if decision_id is None and decision_bindings:
        for key in (str(source), source.name, record_id):
            bound = decision_bindings.get(key)
            if bound and _DECISION.fullmatch(bound):
                decision_id, method = bound, "external-binding"
                break
    gaps: list[BackfillGap] = []
    if decision_id is None:
        gaps.append(BackfillGap(str(source), "decision-binding-missing"))
    fields = {
        "title": _field(text, ("title",))
        or (text.splitlines()[0].lstrip("# ").strip() if text else record_id),
        "status": _field(text, ("Status", "status")),
        "compromise": _section(text, ("Compromise", "Observation", "Problem")),
        "repayment": _section(text, ("Repayment conditions", "Remediation Strategy", "Resolution")),
        "risk": _section(text, ("Estimated impact", "Risk", "Impact", "Leverage Assessment")),
    }
    return BackfillRecord(
        source,
        record_id,
        _record_type(source),
        hashlib.sha256(raw).hexdigest(),
        decision_id,
        method,
        fields,
        tuple(gaps),
    )


def discover_historical_records(roots: Iterable[str | Path]) -> tuple[Path, ...]:
    """Discover only markdown debt/incident records, deterministically and without mutation."""
    found: set[Path] = set()
    for root_value in roots:
        root = Path(root_value)
        if root.is_file() and root.suffix.lower() == ".md":
            found.add(root)
        elif root.is_dir():
            found.update(path for path in root.rglob("*.md") if path.is_file())
    return tuple(sorted(found, key=lambda path: str(path)))


discover_records = discover_historical_records


def build_outcome_node(
    record: BackfillRecord, *, namespace: str, run_id: str, ingested_at: str = _DEFAULT_TIME
) -> dict[str, object]:
    """Build one valid universal envelope; an unbound record is rejected fail-closed."""
    if record.decision_id is None or _DECISION.fullmatch(record.decision_id) is None:
        raise BackfillError(f"{record.path} has no valid Decision binding")
    if record.decision_id.split("/", 3)[2] != namespace:
        raise BackfillError("Decision binding crosses the requested namespace")
    if _SHA256.fullmatch(record.source_hash) is None:
        raise BackfillError("source hash is malformed")
    seed = f"{namespace}:Outcome:{record.record_id}:{record.source_hash}:{record.decision_id}"
    node_id = f"sakg://{namespace}/Outcome/{_crockford_id(seed)}"
    title = record.fields.get("title", record.record_id)[:160]
    compromise = record.fields.get("compromise", "")
    repayment = record.fields.get("repayment", "")
    risk = record.fields.get("risk", "")
    summary = (
        compromise
        or repayment
        or risk
        or f"Historical {record.record_type} outcome {record.record_id}"
    )[:280]
    source_uri = f"file://{record.path}"
    return {
        "id": node_id,
        "type": "Outcome",
        "namespace": namespace,
        "facets": {
            "record_id": {"value": record.record_id},
            "record_type": {"value": record.record_type},
            "bound_decision_id": {"value": record.decision_id},
            "binding_method": {"value": record.binding_method or "unknown"},
            "status_text": {"value": record.fields.get("status", "")},
            "compromise": {"text": compromise},
            "repayment_condition": {"text": repayment},
            "risk": {"text": risk},
            "hand_attributed": {"value": True},
            "evidence_derived": {"value": False},
            "attribution": {"mode": "hand-attributed", "evidence_derived": False},
        },
        "label": f"Historical outcome {record.record_id} — {title}"[:160],
        "summary": summary,
        "provenance": {
            "origin": {"system": "paeos-sakg-backfill", "run_id": run_id},
            "author_kind": "ingest",
            "ingested_at": ingested_at,
            "source_hash": record.source_hash,
        },
        "evidence": [
            {
                "hash": record.source_hash,
                "uri": source_uri,
                "kind": "source",
                "reverification": (
                    "re-read the immutable historical markdown and compare its SHA-256"
                ),
            }
        ],
        "status": "candidate",
        "confidence": 0.25,
        "valid_from": ingested_at,
        "valid_until": None,
        "falsifier": (
            "An automatically observed S3 outcome contradicts the hand attribution or source"
            " record."
        ),
        "coordinates": {"source_record": [record.record_id], "decision": [record.decision_id]},
    }


def _binding_edge(
    record: BackfillRecord, node_id: str, *, namespace: str, run_id: str, source_hash: str
) -> dict[str, object]:
    edge_id = f"sakg://{namespace}/backfill-edge/{_crockford_id(f'{record.record_id}:{source_hash}:{node_id}')}"
    return Edge(
        edge_id=edge_id,
        namespace=namespace,
        source=record.decision_id or "",
        target=node_id,
        family="causal",
        relation="decision_realized_as_historical_outcome",
        properties={"hand_attributed": True, "run_id": run_id, "record_id": record.record_id},
        evidence=(
            {
                "hash": source_hash,
                "uri": f"file://{record.path}",
                "kind": "source",
                "reverification": "re-read source",
            },
        ),
        created_at=_DEFAULT_TIME,
    ).to_dict()


def backfill_historical_outcomes(
    records: Iterable[str | Path | BackfillRecord],
    *,
    namespace: str,
    run_id: str,
    store: GraphStore | None = None,
    decision_bindings: Mapping[str, str] | None = None,
) -> BackfillResult:
    """Convert bound records to candidate Outcomes and causal Decision edges.

    When ``store`` is supplied, the Decision must already exist; nodes/edges are appended
    idempotently through the append-only store. Missing bindings remain explicit gaps.
    """
    parsed = tuple(
        item
        if isinstance(item, BackfillRecord)
        else parse_historical_record(item, decision_bindings=decision_bindings)
        for item in records
    )
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    gaps: list[BackfillGap] = [gap for item in parsed for gap in item.gaps]
    for record in parsed:
        if record.gaps:
            continue
        node = build_outcome_node(record, namespace=namespace, run_id=run_id)
        edge = _binding_edge(
            record,
            str(node["id"]),
            namespace=namespace,
            run_id=run_id,
            source_hash=record.source_hash,
        )
        if store is not None:
            if record.decision_id is None or store.get_node(record.decision_id) is None:
                gaps.append(BackfillGap(str(record.path), "decision-node-missing"))
                continue
            store.append_node(node)
            store.append_edge(edge)
        nodes.append(node)
        edges.append(edge)
    return BackfillResult(tuple(nodes), tuple(edges), tuple(gaps), len(parsed))


backfill_outcomes = backfill_historical_outcomes
