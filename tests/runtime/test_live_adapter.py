"""Phase-2 tests for the live agent adapter (PAEOS-8 §12 R3→R4).

Exercises the adapter's real logic — compiled prompt, isolated workspace, write collection +
write_scopes filtering, cost parsing, cleanup — against a FAKE session. The live `claude` CLI call
(auth + target env) is out of scope for unit tests (behind the `CliInvoker` seam).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from kernel.capability import CapabilityBroker
from kernel.cas import CAS, InMemoryCasStore
from kernel.evidence import EvidenceKind
from kernel.types import Role, StageId
from nacl.signing import SigningKey
from runtime.claude_code import AgentDispatcher
from runtime.integrations import ClaudeCodeRuntime, SessionResult, SessionSpec, build_prompt
from runtime.task_package import (
    Budget,
    EvidenceObligation,
    Permissions,
    TaskPackage,
)

_TRANSCRIPT = json.dumps(
    {"result": "done", "usage": {"input_tokens": 1000, "output_tokens": 500},
     "duration_ms": 2500, "model": "claude-sonnet-x"}
)


def _package(*, write_scopes: tuple[str, ...] = ("runtime/feature.py",)) -> TaskPackage:
    broker = CapabilityBroker(SigningKey.generate())
    token = broker.mint(
        goal_id="g", run_id="r", stage=StageId.IMPLEMENT, role=Role.BUILDER, session="s",
        operations=("mcp:artifacts",), issued_seq=0, expires_seq=100,
    )
    return TaskPackage(
        task_id="t-1", goal_id="g", run_id="r", stage=StageId.IMPLEMENT, role=Role.BUILDER,
        objective="implement feature()", capability=token,
        permissions=Permissions(write_scopes, ("runtime/",), ("artifacts",)),
        required_evidence=(EvidenceObligation("builds", EvidenceKind.BUILD, "exit 0"),),
        context_refs=(), budget=Budget(100000, 60, 1),
    )


def _fake_invoker(
    files: dict[str, bytes],
    transcript: str = _TRANSCRIPT,
    *,
    capture: dict[str, Path] | None = None,
) -> Callable[[SessionSpec], SessionResult]:
    def _invoke(spec: SessionSpec) -> SessionResult:
        if capture is not None:
            capture["workspace"] = spec.workspace
        for rel, content in files.items():
            target = spec.workspace / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return SessionResult(transcript=transcript)

    return _invoke


# ---- compiled prompt ------------------------------------------------------


def test_prompt_is_compiled_from_the_package() -> None:
    prompt = build_prompt(_package(write_scopes=("runtime/feature.py",)))
    assert "implement feature()" in prompt  # objective
    assert "runtime/feature.py" in prompt  # write scope
    assert "builds (BUILD): exit 0" in prompt  # required evidence
    assert "BUILDER at stage IMPLEMENT" in prompt


# ---- run: writes collected + scope-filtered -------------------------------


def test_run_collects_only_in_scope_writes() -> None:
    invoker = _fake_invoker({"runtime/feature.py": b"code", "notes.txt": b"scratch"})
    out = ClaudeCodeRuntime(invoker=invoker).run(_package(write_scopes=("runtime/feature.py",)))
    assert [w.path for w in out.writes] == ["runtime/feature.py"]  # notes.txt dropped
    assert out.writes[0].content == b"code"


def test_run_parses_cost_from_transcript() -> None:
    out = ClaudeCodeRuntime(invoker=_fake_invoker({"runtime/feature.py": b"x"})).run(_package())
    assert out.cost.tokens == 1500  # 1000 + 500
    assert out.cost.wallclock_s == 2.5
    assert out.cost.model_ver == "claude-sonnet-x"
    assert out.trace  # the transcript is persisted


def test_unparseable_transcript_yields_zero_cost_not_fabricated() -> None:
    invoker = _fake_invoker({"runtime/feature.py": b"x"}, transcript="not json")
    out = ClaudeCodeRuntime(invoker=invoker).run(_package())
    assert out.cost.tokens == 0


def test_workspace_is_cleaned_up() -> None:
    capture: dict[str, Path] = {}
    invoker = _fake_invoker({"runtime/feature.py": b"x"}, capture=capture)
    ClaudeCodeRuntime(invoker=invoker).run(_package())
    assert not capture["workspace"].exists()  # isolated workspace removed after the run


# ---- plugs into the dispatcher (it IS an AgentRuntime) --------------------


def test_adapter_plugs_into_the_dispatcher() -> None:
    cas = CAS(InMemoryCasStore())
    broker = CapabilityBroker(SigningKey.generate())
    runtime = ClaudeCodeRuntime(invoker=_fake_invoker({"runtime/feature.py": b"live-code"}))
    dispatcher = AgentDispatcher(broker, cas, runtime, clock=lambda: 0)
    result = dispatcher.dispatch(
        goal_id="g", run_id="r", stage=StageId.IMPLEMENT, role=Role.BUILDER, session="s",
        objective="implement", write_scopes=("runtime/feature.py",), mcp_servers=("artifacts",),
        budget=Budget(100000, 60, 1),
    )
    assert cas.get(result.artifacts[0].hash) == b"live-code"  # live-adapter output landed in CAS
