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
from pathlib import Path

import pytest

from kernel.capability import CapabilityBroker
from kernel.types import Role, StageId
from runtime.claude_code import TaskStatus
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


# ---- CRITICAL-003: no fabricated verdicts in the bridge ----------------------


def test_bridge_source_has_no_auto_feed_or_fabricated_verdicts() -> None:
    """The fabrication lines must not exist anywhere in the bridge source."""
    assert "Auto-feeding" not in BRIDGE_SOURCE
    assert "no dissent" not in BRIDGE_SOURCE
    assert "Stage completed successfully. VERDICT: PASS" not in BRIDGE_SOURCE


def test_bridge_adversarial_review_requires_real_orchestrator_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADVERSARIAL_REVIEW (previously auto-fed) must now block on real orchestrator output
    and return exactly what the orchestrator wrote — including a DISSENT verdict."""
    monkeypatch.chdir(REPO)
    bridge_dir = Path(".paeos_state/bridge")
    bridge_dir.mkdir(parents=True, exist_ok=True)
    output_file = bridge_dir / "current_output.md"
    prompt_file = bridge_dir / "current_prompt.md"
    # Remove stale bridge files so the orchestrator thread reacts to THIS run's prompt and
    # its output is not deleted by the bridge's own stale-output cleanup.
    output_file.unlink(missing_ok=True)
    prompt_file.unlink(missing_ok=True)

    def _orchestrator() -> None:
        for _ in range(120):
            if prompt_file.exists():
                break
            time.sleep(0.25)
        output_file.write_text(
            "dissent: the claim lacks reproduction evidence\nVERDICT: REMAND\n",
            encoding="utf-8",
        )

    thread = threading.Thread(target=_orchestrator, daemon=True)
    thread.start()
    runtime = ChatBridgeRuntime(workspace_root=tmp_path)
    result = runtime.run(_make_package(StageId.ADVERSARIAL_REVIEW))
    thread.join(timeout=5)

    assert result.status == TaskStatus.COMPLETE
    assert b"VERDICT: REMAND" in result.trace
    assert b"no dissent" not in result.trace  # the fabricated report must not leak in


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


def test_root_submit_evidence_script_takes_real_arguments() -> None:
    script = (REPO / "submit_evidence.py").read_text(encoding="utf-8")
    assert "dummy_hash_for_now" not in script
    assert "dummy_env" not in script
    assert "sys.argv" in script  # artifact + command are now required inputs
    assert "artifact_path.read_bytes()" in script
