"""Universal Sidecar Stage Scorer (R5.4).

Executes decorrelated sidecar scoring across every stage artifact (RESEARCH, DESIGN, CRITIQUE,
ADVERSARIAL_REVIEW, PLAN, IMPLEMENT). Emits structured evaluation JSON reports and concise
suggestions if stage score falls below threshold.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from kernel.types import Role, StageId

logger = logging.getLogger(__name__)

__all__ = ["ScoreVerdict", "SidecarScore", "SidecarStageScorer"]


class ScoreVerdict(Enum):
    APPROVED = "APPROVED"
    NEEDS_REFINEMENT = "NEEDS_REFINEMENT"


@dataclass(frozen=True, slots=True)
class SidecarScore:
    """Quantitative evaluation outcome from a sidecar model for one stage."""

    stage: str
    primary_model: str
    scorer_model: str
    completeness_score: int  # 0 - 100
    rigor_score: int  # 0 - 100
    non_vacuity_score: int  # 0 - 100
    overall_score: int  # 0 - 100
    verdict: ScoreVerdict
    suggestions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "primary_model": self.primary_model,
            "scorer_model": self.scorer_model,
            "scores": {
                "completeness": self.completeness_score,
                "rigor": self.rigor_score,
                "non_vacuity": self.non_vacuity_score,
            },
            "overall_score": self.overall_score,
            "verdict": self.verdict.value,
            "suggestions": list(self.suggestions),
        }


class SidecarStageScorer:
    """Evaluates and scores artifacts emitted at each stage using a decorrelated sidecar model."""

    def __init__(self, storage_dir: Path | str = ".paeos_state/evaluations") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def score_stage(
        self,
        *,
        run_id: str,
        stage: StageId,
        primary_model: str = "unknown",
        artifact_content: str = "",
        custom_scores: dict[str, int] | None = None,
    ) -> SidecarScore:
        """Evaluate a stage artifact and persist the evaluation JSON.

        Entry 143 honesty note: this scorer is a DETERMINISTIC HEURISTIC (content length +
        keyword presence), NOT a model call. It is labeled `scorer_model="heuristic-v1"` —
        previously it claimed `glm-5.3`/`gpt-5.6-sol` decoration without any model being
        invoked, which is the CRITICAL-002 fabrication class. Real decorrelated model
        scoring is future work (see notebook Entry 143, remediation R-b).
        """
        scorer_model = "heuristic-v1"

        if custom_scores:
            c_score = custom_scores.get("completeness", 95)
            r_score = custom_scores.get("rigor", 95)
            v_score = custom_scores.get("non_vacuity", 95)
        else:
            # Deterministic baseline scoring heuristic for active runtime evaluation
            content_len = len(artifact_content)
            c_score = 95 if content_len > 100 else 80
            r_score = 95 if "objective" in artifact_content.lower() or "claim" in artifact_content.lower() else 85
            v_score = 95 if "test" in artifact_content.lower() or "assert" in artifact_content.lower() or "pytest" in artifact_content.lower() else 90

        overall = (c_score + r_score + v_score) // 3
        suggestions: list[str] = []
        if overall >= 90:
            verdict = ScoreVerdict.APPROVED
        else:
            verdict = ScoreVerdict.NEEDS_REFINEMENT
            if c_score < 90:
                suggestions.append("Expand coverage of edge cases and input validation.")
            if r_score < 90:
                suggestions.append("Ground assertions explicitly in first-principles constraints.")
            if v_score < 90:
                suggestions.append("Ensure evidence commands discriminate change from baseline.")

        score_obj = SidecarScore(
            stage=stage.name,
            primary_model=primary_model,
            scorer_model=scorer_model,
            completeness_score=c_score,
            rigor_score=r_score,
            non_vacuity_score=v_score,
            overall_score=overall,
            verdict=verdict,
            suggestions=tuple(suggestions),
        )

        out_path = self._storage_dir / f"{run_id}_{stage.name}_score.json"
        out_path.write_text(json.dumps(score_obj.to_dict(), indent=2), encoding="utf-8")
        logger.info("Sidecar scored stage %s for run %s: %d/100 (%s)", stage.name, run_id, overall, verdict.value)
        return score_obj
