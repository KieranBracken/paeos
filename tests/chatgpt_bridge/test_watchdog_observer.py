"""Tests for the watchdog observer module.

Task 4: control-plane recovery — test remediation.
Ratified names only.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from ops.chatgpt_bridge import watchdog


def _forbid(*args, **kwargs):
    """Raise AssertionError on any invocation."""
    raise AssertionError("This call is forbidden in this test")


# ---------------------------------------------------------------------------
# Test 1: collect_report returns all five issues when every monitor is
#         unhealthy; no mutation of subprocess, filesystem, or signals.
# ---------------------------------------------------------------------------

def test_unhealthy_report_performs_no_mutation(monkeypatch):
    """collect_report with all-unhealthy values yields all five issues
    and never touches Popen, run, os.kill, Path.unlink, or Path.write_text."""

    monkeypatch.setattr("subprocess.Popen", _forbid)
    monkeypatch.setattr("subprocess.run", _forbid)
    monkeypatch.setattr("os.kill", _forbid)
    monkeypatch.setattr(Path, "unlink", _forbid)
    monkeypatch.setattr(Path, "write_text", _forbid)

    monkeypatch.setattr(
        watchdog, "check_bridge_monitor",
        lambda _pid_file: (False, 31415),
    )

    def _file_age(path, **_kw):
        return 60.0 if path.name == "bridge.log" else 70.0

    monkeypatch.setattr(watchdog, "file_age_minutes", _file_age)
    monkeypatch.setattr(watchdog, "check_cline_process", lambda: False)
    monkeypatch.setattr(watchdog, "repo_idle_minutes", lambda _root: 45.0)

    repo_root = Path("/some/repo")
    bridge_dir = Path("/some/bridge")
    report = watchdog.collect_report(repo_root, bridge_dir)

    text = " ".join(report.issues).lower()

    assert "bridge monitor stopped" in text
    assert "bridge log stale" in text
    assert "cline process missing" in text
    assert "repository stale" in text
    assert "response stale" in text
    assert report.compatibility_diagnostics == report.issues


# ---------------------------------------------------------------------------
# Test 2: stale PID file — check_bridge_monitor returns (False, numeric_pid)
#         and leaves the original PID bytes untouched on disk.
# ---------------------------------------------------------------------------

def test_stale_pid_file_is_preserved(monkeypatch, tmp_path):
    """Given a nonexistent-numeric PID in the PID file, ps returning
    exit-code 1 with empty stdout, check_bridge_monitor reports stale and
    does not alter the file contents."""

    pid_file = tmp_path / "bridge.pid"
    raw = b"31415\n"
    pid_file.write_bytes(raw)

    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )

    ok, pid = watchdog.check_bridge_monitor(pid_file)

    assert (ok, pid) == (False, 31415)
    assert pid_file.read_bytes() == raw


# ---------------------------------------------------------------------------
# Test 3: run_watchdog — accepts a frozen WatchdogReport, logs every issue
#         at WARNING, and performs no recovery (Popen, kill, unlink, etc.).
# ---------------------------------------------------------------------------

def test_run_watchdog_reports_issues_without_recovery_actions(
    monkeypatch, caplog,
):
    """run_watchdog uses the provided collect_report result, logs all
    issue strings at WARNING level, and never calls Popen, os.kill,
    Path.unlink, Path.write_text, or Path.touch."""

    monkeypatch.setattr("subprocess.Popen", _forbid)
    monkeypatch.setattr("os.kill", _forbid)
    monkeypatch.setattr(Path, "unlink", _forbid)
    monkeypatch.setattr(Path, "write_text", _forbid)
    monkeypatch.setattr(Path, "touch", _forbid)

    issues = (
        "bridge monitor stopped",
        "bridge log stale",
        "cline process missing",
        "repository stale",
        "response stale",
    )
    fake_report = watchdog.WatchdogReport(
        bridge_alive=False,
        bridge_pid=31415,
        bridge_log_age_minutes=60.0,
        cline_alive=False,
        repo_idle_minutes=45.0,
        response_age_minutes=70.0,
        issues=issues,
    )

    monkeypatch.setattr(
        watchdog, "collect_report",
        lambda _root, _dir: fake_report,
    )

    repo_root = Path("/test/repo")
    bridge_dir = Path("/test/bridge")

    with caplog.at_level(logging.WARNING):
        result = watchdog.run_watchdog(repo_root, bridge_dir)

    assert result is fake_report
    for text in issues:
        assert text in caplog.text
