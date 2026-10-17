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

import hashlib
import json
import logging
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from kernel.cas import CAS
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import JsonValue
from kernel.sandbox import (
    SandboxLimits,
    SandboxResult,
    allowlisted_path,
    canonical_command,
    run_sandboxed,
    run_sandboxed_argv,
)
from kernel.types import Hash, Role

from runtime.candidate_materialization import CandidateMaterialization, verify_candidate_integrity
from runtime.court.completeness_firewall import (
    VerificationObligation,
    VerificationObligationKind,
)

logger = logging.getLogger(__name__)

__all__ = [
    "PhysicalVerifierError",
    "build_verification_workspace",
    "candidate_discrimination_commands",
    "derive_physical_evidence",
    "vacuous_commands",
    "workspace_runner",
]


class PhysicalVerifierError(ValueError):
    """A verifier command or its candidate binding is invalid."""


def candidate_discrimination_commands(
    obligations: tuple[VerificationObligation, ...],
) -> tuple[tuple[str, ...], ...]:
    """Return only positive candidate-discrimination argv for L13 vacuity comparison."""

    return tuple(
        obligation.argv
        for obligation in obligations
        if obligation.kind is VerificationObligationKind.CANDIDATE_DISCRIMINATION
    )


def derive_physical_evidence(
    *,
    candidate: CandidateMaterialization,
    claim_id: str,
    argv: tuple[str, ...],
    artifact_hash: str,
    timeout_s: int = 30,
) -> Evidence:
    """Run one frozen verifier obligation and derive evidence only from kernel observations."""
    verify_candidate_integrity(candidate, run_id=candidate.run_id)
    resolved_argv = tuple(
        # Preserve the virtual-environment launcher path.  Resolving its symlink changes the
        # Python interpreter's prefix and can silently drop project dependencies (for example,
        # pytest) from a physically replayed obligation.
        str(Path(sys.executable).absolute()) if item == "{python}" else item for item in argv
    )
    if not claim_id or not resolved_argv or not Path(resolved_argv[0]).is_absolute() or "-c" in resolved_argv:
        raise PhysicalVerifierError("verifier obligation must be a direct absolute argv")
    environment = {"PATH": allowlisted_path(), "LC_ALL": "C"}
    command = canonical_command(resolved_argv, environment=environment)
    result = _run_in_verification_workspace(
        command,
        workspace=candidate.candidate_workspace,
        limits=SandboxLimits(cpu_seconds=timeout_s, wallclock_s=timeout_s),
    )
    observed = {
        "argv": list(result.argv),
        "cwd": ".",
        "environment_fingerprint": result.environment_fingerprint,
        "executable": result.executable,
        "executable_version": result.executable_version,
        "exit_code": 124 if result.timed_out else result.exit_code,
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "duration_ms": result.duration_ms,
    }
    identity = {
        "artifact_hash": artifact_hash,
        "claim_id": claim_id,
        "command": command,
        # Duration is retained in the evidence payload for physical provenance, but it is not
        # stable across Court replay and therefore is excluded from the evidence identity.
        "result": {key: value for key, value in observed.items() if key != "duration_ms"},
    }
    evidence_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return Evidence(
        hash=evidence_hash,
        kind=EvidenceKind.TEST,
        claim_id=claim_id,
        artifact_hash=artifact_hash,
        environment_hash=result.environment_fingerprint,
        reproducible_command=command,
        producer=EvidenceProducer(role=Role.VERIFIER, session="l13-" + candidate.run_id),
        determinism=Determinism.DETERMINISTIC,
        result=observed,
        attestation="kernel-physical:" + evidence_hash,
    )


def _run_in_verification_workspace(
    command: str,
    *,
    workspace: Path,
    limits: SandboxLimits | None = None,
) -> SandboxResult:
    """Execute canonical argv with imports bound to ``workspace``; retain legacy replay."""

    try:
        structured = json.loads(command)
    except (TypeError, json.JSONDecodeError):
        return run_sandboxed(command, limits=limits, cwd=workspace)
    if not isinstance(structured, dict):
        return run_sandboxed(command, limits=limits, cwd=workspace)

    # Round-trip through the kernel's public canonical-command contract.  Besides validating
    # argv and the declared environment, equality rejects extra fields or a non-canonical cwd.
    argv_value = structured.get("argv")
    environment_value = structured.get("environment")
    if not isinstance(argv_value, list) or not isinstance(environment_value, dict):
        return run_sandboxed(command, limits=limits, cwd=workspace)
    argv = tuple(argv_value)
    environment = dict(environment_value)
    canonical = canonical_command(argv, environment=environment)
    if json.loads(canonical) != structured:
        # Preserve the kernel's fail-closed handling and error type for invalid structured input.
        return run_sandboxed(command, limits=limits, cwd=workspace)

    execution_environment = dict(environment)
    execution_environment.setdefault("PATH", allowlisted_path())
    execution_environment.setdefault("LC_ALL", "C")
    execution_environment["PYTHONPATH"] = str(workspace)
    result = run_sandboxed_argv(
        argv,
        limits=limits,
        cwd=workspace,
        environment=execution_environment,
    )
    # PYTHONPATH is a verifier mechanism used to bind imports to the materialized candidate, not
    # part of the command's declared identity.  MCP evidence and the canonical-command contract
    # identify this execution by the validated PATH/LC_ALL environment alone.
    declared_environment = dict(environment)
    declared_environment.setdefault("PATH", allowlisted_path())
    declared_environment.setdefault("LC_ALL", "C")
    environment_fingerprint = hashlib.sha256(
        json.dumps(
            dict(sorted(declared_environment.items())),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return replace(result, environment_fingerprint=environment_fingerprint)


_SKIP = {".git", ".venv", "__pycache__", ".ruff_cache", ".pytest_cache", ".mypy_cache"}
_IGNORE = shutil.ignore_patterns(*_SKIP, "*.pyc")


def _ignore_verification_entries(directory: str, names: list[str]) -> set[str]:
    """Exclude runtime IPC and symlink entries from a verifier snapshot.

    Verification workspaces must contain source bytes only. Copying a live socket raises on macOS,
    while following a symlink could import mutable state outside the repository into Court replay.
    Both cases are excluded by lstat-based type checks; unreadable directory entries remain a hard
    copy failure rather than being silently treated as absent.
    """
    ignored = set(_IGNORE(directory, names))
    for name in names:
        if name in ignored:
            continue
        entry = Path(directory) / name
        try:
            mode = entry.lstat().st_mode
        except OSError:
            continue
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            ignored.add(name)
    return ignored


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
        mode = child.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            continue
        if stat.S_ISDIR(mode):
            shutil.copytree(child, dst, ignore=_ignore_verification_entries, dirs_exist_ok=True)
        elif stat.S_ISREG(mode):
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
        is_test_file = (
            rel_path.startswith("tests/") or "test_" in rel_path or rel_path.endswith("_test.py")
        )
        if is_test_file:
            # Apply new test file to baseline workspace so the test executes against baseline code
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(cas.get(artifact_hash))
        else:
            # Revert non-test production implementation file in baseline workspace to empty stub
            # so Python imports from baseline (failing missing symbols) rather than falling back to repo_root via editable .pth
            if rel_path.endswith(".py"):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    "# baseline stub: implementation removed for non-vacuity check\n",
                    encoding="utf-8",
                )
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
            # Timing is physical provenance, but it is not a semantic verifier result. Comparing
            # it here would let identical evidence evade CANARY-0002 through scheduling jitter.
            stable_with = (
                {key: value for key, value in res_with.items() if key != "duration_ms"}
                if isinstance(res_with, dict)
                else res_with
            )
            stable_without = (
                {key: value for key, value in res_without.items() if key != "duration_ms"}
                if isinstance(res_without, dict)
                else res_without
            )
            is_test_cmd = "pytest" in c or "test" in c
            # Vacuous if identical output in both environments, or if a test passes in baseline without implementation
            if stable_with == stable_without or (
                is_test_cmd
                and stable_with.get("exit_code") == 0
                and stable_without.get("exit_code") == 0
            ):
                vacuous.append(c)
        return tuple(vacuous)
    finally:
        shutil.rmtree(with_change, ignore_errors=True)
        shutil.rmtree(baseline, ignore_errors=True)


def workspace_runner(
    workspace: Path,
    *,
    candidate: CandidateMaterialization | None = None,
) -> Callable[[str], dict[str, JsonValue]]:
    """A `reproduce` runner (command → {exit_code, stdout}) that runs in `workspace` under the same
    resource-limited sandbox as `kernel.sandbox.sandbox_runner`, but with the change applied."""

    def _run(command: str) -> dict[str, JsonValue]:
        if candidate is not None:
            verify_candidate_integrity(candidate, run_id=candidate.run_id)
        result = _run_in_verification_workspace(command, workspace=workspace)
        try:
            structured = json.loads(command)
        except (TypeError, json.JSONDecodeError):
            structured = None
        if isinstance(structured, dict) and structured.get("schema") == "paeos.structured-command/1":
            return {
                "exit_code": 124 if result.timed_out else result.exit_code,
                "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
                "argv": list(result.argv),
                "executable": result.executable,
                "executable_version": result.executable_version,
                "cwd": ".",
                "environment_fingerprint": result.environment_fingerprint,
                "duration_ms": result.duration_ms,
            }
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
