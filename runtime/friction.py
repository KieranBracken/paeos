"""Autonomous friction detection and recording (RB-0008 §3, Phase 4).

When a PAEOS worker agent encounters friction during autonomous execution — a remand, a budget
breach, an adversary block — this module **classifies** the friction and **records** it as a durable
organizational artifact (``ledger/debt/DEBT-XXXX.md`` or ``backlog/research/RB-XXXX.md``). This is
the first rung of the RB-0008 Autonomous Self-Improvement Loop: *observe execution → detect
weakness → record as actionable item*.

The module sits between the Evolution Layer (which writes L3 scars, the soft-loop memory) and the
organizational filing layer (which emits DEBT and RB items that humans and future autonomous
prioritizers consume). Scars help the **next run**; friction records help the **project**.

Design invariants:
    - **No kernel writes**: this module never touches ``kernel/`` or the TCB — it is a runtime
      utility that writes only ``ledger/`` and ``backlog/`` files.
    - **No opinion generation**: it classifies the *type* of friction from structural signals
      (the ``RunOutcome.detail`` string and the ``RunStatus``), never inventing explanations.
    - **Idempotent numbering**: sequence numbers are derived from scanning existing files on disk,
      so concurrent or restarted runs produce the correct next number.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from runtime.orchestrator import RunOutcome, RunStatus

__all__ = ["FrictionCategory", "FrictionRecord", "classify_friction", "record_friction"]


class FrictionCategory(Enum):
    """The organizational category a friction event maps to."""

    NONE = "none"  # clean seal — no friction
    DEBT = "debt"  # known implementation compromise — ledger/debt/
    RESEARCH = "research"  # unknown gap — needs exploration — backlog/research/
    INTAKE_FIX = "intake-fix"  # trivial in-scope repair — log only, no new file


@dataclass(frozen=True, slots=True)
class FrictionRecord:
    """A classified friction event ready for disk recording."""

    category: FrictionCategory
    goal_id: str
    detail: str
    title: str  # human-readable short title for the file heading
    changed_paths: tuple[str, ...]


# ---- classification rules --------------------------------------------------------


# Each rule is (substring to match in RunOutcome.detail, category, title template).
# Order matters: first match wins. More specific patterns come first.
_CLASSIFICATION_RULES: tuple[tuple[str, FrictionCategory, str], ...] = (
    ("builder produced no artifact", FrictionCategory.DEBT,
     "Builder Produced No Artifact — Write-Scope or Agent Failure"),
    ("no evidence submitted", FrictionCategory.DEBT,
     "No Evidence Submitted to Court MCP"),
    ("non-probative (vacuous) evidence", FrictionCategory.DEBT,
     "Non-Probative Evidence — Test Does Not Exercise Change"),
    ("court remanded", FrictionCategory.DEBT,
     "Court Remand — Unmet Evidence Claims"),
    ("adversary blocked the seal", FrictionCategory.RESEARCH,
     "Adversary Blocked Seal — Design Disagreement Requires Investigation"),
    ("budget breach", FrictionCategory.RESEARCH,
     "Budget Breach — Possible Budget Model Miscalibration"),
)


def classify_friction(
    outcome: RunOutcome, changed_paths: tuple[str, ...] = ()
) -> FrictionRecord:
    """Classify a ``RunOutcome`` into a ``FrictionRecord``.

    A ``SEALED`` outcome produces ``FrictionCategory.NONE``. A ``REMANDED`` or ``HALTED`` outcome
    is pattern-matched against known failure signatures to determine whether the friction is a
    ``DEBT`` (known fix, deferred) or ``RESEARCH`` (unknown, needs investigation).
    """
    if outcome.status is RunStatus.SEALED:
        return FrictionRecord(
            category=FrictionCategory.NONE,
            goal_id=outcome.goal_id,
            detail=outcome.detail,
            title="",
            changed_paths=changed_paths,
        )

    for pattern, category, title in _CLASSIFICATION_RULES:
        if pattern in outcome.detail:
            return FrictionRecord(
                category=category,
                goal_id=outcome.goal_id,
                detail=outcome.detail,
                title=title,
                changed_paths=changed_paths,
            )

    # Unrecognized failure detail — conservative: record as debt (known problem, unclear fix).
    return FrictionRecord(
        category=FrictionCategory.DEBT,
        goal_id=outcome.goal_id,
        detail=outcome.detail,
        title=f"Unclassified Friction — {outcome.detail[:60]}",
        changed_paths=changed_paths,
    )


# ---- disk recording --------------------------------------------------------------


_DEBT_PATTERN = re.compile(r"^DEBT-(\d{4})\.md$")
_RB_PATTERN = re.compile(r"^RB-(\d{4})")


def _next_sequence(directory: Path, pattern: re.Pattern[str]) -> int:
    """Scan ``directory`` for files matching ``pattern`` and return the next available number."""
    highest = 0
    if directory.is_dir():
        for child in directory.iterdir():
            m = pattern.match(child.name)
            if m:
                highest = max(highest, int(m.group(1)))
    return highest + 1


def _format_debt(record: FrictionRecord, seq: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    paths_str = ", ".join(f"`{p}`" for p in record.changed_paths) if record.changed_paths else "N/A"
    return textwrap.dedent(f"""\
        # DEBT-{seq:04d} — {record.title}

        Status: **OPEN** · Filed: {now} · Channel: CER-3
        Level: **runtime** (autonomous friction detection, RB-0008).
        Source: Autonomous run — goal `{record.goal_id}`.

        ## 1. Observation

        During autonomous execution, goal `{record.goal_id}` encountered friction:
        `{record.detail}`.

        Implicated paths: {paths_str}.

        ## 2. Root Cause

        To be investigated. This debt item was autonomously filed by the RB-0008 friction handler
        when the runtime detected a non-seal outcome during a self-hosting run.

        ## 3. Remediation Strategy

        - **Short-term:** Review the run outcome and determine whether the friction was caused by
          an intake misconfiguration, a missing write scope, or a genuine code defect.
        - **Long-term:** Address the root cause so future runs of this goal signature seal cleanly.
    """)


def _format_research(record: FrictionRecord, seq: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    paths_str = ", ".join(f"`{p}`" for p in record.changed_paths) if record.changed_paths else "N/A"
    return textwrap.dedent(f"""\
        # RB-{seq:04d} — {record.title}

        **Status:** Research (Auto-filed)
        **Priority:** Medium (Auto-assessed)
        **Type:** Research Backlog
        **Filed:** {now}
        **Source:** Autonomous run — goal `{record.goal_id}`
        **Dependencies:** RB-0008 (Autonomous Technical Leadership)

        ---

        ## Summary

        During autonomous execution, goal `{record.goal_id}` encountered friction that could not
        be classified as a simple implementation debt:
        `{record.detail}`.

        Implicated paths: {paths_str}.

        ## Motivation

        This friction pattern suggests a gap in the PAEOS runtime or methodology that requires
        research investigation rather than a direct code fix. The friction handler classified this
        as a research item because the failure mode (adversary block or budget breach) indicates a
        potential architectural or calibration issue.

        ## Questions to Investigate

        1. What is the root cause of this friction pattern?
        2. Is this a recurring pattern across multiple goals?
        3. Does this indicate a need for a new runtime capability or a recalibration of existing
           parameters?
    """)


def record_friction(record: FrictionRecord, repo_root: Path) -> Path | None:
    """Write a classified friction record to disk. Returns the path written, or ``None``.

    ``NONE`` and ``INTAKE_FIX`` categories produce no disk artifact (the latter is logged by the
    caller but needs no permanent file). ``DEBT`` writes to ``ledger/debt/``, ``RESEARCH`` writes
    to ``backlog/research/``.
    """
    if record.category is FrictionCategory.NONE or record.category is FrictionCategory.INTAKE_FIX:
        return None

    if record.category is FrictionCategory.DEBT:
        directory = repo_root / "ledger" / "debt"
        seq = _next_sequence(directory, _DEBT_PATTERN)
        content = _format_debt(record, seq)
        filename = f"DEBT-{seq:04d}.md"
    elif record.category is FrictionCategory.RESEARCH:
        directory = repo_root / "ledger" / "debt"  # scan debt for max, but write to research
        debt_seq = _next_sequence(directory, _DEBT_PATTERN)  # noqa: F841 — unused but reserved
        research_dir = repo_root / "backlog" / "research"
        seq = _next_sequence(research_dir, _RB_PATTERN)
        content = _format_research(record, seq)
        # RB files use a slug derived from the title
        slug = re.sub(r"[^a-z0-9]+", "-", record.title.lower()).strip("-")[:50]
        filename = f"RB-{seq:04d}-{slug}.md"
        directory = research_dir
    else:
        return None

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path
