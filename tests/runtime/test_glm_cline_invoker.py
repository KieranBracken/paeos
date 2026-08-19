"""GLM-5.3 Cline-native invoker tests (CRITICAL-002 remediation, notebook Entry 142).

The old invoker passed Claude-Code flags the Cline CLI rejects and its failures were recorded
as zero-cost successes. These tests pin the *Cline-native* contract: correct argv, terminal
``run_result`` validation, enforced model attribution, cost parsing, and file-based evidence
helper seeding.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from kernel.types import StageId
from runtime.integrations import SessionSpec, _parse_cost
from runtime.integrations.hybrid import CLINE_MODEL, _court_pool_dir, glm_cli_invoker
from tests.runtime.test_hybrid_runtime import _make_package


def _spec(tmp_path: Path) -> SessionSpec:
    return SessionSpec(
        workspace=tmp_path, prompt="do the thing", allowed_tools=("read",),
        read_scopes=("/",), timeout_s=120,
    )


def _cline_stream(model_id: str = CLINE_MODEL, finish: str = "completed") -> str:
    return "\n".join([
        json.dumps({"ts": "t0", "type": "agent_event", "event": {"type": "iteration_start", "iteration": 1}}),
        json.dumps({"ts": "t1", "type": "agent_event", "event": {"type": "content_end", "contentType": "text", "text": "OK"}}),
        json.dumps({
            "ts": "t2", "type": "run_result", "finishReason": finish,
            "usage": {"inputTokens": 100, "outputTokens": 5, "cacheReadTokens": 20},
            "durationMs": 1500, "text": "OK",
            "model": {"id": model_id, "provider": "cline-pass"},
        }),
    ])


def _patch_cli(monkeypatch: pytest.MonkeyPatch, stdout: str, returncode: int = 0) -> MagicMock:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/cline" if name == "cline" else None)
    run = MagicMock(return_value=SimpleNamespace(returncode=returncode, stdout=stdout, stderr=""))
    monkeypatch.setattr(subprocess, "run", run)
    return run


def test_argv_is_cline_native(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = _patch_cli(monkeypatch, _cline_stream())
    invoker = glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))
    invoker(_spec(tmp_path))
    cmd = run.call_args.args[0]
    assert cmd[0] == "cline"
    assert "-P" in cmd and cmd[cmd.index("-P") + 1] == "cline-pass"
    assert "-m" in cmd and cmd[cmd.index("-m") + 1] == CLINE_MODEL
    assert "--json" in cmd
    assert "--auto-approve" in cmd and cmd[cmd.index("--auto-approve") + 1] == "true"
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == str(tmp_path)
    # the rejected Claude-Code flags must be gone
    for forbidden in ("--output-format", "--allowedTools", "--dangerously-skip-permissions", "--mcp-config"):
        assert forbidden not in cmd


def test_successful_run_returns_stream(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_cli(monkeypatch, _cline_stream())
    result = glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))(_spec(tmp_path))
    assert json.loads(result.transcript.splitlines()[-1])["type"] == "run_result"


def test_wrong_model_fails_loud(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_cli(monkeypatch, _cline_stream(model_id="claude-sonnet-x"))
    with pytest.raises(RuntimeError, match="homogenisation"):
        glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))(_spec(tmp_path))


def test_missing_run_result_fails_loud(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_cli(monkeypatch, json.dumps({"type": "agent_event"}) + "\n")
    with pytest.raises(RuntimeError, match="no run_result"):
        glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))(_spec(tmp_path))


def test_non_completed_finish_fails_loud(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_cli(monkeypatch, _cline_stream(finish="error"))
    with pytest.raises(RuntimeError, match="did not complete"):
        glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))(_spec(tmp_path))


def test_nonzero_exit_fails_loud(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_cli(monkeypatch, "", returncode=1)
    with pytest.raises(RuntimeError, match="CLI failed"):
        glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))(_spec(tmp_path))


def test_cost_parsed_from_cline_stream() -> None:
    cost = _parse_cost(_cline_stream(), "fallback")
    assert cost.tokens == 105  # inputTokens + outputTokens
    assert cost.wallclock_s == pytest.approx(1.5)
    assert cost.model_ver == CLINE_MODEL


def test_cost_unparseable_stays_zero() -> None:
    cost = _parse_cost("not json at all", "fallback")
    assert cost.tokens == 0 and cost.model_ver == "fallback"


def test_court_pool_dir_extraction(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp-config.json"
    cfg.write_text(json.dumps({
        "mcpServers": {"paeos-court": {"command": "python", "args": ["-m", "court_server", str(tmp_path / "court")]}}
    }))
    assert _court_pool_dir(cfg) == tmp_path / "court"
    assert _court_pool_dir(None) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    assert _court_pool_dir(bad) is None


def test_evidence_helper_seeded_when_pool_known(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_cli(monkeypatch, _cline_stream())
    cfg = tmp_path / "mcp-config.json"
    pool = tmp_path / "court"
    cfg.write_text(json.dumps({
        "mcpServers": {"paeos-court": {"command": "python", "args": ["-m", "srv", str(pool)]}}
    }))
    invoker = glm_cli_invoker(_make_package(StageId.IMPLEMENT), mcp_config_path=cfg)
    invoker(_spec(tmp_path))
    helper = tmp_path / "submit_evidence.py"
    assert helper.is_file()
    assert "FileCourtEvidencePool" in helper.read_text()
