"""Court disposition and model provenance reconciliation (Gate G Task 2)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kernel.ledger import LedgerRow


class DecorrelationError(RuntimeError):
    """Raised when Builder and Auditor share the same model family."""


@dataclass(frozen=True, slots=True)
class CourtCounts:
    sealed: int
    remanded: int
    remediated: int


def reconcile_court_counts(rows: Sequence[LedgerRow]) -> CourtCounts:
    claims: dict[str, dict[str, bool]] = {}

    for row in rows:
        etype = row.event.kind if hasattr(row, "event") else getattr(row, "event_type", "")
        payload = (
            getattr(row.event, "payload", {})
            if hasattr(row, "event")
            else getattr(row, "payload", {})
        )
        claim_id = payload.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            continue
        state = claims.setdefault(
            claim_id, {"sealed": False, "remanded": False, "remediated": False}
        )
        if etype == "COURT_SEALED":
            state["sealed"] = True
        elif etype == "COURT_REMANDED":
            state["remanded"] = True
        elif etype == "COURT_REMEDIATED" and state["remanded"]:
            state["remediated"] = True

    return CourtCounts(
        sealed=sum(1 for state in claims.values() if state["sealed"]),
        remanded=sum(1 for state in claims.values() if state["remanded"]),
        remediated=sum(1 for state in claims.values() if state["remediated"]),
    )


def verify_builder_auditor_receipts(
    run_id: str, rows: Sequence[LedgerRow], cas: object = None
) -> tuple[str, str]:
    builder_family = None
    auditor_family = None

    for row in rows:
        payload = (
            getattr(row.event, "payload", {})
            if hasattr(row, "event")
            else getattr(row, "payload", {})
        )
        if payload.get("run_id") == run_id:
            if "builder_family" in payload:
                builder_family = str(payload["builder_family"])
            if "auditor_family" in payload:
                auditor_family = str(payload["auditor_family"])

    unknown_families = {"unknown", "none"}
    if (
        not builder_family
        or not auditor_family
        or builder_family.lower() in unknown_families
        or auditor_family.lower() in unknown_families
    ):
        raise DecorrelationError("missing Builder/Auditor physical identity")
    if builder_family == auditor_family:
        raise DecorrelationError(f"Builder and Auditor share the same family ({builder_family})")

    return (builder_family, auditor_family)
