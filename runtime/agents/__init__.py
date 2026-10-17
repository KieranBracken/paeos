"""Planner / Builder / Reviewer / Adversary role specs + skills for canonical stages (PAEOS-8 §10 B1.C).

Roles are **capability profiles, not personalities** (7 §5): each stage's scoped `TaskPackage` is
derived from a `RoleSpec` — objective, write/read scopes, MCP allow-list, required evidence, and the
skills the stage may invoke (§9). Grounded in the §5.2 role catalog:

  * **Planner** (RE_DERIVE, IDEATE, RESEARCH, TRADEOFF, MITIGATION, DESIGN, PLAN, RETROSPECT, MEMORY_UPDATE):
    reads constitution / memory (scars) / artifacts; writes stage artifacts. Cannot write production code.
  * **Builder** (IMPLEMENT stage 10 / L12): writes on an isolated branch (scopes come from the ratified
    plan), runs local tests; reads plan + design + matched scars.
  * **Critic / Reviewer** (CRITIQUE stage / L09): evaluates candidate designs across canonical stances.
  * **Adversary** (ADVERSARIAL_REVIEW stage / L10 & L14): attempts to refute design / code under information barrier.
  * **Ratifier** (EVOLVE stage / L19): updates constitutional evolution when triggered.
"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.evidence import EvidenceKind
from kernel.types import ArtifactRef, Role, StageId

from runtime.claude_code import AgentDispatcher
from runtime.task_package import Budget, EvidenceObligation, SkillRef, TaskResult

__all__ = ["ROLE_SPECS", "NoRoleForStage", "RoleSpec", "StagePlaybook", "role_spec"]


class NoRoleForStage(Exception):
    """No role is defined for the requested stage."""


@dataclass(frozen=True, slots=True)
class RoleSpec:
    """A stage's capability profile — the template for its scoped `TaskPackage`."""

    stage: StageId
    role: Role
    objective: str
    write_scopes: tuple[str, ...]
    read_scopes: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    required_evidence: tuple[EvidenceObligation, ...]
    skills: tuple[SkillRef, ...]


_RE_DERIVE = RoleSpec(
    stage=StageId.RE_DERIVE,
    role=Role.PLANNER,
    objective="Derive the problem from first principles (What must be true?) without assumptions.",
    write_scopes=("derive/",),
    read_scopes=("constitution/", "spec/"),
    mcp_servers=("constitution", "memory:read", "artifacts"),
    required_evidence=(),
    skills=(SkillRef("first-principles", "1.0"),),
)

_IDEATE = RoleSpec(
    stage=StageId.IDEATE,
    role=Role.PLANNER,
    objective="Generate candidate architectures and idealized solutions across the solution space.",
    write_scopes=("ideate/",),
    read_scopes=("constitution/", "derive/", "spec/"),
    mcp_servers=("constitution", "memory:read", "artifacts"),
    required_evidence=(),
    skills=(SkillRef("architecture", "1.0"),),
)

_RESEARCH = RoleSpec(
    stage=StageId.RESEARCH,
    role=Role.PLANNER,
    objective="Establish state of the art, frontier research, prior art, and novelty assessments.",
    write_scopes=("research/",),
    read_scopes=("constitution/", "derive/", "ideate/", "spec/"),
    mcp_servers=("constitution", "memory:read", "artifacts"),
    required_evidence=(),
    skills=(SkillRef("research", "1.0"),),
)

_TRADEOFF = RoleSpec(
    stage=StageId.TRADEOFF,
    role=Role.PLANNER,
    objective="Identify trade-offs (latency, accuracy, memory, risk, maintainability, complexity) across approaches.",
    write_scopes=("tradeoff/",),
    read_scopes=("constitution/", "ideate/", "research/", "spec/"),
    mcp_servers=("constitution", "memory:read", "artifacts"),
    required_evidence=(),
    skills=(SkillRef("tradeoff-analysis", "1.0"),),
)

_MITIGATION = RoleSpec(
    stage=StageId.MITIGATION,
    role=Role.PLANNER,
    objective="Mitigate hazards identified in L06 Trade-off Analysis by binding safeguards and accepted risks.",
    write_scopes=("mitigation/",),
    read_scopes=("constitution/", "design/", "tradeoff/", "backlog/"),
    mcp_servers=("constitution", "artifacts", "memory:read"),
    required_evidence=(
        EvidenceObligation(
            claim_id="mitigations",
            kind=EvidenceKind.PROOF,
            acceptance="catalogue binding safeguards to hazards emitted",
        ),
    ),
    skills=(SkillRef("planning", "1.0"),),
)

_DESIGN = RoleSpec(
    stage=StageId.DESIGN,
    role=Role.PLANNER,
    objective="Produce the system design (component graph, interfaces, data flow, state machines).",
    write_scopes=("design/",),
    read_scopes=(
        "constitution/",
        "spec/",
        "derive/",
        "ideate/",
        "tradeoff/",
        "mitigation/",
        "design/",
    ),
    mcp_servers=("constitution", "memory:read", "artifacts"),
    required_evidence=(
        EvidenceObligation(
            claim_id="design_coherent",
            kind=EvidenceKind.CITATION,
            acceptance="assumptions surfaced (PAEOS-6), perspectives covered, no orphan/gap",
        ),
    ),
    skills=(SkillRef("architecture", "1.0"), SkillRef("hidden-assumptions", "1.0")),
)

_CRITIQUE = RoleSpec(
    stage=StageId.CRITIQUE,
    role=Role.CRITIC,
    objective="Evaluate candidate designs across canonical stances (Security, Performance, Simplicity, Maintainability, Testability, Backward Compatibility, Constitutional Alignment, Functionality).",
    write_scopes=("critique/",),
    read_scopes=("constitution/", "design/", "plan/"),
    mcp_servers=("constitution", "artifacts", "memory:read"),
    required_evidence=(),
    skills=(SkillRef("planning", "1.0"),),
)

_ADVERSARIAL_REVIEW = RoleSpec(
    stage=StageId.ADVERSARIAL_REVIEW,
    role=Role.ADVERSARY,
    objective="Perform independent adversarial review over the design/implementation artifact bundle.",
    write_scopes=("review/",),
    read_scopes=("constitution/", "design/", "plan/", "review/"),
    mcp_servers=("constitution", "artifacts", "court", "memory:read"),
    required_evidence=(),
    skills=(SkillRef("red-team", "1.0"),),
)

_PLAN = RoleSpec(
    stage=StageId.PLAN,
    role=Role.PLANNER,
    objective="Produce the formal implementation plan: work units, evidence plan, rollback plan.",
    write_scopes=("plan/",),
    read_scopes=("constitution/", "design/", "critique/", "review/", "plan/"),
    mcp_servers=("constitution", "memory:read", "artifacts"),
    required_evidence=(
        EvidenceObligation(
            claim_id="plan_executable",
            kind=EvidenceKind.CITATION,
            acceptance="work units + evidence obligations + rollback declared; refs cited",
        ),
    ),
    skills=(SkillRef("planning", "1.0"),),
)

_IMPLEMENT = RoleSpec(
    stage=StageId.IMPLEMENT,
    role=Role.BUILDER,
    objective="Implement per the ratified plan on an isolated branch; run local tests.",
    write_scopes=(),  # provided per-plan at dispatch (the exact files the plan authorizes)
    # The Builder's verifier must see the exact non-sensitive package closure used by the
    # production runtime.  Quarantined credential/Sentium paths are filtered at seeding time.
    read_scopes=(
        "constitution/",
        "design/",
        "plan/",
        "kernel/",
        "runtime/",
        "paeos/",
        "ops/",
        "tests/",
        "pyproject.toml",
        "uv.lock",
    ),
    mcp_servers=("constitution", "artifacts", "court", "memory:read"),
    required_evidence=(
        EvidenceObligation(
            claim_id="builds", kind=EvidenceKind.TEST, acceptance="exit 0, probative test"
        ),
        EvidenceObligation(
            claim_id="unit", kind=EvidenceKind.TEST, acceptance="probative unit test green"
        ),
    ),
    skills=(SkillRef("testing", "2.1"),),
)

_RETROSPECTIVE_AUDITOR = RoleSpec(
    stage=StageId.RETROSPECT,
    role=Role.DOC,
    objective="Perform the six-question CER retrospective and record attributable operational lessons.",
    write_scopes=("retrospective/",),
    read_scopes=("constitution/", "design/", "plan/", "review/", "retrospective/"),
    mcp_servers=("constitution", "memory:read", "artifacts"),
    required_evidence=(),
    skills=(SkillRef("retrospective", "1.0"),),
)

_MEMORY_UPDATE = RoleSpec(
    stage=StageId.MEMORY_UPDATE,
    role=Role.PLANNER,
    objective="Propose and commit institutional scars to the shared L3 ScarStore.",
    write_scopes=("memory/",),
    read_scopes=("constitution/", "retrospect/", "review/"),
    mcp_servers=("constitution", "memory:write", "artifacts"),
    required_evidence=(),
    skills=(SkillRef("scar-learning", "1.0"),),
)

_EVOLVE = RoleSpec(
    stage=StageId.EVOLVE,
    role=Role.RATIFIER,
    objective="Update constitutional doctrine and invariant definitions if triggered by high-leverage friction.",
    write_scopes=("constitution/",),
    read_scopes=("constitution/", "memory/", "retrospect/"),
    mcp_servers=("constitution", "memory:read", "artifacts"),
    required_evidence=(),
    skills=(SkillRef("constitutional-evolution", "1.0"),),
)

ROLE_SPECS: dict[StageId, RoleSpec] = {
    StageId.RE_DERIVE: _RE_DERIVE,
    StageId.IDEATE: _IDEATE,
    StageId.RESEARCH: _RESEARCH,
    StageId.TRADEOFF: _TRADEOFF,
    StageId.MITIGATION: _MITIGATION,
    StageId.DESIGN: _DESIGN,
    StageId.CRITIQUE: _CRITIQUE,
    StageId.ADVERSARIAL_REVIEW: _ADVERSARIAL_REVIEW,
    StageId.PLAN: _PLAN,
    StageId.IMPLEMENT: _IMPLEMENT,
    StageId.RETROSPECT: _RETROSPECTIVE_AUDITOR,
    StageId.MEMORY_UPDATE: _MEMORY_UPDATE,
    StageId.EVOLVE: _EVOLVE,
}


def role_spec(stage: StageId) -> RoleSpec:
    """The RoleSpec for a stage. Raises NoRoleForStage outside recognized stages."""
    try:
        return ROLE_SPECS[stage]
    except KeyError:
        raise NoRoleForStage(f"no role defined for stage {stage.name}") from None


class StagePlaybook:
    """Dispatches the correct scoped role for a stage, via the B1.B dispatcher."""

    def __init__(self, dispatcher: AgentDispatcher) -> None:
        self._dispatcher = dispatcher

    def run_stage(
        self,
        *,
        goal_id: str,
        run_id: str,
        stage: StageId,
        session: str,
        budget: Budget,
        detail: str = "",
        context_refs: tuple[ArtifactRef, ...] = (),
        scars: tuple[ArtifactRef, ...] = (),
        write_scopes: tuple[str, ...] | None = None,
    ) -> TaskResult:
        """Dispatch `stage`'s role. For IMPLEMENT, `write_scopes` (from the plan) is required."""
        spec = role_spec(stage)
        scopes = write_scopes if write_scopes is not None else spec.write_scopes
        if spec.role is Role.BUILDER and not scopes:
            raise NoRoleForStage("IMPLEMENT requires write_scopes from the ratified plan")
        objective = f"{spec.objective} {detail}".strip()
        return self._dispatcher.dispatch(
            goal_id=goal_id,
            run_id=run_id,
            stage=spec.stage,
            role=spec.role,
            session=session,
            objective=objective,
            write_scopes=scopes,
            read_scopes=spec.read_scopes,
            mcp_servers=spec.mcp_servers,
            required_evidence=spec.required_evidence,
            context_refs=context_refs,
            scars=scars,
            budget=budget,
        )
