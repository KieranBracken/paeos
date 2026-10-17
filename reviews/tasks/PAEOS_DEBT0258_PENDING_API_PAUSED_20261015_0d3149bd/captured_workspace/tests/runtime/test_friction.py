"""Tests for the RB-0008 Autonomous Friction Handler (runtime/friction.py).

Validates that:
    - Clean seals produce no friction records.
    - Each known remand/halt pattern classifies to the correct category.
    - Leverage scoring (Primitive 4) computes substrate, recurrence, and threshold flags.
    - Confidence assessment (Primitive 5) downgrades recurring SOFT DEBT to INTAKE_FIX.
    - Recurring TCB-implicated failures generate PROPOSAL (PAEOS-IP-XXXX.md) items.
    - High leverage friction (>= 5.0) generates immediate queue repair Intakes.
    - Disk recording writes well-formed DEBT, RB, and IP markdown files with leverage notes.
    - Sequence numbering increments correctly.
    - NONE and INTAKE_FIX categories produce no disk artifacts.
"""

from __future__ import annotations

from pathlib import Path

from runtime.friction import (
    FrictionCategory,
    assess_confidence,
    classify_friction,
    record_friction,
    score_leverage,
)
from runtime.orchestrator import RunOutcome, RunStatus


def _outcome(status: RunStatus, detail: str, goal_id: str = "g-test123") -> RunOutcome:
    return RunOutcome(status=status, goal_id=goal_id, detail=detail)


# ---- Primitive 4: Leverage Scoring tests -----------------------------------------


def test_score_leverage_deliverable_path() -> None:
    score = score_leverage(("sakg/probe.py",), has_matching_scar=False)
    assert score.raw == 1.0
    assert not score.is_substrate
    assert not score.is_recurring
    assert not score.exceeds_threshold
    assert score.blast_radius == "SOFT"


def test_score_leverage_substrate_path() -> None:
    score = score_leverage(("runtime/friction.py",), has_matching_scar=False)
    assert score.raw == 3.0
    assert score.is_substrate
    assert not score.is_recurring
    assert not score.exceeds_threshold
    assert score.blast_radius == "SOFT"


def test_score_leverage_recurring_substrate_path() -> None:
    score = score_leverage(("runtime/friction.py",), has_matching_scar=True)
    assert score.raw == 6.0  # 1.0 * 3.0 (substrate) * 2.0 (recurring) = 6.0
    assert score.is_substrate
    assert score.is_recurring
    assert score.exceeds_threshold  # >= 5.0
    assert score.blast_radius == "SOFT"


def test_score_leverage_hard_blast_radius() -> None:
    score = score_leverage(("kernel/cas.py",), has_matching_scar=False)
    assert score.is_substrate  # kernel is top-level substrate
    assert score.blast_radius == "HARD"
    assert score.raw == 4.0  # 1.0 * 3.0 + 1.0 = 4.0


# ---- Primitive 5: Confidence & Auto-Promotion tests ----------------------------


def test_assess_confidence_auto_promotes_recurring_soft_debt() -> None:
    leverage = score_leverage(("sakg/probe.py",), has_matching_scar=True)
    conf = assess_confidence(FrictionCategory.DEBT, leverage)
    assert conf.can_auto_promote
    assert "auto-promoted" in conf.reason


def test_assess_confidence_denies_hard_blast_radius() -> None:
    leverage = score_leverage(("kernel/cas.py",), has_matching_scar=True)
    conf = assess_confidence(FrictionCategory.DEBT, leverage)
    assert not conf.can_auto_promote
    assert "HARD" in conf.reason


def test_assess_confidence_denies_non_recurring() -> None:
    leverage = score_leverage(("sakg/probe.py",), has_matching_scar=False)
    conf = assess_confidence(FrictionCategory.DEBT, leverage)
    assert not conf.can_auto_promote
    assert "First occurrence" in conf.reason


def test_assess_confidence_denies_research() -> None:
    leverage = score_leverage(("sakg/probe.py",), has_matching_scar=True)
    conf = assess_confidence(FrictionCategory.RESEARCH, leverage)
    assert not conf.can_auto_promote
    assert "RESEARCH" in conf.reason


def test_assess_confidence_denies_proposal() -> None:
    leverage = score_leverage(("kernel/cas.py",), has_matching_scar=True)
    conf = assess_confidence(FrictionCategory.PROPOSAL, leverage)
    assert not conf.can_auto_promote
    assert "PROPOSAL" in conf.reason


# ---- classification tests -------------------------------------------------------


def test_sealed_outcome_produces_no_friction() -> None:
    outcome = _outcome(RunStatus.SEALED, "sealed")
    record = classify_friction(outcome)
    assert record.category is FrictionCategory.NONE


def test_remand_no_artifact_classifies_as_debt() -> None:
    outcome = _outcome(RunStatus.REMANDED, "builder produced no artifact")
    record = classify_friction(outcome, changed_paths=("sakg/x.py",))
    assert record.category is FrictionCategory.DEBT
    assert "Write-Scope" in record.title


def test_recurring_remand_auto_promotes_to_intake_fix() -> None:
    outcome = _outcome(RunStatus.REMANDED, "builder produced no artifact")
    record = classify_friction(
        outcome, changed_paths=("sakg/x.py",), has_matching_scar=True
    )
    assert record.category is FrictionCategory.INTAKE_FIX
    assert record.confidence.can_auto_promote


def test_recurring_tcb_failure_classifies_as_proposal() -> None:
    outcome = _outcome(RunStatus.REMANDED, "court remanded")
    record = classify_friction(
        outcome, changed_paths=("kernel/cas.py",), has_matching_scar=True
    )
    assert record.category is FrictionCategory.PROPOSAL
    assert "Recurring TCB Failure" in record.title


def test_high_leverage_friction_generates_high_leverage_intake() -> None:
    outcome = _outcome(RunStatus.REMANDED, "builder produced no artifact", goal_id="g-highlev")
    record = classify_friction(
        outcome, changed_paths=("runtime/friction.py",), has_matching_scar=True
    )
    # leverage is 6.0 (substrate x3 * recurring x2) >= 5.0
    assert record.leverage.exceeds_threshold
    assert record.high_leverage_intake is not None
    assert "RB-0008 Immediate Fix" in record.high_leverage_intake.objective


# ---- recording tests -------------------------------------------------------------


def test_record_friction_none_writes_nothing(tmp_path: Path) -> None:
    outcome = _outcome(RunStatus.SEALED, "sealed")
    record = classify_friction(outcome)
    result = record_friction(record, tmp_path)
    assert result is None


def test_record_friction_intake_fix_writes_nothing(tmp_path: Path) -> None:
    outcome = _outcome(RunStatus.REMANDED, "builder produced no artifact")
    record = classify_friction(
        outcome, changed_paths=("sakg/x.py",), has_matching_scar=True
    )
    assert record.category is FrictionCategory.INTAKE_FIX
    result = record_friction(record, tmp_path)
    assert result is None


def test_record_friction_writes_debt_file(tmp_path: Path) -> None:
    (tmp_path / "ledger" / "debt").mkdir(parents=True)
    outcome = _outcome(RunStatus.REMANDED, "builder produced no artifact", goal_id="g-abc123")
    record = classify_friction(outcome, changed_paths=("sakg/x.py",))
    path = record_friction(record, tmp_path)
    assert path is not None
    assert path.name == "DEBT-0001.md"
    content = path.read_text(encoding="utf-8")
    assert "DEBT-0001" in content
    assert "g-abc123" in content
    assert "builder produced no artifact" in content
    assert "`sakg/x.py`" in content
    assert "Leverage Assessment" in content
    assert "Confidence Assessment" in content
    assert "OPEN" in content


def test_record_friction_writes_research_file(tmp_path: Path) -> None:
    (tmp_path / "backlog" / "research").mkdir(parents=True)
    (tmp_path / "ledger" / "debt").mkdir(parents=True)
    outcome = _outcome(RunStatus.REMANDED, "adversary blocked the seal", goal_id="g-def456")
    record = classify_friction(outcome, changed_paths=("sakg/probe.py",))
    path = record_friction(record, tmp_path)
    assert path is not None
    assert path.name.startswith("RB-0001-")
    content = path.read_text(encoding="utf-8")
    assert "RB-0001" in content
    assert "g-def456" in content
    assert "adversary blocked the seal" in content
    assert "Leverage Assessment" in content
    assert "Research" in content


def test_record_friction_writes_proposal_file(tmp_path: Path) -> None:
    (tmp_path / "proposals").mkdir(parents=True)
    outcome = _outcome(RunStatus.REMANDED, "court remanded", goal_id="g-prop789")
    record = classify_friction(
        outcome, changed_paths=("kernel/cas.py",), has_matching_scar=True
    )
    assert record.category is FrictionCategory.PROPOSAL
    path = record_friction(record, tmp_path)
    assert path is not None
    assert path.name.startswith("PAEOS-IP-0001-")
    content = path.read_text(encoding="utf-8")
    assert "PAEOS-IP-0001" in content
    assert "g-prop789" in content
    assert "PROPOSED" in content
    assert "Human Ratification Gate (A4)" in content


def test_sequence_numbering_increments(tmp_path: Path) -> None:
    debt_dir = tmp_path / "ledger" / "debt"
    debt_dir.mkdir(parents=True)
    (debt_dir / "DEBT-0001.md").write_text("existing", encoding="utf-8")
    (debt_dir / "DEBT-0002.md").write_text("existing", encoding="utf-8")

    outcome = _outcome(RunStatus.REMANDED, "court remanded", goal_id="g-seq")
    record = classify_friction(outcome)
    path = record_friction(record, tmp_path)
    assert path is not None
    assert path.name == "DEBT-0003.md"

    path2 = record_friction(record, tmp_path)
    assert path2 is not None
    assert path2.name == "DEBT-0004.md"
