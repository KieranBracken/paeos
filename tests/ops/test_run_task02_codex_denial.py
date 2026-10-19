"""Synthetic regression for the retired Task 02 Codex entrypoint."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPOSITORY_ROOT / "ops" / "run_task02_codex.sh"
REFUSAL = "Task 02 Codex execution is retired; provider and fallback execution are disabled."


def test_task02_script_refuses_without_invoking_provider_or_fallback(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "client-calls.txt"

    for name in ("codex", "fallback"):
        executable = fake_bin / name
        executable.write_text(
            f"#!/bin/sh\nprintf '%s\\n' '{name}' >> \"$PAEOS_TASK02_CALL_LOG\"\nexit 0\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)

    date = fake_bin / "date"
    date.write_text("#!/bin/sh\nprintf '%s\\n' '2026-10-19T00:00:00Z'\n", encoding="utf-8")
    date.chmod(0o755)

    result = subprocess.run(
        ["/bin/bash", str(SCRIPT_PATH)],
        cwd=tmp_path,
        env={
            "HOME": str(tmp_path),
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": str(fake_bin),
            "PAEOS_TASK02_CALL_LOG": str(calls),
            "TMPDIR": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    observed_calls = calls.read_text(encoding="utf-8") if calls.exists() else "<none>"
    assert result.returncode == 1, (
        f"expected fixed refusal, got {result.returncode}; fake calls: {observed_calls}"
    )
    assert result.stdout == ""
    assert result.stderr == REFUSAL + "\n"
    assert not calls.exists(), f"fake provider/fallback invoked: {observed_calls}"
