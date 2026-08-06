"""Tests for the RB-0008 Autonomous Friction Handler (runtime/friction.py).

Validates that:
    - Clean seals produce no friction records.
    - Each known remand/halt pattern classifies to the correct category.
    - Disk recording writes well-formed DEBT and RB markdown files.
    - Sequence numbering increments correctly.
    - NONE and INTAKE_FIX categories produce no disk artifacts.
"""

from __future__ import annotations

from pathlib import Path

from runtime.friction import (
    FrictionCategory,
    FrictionRecord,
    classify_friction,
    record_friction,
)
from runtime.orchestrator import RunOutcome, RunStatus


def _outcome(status: RunStatus, detail: str, goal_id: str = "g-test123") -> RunOutcome:
    return RunOutcome(status=status, goal_id=goal_id, detail=detail)


# ---- classification tests -------------------------------------------------------


def test_sealed_outcome_produces_no_friction() -> None:
    outcome = _outcome(RunStatus.SEALED, "sealed")
    record = classify_friction(outcome)
    assert record.category is FrictionCategory.NONE


def test_remand_no_artifact_classifies_as_debt() -> None:
    outcome = _outcome(RunStatus.REMANDED, "builder produced no artifact")
    record = classify_friction(outcome, changed_paths=("runtime/x.py",))
    assert record.category is FrictionCategory.DEBT
    assert "Write-Scope" in record.title


def test_remand_no_evidence_classifies_as_debt() -> None:
    outcome = _outcome(RunStatus.REMANDED, "no evidence submitted to the court for this run")
    record = classify_friction(outcome)
    assert record.category is FrictionCategory.DEBT
    assert "Court MCP" in record.title


def test_remand_vacuous_evidence_classifies_as_debt() -> None:
    outcome = _outcome(RunStatus.REMANDED, "non-probative (vacuous) evidence")
    record = classify_friction(outcome)
    assert record.category is FrictionCategory.DEBT
    assert "Non-Probative" in record.title


def test_remand_court_classifies_as_debt() -> None:
    outcome = _outcome(RunStatus.REMANDED, "court remanded")
    record = classify_friction(outcome)
    assert record.category is FrictionCategory.DEBT
    assert "Court Remand" in record.title


def test_adversary_block_classifies_as_research() -> None:
    outcome = _outcome(RunStatus.REMANDED, "adversary blocked the seal")
    record = classify_friction(outcome)
    assert record.category is FrictionCategory.RESEARCH
    assert "Adversary" in record.title


def test_budget_breach_classifies_as_research() -> None:
    outcome = _outcome(RunStatus.HALTED, "budget breach: tokens exceeded")
    record = classify_friction(outcome)
    assert record.category is FrictionCategory.RESEARCH
    assert "Budget" in record.title


def test_unrecognized_detail_defaults_to_debt() -> None:
    outcome = _outcome(RunStatus.REMANDED, "something completely unexpected happened")
    record = classify_friction(outcome)
    assert record.category is FrictionCategory.DEBT
    assert "Unclassified" in record.title


# ---- recording tests -------------------------------------------------------------


def test_record_friction_none_writes_nothing(tmp_path: Path) -> None:
    record = FrictionRecord(
        category=FrictionCategory.NONE,
        goal_id="g-test",
        detail="sealed",
        title="",
        changed_paths=(),
    )
    result = record_friction(record, tmp_path)
    assert result is None


def test_record_friction_intake_fix_writes_nothing(tmp_path: Path) -> None:
    record = FrictionRecord(
        category=FrictionCategory.INTAKE_FIX,
        goal_id="g-test",
        detail="trivial fix",
        title="Trivial",
        changed_paths=(),
    )
    result = record_friction(record, tmp_path)
    assert result is None


def test_record_friction_writes_debt_file(tmp_path: Path) -> None:
    # Create the debt directory with no existing files.
    (tmp_path / "ledger" / "debt").mkdir(parents=True)
    record = FrictionRecord(
        category=FrictionCategory.DEBT,
        goal_id="g-abc123",
        detail="builder produced no artifact",
        title="Builder Produced No Artifact — Write-Scope Failure",
        changed_paths=("runtime/x.py",),
    )
    path = record_friction(record, tmp_path)
    assert path is not None
    assert path.name == "DEBT-0001.md"
    content = path.read_text(encoding="utf-8")
    assert "DEBT-0001" in content
    assert "g-abc123" in content
    assert "builder produced no artifact" in content
    assert "`runtime/x.py`" in content
    assert "OPEN" in content


def test_record_friction_writes_research_file(tmp_path: Path) -> None:
    # Create the research directory with no existing files.
    (tmp_path / "backlog" / "research").mkdir(parents=True)
    (tmp_path / "ledger" / "debt").mkdir(parents=True)
    record = FrictionRecord(
        category=FrictionCategory.RESEARCH,
        goal_id="g-def456",
        detail="adversary blocked the seal",
        title="Adversary Blocked Seal",
        changed_paths=("sakg/probe.py",),
    )
    path = record_friction(record, tmp_path)
    assert path is not None
    assert path.name.startswith("RB-0001-")
    content = path.read_text(encoding="utf-8")
    assert "RB-0001" in content
    assert "g-def456" in content
    assert "adversary blocked the seal" in content
    assert "Research" in content


def test_sequence_numbering_increments(tmp_path: Path) -> None:
    debt_dir = tmp_path / "ledger" / "debt"
    debt_dir.mkdir(parents=True)
    # Pre-populate with existing debt files so the sequence skips them.
    (debt_dir / "DEBT-0001.md").write_text("existing", encoding="utf-8")
    (debt_dir / "DEBT-0002.md").write_text("existing", encoding="utf-8")

    record = FrictionRecord(
        category=FrictionCategory.DEBT,
        goal_id="g-seq",
        detail="court remanded",
        title="Court Remand — Unmet Claims",
        changed_paths=(),
    )
    path = record_friction(record, tmp_path)
    assert path is not None
    assert path.name == "DEBT-0003.md"

    # A second recording should get DEBT-0004.
    path2 = record_friction(record, tmp_path)
    assert path2 is not None
    assert path2.name == "DEBT-0004.md"
