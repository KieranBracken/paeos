"""TDD coverage for the Founder-authorized P1 execution-substrate repair."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import runtime.integrations.process_supervisor as process_supervisor
from kernel.cas import content_hash
from kernel.sandbox import (
    SandboxError,
    allowlisted_path,
    canonical_command,
    run_sandboxed,
    structured_sandbox_runner,
)
from kernel.types import Claim
from runtime.court import Court, VerdictOutcome
from runtime.integrations import (
    SessionResult,
    SessionSpec,
    _collect_writes,
    _seed_workspace,
    hybrid,
)
from runtime.integrations.process_supervisor import (
    ProcessLifecycleState,
    ProcessObservation,
    run_bounded_process,
)
from runtime.transports.mcp.court_server import build_court_mcp_server


def test_hung_provider_times_out_and_persists_terminal_failure(tmp_path: Path) -> None:
    state_path = tmp_path / "lifecycle.json"
    observation = run_bounded_process(
        (sys.executable, "-c", "import time; time.sleep(2)"),
        cwd=tmp_path,
        environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        start_timeout_s=0.2,
        execution_timeout_s=0.2,
        state_path=state_path,
    )

    assert observation.lifecycle_state is ProcessLifecycleState.TIMED_OUT
    record = json.loads(state_path.read_text(encoding="utf-8"))
    assert record["terminal_state"] == "TIMED_OUT"
    assert record["pid"] is not None


def test_launch_ack_deadline_is_bounded_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def stalled_launch(*_args: object, **_kwargs: object) -> object:
        import time

        time.sleep(0.2)
        raise OSError("synthetic launch stall")

    monkeypatch.setattr(process_supervisor.subprocess, "Popen", stalled_launch)
    observation = run_bounded_process(
        (sys.executable, "-c", "raise SystemExit(0)"),
        cwd=tmp_path,
        environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        start_timeout_s=0.02,
        execution_timeout_s=1.0,
        state_path=tmp_path / "launch-timeout.json",
    )
    assert observation.lifecycle_state is ProcessLifecycleState.TIMED_OUT
    assert observation.exit_code is None
    state = json.loads((tmp_path / "launch-timeout.json").read_text(encoding="utf-8"))
    assert state["terminal_state"] == "TIMED_OUT"


def test_silent_live_process_emits_heartbeat_without_being_stage_progress(
    tmp_path: Path,
) -> None:
    observation = run_bounded_process(
        (sys.executable, "-c", "import time; time.sleep(0.65)"),
        cwd=tmp_path,
        environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        start_timeout_s=1.0,
        execution_timeout_s=2.0,
        state_path=tmp_path / "heartbeat.json",
    )
    assert observation.lifecycle_state is ProcessLifecycleState.RETURNED
    state = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert state["heartbeat_count"] > 0
    assert [event["state"] for event in state["events"]][:3] == [
        "NOT_STARTED",
        "STARTED",
        "RUNNING",
    ]


def test_bounded_process_captures_stderr_exit_and_identity(tmp_path: Path) -> None:
    observation = run_bounded_process(
        (
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)",
        ),
        cwd=tmp_path,
        environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        start_timeout_s=1.0,
        execution_timeout_s=1.0,
        state_path=tmp_path / "failure.json",
    )

    assert observation.lifecycle_state is ProcessLifecycleState.FAILED
    assert observation.stdout == b"out\n"
    assert observation.stderr == b"err\n"
    assert observation.exit_code == 7
    assert observation.executable == str(Path(sys.executable).resolve())
    assert observation.environment_fingerprint


def test_sandbox_preserves_stderr_for_physical_observation(tmp_path: Path) -> None:
    script = tmp_path / "emit.py"
    script.write_text("import sys; print('out'); print('err', file=sys.stderr)\n", encoding="utf-8")
    result = run_sandboxed(f"{sys.executable} {script}", cwd=tmp_path)
    assert result.stdout == "out\n"
    assert result.stderr == "err\n"
    assert result.executable == str(Path(sys.executable).resolve())
    assert result.cwd == str(tmp_path)


def test_codex_invoker_uses_bounded_process_supervisor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    observed: dict[str, object] = {}

    def fake_supervisor(argv: tuple[str, ...], **kwargs: object) -> ProcessObservation:
        observed["argv"] = argv
        observed.update(kwargs)
        return ProcessObservation(
            argv=argv,
            executable=argv[0],
            executable_version="sha256:test",
            cwd=str(tmp_path),
            environment_fingerprint="e" * 64,
            stdout=b'{"type":"run_result","finishReason":"completed","model":"gpt-5.6-sol"}\n',
            stderr=b"",
            exit_code=0,
            duration_ms=1,
            lifecycle_state=ProcessLifecycleState.RETURNED,
        )

    monkeypatch.setattr(shutil, "which", lambda _name: "/bin/codex")
    monkeypatch.setattr(hybrid, "run_bounded_process", fake_supervisor, raising=False)
    spec = SessionSpec(
        workspace=tmp_path,
        prompt="bounded",
        allowed_tools=(),
        read_scopes=(),
        timeout_s=2,
        lifecycle_state_path=tmp_path / "worker.json",
    )
    result = hybrid.codex_cli_invoker(object(), mcp_config_path=None)(spec)

    assert isinstance(result, SessionResult)
    assert observed["cwd"] == tmp_path
    assert observed["state_path"] == tmp_path / "worker.json"
    assert observed["execution_timeout_s"] == 2
    assert "--skip-git-repo-check" in observed["argv"]
    assert "gpt-5.6-sol" in observed["argv"]


def test_mcp_submit_evidence_has_no_caller_authoritative_observation_fields(
    tmp_path: Path,
) -> None:
    server = build_court_mcp_server(tmp_path / "court", workspace_root=tmp_path)
    with pytest.raises(Exception, match=r"caller|observation|artifact|exit|stdout"):
        asyncio.run(
            server.call_tool(
                "submit_evidence",
                {
                    "run_id": "r-1",
                    "claim_id": "builds",
                    "argv": ["/usr/bin/true"],
                    "workspace_root": str(tmp_path),
                    "artifact_path": "artifact.txt",
                    "artifact_hash": "0" * 64,
                    "exit_code": 0,
                    "stdout": "forged\n",
                },
            )
        )


def test_mcp_verifier_physically_derives_observation_and_rejects_nested_command(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("artifact\n", encoding="utf-8")
    server = build_court_mcp_server(tmp_path / "court", workspace_root=tmp_path)

    with pytest.raises(Exception, match=r"shell|nested|command|argv"):
        asyncio.run(
            server.call_tool(
                "submit_evidence",
                {
                    "run_id": "r-1",
                    "claim_id": "builds",
                    "argv": ["/bin/sh", "-c", "true"],
                    "workspace_root": str(tmp_path),
                    "artifact_path": "artifact.txt",
                },
            )
        )


def test_kernel_structured_command_rejects_nested_interpreter() -> None:
    with pytest.raises(SandboxError, match=r"nested|shell"):
        canonical_command(
            (sys.executable, "-c", "print('not a replayable verifier')"),
            environment={"PATH": allowlisted_path(), "LC_ALL": "C"},
        )


def test_mcp_rejects_missing_artifact_before_pool_submission(tmp_path: Path) -> None:
    verifier = tmp_path / "verify.py"
    verifier.write_text("print('physical')\n", encoding="utf-8")
    server = build_court_mcp_server(tmp_path / "court", workspace_root=tmp_path)
    with pytest.raises(Exception, match="artifact"):
        asyncio.run(
            server.call_tool(
                "submit_evidence",
                {
                    "run_id": "r-1",
                    "claim_id": "builds",
                    "argv": [sys.executable, verifier.name],
                    "workspace_root": str(tmp_path),
                    "artifact_path": "missing.txt",
                },
            )
        )


def test_mcp_rejects_run_id_path_escape(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("artifact\n", encoding="utf-8")
    server = build_court_mcp_server(tmp_path / "court", workspace_root=tmp_path)
    with pytest.raises(Exception, match="run_id"):
        asyncio.run(
            server.call_tool(
                "submit_evidence",
                {
                    "run_id": "../escaped",
                    "claim_id": "builds",
                    "argv": ["/usr/bin/true"],
                    "workspace_root": str(tmp_path),
                    "artifact_path": "artifact.txt",
                },
            )
        )


def test_mcp_success_stores_only_verifier_derived_physical_fields(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("artifact\n", encoding="utf-8")
    verifier = tmp_path / "verify.py"
    verifier.write_text(
        "import sys; print('physical'); print('physical-error', file=sys.stderr)\n",
        encoding="utf-8",
    )
    server = build_court_mcp_server(tmp_path / "court", workspace_root=tmp_path)
    asyncio.run(
        server.call_tool(
            "submit_evidence",
            {
                "run_id": "r-1",
                "claim_id": "builds",
                "argv": [sys.executable, verifier.name],
                "workspace_root": str(tmp_path),
                "artifact_path": "artifact.txt",
            },
        )
    )
    from runtime.orchestrator import FileCourtEvidencePool

    evidence = FileCourtEvidencePool(tmp_path / "court").evidence_for("r-1")[0]
    assert evidence.result["exit_code"] == 0
    assert evidence.result["stdout_sha256"]
    assert evidence.result["stderr_sha256"]
    assert "physical" not in json.dumps(evidence.result)


def test_court_rejects_tampered_environment_identity(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("artifact\n", encoding="utf-8")
    verifier = tmp_path / "verify.py"
    verifier.write_text("print('physical')\n", encoding="utf-8")
    server = build_court_mcp_server(tmp_path / "court", workspace_root=tmp_path)
    asyncio.run(
        server.call_tool(
            "submit_evidence",
            {
                "run_id": "r-1",
                "claim_id": "builds",
                "argv": [sys.executable, verifier.name],
                "workspace_root": str(tmp_path),
                "artifact_path": "artifact.txt",
            },
        )
    )
    from runtime.orchestrator import FileCourtEvidencePool

    evidence = FileCourtEvidencePool(tmp_path / "court").evidence_for("r-1")[0]
    tampered = replace(
        evidence,
        result={**evidence.result, "environment_fingerprint": "0" * 64},
    )
    court = Court(runner=structured_sandbox_runner())
    court.submit_evidence(tampered)
    verdict = court.adjudicate(
        evidence.artifact_hash,
        (Claim(id="builds", statement="built", evidence_refs=(tampered.hash,)),),
    )
    assert verdict.outcome is VerdictOutcome.REMAND


def test_court_remands_a_deliberately_failing_physical_verification(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("artifact\n", encoding="utf-8")
    verifier = tmp_path / "fail.py"
    verifier.write_text("import sys; print('failure', file=sys.stderr); raise SystemExit(17)\n", encoding="utf-8")
    command = canonical_command(
        (sys.executable, str(verifier)),
        environment={"PATH": allowlisted_path(), "LC_ALL": "C"},
    )
    evidence = {
        "hash": "f" * 64,
        "kind": "TEST",
        "claim_id": "canary",
        "artifact_hash": content_hash(artifact.read_bytes()),
        "environment_hash": "e" * 64,
        "reproducible_command": command,
        "producer_role": "BUILDER",
        "producer_session": "negative-canary",
        "determinism": "DETERMINISTIC",
        "result": {"exit_code": 0},
        "attestation": "test",
    }
    from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
    from kernel.types import Role

    claimed = Evidence(
        hash=evidence["hash"],
        kind=EvidenceKind.TEST,
        claim_id=evidence["claim_id"],
        artifact_hash=evidence["artifact_hash"],
        environment_hash=evidence["environment_hash"],
        reproducible_command=evidence["reproducible_command"],
        producer=EvidenceProducer(role=Role.BUILDER, session=evidence["producer_session"]),
        determinism=Determinism.DETERMINISTIC,
        result=evidence["result"],
        attestation=evidence["attestation"],
    )
    court = Court(runner=structured_sandbox_runner())
    court.submit_evidence(claimed)
    verdict = court.adjudicate(
        claimed.artifact_hash,
        (Claim(id="canary", statement="must fail", evidence_refs=(claimed.hash,)),),
    )
    assert verdict.outcome is VerdictOutcome.REMAND


def test_builder_seed_contains_declared_runtime_closure_but_not_quarantined_paths(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    for directory in ("kernel", "runtime", "paeos/model_router", "tests", "sentium"):
        (source / directory).mkdir(parents=True)
    (source / "kernel" / "types.py").write_text("kernel\n", encoding="utf-8")
    (source / "runtime" / "runner.py").write_text("runtime\n", encoding="utf-8")
    (source / "paeos" / "model_router" / "router.py").write_text("router\n", encoding="utf-8")
    (source / "paeos" / "model_router" / "credentials.py").write_text("secret\n", encoding="utf-8")
    (source / "tests" / "test_runtime.py").write_text("test\n", encoding="utf-8")
    (source / "sentium" / "live.py").write_text("frozen\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_workspace(
        workspace,
        source,
        write_scopes=("runtime/runner.py",),
        read_scopes=("kernel/", "runtime/", "paeos/", "tests/", "sentium/"),
    )
    assert (workspace / "kernel/types.py").is_file()
    assert (workspace / "paeos/model_router/router.py").is_file()
    assert not (workspace / "paeos/model_router/credentials.py").exists()
    assert not (workspace / "sentium/live.py").exists()


def test_quarantined_worker_write_fails_closed_before_collection(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "sentium").mkdir(parents=True)
    (workspace / "sentium" / "attempt.txt").write_text("frozen\n", encoding="utf-8")
    with pytest.raises(ValueError, match="quarantined"):
        _collect_writes(workspace, ("sentium/",))
