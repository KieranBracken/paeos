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


# ---- B2.I: workspace seeding + headless auto-accept -----------------------


def test_workspace_is_seeded_with_existing_write_scope_files(tmp_path: Path) -> None:
    # a repo-like source with an existing file the objective will edit
    source = tmp_path / "repo"
    (source / "runtime").mkdir(parents=True)
    (source / "runtime" / "feature.py").write_bytes(b"original\n")
    capture: dict[str, bytes] = {}

    def _inspecting_invoker(spec: SessionSpec) -> SessionResult:
        # the session sees the seeded file and can edit it in place
        capture["seeded"] = (spec.workspace / "runtime" / "feature.py").read_bytes()
        (spec.workspace / "runtime" / "feature.py").write_bytes(b"original\n# edited\n")
        return SessionResult(transcript=_TRANSCRIPT)

    out = ClaudeCodeRuntime(invoker=_inspecting_invoker, workspace_source=source).run(
        _package(write_scopes=("runtime/feature.py",))
    )
    assert capture["seeded"] == b"original\n"  # seeded from the source
    assert out.writes[0].content == b"original\n# edited\n"  # the edit is collected


def test_no_source_means_empty_workspace(tmp_path: Path) -> None:
    capture: dict[str, bytes | None] = {}

    def _inspecting_invoker(spec: SessionSpec) -> SessionResult:
        f = spec.workspace / "runtime" / "feature.py"
        capture["present"] = f.read_bytes() if f.exists() else None
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"new\n")
        return SessionResult(transcript=_TRANSCRIPT)

    ClaudeCodeRuntime(invoker=_inspecting_invoker).run(_package())  # no workspace_source
    assert capture["present"] is None  # nothing seeded — a fresh workspace


def test_builder_session_is_granted_bash_to_produce_court_evidence() -> None:
    # DEBT-0019: an autonomous builder must RUN a reproduction command to obtain probative
    # exit_code/stdout for the court. Without Bash on the allow-list, the headless session's
    # command execution is declined ("requires approval") and no evidence is ever submitted.
    captured: dict[str, tuple[str, ...]] = {}

    def _capture(spec: SessionSpec) -> SessionResult:
        captured["allowed"] = spec.allowed_tools
        (spec.workspace / "runtime").mkdir(parents=True, exist_ok=True)
        (spec.workspace / "runtime" / "feature.py").write_bytes(b"code")
        return SessionResult(transcript=_TRANSCRIPT)

    ClaudeCodeRuntime(invoker=_capture).run(_package(write_scopes=("runtime/feature.py",)))
    assert "Bash" in captured["allowed"], captured["allowed"]


def test_live_invoker_passes_accept_edits_permission_mode(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import runtime.integrations as integ

    captured: dict[str, list[str]] = {}

    class _Proc:
        stdout = _TRANSCRIPT

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(integ.subprocess, "run", _fake_run)
    invoker = integ.claude_cli_invoker(_package())
    invoker(SessionSpec(Path("/tmp"), "p", ("Write",), (), 60))
    assert "--permission-mode" in captured["cmd"]
    assert "acceptEdits" in captured["cmd"]


# ---- B2.J: workspace context (constitution + materialized refs) -----------


def test_constitution_is_seeded_into_the_workspace(tmp_path: Path) -> None:
    source = tmp_path / "repo"
    (source / "constitution").mkdir(parents=True)
    (source / "constitution" / "PAEOS-4.md").write_text("K1: durable seals")
    captured: dict[str, bool] = {}

    def _inspect(spec: SessionSpec) -> SessionResult:
        captured["has_law"] = (spec.workspace / "constitution" / "PAEOS-4.md").is_file()
        return SessionResult(_TRANSCRIPT)

    ClaudeCodeRuntime(invoker=_inspect, workspace_source=source).run(_package())
    assert captured["has_law"]  # the session can read/cite the law (B2.J)


def test_context_refs_are_materialized_from_the_resolver(tmp_path: Path) -> None:
    from dataclasses import replace

    from kernel.types import ArtifactRef

    pkg = replace(_package(), context_refs=(ArtifactRef(hash="a" * 64, type="plan"),))
    captured: dict[str, bytes | None] = {}

    def _inspect(spec: SessionSpec) -> SessionResult:
        files = [p for p in (spec.workspace / "context").rglob("*") if p.is_file()]
        captured["content"] = files[0].read_bytes() if files else None
        return SessionResult(_TRANSCRIPT)

    ClaudeCodeRuntime(invoker=_inspect, artifact_resolver=lambda _h: b"the plan").run(pkg)
    assert captured["content"] == b"the plan"  # the injected context is readable in the workspace


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
