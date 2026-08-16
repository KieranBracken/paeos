"""Planner / Builder role specs + skills for stages DESIGN, PLAN, IMPLEMENT (PAEOS-8 §10 B1.C).

Roles are **capability profiles, not personalities** (7 §5): each stage's scoped `TaskPackage` is
derived from a `RoleSpec` — objective, write/read scopes, MCP allow-list, required evidence, and the
skills the stage may invoke (§9). Grounded in the §5.2 role catalog:

  * **Planner** (DESIGN stage 7, PLAN stage 9): reads constitution / memory (scars) / artifacts;
    writes design & plan artifacts. **Cannot write production code** — its write scope is `design/`
    or `plan/`, never `kernel/`/`runtime/` (enforced by the dispatcher's `write_scopes`, B1.B).
  * **Builder** (IMPLEMENT stage 10): writes on an isolated branch (scopes come from the ratified
    plan), runs local tests; reads plan + design + matched scars. Its required evidence is a BUILD
    and a TEST the court will reproduce (B1.E). It holds no seal/merge/ledger authority.

Note: "stages 7/9/10" (PAEOS-8 §10) are the PAEOS-7 §4.1 canonical constants `DESIGN`/`PLAN`/
`IMPLEMENT` — not the operational L-numbers. `StagePlaybook.run_stage` dispatches the right role.
"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.evidence import EvidenceKind
from kernel.types import ArtifactRef, Role, StageId

from runtime.claude_code import AgentDispatcher
from runtime.task_package import Budget, EvidenceObligation, SkillRef, TaskResult

__all__ = ["ROLE_SPECS", "NoRoleForStage", "RoleSpec", "StagePlaybook", "role_spec"]


class NoRoleForStage(Exception):
    """No Planner/Builder role is defined for the stage (B1.C covers DESIGN/PLAN/IMPLEMENT)."""


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


_DESIGN = RoleSpec(
    stage=StageId.DESIGN,
    role=Role.PLANNER,
    objective="Produce the system design (component graph, interfaces, data flow, state machines).",
    write_scopes=("design/",),  # Planner writes design artifacts only — never production code
    read_scopes=("constitution/", "spec/", "design/"),
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

_PLAN = RoleSpec(
    stage=StageId.PLAN,
    role=Role.PLANNER,
    objective="Produce the formal implementation plan: work units, evidence plan, rollback plan.",
    write_scopes=("plan/",),
    read_scopes=("constitution/", "design/", "plan/"),
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
    read_scopes=("constitution/", "design/", "plan/"),
    mcp_servers=("constitution", "artifacts", "memory:read"),
    required_evidence=(
        EvidenceObligation(claim_id="builds", kind=EvidenceKind.BUILD, acceptance="exit 0"),
        EvidenceObligation(
            claim_id="unit", kind=EvidenceKind.TEST, acceptance="tests green, reproducible"
        ),
    ),
    skills=(SkillRef("testing", "2.1"),),
)

ROLE_SPECS: dict[StageId, RoleSpec] = {
    StageId.DESIGN: _DESIGN,
    StageId.PLAN: _PLAN,
    StageId.IMPLEMENT: _IMPLEMENT,
}


def role_spec(stage: StageId) -> RoleSpec:
    """The RoleSpec for a stage. Raises NoRoleForStage outside DESIGN/PLAN/IMPLEMENT."""
    try:
        return ROLE_SPECS[stage]
    except KeyError:
        raise NoRoleForStage(f"no Planner/Builder role defined for stage {stage.name}") from None


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
