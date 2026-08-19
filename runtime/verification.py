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

import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from kernel.cas import CAS
from kernel.ledger import JsonValue
from kernel.sandbox import run_sandboxed
from kernel.types import Hash

logger = logging.getLogger(__name__)

__all__ = ["build_verification_workspace", "vacuous_commands", "workspace_runner"]

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


def vacuous_commands(
    repo_root: Path,
    written_paths: tuple[tuple[str, Hash], ...],
    cas: CAS,
    commands: tuple[str, ...],
) -> tuple[str, ...]:
    """The **vacuous** commands (B2.O / CANARY-0002): those whose sandboxed result is **identical**
    whether the production implementation change is applied or not — zero discriminating power.

    HARDENED CANARY-0002 DISCRIMINATION:
    - `with_change`: repo_root + all written files (production implementation + test files).
    - `baseline`: repo_root + written TEST files ONLY, with production implementation files reverted.
    The test file runs in BOTH environments. The command MUST fail in `baseline` (proving the
    production implementation is required) and pass in `with_change`."""
    with_change = build_verification_workspace(repo_root, written_paths, cas)
    baseline = build_verification_workspace(repo_root, (), cas)

    for rel_path, artifact_hash in written_paths:
        target = baseline / rel_path
        is_test_file = rel_path.startswith("tests/") or "test_" in rel_path or rel_path.endswith("_test.py")
        if is_test_file:
            # Apply new test file to baseline workspace so the test executes against baseline code
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(cas.get(artifact_hash))
        else:
            # Revert non-test production implementation file in baseline workspace to empty stub
            # so Python imports from baseline (failing missing symbols) rather than falling back to repo_root via editable .pth
            if rel_path.endswith(".py"):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# baseline stub: implementation removed for non-vacuity check\n", encoding="utf-8")
            elif target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target, ignore_errors=True)



    try:
        run_with, run_without = workspace_runner(with_change), workspace_runner(baseline)
        vacuous: list[str] = []
        for c in commands:
            res_with = run_with(c)
            res_without = run_without(c)
            is_test_cmd = "pytest" in c or "test" in c
            # Vacuous if identical output in both environments, or if a test passes in baseline without implementation
            if res_with == res_without:
                vacuous.append(c)
            elif is_test_cmd and res_with.get("exit_code") == 0 and res_without.get("exit_code") == 0:
                vacuous.append(c)
        return tuple(vacuous)
    finally:
        shutil.rmtree(with_change, ignore_errors=True)
        shutil.rmtree(baseline, ignore_errors=True)




def workspace_runner(workspace: Path) -> Callable[[str], dict[str, JsonValue]]:
    """A `reproduce` runner (command → {exit_code, stdout}) that runs in `workspace` under the same
    resource-limited sandbox as `kernel.sandbox.sandbox_runner`, but with the change applied."""

    def _run(command: str) -> dict[str, JsonValue]:
        result = run_sandboxed(command, cwd=workspace)
        exit_code = 124 if result.timed_out else result.exit_code  # 124 = timeout, so success ≠ met
        return {"exit_code": exit_code, "stdout": result.stdout}

    return _run


def check_ast(
    repo_root: Path, written_paths: tuple[tuple[str, Hash], ...], cas: CAS
) -> tuple[str, ...]:
    """Verify that all written python files comply with PAEOS AST exception handling rules."""
    from runtime.ast_linter import check_ast as check_ast_linter

    violations: list[str] = []
    for rel_path, artifact_hash in written_paths:
        if not rel_path.endswith(".py"):
            continue
        code = cas.get(artifact_hash).decode("utf-8")
        file_violations = check_ast_linter(code)
        for v in file_violations:
            violations.append(f"{rel_path}: {v}")
    return tuple(violations)

