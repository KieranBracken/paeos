"""Reject implicit provider selection before state creation or host key access."""

from pathlib import Path

import pytest
from runtime.scheduler import GlobalBudget

from ops import autonomous_run


@pytest.mark.parametrize("selector", [None, "", "typo", "CODEX", " codex", "bound-cline"])
def test_invalid_runtime_denied_before_state_or_key_access(tmp_path, monkeypatch, selector):
    def forbidden_key(*args, **kwargs):
        pytest.fail("runtime rejection occurred after signing-key access")

    monkeypatch.setattr(autonomous_run, "load_or_create_signing_key", forbidden_key)
    state = tmp_path / "state"
    with pytest.raises(ValueError, match="runtime"):
        autonomous_run.build_scheduler(
            state,
            tmp_path / "absent-repository",
            global_budget=GlobalBudget(tokens=1, wallclock_s=1, runs=1),
            **({} if selector is None else {"runtime_type": selector}),
        )
    assert not state.exists()


@pytest.mark.parametrize(
    "suffix", [[], ["1"], ["1", "1"], ["1", "1", "typo"], ["1", "1", "bound-cline"]]
)
def test_cli_rejects_missing_or_invalid_selector_before_backlog_read(tmp_path, suffix, capsys):
    state = tmp_path / "state"
    assert autonomous_run.main([str(tmp_path / "missing.json"), str(state), *suffix]) == 64
    assert "runtime" in capsys.readouterr().err
    assert not state.exists()


@pytest.mark.parametrize(
    "selector", ["codex", "hybrid", "claude", "glm", "cline", "chat-bridge", "antigravity"]
)
def test_cli_preserves_explicit_selection_without_fallback(tmp_path, monkeypatch, selector):
    # Stop at composition: never load host identities, run a worker or create a ledger.
    class SelectionReached(Exception):
        pass

    backlog = tmp_path / "backlog.json"
    backlog.write_text("[]", encoding="utf-8")

    def capture_selection(state_dir, repo_root, *, runtime_type, **kwargs):
        assert state_dir == tmp_path / "state"
        assert isinstance(repo_root, Path)
        assert runtime_type == selector
        raise SelectionReached

    monkeypatch.setattr(autonomous_run, "build_scheduler", capture_selection)
    with pytest.raises(SelectionReached):
        autonomous_run.main([str(backlog), str(tmp_path / "state"), "1", "1", selector])
    assert not (tmp_path / "state").exists()
