"""Unit tests for Codex, Glm, and HybridRuntime multi-provider stage routing."""

from __future__ import annotations

from unittest.mock import MagicMock

from kernel.capability import CapabilityBroker
from kernel.types import Role, StageId
from runtime.claude_code import RunOutput, TaskStatus
from runtime.integrations.hybrid import HybridRuntime
from runtime.task_package import Budget, Permissions, TaskPackage


def _make_package(stage: StageId) -> TaskPackage:
    broker = CapabilityBroker()
    cap = broker.mint(
        goal_id="g-test",
        run_id="r-5678",
        stage=stage,
        role=Role.PLANNER,
        session="s-1",
        operations=("read", "write"),
        issued_seq=1,
        expires_seq=10,
    )
    return TaskPackage(
        task_id="t-1234",
        goal_id="g-test",
        run_id="r-5678",
        stage=stage,
        role=Role.PLANNER,
        objective="Test objective",
        capability=cap,
        permissions=Permissions(read_scopes=("/",), write_scopes=("/tmp",), mcp_servers=()),
        required_evidence=(),
        context_refs=(),
        budget=Budget(tokens=1000, wallclock_s=60, retries=1),
    )


def test_hybrid_runtime_routing() -> None:
    mock_codex = MagicMock()
    mock_glm = MagicMock()

    mock_codex.run.return_value = RunOutput(
        status=TaskStatus.COMPLETE, writes=(), evidence=(), trace=b"codex", cost=None
    )
    mock_glm.run.return_value = RunOutput(
        status=TaskStatus.COMPLETE, writes=(), evidence=(), trace=b"glm", cost=None
    )

    router = HybridRuntime(codex_runtime=mock_codex, glm_runtime=mock_glm)

    # 1. Main construction stages -> Codex
    for stage in (StageId.RE_DERIVE, StageId.IDEATE, StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT):
        pkg = _make_package(stage)
        res = router.run(pkg)
        assert res.trace == b"codex"

    # 2. Heterogeneous Audit stages -> GLM
    for stage in (StageId.CRITIQUE, StageId.ADVERSARIAL_REVIEW):
        pkg = _make_package(stage)
        res = router.run(pkg)
        assert res.trace == b"glm"
