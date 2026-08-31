"""The retired GUI bridge must not be an executable control-plane path."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_legacy_gui_bridge_exits_closed_before_argument_or_network_handling() -> None:
    repo = Path(__file__).resolve().parents[2]
    bridge = repo / "ops" / "chatgpt_bridge" / "bridge.py"

    result = subprocess.run(
        [sys.executable, str(bridge), "--help"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )

    assert result.returncode == 2
    assert "disabled" in result.stderr.lower()
    assert "chrome" not in result.stderr.lower()


def test_legacy_gui_launchers_are_guarded_before_side_effects() -> None:
    repo = Path(__file__).resolve().parents[2]
    for name in ("cron_bridge.sh", "launch_chrome_debug.sh"):
        source = (repo / "ops" / "chatgpt_bridge" / name).read_text(encoding="utf-8")
        guard = source.find("LEGACY_GUI_BRIDGE_DISABLED")
        exit_point = source.find("exit 2", guard)
        assert guard >= 0
        assert exit_point > guard
        for side_effect in ("curl", "osascript", "Google Chrome"):
            side_effect_point = source.find(side_effect)
            assert side_effect_point < 0 or exit_point < side_effect_point
