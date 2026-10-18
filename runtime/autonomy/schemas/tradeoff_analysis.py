"""Structured Schema for Trade-Off Analysis (L06).

Replaces informal prose with quantitative multi-criteria Pareto scoring matrices.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradeOffCriterion:
    """A weighted evaluation criterion."""
    criterion_id: str
    name: str
    weight: float  # e.g. 0.0 to 1.0
    description: str


@dataclass(frozen=True, slots=True)
class CandidateOptionScore:
    """Score for one candidate option on one criterion."""
    option_id: str
    criterion_id: str
    score: float  # e.g. 0.0 to 10.0
    evidence_notes: str


@dataclass(frozen=True, slots=True)
class CandidateOption:
    """An architectural candidate option evaluated in the trade-off matrix."""
    option_id: str
    name: str
    description: str
    is_pareto_optimal: bool
    scores: tuple[CandidateOptionScore, ...] = ()


@dataclass(frozen=True, slots=True)
class MultiCriteriaTradeOffMatrix:
    """A formal machine-readable trade-off matrix submitted from L06 to L07/L08."""
    matrix_id: str
    decision_topic: str
    criteria: tuple[TradeOffCriterion, ...]
    options: tuple[CandidateOption, ...]
    recommended_option_id: str
    selection_rationale: str
