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
from kernel.cas import CAS, CasMiss, InMemoryCasStore
from kernel.evidence import EvidenceKind
from kernel.types import ArtifactRef, Role, StageId
from nacl.signing import SigningKey
from runtime.claude_code import AgentDispatcher
from runtime.integrations import ClaudeCodeRuntime, SessionResult, SessionSpec, build_prompt
from runtime.integrations.process_supervisor import ProcessLifecycleState, ProcessObservation
from runtime.review import InformationBarrierManager, ReviewHarness
from runtime.task_package import (
    Budget,
    EvidenceObligation,
    Permissions,
    TaskPackage,
    TaskStatus,
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


def test_adversary_prompt_names_physical_bundle_boundary() -> None:
    from dataclasses import replace

    prompt = build_prompt(
        replace(
            _package(),
            stage=StageId.ADVERSARIAL_REVIEW,
            role=Role.ADVERSARY,
            permissions=Permissions(
                ("review/adversary_report.md",), ("context/",), ("constitution",)
            ),
            context_refs=(ArtifactRef(hash="a" * 64, type="candidate"),),
        )
    )
    assert "physically materialized only under `context/`" in prompt
    assert "builder/planner source paths" in prompt
    assert "Research Backlog" not in prompt


# ---- run: writes collected + scope-filtered -------------------------------


def test_run_collects_only_in_scope_writes() -> None:
    invoker = _fake_invoker({"runtime/feature.py": b"code", "notes.txt": b"scratch"})
    out = ClaudeCodeRuntime(invoker=invoker).run(_package(write_scopes=("runtime/feature.py",)))
    assert [w.path for w in out.writes] == ["runtime/feature.py"]  # notes.txt dropped
    assert out.writes[0].content == b"code"


def test_run_excludes_pycache_bytecode_byproducts() -> None:
    # DEBT-0022: a `builds` command like `python -m py_compile lib/greet.py` emits a `.pyc` under
    # __pycache__. Even in-scope, the compiled bytecode must NOT be collected — otherwise it can
    # become the reviewed artifact and the adversary must materialise sourceless, version-coupled
    # bytecode. The reviewed artifact must be the deterministic Python SOURCE the goal authored.
    invoker = _fake_invoker(
        {
            "lib/greet.py": b"def greet():\n    return 'hi'\n",
            "lib/__pycache__/greet.cpython-313.pyc": b"\x00compiled-bytecode",
            "lib/greet.pyo": b"\x00optimised-bytecode",
        }
    )
    out = ClaudeCodeRuntime(invoker=invoker).run(_package(write_scopes=("lib/",)))
    assert [w.path for w in out.writes] == ["lib/greet.py"]  # only source; .pyc/.pyo dropped
    assert out.writes[0].content.startswith(b"def greet()")


def test_is_build_byproduct_matches_bytecode_only() -> None:
    from runtime.integrations import _is_build_byproduct

    assert _is_build_byproduct("lib/__pycache__/greet.cpython-313.pyc")
    assert _is_build_byproduct("lib/greet.pyc")
    assert _is_build_byproduct("greet.pyo")
    assert not _is_build_byproduct("lib/greet.py")  # source is not a by-product
    assert not _is_build_byproduct("pycache_notes.py")  # not under a __pycache__ dir


def test_run_parses_cost_from_transcript() -> None:
    out = ClaudeCodeRuntime(invoker=_fake_invoker({"runtime/feature.py": b"x"})).run(_package())
    assert out.cost.tokens == 1500  # 1000 + 500
    assert out.cost.wallclock_s == 2.5
    assert out.cost.model_ver == "claude-sonnet-x"
    assert out.trace  # the transcript is persisted


def test_failed_trusted_worker_returns_failed_without_collecting_writes() -> None:
    def failed_invoker(spec: SessionSpec) -> SessionResult:
        (spec.workspace / "runtime/feature.py").parent.mkdir(parents=True, exist_ok=True)
        (spec.workspace / "runtime/feature.py").write_text("must-not-become-an-artifact\n")
        return SessionResult(
            transcript="provider output is not a governed failure observation",
            lifecycle_state="FAILED",
            exit_code=17,
            failure_code="provider_execution_failure",
        )

    out = ClaudeCodeRuntime(invoker=failed_invoker).run(_package())

    assert out.status is TaskStatus.FAILED
    assert out.writes == ()
    assert out.trace == b"trusted_worker_failure:provider_execution_failure"
    assert b"provider output" not in out.trace


def test_l12_provider_failure_is_classified_before_capture() -> None:
    """The .08 boundary must distinguish provider failure from capture/materialization failure."""

    captured: dict[str, Path] = {}

    def failed_provider(spec: SessionSpec) -> SessionResult:
        captured["workspace"] = spec.workspace
        target = spec.workspace / "runtime" / "feature.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"partial-provider-write\n")
        return SessionResult(
            transcript="provider execution failed",
            lifecycle_state="FAILED",
            exit_code=1,
            failure_code="provider_execution_failure",
        )

    out = ClaudeCodeRuntime(invoker=failed_provider).run(_package())

    assert out.status is TaskStatus.FAILED
    assert out.failure_code == "provider_execution_failure"
    assert out.writes == ()
    assert out.trace == b"trusted_worker_failure:provider_execution_failure"
    assert not captured["workspace"].exists()


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


def _planner_package() -> TaskPackage:
    broker = CapabilityBroker(SigningKey.generate())
    token = broker.mint(
        goal_id="g", run_id="r", stage=StageId.DESIGN, role=Role.PLANNER, session="s",
        operations=("mcp:artifacts",), issued_seq=0, expires_seq=100,
    )
    return TaskPackage(
        task_id="t-1", goal_id="g", run_id="r", stage=StageId.DESIGN, role=Role.PLANNER,
        objective="produce the design", capability=token,
        permissions=Permissions(("design/",), ("constitution/",), ("artifacts",)),
        required_evidence=(), context_refs=(), budget=Budget(100000, 60, 1),
    )


def test_builder_allow_list_contains_bash() -> None:
    # DEBT-0021: the BUILDER (and only the builder) gets Bash to run its reproduction command.
    from runtime.integrations import _allowed_tools

    assert "Bash" in _allowed_tools(_package())


def test_planner_allow_list_omits_bash_least_privilege() -> None:
    # DEBT-0021 / FP-7: a PLANNER produces design/plan artifacts and never runs code, so it must
    # NOT receive command-execution authority. Least privilege — Bash is builder-only.
    from runtime.integrations import _allowed_tools

    allowed = _allowed_tools(_planner_package())
    assert "Bash" not in allowed, allowed
    assert {"Read", "Write", "Edit"} <= set(allowed)  # still gets the scoped non-exec tools


def test_live_invoker_passes_dangerously_skip_permissions(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    import runtime.integrations as integ

    captured: dict[str, list[str]] = {}

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        return ProcessObservation(
            argv=tuple(cmd),
            executable="/usr/local/bin/claude",
            executable_version="sha256:test",
            cwd=str(kwargs["cwd"]),
            environment_fingerprint="e" * 64,
            stdout=_TRANSCRIPT.encode(),
            stderr=b"",
            exit_code=0,
            duration_ms=1,
            lifecycle_state=ProcessLifecycleState.RETURNED,
        )

    monkeypatch.setattr(integ, "run_bounded_process", _fake_run)
    invoker = integ.claude_cli_invoker(_package())
    invoker(SessionSpec(tmp_path, "p", ("Write",), (), 60))
    assert "--dangerously-skip-permissions" in captured["cmd"]


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


def test_adversary_bundle_is_physically_reviewable_in_scoped_context(tmp_path: Path) -> None:
    """Reproduce the .07 failure at the real adapter boundary.

    The review bundle must be materialized under a deterministic, explicitly named directory.
    The worker must not depend on a content hash being interpreted as a filesystem path, and no
    source/planner overlay may be present in this isolated review workspace.
    """
    candidate = b"candidate bytes"
    evidence = b"physical evidence bytes"
    cas = CAS(InMemoryCasStore())
    candidate_hash = cas.put(candidate)
    evidence_hash = cas.put(evidence)
    ibm = InformationBarrierManager()
    bundle = ibm.seal(
        artifact_refs=(ArtifactRef(hash=candidate_hash, type="candidate"),),
        evidence_refs=(evidence_hash,),
    )
    observed: dict[str, object] = {}

    def _inspect(spec: SessionSpec) -> SessionResult:
        observed["read_scopes"] = spec.read_scopes
        observed["prompt"] = spec.prompt
        observed["context_files"] = tuple(
            sorted(
                str(path.relative_to(spec.workspace))
                for path in (spec.workspace / "context").rglob("*")
                if path.is_file()
            )
        )
        observed["forbidden_paths"] = tuple(
            name for name in ("design", "plan", "review") if (spec.workspace / name).exists()
        )
        report = spec.workspace / "review" / "adversary_report.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("VERDICT: PASS\n")
        return SessionResult(_TRANSCRIPT)

    runtime = ClaudeCodeRuntime(invoker=_inspect, artifact_resolver=cas.get)
    dispatcher = AgentDispatcher(
        CapabilityBroker(SigningKey.generate()), cas, runtime, clock=lambda: 0
    )
    result = ReviewHarness(ibm, dispatcher).review(
        goal_id="g",
        run_id="r",
        session="adversary",
        bundle=bundle,
        budget=Budget(100000, 60, 1),
    )

    assert result.status is TaskStatus.COMPLETE
    assert observed["read_scopes"] == ("context/",)
    assert "context/" in observed["prompt"]  # type: ignore[operator]
    assert observed["context_files"] == (
        f"context/candidate-{candidate_hash[:12]}.txt",
        f"context/evidence-{evidence_hash[:12]}.txt",
    )
    assert observed["forbidden_paths"] == ()


def test_adversary_missing_bundle_blob_fails_closed_before_worker_launch() -> None:
    """A sealed adversary chamber cannot silently review an empty/missing bundle."""
    invoked = False

    def _unexpected_worker(_spec: SessionSpec) -> SessionResult:
        nonlocal invoked
        invoked = True
        return SessionResult(_TRANSCRIPT)

    def _missing(_hash: str) -> bytes:
        raise CasMiss("missing")

    runtime = ClaudeCodeRuntime(invoker=_unexpected_worker, artifact_resolver=_missing)
    pkg = _package()
    from dataclasses import replace

    adversary = replace(
        pkg,
        stage=StageId.ADVERSARIAL_REVIEW,
        role=Role.ADVERSARY,
        permissions=Permissions(
            ("review/adversary_report.md",), ("context/",), ("constitution",)
        ),
        context_refs=(ArtifactRef(hash="f" * 64, type="evidence"),),
    )

    out = runtime.run(adversary)

    assert out.status is TaskStatus.FAILED
    assert out.failure_code == "sealed_bundle_context_missing"
    assert out.writes == ()
    assert not invoked


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
