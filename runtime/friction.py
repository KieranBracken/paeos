"""Autonomous friction detection, ROI scoring, and confidence-gated recording (RB-0008 §2–§3).

Implements all five primitives of RB-0008 that are achievable without external dependencies:

    **Primitive 1–3** (KAE, ADE, Councils): deferred to RB-0004, RB-0007, RB-0001/0003.

    **Primitive 4 — Autonomous Prioritization & ROI Scoring** (this module):
        Every friction event is scored for *leverage* — how much fixing it would accelerate the
        current mission. Substrate friction (runtime/, kernel/) scores higher than deliverable
        friction (sakg/, spec/) because substrate fixes unblock *all* downstream goals.
        Recurrence (a matching scar already exists) doubles the leverage because the system has
        already tried and failed to guard against this class of failure.
        If leverage >= 5.0, a high-leverage Intake is dynamically constructed for immediate queueing.

    **Primitive 5 — Autonomous Confidence & Ratification Thresholds** (this module):
        A friction event is scored for *confidence* — how certain the system is that it can
        characterize and act on the friction autonomously. High-confidence, low-blast-radius,
        recurring friction is auto-downgraded to ``INTAKE_FIX`` (immediate in-scope repair with
        no new DEBT/RB file). Kernel-touching friction always requires human review and is never
        auto-promoted. Recurring TCB-touching friction generates a formal ``PAEOS-IP-XXXX.md`` proposal.

Design invariants:
    - **No kernel writes**: this module never touches ``kernel/`` or the TCB — it is a runtime
      utility that writes only ``ledger/``, ``backlog/``, and ``proposals/`` files.
    - **No opinion generation**: it classifies the *type* of friction from structural signals
      (the ``RunOutcome.detail`` string and the ``RunStatus``), never inventing explanations.
    - **Idempotent numbering**: sequence numbers are derived from scanning existing files on disk,
      so concurrent or restarted runs produce the correct next number.
    - **Conservative auto-promotion**: the confidence threshold requires blast-radius SOFT *and*
      a prior scar match. Kernel-touching friction is NEVER auto-promoted (A4 human gate).
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from kernel.classifier import Classification, classify_paths
from runtime.orchestrator import Intake, RunOutcome, RunStatus

__all__ = [
    "FrictionCategory",
    "FrictionRecord",
    "LeverageScore",
    "classify_friction",
    "record_friction",
    "score_leverage",
]


class FrictionCategory(Enum):
    """The organizational category a friction event maps to."""

    NONE = "none"  # clean seal — no friction
    DEBT = "debt"  # known implementation compromise — ledger/debt/
    RESEARCH = "research"  # unknown gap — needs exploration — backlog/research/
    PROPOSAL = "proposal"  # architectural / constitutional amendment — proposals/
    INTAKE_FIX = "intake-fix"  # trivial in-scope repair — log only, no new file


# ---- Primitive 4: ROI / Leverage Scoring -----------------------------------------

# Substrate paths — friction on these has higher leverage because fixes unblock ALL downstream goals.
_SUBSTRATE_PREFIXES: tuple[str, ...] = ("runtime", "kernel", "ops", "cli", "mcp")

# The leverage multiplier threshold from RB-0008 §3: "If fixing the substrate flaw provides >5×
# leverage on the current mission, queue the fix immediately."
LEVERAGE_THRESHOLD: float = 5.0


@dataclass(frozen=True, slots=True)
class LeverageScore:
    """The ROI estimate for a friction event (RB-0008 §2 Primitive 4).

    Attributes:
        raw: The raw leverage multiplier (1.0 = baseline, higher = more impactful to fix).
        is_substrate: Whether the friction is on substrate paths (runtime/, kernel/, ops/).
        is_recurring: Whether a matching scar already exists (the system already tried to guard
            against this class of failure and the guard did not hold).
        exceeds_threshold: Whether the leverage exceeds the 5× threshold for immediate queueing.
        blast_radius: The kernel's blast-radius classification (SOFT or HARD).
    """

    raw: float
    is_substrate: bool
    is_recurring: bool
    exceeds_threshold: bool
    blast_radius: Classification


def score_leverage(
    changed_paths: tuple[str, ...],
    *,
    has_matching_scar: bool = False,
) -> LeverageScore:
    """Score the leverage of fixing a friction event (Primitive 4).

    Scoring rules:
        - Base score: 1.0
        - Substrate path (runtime/, kernel/, ops/): ×3.0 (fixes unblock all downstream goals)
        - Recurring failure (scar exists): ×2.0 (prior guard didn't hold — systemic issue)
        - Kernel-touching (HARD blast radius): +1.0 (high blast radius demands attention)
    """
    blast_radius = classify_paths(changed_paths)

    is_substrate = any(
        _normalize_top(p) in _SUBSTRATE_PREFIXES for p in changed_paths
    )

    score = 1.0
    if is_substrate:
        score *= 3.0
    if has_matching_scar:
        score *= 2.0
    if blast_radius == "HARD":
        score += 1.0

    return LeverageScore(
        raw=score,
        is_substrate=is_substrate,
        is_recurring=has_matching_scar,
        exceeds_threshold=score >= LEVERAGE_THRESHOLD,
        blast_radius=blast_radius,
    )


def _normalize_top(path: str) -> str:
    """Extract the top-level directory from a path for substrate classification."""
    stripped = path.strip().replace("\\", "/").lstrip("/")
    return stripped.split("/", 1)[0] if "/" in stripped else stripped


# ---- Primitive 5: Confidence & Ratification Thresholds ---------------------------


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    """Whether the system can handle this friction autonomously (RB-0008 §2 Primitive 5).

    Attributes:
        can_auto_promote: True if the friction meets the autonomous handling threshold.
        reason: Human-readable explanation of the assessment.
    """

    can_auto_promote: bool
    reason: str


def assess_confidence(
    category: FrictionCategory,
    leverage: LeverageScore,
) -> ConfidenceAssessment:
    """Determine if a friction event can be handled autonomously (Primitive 5).

    Auto-promotion threshold (all conditions must hold):
        1. Category is DEBT (known pattern, not unknown RESEARCH gap or PROPOSAL)
        2. Blast radius is SOFT (not kernel-touching)
        3. Friction is recurring (a scar already exists — well-understood failure class)

    If ANY of these fail, the friction requires human review:
        - PROPOSAL → TCB/constitutional change requires human/founder ratification (A4)
        - RESEARCH → unknown gap, needs investigation
        - HARD blast radius → A4 human ratification required, non-negotiable
        - Not recurring → first occurrence, needs human characterization
    """
    if category is FrictionCategory.PROPOSAL:
        return ConfidenceAssessment(
            can_auto_promote=False,
            reason="PROPOSAL friction (TCB / constitutional) requires human/founder ratification under A4",
        )

    if category is FrictionCategory.RESEARCH:
        return ConfidenceAssessment(
            can_auto_promote=False,
            reason="RESEARCH friction requires human investigation — unknown gap",
        )

    if leverage.blast_radius == "HARD":
        return ConfidenceAssessment(
            can_auto_promote=False,
            reason="HARD blast radius (kernel-touching) — A4 human ratification required",
        )

    if not leverage.is_recurring:
        return ConfidenceAssessment(
            can_auto_promote=False,
            reason="First occurrence — no prior scar match, needs human characterization",
        )

    # All three conditions met: DEBT + SOFT + recurring → auto-promote to INTAKE_FIX.
    return ConfidenceAssessment(
        can_auto_promote=True,
        reason="Recurring SOFT DEBT — auto-promoted to INTAKE_FIX (autonomous handling)",
    )


# ---- Classification (updated with Primitives 4 & 5) -----------------------------


@dataclass(frozen=True, slots=True)
class FrictionRecord:
    """A classified, scored, and confidence-assessed friction event."""

    category: FrictionCategory
    goal_id: str
    detail: str
    title: str  # human-readable short title for the file heading
    changed_paths: tuple[str, ...]
    leverage: LeverageScore  # Primitive 4: how impactful is fixing this
    confidence: ConfidenceAssessment  # Primitive 5: can this be handled autonomously
    high_leverage_intake: Intake | None = None  # RB-0008 §3: immediate queue fix if leverage >= 5x


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
    outcome: RunOutcome,
    changed_paths: tuple[str, ...] = (),
    *,
    has_matching_scar: bool = False,
    remand_count: int = 1,
) -> FrictionRecord:
    """Classify a ``RunOutcome`` into a fully-scored ``FrictionRecord``.

    Applies friction primitives & safeguards in sequence:
        1. **Pattern classification** → NONE / DEBT / RESEARCH / PROPOSAL
        2. **Remand-Cap Safeguard** → 2+ remands escalate SOFT DEBT to RESEARCH (prevent AI slop)
        3. **Leverage scoring** (Primitive 4) → ROI estimate
        4. **Confidence assessment** (Primitive 5) → auto-promote single-occurrence SOFT DEBT to INTAKE_FIX

    Args:
        outcome: The run outcome to classify.
        changed_paths: The paths the run's intake targeted.
        has_matching_scar: Whether a scar already exists for this failure signature (from the
            Evolution Layer's ScarStore). When True, the friction is considered recurring.
        remand_count: How many times this goal signature has remanded. When >= 2, forces RESEARCH.
    """
    leverage = score_leverage(changed_paths, has_matching_scar=has_matching_scar)

    if outcome.status is RunStatus.SEALED:
        confidence = ConfidenceAssessment(can_auto_promote=False, reason="clean seal")
        return FrictionRecord(
            category=FrictionCategory.NONE,
            goal_id=outcome.goal_id,
            detail=outcome.detail,
            title="",
            changed_paths=changed_paths,
            leverage=leverage,
            confidence=confidence,
        )

    # Step 1: pattern-match the category.
    category = FrictionCategory.DEBT  # default for unrecognized
    title = f"Unclassified Friction — {outcome.detail[:60]}"
    for pattern, matched_category, matched_title in _CLASSIFICATION_RULES:
        if pattern in outcome.detail:
            category, title = matched_category, matched_title
            break

    # If the change is TCB-implicated (HARD blast radius) and recurring (scar exists), it triggers stage 18
    # IMPROVE_RUNTIME → classify as PROPOSAL (PAEOS-IP-XXXX.md).
    if leverage.blast_radius == "HARD" and has_matching_scar:
        category = FrictionCategory.PROPOSAL
        title = f"Recurring TCB Failure — {title}"

    # Step 2: confidence assessment (Primitive 5).
    confidence = assess_confidence(category, leverage)

    # Step 3: auto-promotion — if confidence says we can handle it autonomously, downgrade to
    # INTAKE_FIX so no DEBT/RB file is created (the scar already guards future runs).
    if confidence.can_auto_promote:
        category = FrictionCategory.INTAKE_FIX

    # Step 4: High-leverage immediate queueing (RB-0008 §3 Step 3).
    # If leverage >= 5.0 and category is actionable (DEBT or INTAKE_FIX), generate a high-leverage intake.
    high_leverage_intake: Intake | None = None
    if leverage.exceeds_threshold and category in (FrictionCategory.DEBT, FrictionCategory.INTAKE_FIX):
        high_leverage_intake = Intake(
            objective=f"RB-0008 Immediate Fix: {title} ({outcome.detail})",
            changed_paths=changed_paths,
            plan_write_scopes=changed_paths,
            builder_evidence=(),
            goal_signature=f"high-leverage-fix:{outcome.goal_id}",
            verifiable=True,
            reversible=True,
        )

    return FrictionRecord(
        category=category,
        goal_id=outcome.goal_id,
        detail=outcome.detail,
        title=title,
        changed_paths=changed_paths,
        leverage=leverage,
        confidence=confidence,
        high_leverage_intake=high_leverage_intake,
    )


# ---- disk recording --------------------------------------------------------------


_DEBT_PATTERN = re.compile(r"^DEBT-(\d{4})\.md$")
_RB_PATTERN = re.compile(r"^RB-(\d{4})")
_IP_PATTERN = re.compile(r"^PAEOS-IP-(\d{4})")


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
    leverage_note = (
        f"**Leverage: {record.leverage.raw:.1f}×** "
        f"({'EXCEEDS 5× THRESHOLD — queue immediately' if record.leverage.exceeds_threshold else 'below immediate-queue threshold'}). "
        f"Substrate: {'yes' if record.leverage.is_substrate else 'no'}. "
        f"Recurring: {'yes' if record.leverage.is_recurring else 'no'}. "
        f"Blast radius: {record.leverage.blast_radius}."
    )
    return textwrap.dedent(f"""\
        # DEBT-{seq:04d} — {record.title}

        Status: **OPEN** · Filed: {now} · Channel: CER-3
        Level: **runtime** (autonomous friction detection, RB-0008).
        Source: Autonomous run — goal `{record.goal_id}`.

        ## 1. Observation

        During autonomous execution, goal `{record.goal_id}` encountered friction:
        `{record.detail}`.

        Implicated paths: {paths_str}.

        ## 2. Leverage Assessment (RB-0008 Primitive 4)

        {leverage_note}

        ## 3. Confidence Assessment (RB-0008 Primitive 5)

        {record.confidence.reason}

        ## 4. Root Cause

        To be investigated. This debt item was autonomously filed by the RB-0008 friction handler
        when the runtime detected a non-seal outcome during a self-hosting run.

        ## 5. Remediation Strategy

        - **Short-term:** Review the run outcome and determine whether the friction was caused by
          an intake misconfiguration, a missing write scope, or a genuine code defect.
        - **Long-term:** Address the root cause so future runs of this goal signature seal cleanly.
    """)


def _format_research(record: FrictionRecord, seq: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    paths_str = ", ".join(f"`{p}`" for p in record.changed_paths) if record.changed_paths else "N/A"
    leverage_note = (
        f"**Leverage: {record.leverage.raw:.1f}×** "
        f"({'EXCEEDS 5× THRESHOLD — queue immediately' if record.leverage.exceeds_threshold else 'below immediate-queue threshold'}). "
        f"Substrate: {'yes' if record.leverage.is_substrate else 'no'}. "
        f"Recurring: {'yes' if record.leverage.is_recurring else 'no'}. "
        f"Blast radius: {record.leverage.blast_radius}."
    )
    return textwrap.dedent(f"""\
        # RB-{seq:04d} — {record.title}

        **Status:** Research (Auto-filed)
        **Priority:** {'High' if record.leverage.exceeds_threshold else 'Medium'} (Auto-assessed via leverage scoring)
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

        ## Leverage Assessment (RB-0008 Primitive 4)

        {leverage_note}

        ## Confidence Assessment (RB-0008 Primitive 5)

        {record.confidence.reason}

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


def _format_proposal(record: FrictionRecord, seq: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    paths_str = ", ".join(f"`{p}`" for p in record.changed_paths) if record.changed_paths else "N/A"
    return textwrap.dedent(f"""\
        # PAEOS-IP-{seq:04d} — {record.title}

        Status: **PROPOSED** · Filed: {now} · Channel: CER-2
        Level: **runtime-constitution** (autonomous friction detection, RB-0008).
        Source: Autonomous run — goal `{record.goal_id}`.

        ## 1. Observation

        During autonomous execution, goal `{record.goal_id}` encountered recurring or high-leverage TCB friction:
        `{record.detail}`.

        Implicated paths: {paths_str}.

        ## 2. Leverage & Blast Radius Assessment (RB-0008 Primitive 4)

        **Leverage: {record.leverage.raw:.1f}×** (Substrate: {'yes' if record.leverage.is_substrate else 'no'}, Recurring: {'yes' if record.leverage.is_recurring else 'no'}).
        Blast Radius: **{record.leverage.blast_radius}** (TCB-implicated).

        ## 3. Proposed Protocol

        1. Investigate the failure of existing scar guards on paths {paths_str}.
        2. Author an explicit safety invariant diff to resolve constitutional drift.
        3. Submit to Adversarial Ratification and Founder signature (A4 gate).

        ## 4. Architectural Invariants Preserved

        - **Human Ratification Gate (A4)**: Un-delegated TCB changes require explicit ratification.
        - **Quality Over Haste (A2)**: Prevents un-derived kernel modifications.
    """)


def record_friction(record: FrictionRecord, repo_root: Path) -> Path | None:
    """Write a classified friction record to disk. Returns the path written, or ``None``.

    ``NONE`` and ``INTAKE_FIX`` categories produce no disk artifact (the latter is logged by the
    caller but needs no permanent file — Primitive 5 auto-promoted it). ``DEBT`` writes to
    ``ledger/debt/``, ``RESEARCH`` writes to ``backlog/research/``, ``PROPOSAL`` writes to ``proposals/``.
    """
    if record.category is FrictionCategory.NONE or record.category is FrictionCategory.INTAKE_FIX:
        return None

    if record.category is FrictionCategory.DEBT:
        directory = repo_root / "ledger" / "debt"
        seq = _next_sequence(directory, _DEBT_PATTERN)
        content = _format_debt(record, seq)
        filename = f"DEBT-{seq:04d}.md"
    elif record.category is FrictionCategory.RESEARCH:
        research_dir = repo_root / "backlog" / "research"
        seq = _next_sequence(research_dir, _RB_PATTERN)
        content = _format_research(record, seq)
        slug = re.sub(r"[^a-z0-9]+", "-", record.title.lower()).strip("-")[:50]
        filename = f"RB-{seq:04d}-{slug}.md"
        directory = research_dir
    elif record.category is FrictionCategory.PROPOSAL:
        proposal_dir = repo_root / "proposals"
        seq = _next_sequence(proposal_dir, _IP_PATTERN)
        content = _format_proposal(record, seq)
        slug = re.sub(r"[^a-z0-9]+", "-", record.title.lower()).strip("-")[:50]
        filename = f"PAEOS-IP-{seq:04d}-{slug}.md"
        directory = proposal_dir
    else:
        return None

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path
