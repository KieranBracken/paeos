"""Core types and data models for the PAEOS Semantic-Assurance Kernel.

Preserves canonical L01-L19 lifecycle invariants.
Provides deterministic structures for semantic intent reconstruction, obligation lineage,
bidirectional delta analysis, and fail-closed L11 freeze enforcement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SemanticAssuranceError(ValueError):
    """Base error for semantic-assurance failures."""


class SemanticScopeNarrowingError(SemanticAssuranceError):
    """Raised when child task or candidate silently narrows scope or drops obligations."""


class L11FreezeDeniedError(SemanticAssuranceError):
    """Raised when an L11 contract or capability manifest fails semantic completeness validation."""


class AuthoritativeSourceTier(StrEnum):
    """Authoritative source hierarchy (Tiers 1-6).

    Tier 1 is highest authority. Tests and current implementations are deliberately absent.
    """
    TIER_1_FOUNDER_DIRECTIVE = "TIER_1_FOUNDER_DIRECTIVE"
    TIER_2_RATIFIED_ARCHITECTURAL_DECISION = "TIER_2_RATIFIED_ARCHITECTURAL_DECISION"
    TIER_3_ORIGINAL_PROBLEM_STATEMENT = "TIER_3_ORIGINAL_PROBLEM_STATEMENT"
    TIER_4_CANONICAL_SPECIFICATION = "TIER_4_CANONICAL_SPECIFICATION"
    TIER_5_ACCEPTED_AMENDMENT = "TIER_5_ACCEPTED_AMENDMENT"
    TIER_6_HISTORICAL_DESIGN_RATIONALE = "TIER_6_HISTORICAL_DESIGN_RATIONALE"


class ObligationNature(StrEnum):
    """Classification of an obligation's provenance."""
    HISTORICAL_CANONICAL = "HISTORICAL_CANONICAL"
    DEBT_0250_HARDENING = "DEBT_0250_HARDENING"
    DERIVED_INFERENCE = "DERIVED_INFERENCE"


class SemanticDispositionKind(StrEnum):
    """Lawful disposition categories for capability obligations."""
    IMPLEMENTED = "IMPLEMENTED"
    PRESERVED_AS_IS = "PRESERVED_AS_IS"
    AUTHORIZED_DEFERMENT = "AUTHORIZED_DEFERMENT"
    AUTHORIZED_SUPERSESSION = "AUTHORIZED_SUPERSESSION"
    UNPLANNED_EXTRA_CAPABILITY = "UNPLANNED_EXTRA_CAPABILITY"
    IMPLEMENTATION_DETAIL = "IMPLEMENTATION_DETAIL"
    INTENT_AMBIGUOUS = "INTENT_AMBIGUOUS"
    UNAUTHORIZED_SCOPE_NARROWING = "UNAUTHORIZED_SCOPE_NARROWING"
    MISSING_CAPABILITY = "MISSING_CAPABILITY"


class SemanticDeltaClassification(StrEnum):
    """Classification of delta between expected and current capability surfaces."""
    MISSING_CAPABILITY = "MISSING_CAPABILITY"
    UNAUTHORIZED_SCOPE_NARROWING = "UNAUTHORIZED_SCOPE_NARROWING"
    AUTHORIZED_DEFERMENT = "AUTHORIZED_DEFERMENT"
    AUTHORIZED_SUPERSESSION = "AUTHORIZED_SUPERSESSION"
    UNPLANNED_EXTRA_CAPABILITY = "UNPLANNED_EXTRA_CAPABILITY"
    IMPLEMENTATION_DETAIL = "IMPLEMENTATION_DETAIL"
    INTENT_AMBIGUOUS = "INTENT_AMBIGUOUS"


class SemanticRequalificationStatus(StrEnum):
    """Final requalification status of an audited subsystem."""
    SEMANTICALLY_REQUALIFIED = "SEMANTICALLY_REQUALIFIED"
    SEMANTICALLY_REQUALIFIED_WITH_DEFERRED_OBLIGATIONS = "SEMANTICALLY_REQUALIFIED_WITH_DEFERRED_OBLIGATIONS"
    SEMANTIC_SCOPE_REMAND = "SEMANTIC_SCOPE_REMAND"
    INTENT_RECONSTRUCTION_REQUIRED = "INTENT_RECONSTRUCTION_REQUIRED"


@dataclass(frozen=True, slots=True)
class SemanticObligation:
    """An authoritative capability obligation derived from intent sources."""
    obligation_id: str
    subsystem_id: str
    description: str
    source_tier: AuthoritativeSourceTier
    source_reference: str
    obligation_nature: ObligationNature
    invariants_affected: tuple[str, ...] = ()
    intent_hash: str = ""

    def __post_init__(self) -> None:
        if not self.obligation_id or not self.subsystem_id:
            raise SemanticAssuranceError("obligation_id and subsystem_id must be non-empty")
        if not self.intent_hash:
            h = hashlib.sha256(
                f"{self.obligation_id}:{self.subsystem_id}:{self.description}:{self.source_tier.value}:{self.source_reference}".encode("utf-8")
            ).hexdigest()
            object.__setattr__(self, "intent_hash", h)


@dataclass(frozen=True, slots=True)
class SemanticObligationDisposition:
    """Lawful disposition of an obligation."""
    obligation_id: str
    disposition: SemanticDispositionKind
    rationale: str
    debt_id: str | None = None
    observation_refs: tuple[str, ...] = ()
    superseded_by: str | None = None
    court_verdict_ref: str | None = None

    def validate(self) -> None:
        """Validate lawful disposition rules."""
        if not self.obligation_id:
            raise SemanticAssuranceError("obligation_id must not be empty")
        if self.disposition in (SemanticDispositionKind.IMPLEMENTED, SemanticDispositionKind.PRESERVED_AS_IS):
            if not self.observation_refs:
                raise SemanticAssuranceError(
                    f"Disposition {self.disposition} for {self.obligation_id} requires observation_refs"
                )
        elif self.disposition == SemanticDispositionKind.AUTHORIZED_DEFERMENT:
            if not self.debt_id or not self.debt_id.startswith("DEBT-"):
                raise SemanticAssuranceError(
                    f"AUTHORIZED_DEFERMENT for {self.obligation_id} requires a valid debt_id (e.g. DEBT-xxxx)"
                )
        elif self.disposition == SemanticDispositionKind.AUTHORIZED_SUPERSESSION:
            if not self.superseded_by:
                raise SemanticAssuranceError(
                    f"AUTHORIZED_SUPERSESSION for {self.obligation_id} requires superseded_by reference"
                )
        elif self.disposition in (
            SemanticDispositionKind.UNAUTHORIZED_SCOPE_NARROWING,
            SemanticDispositionKind.MISSING_CAPABILITY,
        ):
            raise SemanticScopeNarrowingError(
                f"Obligation {self.obligation_id} is in unlawful state: {self.disposition}"
            )


@dataclass(frozen=True, slots=True)
class SemanticDelta:
    """One delta item between expected and current capability surfaces."""
    delta_name: str
    classification: SemanticDeltaClassification
    direction: str  # "EXPECTED_MINUS_CURRENT" | "CURRENT_MINUS_EXPECTED"
    justification: str
    debt_ref: str | None = None


@dataclass(frozen=True, slots=True)
class SemanticDeltaReport:
    """Result of bidirectional delta analysis between expected and current surfaces."""
    subsystem_id: str
    expected_surface: tuple[str, ...]
    current_surface: tuple[str, ...]
    missing: tuple[str, ...]
    extra: tuple[str, ...]
    deltas: tuple[SemanticDelta, ...]
    is_clean: bool
    status: SemanticRequalificationStatus
    details: tuple[str, ...] = ()
