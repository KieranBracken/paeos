"""Fail-closed regression tests for CRITICAL-002 / CRITICAL-003 (notebook Entry 138).

For ~3 days the chat bridge auto-fed fabricated verdicts ("VERDICT: PASS", "no dissent"),
instructed builders to submit placeholder court evidence ("dummy_hash_for_now", invented
exit codes), and both hybrid invokers silently fell back across providers and recorded
failed CLI sessions as zero-cost COMPLETE runs. These tests make each fabrication
impossible to reintroduce without a visible failure here.
"""

from __future__ import annotations

import threading
import time
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from kernel.capability import CapabilityBroker
from kernel.types import Role, StageId
from runtime.claude_code import TaskStatus
from runtime.integrations.bridge_protocol import BridgePaths, write_once_bytes
from runtime.integrations.chat_bridge import ChatBridgeRuntime
from runtime.integrations.hybrid import codex_cli_invoker, glm_cli_invoker
from runtime.task_package import Budget, Permissions, TaskPackage

REPO = Path(__file__).resolve().parents[2]
BRIDGE_SOURCE = (REPO / "runtime" / "integrations" / "chat_bridge.py").read_text(encoding="utf-8")
HYBRID_SOURCE = (REPO / "runtime" / "integrations" / "hybrid.py").read_text(encoding="utf-8")


def _make_package(stage: StageId, role: Role = Role.ADVERSARY) -> TaskPackage:
    broker = CapabilityBroker()
    cap = broker.mint(
        goal_id="g-test",
        run_id="r-5678",
        stage=stage,
        role=role,
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
        role=role,
        objective="Test objective",
        capability=cap,
        permissions=Permissions(read_scopes=("/",), write_scopes=("/tmp",), mcp_servers=()),
        required_evidence=(),
        context_refs=(),
        budget=Budget(tokens=1000, wallclock_s=60, retries=1),
    )


def _bridge_files(
    state_root: Path,
    package: TaskPackage,
) -> tuple[BridgePaths, Path, Path]:
    paths = BridgePaths(state_root)
    paths.ensure()
    exchange_id = "--".join((package.run_id, package.task_id, package.stage.name.lower()))
    return (
        paths,
        paths.requests / f"{exchange_id}.prompt.md",
        paths.responses / f"{exchange_id}.response.md",
    )


def _respond_after_prompt(
    prompt_path: Path,
    response_path: Path,
    payload: bytes,
    delivered: threading.Event,
) -> None:
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if prompt_path.exists():
            write_once_bytes(response_path, payload)
            delivered.set()
            return
        time.sleep(0.005)


# ---- CRITICAL-003: no fabricated verdicts in the bridge ----------------------


def test_bridge_source_has_no_auto_feed_or_fabricated_verdicts() -> None:
    """The fabrication lines must not exist anywhere in the bridge source."""
    assert "Auto-feeding" not in BRIDGE_SOURCE
    assert "no dissent" not in BRIDGE_SOURCE
    assert "Stage completed successfully. VERDICT: PASS" not in BRIDGE_SOURCE


def test_bridge_adversarial_review_requires_real_orchestrator_output(
    tmp_path: Path,
) -> None:
    """ADVERSARIAL_REVIEW must block on a unique, real orchestrator response."""
    state_root = tmp_path / "state"
    package = _make_package(StageId.ADVERSARIAL_REVIEW)
    _paths, prompt_path, response_path = _bridge_files(state_root, package)
    response = b"dissent: the claim lacks reproduction evidence\nVERDICT: REMAND\n"

    sentinel = tmp_path / "production-sentinel" / "unchanged.txt"
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"must remain unchanged\n")
    sentinel_before = sha256(sentinel.read_bytes()).hexdigest()

    delivered = threading.Event()
    thread = threading.Thread(
        target=_respond_after_prompt,
        args=(prompt_path, response_path, response, delivered),
        daemon=True,
    )
    thread.start()
    runtime = ChatBridgeRuntime(
        state_root=state_root,
        workspace_root=tmp_path,
        timeout_seconds=2.0,
        poll_seconds=0.005,
    )
    result = runtime.run(package)
    thread.join(timeout=2.0)

    assert delivered.is_set()
    assert result.status == TaskStatus.COMPLETE
    assert result.trace == response
    assert b"no dissent" not in result.trace
    assert response_path.read_bytes() == response
    assert sha256(sentinel.read_bytes()).hexdigest() == sentinel_before
    bridge_files = tuple(path for path in (state_root / "bridge").rglob("*") if path.is_file())
    assert bridge_files
    assert all(path.resolve().is_relative_to(state_root.resolve()) for path in bridge_files)


# ---- CRITICAL-002: no placeholder evidence, no silent provider fallback ------


def test_bridge_evidence_template_has_no_placeholders() -> None:
    assert "dummy_hash_for_now" not in BRIDGE_SOURCE
    assert "dummy_env" not in BRIDGE_SOURCE
    assert '"test passed"' not in BRIDGE_SOURCE  # invented stdout
    # the template must instruct a real command run + real artifact hash
    assert "subprocess.run" in BRIDGE_SOURCE
    assert "artifact_path.read_bytes()" in BRIDGE_SOURCE


def test_glm_invoker_refuses_silent_provider_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """No `cline` on PATH must raise, never fall back to `claude` (audit homogenisation)."""
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="cline"):
        glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))


def test_codex_invoker_refuses_silent_provider_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """No `codex`/`openai` on PATH must raise, never fall back to `claude`."""
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="codex"):
        codex_cli_invoker(_make_package(StageId.PLAN, role=Role.PLANNER))


def test_invokers_fail_loud_on_cli_error() -> None:
    """A nonzero exit or empty transcript must raise, not become a zero-cost success."""
    assert "check=False" in HYBRID_SOURCE
    assert "RuntimeError" in HYBRID_SOURCE
    assert "timeout_transcript" not in HYBRID_SOURCE  # the silent timeout-transcript path is gone


def test_submit_evidence_script_takes_real_arguments() -> None:
    script = (REPO / "ops" / "submit_evidence.py").read_text(encoding="utf-8")
    assert "dummy_hash_for_now" not in script
    assert "dummy_env" not in script
    assert "required=True" in script  # artifact + command are now required inputs
    assert "--artifact-hash" in script


def test_bridge_rejects_preexisting_correlated_response(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    package = _make_package(StageId.ADVERSARIAL_REVIEW)
    paths, prompt_path, response_path = _bridge_files(state_root, package)
    stale = b"valid-looking stale response\nVERDICT: CONTINUE\n"
    write_once_bytes(response_path, stale)

    runtime = ChatBridgeRuntime(
        state_root=state_root,
        workspace_root=tmp_path,
        timeout_seconds=0.1,
        poll_seconds=0.001,
    )
    result = runtime.run(package)

    assert result.status == TaskStatus.FAILED
    assert b"BRIDGE_STALE_RESPONSE" in result.trace
    assert response_path.read_bytes() == stale
    assert not prompt_path.exists()
    quarantine_payloads = tuple(
        path.read_bytes() for path in paths.quarantine.iterdir() if path.is_file()
    )
    assert stale in quarantine_payloads


def test_bridge_refuses_reusing_exchange_id(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    package = _make_package(StageId.ADVERSARIAL_REVIEW)
    paths, prompt_path, response_path = _bridge_files(state_root, package)
    response = b"first delivery only\nVERDICT: REMAND\n"
    delivered = threading.Event()
    thread = threading.Thread(
        target=_respond_after_prompt,
        args=(prompt_path, response_path, response, delivered),
        daemon=True,
    )
    thread.start()
    runtime = ChatBridgeRuntime(
        state_root=state_root,
        workspace_root=tmp_path,
        timeout_seconds=2.0,
        poll_seconds=0.005,
    )

    first = runtime.run(package)
    thread.join(timeout=2.0)
    first_request = prompt_path.read_bytes()
    second = runtime.run(package)

    assert delivered.is_set()
    assert first.status == TaskStatus.COMPLETE
    assert second.status == TaskStatus.FAILED
    assert b"BRIDGE_DUPLICATE_REQUEST" in second.trace
    assert prompt_path.read_bytes() == first_request
    assert response_path.read_bytes() == response
    assert tuple(paths.requests.glob("*.prompt.md")) == (prompt_path,)
    assert tuple(paths.responses.glob("*.response.md")) == (response_path,)


def test_bridge_rejects_unbound_or_mismatched_worker_before_delivery(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    base = _make_package(StageId.ADVERSARIAL_REVIEW)
    empty_session = replace(
        base,
        task_id="t-unbound",
        capability=replace(
            base.capability,
            bound_to=replace(base.capability.bound_to, session=""),
        ),
    )
    mismatched_run = replace(
        base,
        task_id="t-mismatched",
        capability=replace(
            base.capability,
            bound_to=replace(base.capability.bound_to, run_id="r-other"),
        ),
    )
    paths = BridgePaths(state_root)
    paths.ensure()
    runtime = ChatBridgeRuntime(
        state_root=state_root,
        workspace_root=tmp_path,
        timeout_seconds=0.1,
        poll_seconds=0.001,
    )

    for package in (empty_session, mismatched_run):
        result = runtime.run(package)
        assert result.status == TaskStatus.FAILED
        assert b"BRIDGE_UNBOUND_WORKER" in result.trace

    assert tuple(paths.requests.iterdir()) == ()


def test_bridge_missing_response_times_out_without_retry(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    package = _make_package(StageId.ADVERSARIAL_REVIEW)
    paths, prompt_path, _response_path = _bridge_files(state_root, package)
    runtime = ChatBridgeRuntime(
        state_root=state_root,
        workspace_root=tmp_path,
        timeout_seconds=0.01,
        poll_seconds=0.001,
    )

    result = runtime.run(package)

    assert result.status == TaskStatus.FAILED
    assert b"BRIDGE_RESPONSE_TIMEOUT" in result.trace
    assert tuple(paths.requests.glob("*.prompt.md")) == (prompt_path,)
    assert tuple(paths.responses.iterdir()) == ()
    assert len(tuple(paths.requests.iterdir())) == 1


def test_bridge_malformed_response_is_quarantined(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    package = _make_package(StageId.ADVERSARIAL_REVIEW)
    paths, prompt_path, response_path = _bridge_files(state_root, package)
    malformed = b"\xff"
    delivered = threading.Event()
    thread = threading.Thread(
        target=_respond_after_prompt,
        args=(prompt_path, response_path, malformed, delivered),
        daemon=True,
    )
    thread.start()
    runtime = ChatBridgeRuntime(
        state_root=state_root,
        workspace_root=tmp_path,
        timeout_seconds=2.0,
        poll_seconds=0.005,
    )

    result = runtime.run(package)
    thread.join(timeout=2.0)

    assert delivered.is_set()
    assert result.status == TaskStatus.FAILED
    assert b"BRIDGE_MALFORMED_RESPONSE" in result.trace
    assert response_path.read_bytes() == malformed
    quarantine_payloads = tuple(
        path.read_bytes() for path in paths.quarantine.iterdir() if path.is_file()
    )
    assert malformed in quarantine_payloads
