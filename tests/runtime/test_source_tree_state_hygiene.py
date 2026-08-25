from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_runtime_state_is_untracked_and_ignored() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "--", ".paeos_state"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    assert tracked.stdout == ""

    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", ".paeos_state/runtime-hygiene-probe"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 0
