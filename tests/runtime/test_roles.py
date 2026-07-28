"""B1.C acceptance tests for Planner/Builder role specs (PAEOS-8 §10 / 7 §5.2).

An intake produces design → plan → branch-impl, each a bound artifact in CAS. The Planner cannot
write production code (scope is design/ or plan/); IMPLEMENT requires plan-supplied scopes.
"""

from __future__ import annotations

import pytest
from kernel.capability import CapabilityBroker
from kernel.cas import CAS, InMemoryCasStore
from kernel.types import Role, StageId
from nacl.signing import SigningKey
from runtime.agents import NoRoleForStage, StagePlaybook, role_spec
from runtime.claude_code import AgentDispatcher, AgentWrite, RunOutput, ScopeViolation
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus


class _MockRuntime:
    def __init__(self, path: str, content: bytes = b"artifact") -> None:
        self.writes = (AgentWrite(path, content),)
        self.received: TaskPackage | None = None

    def run(self, package: TaskPackage) -> RunOutput:
        self.received = package
        return RunOutput(TaskStatus.COMPLETE, self.writes, (), b"trace", Cost(0, 0.0, "m"))


def _playbook(runtime: _MockRuntime) -> tuple[StagePlaybook, CAS]:
    cas = CAS(InMemoryCasStore())
    broker = CapabilityBroker(SigningKey.generate())
    return StagePlaybook(AgentDispatcher(broker, cas, runtime, clock=lambda: 0)), cas


_BUDGET = Budget(400000, 1800, 2)


# ---- role specs -----------------------------------------------------------


def test_role_specs_cover_the_three_stages() -> None:
    assert role_spec(StageId.DESIGN).role is Role.PLANNER
    assert role_spec(StageId.PLAN).role is Role.PLANNER
    assert role_spec(StageId.IMPLEMENT).role is Role.BUILDER
    with pytest.raises(NoRoleForStage):
        role_spec(StageId.SEAL)


# ---- intake → design → plan → impl, each a bound artifact -----------------


def test_design_produces_bound_artifact_and_scoped_package() -> None:
    runtime = _MockRuntime("design/design.md")
    playbook, cas = _playbook(runtime)
    result = playbook.run_stage(
        goal_id="g", run_id="r", stage=StageId.DESIGN, session="planner", budget=_BUDGET
    )
    assert len(result.artifacts) == 1
    assert cas.get(result.artifacts[0].hash) == b"artifact"  # design bound in CAS
    package = runtime.received
    assert package is not None
    assert package.role is Role.PLANNER
    assert package.permissions.write_scopes == ("design/",)
    assert set(package.capability.operations) == {
        "mcp:constitution", "mcp:memory:read", "mcp:artifacts",
    }
    assert package.required_evidence[0].claim_id == "design_coherent"


def test_plan_produces_bound_artifact() -> None:
    runtime = _MockRuntime("plan/plan.md")
    playbook, cas = _playbook(runtime)
    result = playbook.run_stage(
        goal_id="g", run_id="r", stage=StageId.PLAN, session="planner", budget=_BUDGET
    )
    assert cas.get(result.artifacts[0].hash) == b"artifact"


def test_implement_produces_bound_artifact_with_plan_scopes() -> None:
    runtime = _MockRuntime("kernel/validator.py", b"def validate(): ...")
    playbook, cas = _playbook(runtime)
    result = playbook.run_stage(
        goal_id="g", run_id="r", stage=StageId.IMPLEMENT, session="builder", budget=_BUDGET,
        write_scopes=("kernel/validator.py",),  # from the ratified plan
    )
    assert cas.get(result.artifacts[0].hash) == b"def validate(): ..."
    package = runtime.received
    assert package is not None
    assert package.role is Role.BUILDER
    assert {ob.claim_id for ob in package.required_evidence} == {"builds", "unit"}


# ---- role prohibitions ----------------------------------------------------


def test_planner_cannot_write_production_code() -> None:
    # a design session that tries to write kernel/ is outside its design/ scope → refused
    runtime = _MockRuntime("kernel/evil.py")
    playbook, _ = _playbook(runtime)
    with pytest.raises(ScopeViolation):
        playbook.run_stage(
            goal_id="g", run_id="r", stage=StageId.DESIGN, session="planner", budget=_BUDGET
        )


def test_implement_requires_plan_supplied_scopes() -> None:
    runtime = _MockRuntime("kernel/x.py")
    playbook, _ = _playbook(runtime)
    with pytest.raises(NoRoleForStage):
        playbook.run_stage(
            goal_id="g", run_id="r", stage=StageId.IMPLEMENT, session="builder", budget=_BUDGET
        )  # no write_scopes from a plan
