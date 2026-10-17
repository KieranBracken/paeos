"""Unit tests for Codex, Glm, and HybridRuntime multi-provider stage routing."""

from __future__ import annotations

from unittest.mock import MagicMock

from kernel.capability import CapabilityBroker
from kernel.types import Role, StageId
from runtime.claude_code import RunOutput, TaskStatus
from runtime.integrations.hybrid import HybridRuntime
from runtime.planner_transport import PlannerTransportNotReady
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

    assert mock_codex.run.call_count == 5
    assert mock_glm.run.call_count == 2


def test_qualified_planner_critique_uses_luna_transport() -> None:
    """A qualified planner CRITIQUE must not fall back to the legacy Cline adapter."""

    mock_codex = MagicMock()
    mock_glm = MagicMock()
    mock_codex.run.return_value = RunOutput(
        status=TaskStatus.COMPLETE, writes=(), evidence=(), trace=b"luna", cost=None
    )
    mock_glm.run.return_value = RunOutput(
        status=TaskStatus.COMPLETE, writes=(), evidence=(), trace=b"glm", cost=None
    )
    readiness = MagicMock()
    readiness.require.return_value = object()

    router = HybridRuntime(
        codex_runtime=mock_codex,
        glm_runtime=mock_glm,
        planner_transport=object(),
        planner_readiness=readiness,
    )

    result = router.run(_make_package(StageId.CRITIQUE))

    assert result.trace == b"luna"
    readiness.require.assert_called_once_with("CRITIQUE")
    mock_codex.run.assert_called_once()
    mock_glm.run.assert_not_called()


def test_unready_planner_critique_fails_closed_without_glm_fallback() -> None:
    mock_codex = MagicMock()
    mock_glm = MagicMock()
    readiness = MagicMock()
    readiness.require.side_effect = PlannerTransportNotReady("CRITIQUE is not qualified")
    router = HybridRuntime(
        codex_runtime=mock_codex,
        glm_runtime=mock_glm,
        planner_transport=object(),
        planner_readiness=readiness,
    )

    try:
        router.run(_make_package(StageId.CRITIQUE))
    except PlannerTransportNotReady:
        pass
    else:
        raise AssertionError("unready planner CRITIQUE did not fail closed")

    readiness.require.assert_called_once_with("CRITIQUE")
    mock_codex.run.assert_not_called()
    mock_glm.run.assert_not_called()
