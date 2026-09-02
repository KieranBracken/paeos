"""Architecture Discovery Engine (RB-0007).

Executes the multi-role exploration of architectural gaps when PAEOS exhausts its current
objectives or encounters high-leverage friction (RB-0008).

Unlike a naive LLM fallback, ADE uses Epistemic Sandboxing (RB-0009):
1. RESEARCH: Independent generation of candidate architectures or solutions.
2. CRITIQUE: Adversarial evaluation of those candidates.
3. TRADEOFF: Synthesis of the debate into an optimal Intake payload.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path

from kernel.types import StageId
from nacl.signing import SigningKey

from runtime.agents import StagePlaybook
from runtime.claude_code import AgentDispatcher
from runtime.orchestrator import CapabilityBroker
from runtime.selfhost import Intake, _parse_intake
from runtime.task_package import Budget

logger = logging.getLogger(__name__)


def _build_canonical_audit_context(repo_root: Path) -> str:
    """Surface the 19-layer canonical audit artifacts to the RESEARCH agent.

    The reviews/paeos-gaps/ directory contains the forensic architectural audit of the
    canonical 19-layer execution doctrine vs. the current SoftLoop implementation. These
    documents are the architectural ground truth for determining the correct next objective:

    - 01_CANONICAL_INVENTORY.md: The 19 canonical layers and their purposes
    - 02_IMPLEMENTATION_MATRIX.md: Which layers are IMPLEMENTED, PARTIAL, or MISSING
    - 05_DEPENDENCY_DAG.md: The strict dataflow dependency order for missing layers
    - 06_COMPLETENESS_CRITERIA.md: Definition of Done for any lifecycle layer
    - 07_CONSTRUCTION_SEQUENCE.md: The safe implementation sequence
    - 08_FINDINGS_REGISTER.md: Architectural findings including RCL integration status
    - 09_RECOMMENDED_TARGET.md: Canonical next-target recommendation

    These are read at call time so ADE always operates against the current audit state.
    """
    audit_dir = repo_root / "reviews" / "paeos-gaps"
    if not audit_dir.is_dir():
        return ""
    # Surface the key audit documents that establish the canonical construction order
    audit_files = [
        "01_CANONICAL_INVENTORY.md",
        "02_IMPLEMENTATION_MATRIX.md",
        "05_DEPENDENCY_DAG.md",
        "06_COMPLETENESS_CRITERIA.md",
        "07_CONSTRUCTION_SEQUENCE.md",
        "08_FINDINGS_REGISTER.md",
        "09_RECOMMENDED_TARGET.md",
    ]
    existing = [f for f in audit_files if (audit_dir / f).exists()]
    if not existing:
        return ""
    names = "\n".join(f"  - reviews/paeos-gaps/{f}" for f in existing)
    return (
        "\n\nCRITICAL: The following canonical 19-layer audit artifacts document the forensic "
        "analysis of the current implementation against the canonical architecture. You MUST "
        "read these before proposing candidates — they contain the authoritative implementation "
        "matrix (which layers are IMPLEMENTED vs MISSING), the dependency DAG (the strict "
        "dataflow order for missing layers), and the canonical construction sequence:\n" + names
    )


def _build_research_context(repo_root: Path) -> str:
    """Dynamically surface pending research backlog items to the RESEARCH agent.

    Reads RB-*.md files from backlog/research/. These represent pre-designed specifications
    that have not yet been implemented. The prompt context is built at call time so that
    once an item is implemented and removed from the backlog, it stops appearing in prompts.
    Returns an empty string if there are no pending items.
    """
    rb_dir = repo_root / "backlog" / "research"
    if not rb_dir.is_dir():
        return ""
    items = sorted(rb_dir.glob("RB-*.md"))
    if not items:
        return ""
    names = "\n".join(f"  - {p.name}" for p in items)
    return (
        "\n\nThe research backlog contains pre-designed specifications for unimplemented capabilities. "
        "These represent prior architectural thinking that should inform your proposals — read the "
        "most relevant ones and weigh them honestly against alternatives:\n" + names
    )


def run_ade(
    repo_root: Path,
    agent_runtime,
    cas,
) -> Intake | None:
    """Run the multi-stage Architecture Discovery Engine to synthesize the next objective."""
    broker = CapabilityBroker(SigningKey.generate())
    # For now we use lambda: 0 for clock since we just need the dispatcher
    dispatcher = AgentDispatcher(broker, cas, agent_runtime, clock=lambda: 0)
    playbook = StagePlaybook(dispatcher)

    run_id = "r-" + uuid.uuid4().hex[:8]
    ade_budget = Budget(1_000_000, 3600, 1)

    # Dynamically surface any pending research backlog items so the RESEARCH agent
    # is aware of pre-designed specs — without permanently hardcoding any specific item.
    # Items are read from disk at call time, so completed/removed specs naturally disappear.
    research_context = _build_research_context(repo_root)

    # Surface the canonical 19-layer audit artifacts — the architectural ground truth
    # that establishes which layers are IMPLEMENTED/MISSING, the dependency DAG, and
    # the canonical construction sequence. ADE must reason from these, not speculation.
    canonical_audit_context = _build_canonical_audit_context(repo_root)

    print("ADE: Commencing Architectural Research...")
    # 1. RESEARCH stage: generate candidates
    research_result = playbook.run_stage(
        goal_id="g-ade",
        run_id=run_id,
        stage=StageId.RESEARCH,
        session="ade_research",
        detail=(
            "Analyze the canonical PAEOS architecture (spec/PAEOS-9-execution-architecture.md), "
            "the current implementation state, and the debt ledger (ledger/debt/) to determine what "
            "canonical layer should be built next.\n\n"
            "IMPORTANT: Do NOT propose cross-cutting capabilities, new layers, or research backlog "
            "items unless they are the first missing layer in the canonical 19-layer dependency chain. "
            "The canonical architecture is fixed at 19 layers. Your task is to identify which MISSING "
            "canonical layer should be instantiated next in the SoftLoop, based strictly on the "
            "dependency DAG and implementation matrix.\n\n"
            "Evaluate candidates against the following self-hosting criteria:\n"
            "1. What does PAEOS need to become genuinely self-hosting?\n"
            "2. Which missing canonical layers are direct prerequisites for that?\n"
            "3. Where does each candidate sit in the 19-layer dependency graph?\n"
            "4. What happens if a candidate is deferred?\n"
            "5. What becomes easier/harder if it is built first?\n"
            "6. Is the candidate itself dependent on missing PAEOS layers?\n"
            "7. Can it be implemented cleanly now without creating architectural shortcuts?\n\n"
            "Propose 3 distinct, plausible architectural candidates, providing clear rationale for each."
            + canonical_audit_context
            + research_context
        ),
        budget=ade_budget,
    )
    if research_result.status.value != "COMPLETE":
        print("ADE: Research failed.")
        return None

    # Pace to avoid 429 free tier limits
    print("ADE: Pacing API requests (20s delay)...")
    time.sleep(20)

    print("ADE: Commencing Architectural Critique...")
    # 2. CRITIQUE stage: evaluate candidates
    critique_result = playbook.run_stage(
        goal_id="g-ade",
        run_id=run_id,
        stage=StageId.CRITIQUE,
        session="ade_critique",
        detail=(
            "Adversarially critique the proposed architectural candidates from the research stage. "
            "For each candidate, evaluate whether it creates architectural shortcuts, hidden coupling, "
            "or premature abstractions. Specifically answer whether the proposed candidate is genuinely "
            "a prerequisite for autonomous self-construction or if another layer must precede it."
        ),
        budget=ade_budget,
        # In a full implementation, we inject the research artifacts into the context_refs
        context_refs=research_result.artifacts,
    )
    if critique_result.status.value != "COMPLETE":
        print("ADE: Critique failed.")
        return None

    # Pace to avoid 429 free tier limits
    print("ADE: Pacing API requests (20s delay)...")
    time.sleep(20)

    print("ADE: Synthesizing Trade-offs and Minting Intake...")
    # 3. TRADEOFF stage: select winner and mint intake
    tradeoff_result = playbook.run_stage(
        goal_id="g-ade",
        run_id=run_id,
        stage=StageId.TRADEOFF,
        session="ade_tradeoff",
        detail=(
            "Review the proposed architectural candidates and the adversarial critique. Select the "
            "highest-leverage, dependency-sound approach that advances PAEOS toward canonical 19-layer "
            "self-hosting. Write a valid Intake JSON object for this approach to ops/backlogs/ade_intake.json. "
            "If the architecture is verifiably complete, output {}."
        ),
        budget=ade_budget,
        context_refs=research_result.artifacts + critique_result.artifacts,
    )
    if tradeoff_result.status.value != "COMPLETE":
        print("ADE: Tradeoff failed.")
        return None

    # Apply TRADEOFF writes to the repo root using CAS
    for path_str, h in tradeoff_result.written_paths:
        path = repo_root / path_str
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(cas.get(h))

    target = repo_root / "ops" / "backlogs" / "ade_intake.json"
    if target.exists():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if not raw:
                return None
            if isinstance(raw, list):
                if not raw:
                    return None
                raw = raw[0]
            return _parse_intake(raw)
        except Exception as e:
            logger.exception("ADE: Failed to parse ade_intake.json: %s", e)
    else:
        print("ADE: Target ade_intake.json does not exist. Printing TRADEOFF trace:")
        print(cas.get(tradeoff_result.trace_ref).decode("utf-8"))
    return None
