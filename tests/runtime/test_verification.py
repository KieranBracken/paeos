"""B2.N tests — probative court verification against a workspace with the change applied.

The live adversary refused vacuous `echo` evidence because the Court re-ran commands without the
change present. Here the workspace *has* the builder's artifact applied, so a command that reads the
change sees it — the substrate for probative evidence that passes only if the change is real.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from kernel.cas import CAS, InMemoryCasStore
from runtime.verification import build_verification_workspace, workspace_runner


def test_workspace_applies_the_change_over_the_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "m.py").write_text("VALUE = 1\n")  # the ORIGINAL
    (repo / "other.txt").write_text("unchanged")
    cas = CAS(InMemoryCasStore())
    changed = cas.put(b"VALUE = 42\n")  # the builder's produced artifact

    ws = build_verification_workspace(repo, (("pkg/m.py", changed),), cas)
    try:
        assert (ws / "pkg" / "m.py").read_text() == "VALUE = 42\n"  # change applied
        assert (ws / "other.txt").read_text() == "unchanged"  # rest of the repo present
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_workspace_runner_sees_the_applied_change(tmp_path: Path) -> None:
    # a probative command run in the workspace observes the change (not the original) — unlike a
    # bare `echo`, its result differs for the change vs its absence
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "marker.txt").write_text("ABSENT\n")
    cas = CAS(InMemoryCasStore())
    ws = build_verification_workspace(repo, (("marker.txt", cas.put(b"PRESENT\n")),), cas)
    try:
        result = workspace_runner(ws)("cat marker.txt")
        assert result["exit_code"] == 0
        assert "PRESENT" in str(result["stdout"])  # the applied change is what the command sees
    finally:
        shutil.rmtree(ws, ignore_errors=True)
