"""B1.B acceptance tests for the agent dispatcher (PAEOS-8 §10 / 7.6 §5).

A dispatched Builder session writes only its write_scopes; result artifacts land in CAS; the trace
is persisted. Adversary T9: a session that writes outside scope (incl. via traversal) is refused.
"""

from __future__ import annotations

import pytest
from kernel.capability import CapabilityBroker
from kernel.cas import CAS, InMemoryCasStore
from kernel.types import Role, StageId
from nacl.signing import SigningKey
from runtime.claude_code import (
    AgentDispatcher,
    AgentWrite,
    RunOutput,
    ScopeViolation,
    within_scopes,
)
from runtime.task_package import Budget, Cost, TaskPackage, TaskResult, TaskStatus


class MockRuntime:
    """A stand-in for a real scoped Claude Code session (the DEBT-0002 spawn seam)."""

    def __init__(
        self,
        writes: tuple[AgentWrite, ...],
        *,
        status: TaskStatus = TaskStatus.COMPLETE,
        trace: bytes = b"transcript",
    ) -> None:
        self.writes = writes
        self.status = status
        self.trace = trace
        self.received: TaskPackage | None = None

    def run(self, package: TaskPackage) -> RunOutput:
        self.received = package
        return RunOutput(
            status=self.status,
            writes=self.writes,
            evidence=("ev" + "0" * 62,),
            trace=self.trace,
            cost=Cost(tokens=1000, wallclock_s=1.2, model_ver="sonnet-x"),
        )


def _dispatcher(runtime: MockRuntime) -> tuple[AgentDispatcher, CAS]:
    cas = CAS(InMemoryCasStore())
    broker = CapabilityBroker(SigningKey.generate())
    return AgentDispatcher(broker, cas, runtime, clock=lambda: 0), cas


def _dispatch(dispatcher: AgentDispatcher, **over: object) -> TaskResult:
    kwargs: dict[str, object] = {
        "goal_id": "g", "run_id": "r", "stage": StageId.IMPLEMENT, "role": Role.BUILDER,
        "session": "builder-1", "objective": "implement the validator",
        "write_scopes": ("kernel/validator.py",), "mcp_servers": ("artifacts", "constitution"),
        "budget": Budget(400000, 1800, 2),
    }
    kwargs.update(over)
    return dispatcher.dispatch(**kwargs)  # type: ignore[arg-type]


# ---- happy path -----------------------------------------------------------


def test_in_scope_write_lands_in_cas_and_trace_persisted() -> None:
    runtime = MockRuntime((AgentWrite("kernel/validator.py", b"def validate(): ..."),))
    dispatcher, cas = _dispatcher(runtime)
    result = _dispatch(dispatcher)
    assert result.status is TaskStatus.COMPLETE
    assert len(result.artifacts) == 1
    assert cas.get(result.artifacts[0].hash) == b"def validate(): ..."  # artifact in CAS
    assert cas.get(result.trace_ref) == b"transcript"  # trace persisted
    assert result.cost.model_ver == "sonnet-x"


def test_package_is_scoped_and_capability_minted() -> None:
    runtime = MockRuntime((AgentWrite("kernel/validator.py", b"x"),))
    dispatcher, _ = _dispatcher(runtime)
    _dispatch(dispatcher)
    package = runtime.received
    assert package is not None
    assert package.permissions.write_scopes == ("kernel/validator.py",)
    assert package.role is Role.BUILDER
    # the capability grants exactly the requested MCP servers, nothing else
    assert set(package.capability.operations) == {"mcp:artifacts", "mcp:constitution"}
    assert package.capability.bound_to.session == "builder-1"


# ---- Adversary T9: out-of-scope writes refused ----------------------------


def test_write_outside_scope_is_refused() -> None:
    runtime = MockRuntime((AgentWrite("constitution/PAEOS-0.md", b"evil"),))
    dispatcher, cas = _dispatcher(runtime)
    with pytest.raises(ScopeViolation):
        _dispatch(dispatcher, write_scopes=("kernel/",))
    assert list(cas._store.iter_keys()) == []  # nothing landed


def test_traversal_out_of_scope_is_refused() -> None:
    runtime = MockRuntime((AgentWrite("kernel/../constitution/x.md", b"evil"),))
    dispatcher, _ = _dispatcher(runtime)
    with pytest.raises(ScopeViolation):
        _dispatch(dispatcher, write_scopes=("kernel/",))


def test_partial_scope_escape_refused_atomically() -> None:
    # one in-scope + one out-of-scope write ⇒ the whole dispatch refuses (no partial artifacts)
    runtime = MockRuntime(
        (AgentWrite("kernel/a.py", b"ok"), AgentWrite("runtime/b.py", b"escape"))
    )
    dispatcher, _ = _dispatcher(runtime)
    with pytest.raises(ScopeViolation):
        _dispatch(dispatcher, write_scopes=("kernel/",))


# ---- within_scopes unit ---------------------------------------------------


def test_within_scopes() -> None:
    assert within_scopes("kernel/validator.py", ("kernel/validator.py",)) is True
    assert within_scopes("kernel/x.py", ("kernel/",)) is True  # dir scope
    assert within_scopes("runtime/x.py", ("kernel/",)) is False
    assert within_scopes("kernel/../constitution/x", ("kernel/",)) is False  # traversal
    assert within_scopes("../etc/passwd", ("kernel/",)) is False
    assert within_scopes("kernelish/x.py", ("kernel/",)) is False  # not the kernel dir
