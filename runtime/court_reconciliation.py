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
    sealed = 0
    remanded = 0
    remediated = 0

    for row in rows:
        etype = row.event.kind if hasattr(row, "event") else getattr(row, "event_type", "")
        if etype == "COURT_SEALED":
            sealed += 1
        elif etype == "COURT_REMANDED":
            remanded += 1
        elif etype == "COURT_REMEDIATED":
            remediated += 1

    return CourtCounts(sealed=sealed, remanded=remanded, remediated=remediated)


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

    if (
        builder_family is not None
        and auditor_family is not None
        and builder_family == auditor_family
    ):
        raise DecorrelationError(
            f"Builder and Auditor share the same family ({builder_family})"
        )


    return (builder_family or "unknown", auditor_family or "unknown")
