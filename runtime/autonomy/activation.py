"""Derive activation state from correlated ledger and CAS evidence (Gate F Task 1)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

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
    probes = 0
    trace_a = 0
    rotations = 0
    quota_stops = 0
    promotions = 0
    sealed = 0
    remanded = 0
    remediated = 0
    critical = 0

    evidence_head = rows[-1].row_hash if rows else "0" * 64

    for row in rows:
        etype = row.event.kind if hasattr(row, "event") else getattr(row, "event_type", "")
        if etype == "ROUTE_PROBE_ADMITTED":
            probes += 1
        elif etype == "TRACE_A_CANARY_PASSED":
            trace_a += 1
        elif etype == "SUPERVISOR_ROTATED":
            rotations += 1
        elif etype == "QUOTA_STOP_RECOVERED":
            quota_stops += 1
        elif etype == "PROMOTION_EXECUTED":
            promotions += 1
        elif etype == "COURT_SEALED":
            sealed += 1
        elif etype == "COURT_REMANDED":
            remanded += 1
        elif etype == "COURT_REMEDIATED":
            remediated += 1
        elif etype == "CRITICAL_FAILURE":
            critical += 1


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

    if probes < 3:
        blocking.append("MINIMUM_PROBES_OUTSTANDING")
    else:
        stage = ActivationStage.ISOLATED_CANARY

    if stage == ActivationStage.ISOLATED_CANARY:
        if trace_a < 3:
            blocking.append("MINIMUM_TRACE_A_CANARIES_OUTSTANDING")
        elif rotations < 1 or quota_stops < 1:
            blocking.append("MINIMUM_ROTATION_QUOTA_STOPS_OUTSTANDING")
        else:
            stage = ActivationStage.AWAITING_FOUNDER_BOOTSTRAP

    return ActivationDecision(
        stage=stage,
        counts=counts,
        blocking_reason_codes=tuple(blocking),
        evidence_head=evidence_head,
    )
