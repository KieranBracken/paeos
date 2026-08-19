"""Unit tests for Universal Sidecar Stage Scorer (R5.4)."""

import json
from pathlib import Path

from kernel.types import StageId
from runtime.sidecar_scorer import ScoreVerdict, SidecarScore, SidecarStageScorer


def test_sidecar_stage_scorer_evaluation(tmp_path: Path) -> None:
    scorer = SidecarStageScorer(storage_dir=tmp_path)
    score = scorer.score_stage(
        run_id="run-test-01",
        stage=StageId.DESIGN,
        primary_model="gpt-5.6-sol",
        artifact_content="Objective: System design specification with test claims",
    )

    assert isinstance(score, SidecarScore)
    assert score.stage == "DESIGN"
    assert score.primary_model == "gpt-5.6-sol"
    assert score.scorer_model == "heuristic-v1"  # Entry 143: honest label — no model call happens
    assert score.overall_score >= 90
    assert score.verdict == ScoreVerdict.APPROVED

    json_file = tmp_path / "run-test-01_DESIGN_score.json"
    assert json_file.exists()

    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data["stage"] == "DESIGN"
    assert data["scorer_model"] == "heuristic-v1"
    assert data["overall_score"] >= 90


def test_sidecar_stage_scorer_refinement_suggestions(tmp_path: Path) -> None:
    scorer = SidecarStageScorer(storage_dir=tmp_path)
    score = scorer.score_stage(
        run_id="run-test-02",
        stage=StageId.PLAN,
        primary_model="glm-5.3",
        artifact_content="short",
        custom_scores={"completeness": 70, "rigor": 80, "non_vacuity": 85},
    )

    assert score.scorer_model == "heuristic-v1"  # Entry 143: honest label regardless of primary
    assert score.verdict == ScoreVerdict.NEEDS_REFINEMENT
    assert len(score.suggestions) > 0
