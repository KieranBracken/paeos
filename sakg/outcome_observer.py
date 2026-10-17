"""Append-only longitudinal outcome observation for the live SAKG graph.

The observer turns strictly validated runtime records into deterministic candidate
``Outcome`` snapshots.  Runtime state (``OBSERVED``, ``VERIFIED``, or ``FALSIFIED``)
lives in facets because the universal node envelope has its own claim-lifecycle status.
Each state transition is a new immutable node; replaying the same snapshot is idempotent.

SAEOS-1 defines exactly eight edge families.  Belief revision therefore uses the
canonical ``similarity`` family with relation ``revises`` and retains the requested
semantic type as ``properties.typed_relation = "epistemic:revises"``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from .store import DuplicateIdentity, Edge, GraphStore, validate_node_envelope

__all__ = [
    "MalformedOutcomeRecord",
    "OutcomeBindingError",
    "OutcomeEvent",
    "OutcomeObservationError",
    "OutcomeObserver",
    "OutcomeResult",
    "OutcomeState",
    "OutcomeTransitionError",
    "observe_event",
    "observe_outcome",
]

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_DECISION_ID = re.compile(r"^sakg://[^/]+/Decision/[0-9A-HJKMNP-TV-Z]{26}$")
_TRADEOFF_ID = re.compile(r"^sakg://[^/]+/TradeOff/[0-9A-HJKMNP-TV-Z]{26}$")
_EVIDENCE_KINDS = frozenset({"artifact", "test", "report", "observation", "decision", "source"})
_REVISION_EVENT_TYPES = frozenset({"court_remand", "regression", "scar"})
_OBSERVED_STATUSES = frozenset({"observed", "pending", "queued", "running", "started"})
_VERIFIED_STATUSES = frozenset({"pass", "passed", "recovered", "sealed", "verified"})
_FALSIFIED_STATUSES = frozenset(
    {"fail", "failed", "failure", "falsified", "recorded", "regressed", "remanded"}
)
_EVENT_FIELDS = frozenset(
    {
        "decision_id",
        "details",
        "event_id",
        "event_type",
        "evidence",
        "observed_at",
        "run_id",
        "source_system",
        "state",
        "status",
        "summary",
        "tradeoff_ids",
    }
)


class OutcomeObservationError(ValueError):
    """Base class for fail-closed observer input and state errors."""


class MalformedOutcomeRecord(OutcomeObservationError):
    """A runtime observation does not satisfy the observer input contract."""


class OutcomeBindingError(OutcomeObservationError):
    """A runtime observation references an absent or incorrectly typed graph node."""


class OutcomeTransitionError(OutcomeObservationError):
    """A runtime observation attempts to move an immutable outcome state backwards."""


class OutcomeState(StrEnum):
    """Longitudinal state carried by an append-only Outcome snapshot."""

    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    FALSIFIED = "FALSIFIED"


@dataclass(frozen=True, slots=True)
class OutcomeEvent:
    """Normalized, evidence-bound runtime event accepted by :class:`OutcomeObserver`."""

    event_id: str
    event_type: str
    decision_id: str
    status: str
    observed_at: str
    summary: str
    evidence: tuple[Mapping[str, object], ...]
    state: OutcomeState
    tradeoff_ids: tuple[str, ...] = ()
    source_system: str = "paeos-runtime"
    run_id: str = ""
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutcomeResult:
    """Persistence accounting for one observed append-only snapshot."""

    node_id: str
    state: OutcomeState
    nodes_appended: int
    nodes_replayed: int
    edges_appended: int
    edges_replayed: int


def _text(value: object, name: str, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MalformedOutcomeRecord(f"{name} must be a non-empty string")
    result = value.strip()
    if maximum is not None and len(result) > maximum:
        raise MalformedOutcomeRecord(f"{name} exceeds {maximum} characters")
    return result


def _timestamp(value: object) -> str:
    text = _text(value, "observed_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MalformedOutcomeRecord("observed_at must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise MalformedOutcomeRecord("observed_at must include a timezone")
    return text


def _canonical_bytes(value: object, name: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise MalformedOutcomeRecord(f"{name} must be canonical JSON data") from exc


def _state(event_type: str, status: str, explicit: object = None) -> OutcomeState:
    if explicit is not None:
        try:
            requested = OutcomeState(_text(explicit, "state").upper())
        except ValueError as exc:
            raise MalformedOutcomeRecord("state is not OBSERVED, VERIFIED, or FALSIFIED") from exc
        if event_type in _REVISION_EVENT_TYPES and requested is not OutcomeState.FALSIFIED:
            raise MalformedOutcomeRecord(f"{event_type} events must be FALSIFIED snapshots")
        return requested
    normalized = status.lower().replace("-", "_").replace(" ", "_")
    if event_type in _REVISION_EVENT_TYPES:
        if normalized not in _FALSIFIED_STATUSES:
            raise MalformedOutcomeRecord(f"status {status!r} is invalid for {event_type}")
        return OutcomeState.FALSIFIED
    if normalized in _OBSERVED_STATUSES:
        return OutcomeState.OBSERVED
    if normalized in _VERIFIED_STATUSES:
        return OutcomeState.VERIFIED
    if normalized in _FALSIFIED_STATUSES - {"recorded"}:
        return OutcomeState.FALSIFIED
    raise MalformedOutcomeRecord(f"status {status!r} has no fail-closed outcome mapping")


def _evidence_item(value: object, index: int) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise MalformedOutcomeRecord(f"evidence[{index}] must be an object")
    required = {"hash", "uri", "kind", "reverification"}
    if set(value) != required:
        raise MalformedOutcomeRecord(f"evidence[{index}] fields must be {sorted(required)}")
    digest = _text(value.get("hash"), f"evidence[{index}].hash")
    if _HASH.fullmatch(digest) is None:
        raise MalformedOutcomeRecord(f"evidence[{index}].hash must be lowercase SHA-256")
    kind = _text(value.get("kind"), f"evidence[{index}].kind")
    if kind not in _EVIDENCE_KINDS:
        raise MalformedOutcomeRecord(f"evidence[{index}].kind is unknown")
    return {
        "hash": digest,
        "uri": _text(value.get("uri"), f"evidence[{index}].uri"),
        "kind": kind,
        "reverification": _text(
            value.get("reverification"), f"evidence[{index}].reverification"
        ),
    }


def _evidence(value: object) -> tuple[Mapping[str, object], ...]:
    values = [value] if isinstance(value, Mapping) else value
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise MalformedOutcomeRecord("evidence must be an object or non-empty array")
    result = tuple(_evidence_item(item, index) for index, item in enumerate(values))
    if not result:
        raise MalformedOutcomeRecord("evidence must not be empty")
    return result


def _tradeoffs(value: object, namespace: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise MalformedOutcomeRecord("tradeoff_ids must be an array")
    result = tuple(sorted(_text(item, "tradeoff_id") for item in value))
    if len(result) != len(set(result)):
        raise MalformedOutcomeRecord("tradeoff_ids must be unique")
    if any(
        _TRADEOFF_ID.fullmatch(item) is None or item.split("/", 3)[2] != namespace
        for item in result
    ):
        raise OutcomeBindingError("tradeoff reference crosses namespace or is not a TradeOff URI")
    return result


def _normalise(record: OutcomeEvent | Mapping[str, object], namespace: str) -> OutcomeEvent:
    if isinstance(record, OutcomeEvent):
        data: Mapping[str, object] = {
            "event_id": record.event_id,
            "event_type": record.event_type,
            "decision_id": record.decision_id,
            "status": record.status,
            "observed_at": record.observed_at,
            "summary": record.summary,
            "evidence": record.evidence,
            "state": record.state.value,
            "tradeoff_ids": record.tradeoff_ids,
            "source_system": record.source_system,
            "run_id": record.run_id,
            "details": record.details,
        }
    elif isinstance(record, Mapping):
        data = record
    else:
        raise MalformedOutcomeRecord("runtime event must be an object")
    extra = set(data) - _EVENT_FIELDS
    if extra:
        raise MalformedOutcomeRecord(f"runtime event has unknown fields: {sorted(extra)}")
    event_id = _text(data.get("event_id"), "event_id", maximum=160)
    event_type = _text(data.get("event_type"), "event_type", maximum=80).lower().replace(
        "-", "_"
    )
    decision_id = _text(data.get("decision_id"), "decision_id")
    if (
        _DECISION_ID.fullmatch(decision_id) is None
        or decision_id.split("/", 3)[2] != namespace
    ):
        raise OutcomeBindingError("decision reference crosses namespace or is not a Decision URI")
    status = _text(data.get("status"), "status", maximum=80)
    details_value = data.get("details", {})
    if not isinstance(details_value, Mapping) or any(
        not isinstance(key, str) for key in details_value
    ):
        raise MalformedOutcomeRecord("details must be an object with string keys")
    details = dict(details_value)
    _canonical_bytes(details, "details")
    return OutcomeEvent(
        event_id=event_id,
        event_type=event_type,
        decision_id=decision_id,
        status=status,
        observed_at=_timestamp(data.get("observed_at")),
        summary=_text(data.get("summary"), "summary", maximum=280),
        evidence=_evidence(data.get("evidence")),
        state=_state(event_type, status, data.get("state")),
        tradeoff_ids=_tradeoffs(data.get("tradeoff_ids", ()), namespace),
        source_system=_text(data.get("source_system", "paeos-runtime"), "source_system"),
        run_id=_text(data.get("run_id", event_id), "run_id"),
        details=details,
    )


def _crockford(seed: bytes) -> str:
    number = int.from_bytes(hashlib.sha256(seed).digest()[:16], "big")
    characters = ["0"] * 26
    for index in range(25, -1, -1):
        number, remainder = divmod(number, 32)
        characters[index] = _ALPHABET[remainder]
    return "".join(characters)


def _outcome_id(namespace: str, event: OutcomeEvent) -> str:
    identity = {
        "decision_id": event.decision_id,
        "event_id": event.event_id,
        "namespace": namespace,
        "state": event.state.value,
    }
    return f"sakg://{namespace}/Outcome/{_crockford(_canonical_bytes(identity, 'identity'))}"


def _edge(
    namespace: str,
    source: str,
    target: str,
    family: str,
    relation: str,
    typed_relation: str,
    event: OutcomeEvent,
) -> dict[str, object]:
    identity = _canonical_bytes(
        {
            "event_id": event.event_id,
            "family": family,
            "relation": relation,
            "source": source,
            "state": event.state.value,
            "target": target,
        },
        "edge identity",
    )
    return Edge(
        edge_id=f"edge:task25:{hashlib.sha256(identity).hexdigest()[:32]}",
        namespace=namespace,
        source=source,
        target=target,
        family=family,
        relation=relation,
        properties={
            "event_id": event.event_id,
            "state": event.state.value,
            "typed_relation": typed_relation,
        },
        evidence=event.evidence,
        created_at=event.observed_at,
    ).to_dict()


class OutcomeObserver:
    """Validate runtime events and append deterministic Outcome snapshots and edges."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store
        self.namespace = store.namespace

    def _validate_bindings(self, event: OutcomeEvent) -> None:
        decision = self.store.get_node(event.decision_id)
        if decision is None or decision.get("type") != "Decision":
            raise OutcomeBindingError(f"bound Decision is absent: {event.decision_id}")
        for tradeoff_id in event.tradeoff_ids:
            tradeoff = self.store.get_node(tradeoff_id)
            if tradeoff is None or tradeoff.get("type") != "TradeOff":
                raise OutcomeBindingError(f"bound TradeOff is absent: {tradeoff_id}")

    def _prior_states(self, event_id: str) -> frozenset[OutcomeState]:
        states: set[OutcomeState] = set()
        for node in self.store.query_nodes("Outcome"):
            facets = node.get("facets")
            if not isinstance(facets, Mapping):
                continue
            runtime_event = facets.get("runtime_event")
            state = facets.get("state")
            if not isinstance(runtime_event, Mapping) or runtime_event.get("id") != event_id:
                continue
            if not isinstance(state, Mapping):
                raise OutcomeTransitionError("existing Outcome snapshot has malformed state facets")
            try:
                states.add(OutcomeState(cast(Any, state.get("value"))))
            except ValueError as exc:
                raise OutcomeTransitionError(
                    "existing Outcome snapshot has an unknown longitudinal state"
                ) from exc
        return frozenset(states)

    def _validate_transition(self, event: OutcomeEvent) -> None:
        prior = self._prior_states(event.event_id)
        if event.state in prior:
            return
        if OutcomeState.FALSIFIED in prior:
            raise OutcomeTransitionError("FALSIFIED is terminal for an observed event")
        if event.state is OutcomeState.OBSERVED and OutcomeState.VERIFIED in prior:
            raise OutcomeTransitionError("a VERIFIED event cannot return to OBSERVED")

    def _node(self, event: OutcomeEvent) -> dict[str, object]:
        node_id = _outcome_id(self.namespace, event)
        belief_revision = event.state is OutcomeState.FALSIFIED
        facets: dict[str, object] = {
            "runtime_event": {
                "id": event.event_id,
                "type": event.event_type,
                "reported_status": event.status,
            },
            "state": {"value": event.state.value},
            "binding": {
                "decision_id": event.decision_id,
                "tradeoff_ids": list(event.tradeoff_ids),
            },
            "belief_revision": {"value": belief_revision},
            "details": dict(event.details),
        }
        if event.event_type == "scar":
            facets["scar"] = dict(event.details)
        confidence = {
            OutcomeState.OBSERVED: 0.5,
            OutcomeState.VERIFIED: 0.9,
            OutcomeState.FALSIFIED: 0.1,
        }[event.state]
        node = {
            "id": node_id,
            "type": "Outcome",
            "namespace": self.namespace,
            "facets": facets,
            "label": f"{event.state.value.title()} outcome — {event.event_id}"[:160],
            "summary": event.summary,
            "provenance": {
                "origin": {"system": event.source_system, "run_id": event.run_id},
                "author_kind": "inferred",
                "ingested_at": event.observed_at,
                "source_hash": str(event.evidence[0]["hash"]),
            },
            "evidence": [dict(item) for item in event.evidence],
            "status": "candidate",
            "confidence": confidence,
            "valid_from": event.observed_at,
            "valid_until": None,
            "falsifier": None,
            "coordinates": {
                "decision": [event.decision_id],
                "event_type": [event.event_type],
                "outcome_state": [event.state.value],
            },
        }
        validate_node_envelope(node, self.namespace)
        return node

    def _edges(self, event: OutcomeEvent, node_id: str) -> tuple[dict[str, object], ...]:
        edges = [
            _edge(
                self.namespace,
                event.decision_id,
                node_id,
                "causal",
                "outcome",
                "causal:outcome",
                event,
            )
        ]
        if event.state is OutcomeState.FALSIFIED:
            for target in (event.decision_id, *event.tradeoff_ids):
                edges.append(
                    _edge(
                        self.namespace,
                        node_id,
                        target,
                        "similarity",
                        "revises",
                        "epistemic:revises",
                        event,
                    )
                )
        return tuple(edges)

    def _preflight_identity(
        self, node: Mapping[str, object], edges: Iterable[Mapping[str, object]]
    ) -> tuple[bool, tuple[bool, ...]]:
        node_id = str(node["id"])
        existing_node = self.store.get_node(node_id)
        if existing_node is not None and existing_node != node:
            raise DuplicateIdentity(f"Outcome identity contains different content: {node_id}")
        edge_states: list[bool] = []
        for edge in edges:
            edge_id = str(edge["edge_id"])
            existing_edge = self.store.get_edge(edge_id)
            if existing_edge is not None and existing_edge != edge:
                raise DuplicateIdentity(f"Outcome edge identity contains different content: {edge_id}")
            edge_states.append(existing_edge is not None)
        return existing_node is not None, tuple(edge_states)

    def observe(self, record: OutcomeEvent | Mapping[str, object]) -> OutcomeResult:
        """Observe one event after validating the complete node/edge write set."""
        event = _normalise(record, self.namespace)
        self._validate_bindings(event)
        self._validate_transition(event)
        node = self._node(event)
        edges = self._edges(event, str(node["id"]))
        node_existed, edge_existed = self._preflight_identity(node, edges)
        self.store.append_node(node)
        for edge in edges:
            self.store.append_edge(edge)
        return OutcomeResult(
            node_id=str(node["id"]),
            state=event.state,
            nodes_appended=int(not node_existed),
            nodes_replayed=int(node_existed),
            edges_appended=sum(not existed for existed in edge_existed),
            edges_replayed=sum(edge_existed),
        )

    def observe_many(
        self, records: Iterable[OutcomeEvent | Mapping[str, object]]
    ) -> tuple[OutcomeResult, ...]:
        """Observe a batch, rejecting every malformed or unbound record before writes."""
        events = tuple(_normalise(record, self.namespace) for record in records)
        for event in events:
            self._validate_bindings(event)
        return tuple(self.observe(event) for event in events)

    def observe_scars_db(
        self,
        path: str | Path,
        *,
        decision_bindings: Mapping[str, str],
        observed_at: str,
    ) -> tuple[OutcomeResult, ...]:
        """Read durable ``scars.db`` rows and observe them as FALSIFIED snapshots."""
        database_path = Path(path)
        if not database_path.is_file():
            raise MalformedOutcomeRecord(f"scars.db is absent: {database_path}")
        timestamp = _timestamp(observed_at)
        try:
            connection = sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)
            rows = connection.execute(
                "SELECT seq, id, signature, lesson, detection, severity FROM scars ORDER BY seq"
            ).fetchall()
            connection.close()
        except sqlite3.Error as exc:
            raise MalformedOutcomeRecord("scars.db does not expose the durable scars schema") from exc
        records: list[dict[str, object]] = []
        for row in rows:
            sequence, scar_id, raw_signature, lesson, detection, severity = row
            if (
                isinstance(sequence, bool)
                or not isinstance(sequence, int)
                or not isinstance(scar_id, str)
                or not scar_id
                or not all(isinstance(value, str) and value for value in row[2:])
            ):
                raise MalformedOutcomeRecord("scars.db contains a malformed row")
            try:
                signature = json.loads(raw_signature)
            except json.JSONDecodeError as exc:
                raise MalformedOutcomeRecord("scar signature is not valid JSON") from exc
            if not isinstance(signature, list) or not all(
                isinstance(tag, str) and tag for tag in signature
            ):
                raise MalformedOutcomeRecord("scar signature must be an array of strings")
            decision_id = decision_bindings.get(scar_id)
            if decision_id is None:
                raise OutcomeBindingError(f"scar has no Decision binding: {scar_id}")
            source = {
                "seq": sequence,
                "id": scar_id,
                "signature": signature,
                "lesson": lesson,
                "detection": detection,
                "severity": severity,
            }
            digest = hashlib.sha256(_canonical_bytes(source, "scar row")).hexdigest()
            records.append(
                {
                    "event_id": scar_id,
                    "event_type": "scar",
                    "decision_id": decision_id,
                    "tradeoff_ids": [],
                    "status": "recorded",
                    "observed_at": timestamp,
                    "summary": lesson[:280],
                    "source_system": "paeos-scar-store",
                    "run_id": f"scar-seq-{sequence}",
                    "details": {
                        "signature": signature,
                        "detection": detection,
                        "severity": severity,
                    },
                    "evidence": {
                        "hash": digest,
                        "uri": f"{database_path.resolve().as_uri()}#{scar_id}",
                        "kind": "observation",
                        "reverification": "re-open scars.db read-only and hash the canonical row",
                    },
                }
            )
        return self.observe_many(records)


def observe_event(
    store: GraphStore, record: OutcomeEvent | Mapping[str, object]
) -> OutcomeResult:
    """Functional entry point for observing one runtime event."""
    return OutcomeObserver(store).observe(record)


observe_outcome = observe_event
