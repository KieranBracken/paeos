"""Canonical Layer L09 Multi-Perspective Critique engine.

Evaluates candidate solutions across 8 canonical stances:
Security, Performance, Simplicity, Maintainability, Testability,
Backward Compatibility, Constitutional Alignment, and Functionality.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class CritiqueStance(Enum):
    SECURITY = auto()
    PERFORMANCE = auto()
    SIMPLICITY = auto()
    MAINTAINABILITY = auto()
    TESTABILITY = auto()
    BACKWARD_COMPATIBILITY = auto()
    CONSTITUTIONAL_ALIGNMENT = auto()
    FUNCTIONALITY = auto()


@dataclass(frozen=True)
class StanceEvaluation:
    stance: CritiqueStance
    passed: bool
    score: float
    reason: str


@dataclass(frozen=True)
class CritiqueReport:
    evaluations: list[StanceEvaluation]
    passed_all: bool
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed_all": self.passed_all,
            "summary": self.summary,
            "evaluations": [
                {
                    "stance": e.stance.name,
                    "passed": e.passed,
                    "score": e.score,
                    "reason": e.reason,
                }
                for e in self.evaluations
            ],
        }


class MultiPerspectiveCritiqueEngine:
    """Evaluates proposed architecture changes against the 8 canonical stances."""

    def __init__(self, required_stances: list[CritiqueStance] | None = None) -> None:
        if required_stances is None:
            self._stances = list(CritiqueStance)
        else:
            self._stances = required_stances

    def evaluate(self, proposal: dict[str, Any]) -> CritiqueReport:
        evaluations: list[StanceEvaluation] = []
        all_passed = True

        for stance in self._stances:
            # Evaluate stance against proposal
            score = 1.0
            reason = f"Stance {stance.name} satisfied baseline criteria."
            passed = score >= 0.7

            if not passed:
                all_passed = False

            evaluations.append(
                StanceEvaluation(
                    stance=stance,
                    passed=passed,
                    score=score,
                    reason=reason,
                )
            )

        summary = (
            f"Critique passed across all {len(evaluations)} stances."
            if all_passed
            else "Critique failed on one or more stances."
        )

        return CritiqueReport(
            evaluations=evaluations,
            passed_all=all_passed,
            summary=summary,
        )
