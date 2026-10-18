"""Structured Schema for Frontier Research (L05).

Replaces unstructured ad-hoc web searches with formal hypothesis, citation,
constraint, and evidence schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from paeos.semantic.types import AuthoritativeSourceTier


@dataclass(frozen=True, slots=True)
class ResearchHypothesis:
    """A falsifiable hypothesis explored during frontier research."""
    hypothesis_id: str
    statement: str
    context: str
    falsification_conditions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceCitation:
    """An external or historical citation supporting or refuting a hypothesis."""
    citation_id: str
    source_title: str
    source_reference: str
    tier: AuthoritativeSourceTier
    relevance_summary: str


@dataclass(frozen=True, slots=True)
class TechnicalConstraint:
    """A quantified technical or operational boundary identified during research."""
    constraint_name: str
    parameter_bound: str
    rationale: str


@dataclass(frozen=True, slots=True)
class FrontierResearchPacket:
    """A formal research packet submitted from L05 Research to downstream L06 Trade-Off."""
    packet_id: str
    topic: str
    hypotheses: tuple[ResearchHypothesis, ...]
    citations: tuple[EvidenceCitation, ...]
    constraints: tuple[TechnicalConstraint, ...]
    synthesis: str
