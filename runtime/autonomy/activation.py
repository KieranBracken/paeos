"""Derive activation state from correlated ledger and CAS evidence (Gate F Task 1)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from kernel.cas import is_valid_hash
from kernel.ledger import LedgerRow


class ActivationStage(StrEnum):
    SUPERVISED_RECOVERY_ONLY = "SUPERVISED_RECOVERY_ONLY"
    ISOLATED_CANARY = "ISOLATED_CANARY"
    AWAITING_FOUNDER_BOOTSTRAP = "AWAITING_FOUNDER_BOOTSTRAP"
    SINGLE_FLIGHT_PROMOTION = "SINGLE_FLIGHT_PROMOTION"
    BROADER_TRACE_A = "BROADER_TRACE_A"


@dataclass(frozen=True, slots=True)
class ActivationCounts:
    admitted_route_probes: int = 0
    end_to_end_trace_a: int = 0
    clean_rotations: int = 0
    forced_quota_stops: int = 0
    automatic_promotions: int = 0
    sealed: int = 0
    remanded: int = 0
    remediated: int = 0
    critical_failures: int = 0


@dataclass(frozen=True, slots=True)
class ActivationDecision:
    stage: ActivationStage
    counts: ActivationCounts
    blocking_reason_codes: tuple[str, ...]
    evidence_head: str


def evaluate_activation(
    rows: Sequence[LedgerRow], cas: object = None
) -> ActivationDecision:
    """Derive the activation frontier from durable, content-addressed facts only.

    Event prose is deliberately ignored.  A countable fact must carry a unique
    ``transaction_id`` and a SHA-256 ``evidence_hash`` that exists in the supplied
    CAS.  Repeated rows for one transaction are idempotent; a transaction whose
    identity or evidence changes is a provenance conflict and forces recovery.
    """

    evidence_head = rows[-1].row_hash if rows else "0" * 64
    seen: dict[str, str] = {}
    conflicts = False
    valid_events: list[tuple[str, dict[str, object], str]] = []

    def payload_for(row: LedgerRow) -> dict[str, object]:
        value = getattr(getattr(row, "event", None), "payload", None)
        return value if isinstance(value, dict) else {}

    def kind_for(row: LedgerRow) -> str:
        event = getattr(row, "event", None)
        value = getattr(event, "kind", getattr(row, "event_type", ""))
        return value if isinstance(value, str) else ""

    def evidence_present(payload: dict[str, object]) -> bool:
        if cas is None:
            return False
        ref = payload.get("evidence_hash", payload.get("evidence_ref"))
        if not isinstance(ref, str) or not is_valid_hash(ref):
            return False
        has = getattr(cas, "has", None)
        return callable(has) and bool(has(ref))

    def transaction_for(payload: dict[str, object]) -> str | None:
        value = payload.get("transaction_id")
        if not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value):
            return None
        return value

    for row in rows:
        kind = kind_for(row)
        payload = payload_for(row)
        tx = transaction_for(payload)
        if tx is None:
            # A critical signal still blocks activation, but cannot inflate a
            # corroborated count without a transaction identity.
            if kind == "CRITICAL_FAILURE":
                conflicts = True
            continue
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "kind": kind,
                    "transaction_id": tx,
                    "route": payload.get("route"),
                    "evidence_hash": payload.get("evidence_hash", payload.get("evidence_ref")),
                    "claim_id": payload.get("claim_id"),
                    "canary_id": payload.get("canary_id"),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        prior = seen.get(tx)
        if prior is not None and prior != fingerprint:
            conflicts = True
            continue
        seen[tx] = fingerprint
        if kind == "CRITICAL_FAILURE" or evidence_present(payload):
            valid_events.append((kind, payload, tx))

    def distinct(kind: str) -> list[tuple[str, dict[str, object], str]]:
        return [event for event in valid_events if event[0] == kind]

    probes_by_route: dict[str, set[str]] = {}
    for _, payload, tx in distinct("ROUTE_PROBE_ADMITTED"):
        route = payload.get("route")
        if isinstance(route, str) and route.strip():
            probes_by_route.setdefault(route, set()).add(tx)
    probes = sum(len(ids) for ids in probes_by_route.values())
    trace_a = len({tx for _, _, tx in distinct("TRACE_A_CANARY_PASSED")})
    rotations = len({tx for _, _, tx in distinct("SUPERVISOR_ROTATED")})
    quota_stops = len({tx for _, _, tx in distinct("QUOTA_STOP_RECOVERED")})
    promotions = len({tx for _, _, tx in distinct("PROMOTION_EXECUTED")})
    critical = len({tx for _, _, tx in distinct("CRITICAL_FAILURE")})

    court_claims: dict[str, set[str]] = {}
    for kind in ("COURT_SEALED", "COURT_REMANDED", "COURT_REMEDIATED"):
        for _, payload, tx in distinct(kind):
            claim = payload.get("claim_id", tx)
            if isinstance(claim, str) and claim.strip():
                court_claims.setdefault(claim, set()).add(kind)
    sealed = sum("COURT_SEALED" in kinds for kinds in court_claims.values())
    remanded = sum("COURT_REMANDED" in kinds for kinds in court_claims.values())
    remediated = sum(
        "COURT_REMEDIATED" in kinds and "COURT_REMANDED" in kinds
        for kinds in court_claims.values()
    )

    counts = ActivationCounts(
        admitted_route_probes=probes,
        end_to_end_trace_a=trace_a,
        clean_rotations=rotations,
        forced_quota_stops=quota_stops,
        automatic_promotions=promotions,
        sealed=sealed,
        remanded=remanded,
        remediated=remediated,
        critical_failures=critical,
    )

    blocking: list[str] = []
    stage = ActivationStage.SUPERVISED_RECOVERY_ONLY
    if conflicts:
        blocking.append("PROVENANCE_CONFLICT")
    if critical:
        blocking.append("CRITICAL_FAILURE_PRESENT")

    routes_incomplete = not probes_by_route or any(len(ids) < 3 for ids in probes_by_route.values())
    if routes_incomplete:
        blocking.append("MINIMUM_PROBES_OUTSTANDING")
    else:
        stage = ActivationStage.ISOLATED_CANARY

    if stage == ActivationStage.ISOLATED_CANARY:
        if trace_a < 3:
            blocking.append("MINIMUM_TRACE_A_CANARIES_OUTSTANDING")
        elif rotations < 1 or quota_stops < 1:
            blocking.append("MINIMUM_ROTATION_QUOTA_STOPS_OUTSTANDING")
        else:
            bootstrap = any(
                kind == "FOUNDER_BOOTSTRAP_SEALED" for kind, _, _ in valid_events
            )
            stage = (
                ActivationStage.BROADER_TRACE_A
                if bootstrap and promotions >= 5
                else ActivationStage.SINGLE_FLIGHT_PROMOTION
                if bootstrap
                else ActivationStage.AWAITING_FOUNDER_BOOTSTRAP
            )
            if bootstrap and promotions < 5:
                blocking.append("MINIMUM_PROMOTIONS_OUTSTANDING")

    return ActivationDecision(
        stage=stage,
        counts=counts,
        blocking_reason_codes=tuple(blocking),
        evidence_head=evidence_head,
    )
