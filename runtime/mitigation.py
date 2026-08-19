"""Canonical Layer L07: Trade-off Mitigation (StageId.MITIGATION).

Binds safeguards, kill-switches, fallback behaviors, and accepted-risk records to
hazards identified during L06 Trade-off Analysis.
"""

from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class TradeoffHazard:
    id: str
    title: str
    severity: str  # HIGH, MEDIUM, LOW


@dataclass(frozen=True)
class Safeguard:
    id: str
    hazard_id: str
    mechanism: str  # KILL_SWITCH, FALLBACK, SHADOW_MODE, SAFETY_CONSTRAINT
    description: str


@dataclass(frozen=True)
class AcceptedRisk:
    id: str
    hazard_id: str
    rationale: str
    approver: str


@dataclass(frozen=True)
class MitigationCatalogue:
    safeguards: tuple[Safeguard, ...] = ()
    accepted_risks: tuple[AcceptedRisk, ...] = ()
    hazards: tuple[TradeoffHazard, ...] = ()

    def has_high_severity_coverage(self) -> bool:
        """Assert exit guard: every HIGH-severity hazard carries a safeguard or accepted-risk."""
        high_hazards = {h.id for h in self.hazards if h.severity.upper() == "HIGH"}
        if not high_hazards:
            return True
        covered = {s.hazard_id for s in self.safeguards} | {r.hazard_id for r in self.accepted_risks}
        return high_hazards.issubset(covered)


def mitigate_tradeoffs(hazards: Sequence[TradeoffHazard]) -> MitigationCatalogue:
    """Produce a canonical MitigationCatalogue binding safeguards to identified hazards."""
    safeguards: list[Safeguard] = []
    accepted_risks: list[AcceptedRisk] = []

    for idx, h in enumerate(hazards, start=1):
        if h.severity.upper() == "HIGH":
            safeguards.append(
                Safeguard(
                    id=f"SG-{idx}",
                    hazard_id=h.id,
                    mechanism="FALLBACK",
                    description=f"Automated fallback mechanism bound to hazard {h.id}: {h.title}",
                )
            )
        else:
            accepted_risks.append(
                AcceptedRisk(
                    id=f"AR-{idx}",
                    hazard_id=h.id,
                    rationale=f"Low/medium risk accepted under standard operational boundaries: {h.title}",
                    approver="L07_MITIGATION_STAGE",
                )
            )

    return MitigationCatalogue(
        safeguards=tuple(safeguards),
        accepted_risks=tuple(accepted_risks),
        hazards=tuple(hazards),
    )
