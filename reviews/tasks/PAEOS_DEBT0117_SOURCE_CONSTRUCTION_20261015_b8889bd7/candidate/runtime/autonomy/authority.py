"""Deterministic A0–A5 authority classifier, Root-Envelope resolver, and Founder-stop predicate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


from kernel.types import (
    ActionPermission,
    AuthorityEnvelope,
    AuthorityExpansionForbiddenError,
    AuthorityTier,
)


class FindingClass(StrEnum):
    CURRENT_BLOCKER = "CURRENT_BLOCKER"
    NONBLOCKING_FINDING = "NONBLOCKING_FINDING"
    FUTURE_IMPROVEMENT = "FUTURE_IMPROVEMENT"


class FounderStopRequiredError(RuntimeError):
    """Action requires explicit Founder ratification or sovereign decision."""


_TIER_TO_PERMISSION = {
    AuthorityTier.A0_IMPLEMENTATION: ActionPermission.AUTONOMOUS,
    AuthorityTier.A1_LOCAL_SUBSYSTEM: ActionPermission.AUTONOMOUS,
    AuthorityTier.A2_CROSS_SUBSYSTEM: ActionPermission.GOVERNED_REVIEW,
    AuthorityTier.A3_ACCEPTANCE_CONTRACT: ActionPermission.COUNCIL_EVIDENCE_GATE,
    AuthorityTier.A4_CONSTITUTIONAL: ActionPermission.FOUNDER_RATIFICATION,
    AuthorityTier.A5_SOVEREIGN: ActionPermission.FOUNDER_EXCLUSIVE,
}

_SENTIUM_QUARANTINE_MARKERS = frozenset({"sentium", "trading", "order_execution", "live_capital"})
_CONSTITUTIONAL_PREFIXES = frozenset({"constitution", "operations/ENGINEERING_LIFECYCLE.md"})


@dataclass(frozen=True, slots=True)
class FounderDecisionPacket:
    gap_summary: str
    classification: AuthorityTier
    evidence_hashes: tuple[str, ...]
    alternatives_considered: tuple[str, ...]
    reversible_checkpoint_ref: str
    exact_decision_required: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class AuthorityClassifier:
    """Deterministic classifier assigning finding to A0–A5 tier."""

    @staticmethod
    def classify(
        *,
        description: str,
        paths: tuple[str, ...],
        is_reversible: bool = True,
        affects_constitution: bool = False,
        affects_external_capital: bool = False,
        affects_acceptance_criteria: bool = False,
        crosses_subsystems: bool = False,
    ) -> AuthorityTier:
        desc_lower = description.lower()

        # Check A5 Sovereign: live capital, Sentium, trading
        if affects_external_capital or any(marker in desc_lower for marker in _SENTIUM_QUARANTINE_MARKERS):
            return AuthorityTier.A5_SOVEREIGN
        for p in paths:
            norm_p = p.lower()
            if any(marker in norm_p for marker in _SENTIUM_QUARANTINE_MARKERS):
                return AuthorityTier.A5_SOVEREIGN

        # Check A4 Constitutional: constitution files or explicit constitutional amendment
        if affects_constitution or any(p.startswith(tuple(_CONSTITUTIONAL_PREFIXES)) for p in paths):
            return AuthorityTier.A4_CONSTITUTIONAL
        if "constitutional" in desc_lower or "ceremony_override" in desc_lower:
            return AuthorityTier.A4_CONSTITUTIONAL

        # Check A3 Acceptance / Contract: manifest or milestone criteria
        if affects_acceptance_criteria or "manifest" in desc_lower or "acceptance" in desc_lower:
            return AuthorityTier.A3_ACCEPTANCE_CONTRACT

        # Check A2 Cross-Subsystem
        if crosses_subsystems or len({p.split("/")[0] for p in paths if "/" in p}) > 1:
            return AuthorityTier.A2_CROSS_SUBSYSTEM
        if "cross-subsystem" in desc_lower or "integration" in desc_lower:
            return AuthorityTier.A2_CROSS_SUBSYSTEM

        # Check A1 Local Subsystem
        if len(paths) > 1 or "subsystem" in desc_lower or "architecture" in desc_lower:
            return AuthorityTier.A1_LOCAL_SUBSYSTEM

        # Default A0 Implementation Repair
        return AuthorityTier.A0_IMPLEMENTATION


class RootEnvelopeAuthorityResolver:
    """Enforces Root-Envelope Model for recursive remediation authority."""

    @staticmethod
    def resolve_child_envelope(
        *,
        root_envelope: AuthorityEnvelope,
        parent_envelope: AuthorityEnvelope,
        requested_paths: tuple[str, ...],
        requested_tier: AuthorityTier,
        is_reversible: bool = True,
    ) -> AuthorityEnvelope:
        """Derive child authority within RootEnvelope & DelegatedAuthorityCeiling.
        
        Permits child scope to differ from parent task-local scope, provided all paths
        are contained in root_envelope.
        """
        # Check that requested tier does not exceed root envelope ceiling
        _tiers = list(AuthorityTier)
        if _tiers.index(requested_tier) > _tiers.index(root_envelope.delegated_ceiling):
            raise AuthorityExpansionForbiddenError(
                f"Requested tier {requested_tier} exceeds root ceiling {root_envelope.delegated_ceiling}"
            )

        # Check that every requested path is in the root mission envelope
        unauthorized = []
        for path in requested_paths:
            if not root_envelope.contains_path(path):
                unauthorized.append(path)

        if unauthorized:
            raise AuthorityExpansionForbiddenError(
                f"Requested paths outside root envelope: {unauthorized}"
            )

        action_perm = _TIER_TO_PERMISSION[requested_tier]
        return AuthorityEnvelope(
            root_mission_id=root_envelope.root_mission_id,
            authorized_paths=frozenset(requested_paths),
            delegated_ceiling=root_envelope.delegated_ceiling,
            allowed_action=action_perm,
            is_reversible=is_reversible,
        )


class FounderStopPredicate:
    """Evaluates if an action or condition requires stopping for Founder decision."""

    @staticmethod
    def evaluate(
        tier: AuthorityTier,
        paths: tuple[str, ...] = (),
        description: str = "",
        evidence_hashes: tuple[str, ...] = (),
        checkpoint_ref: str = "",
    ) -> tuple[bool, FounderDecisionPacket | None]:
        desc_lower = description.lower()
        is_stop = False
        reasons = []

        if tier in {AuthorityTier.A4_CONSTITUTIONAL, AuthorityTier.A5_SOVEREIGN}:
            is_stop = True
            reasons.append(f"Authority tier {tier.value} is reserved")

        for p in paths:
            if any(m in p.lower() for m in _SENTIUM_QUARANTINE_MARKERS):
                is_stop = True
                reasons.append(f"Quarantined Sentium/capital path: {p}")

        if any(m in desc_lower for m in _SENTIUM_QUARANTINE_MARKERS):
            is_stop = True
            reasons.append("Sentium or live-capital reference in description")

        if not is_stop:
            return False, None

        packet = FounderDecisionPacket(
            gap_summary="; ".join(reasons) or "Founder-stop condition triggered",
            classification=tier,
            evidence_hashes=evidence_hashes,
            alternatives_considered=("Halt and await sovereign Founder decision", "Revert to checkpoint"),
            reversible_checkpoint_ref=checkpoint_ref,
            exact_decision_required=f"Ratify or reject transition requiring {tier.value}",
        )
        return True, packet
