"""Probative court verification (B2.N).

The live adversary correctly refused a seal whose evidence was *non-probative*: a bare
`echo` reproduces faithfully but never exercises the change, so it "returns the same PASS for the
claim and its negation." The reason the Court could only accept such evidence is that it re-ran the
`reproducible_command` in a sandbox that did **not** have the builder's change applied — so a real
test (importing/exercising the change) could never pass.

This module closes that gap: build a **verification workspace** that is a copy of the repo with the
builder's produced artifact applied at its real path, and run the Court's command **there**
(`workspace_runner`, cwd = the workspace). Now a probative command — one that imports the change and
asserts on it — passes iff the change is actually present and correct, and fails for its negation.

It wraps `kernel.sandbox.run_sandboxed` (a kernel function it *calls*, never modifies), so this
stays F2-SOFT; the resource-limited sandbox and the deterministic-reproduction contract are intact.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from kernel.cas import CAS
from kernel.ledger import JsonValue
from kernel.sandbox import run_sandboxed
from kernel.types import Hash

__all__ = ["build_verification_workspace", "workspace_runner"]

_SKIP = {".git", ".venv", "__pycache__", ".ruff_cache", ".pytest_cache", ".mypy_cache"}
_IGNORE = shutil.ignore_patterns(*_SKIP, "*.pyc")


def build_verification_workspace(
    repo_root: Path, written_paths: tuple[tuple[str, Hash], ...], cas: CAS
) -> Path:
    """A temp copy of `repo_root` (minus VCS/venv/caches) with the builder's produced files applied
    at their real paths, so the Court's command can import and exercise the change."""
    ws = Path(tempfile.mkdtemp(prefix="paeos-verify-"))
    for child in repo_root.iterdir():
        if child.name in _SKIP:
            continue
        dst = ws / child.name
        if child.is_dir():
            shutil.copytree(child, dst, ignore=_IGNORE, dirs_exist_ok=True)
        elif child.is_file():
            shutil.copy2(child, dst)
    for rel_path, artifact_hash in written_paths:  # apply the change on top
        target = ws / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(cas.get(artifact_hash))
    return ws


def workspace_runner(workspace: Path) -> Callable[[str], dict[str, JsonValue]]:
    """A `reproduce` runner (command → {exit_code, stdout}) that runs in `workspace` under the same
    resource-limited sandbox as `kernel.sandbox.sandbox_runner`, but with the change applied."""

    def _run(command: str) -> dict[str, JsonValue]:
        result = run_sandboxed(command, cwd=workspace)
        exit_code = 124 if result.timed_out else result.exit_code  # 124 = timeout, so success ≠ met
        return {"exit_code": exit_code, "stdout": result.stdout}

    return _run
