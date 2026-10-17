"""B2.N tests — probative court verification against a workspace with the change applied.

The live adversary refused vacuous `echo` evidence because the Court re-ran commands without the
change present. Here the workspace *has* the builder's artifact applied, so a command that reads the
change sees it — the substrate for probative evidence that passes only if the change is real.
"""

from __future__ import annotations

import shutil
import socket
import sys
import tempfile
from pathlib import Path

from kernel.cas import CAS, InMemoryCasStore
from kernel.sandbox import SandboxResult, allowlisted_path, canonical_command
from runtime.court.completeness_firewall import (
    VerificationObligation,
    VerificationObligationKind,
    load_authoritative_manifest,
)
from runtime.verification import (
    build_verification_workspace,
    candidate_discrimination_commands,
    vacuous_commands,
    workspace_runner,
)


def test_vacuous_commands_flags_non_discriminating(tmp_path: Path) -> None:
    # B2.O: a command whose result is the same with/without the change is vacuous; one that
    # observes the change is probative.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "marker.txt").write_text("ABSENT\n")
    cas = CAS(InMemoryCasStore())
    written = (("marker.txt", cas.put(b"PRESENT\n")),)
    vac = vacuous_commands(repo, written, cas, ("echo hi", "cat marker.txt"))
    assert "echo hi" in vac  # same output regardless of the change → vacuous
    assert "cat marker.txt" not in vac  # reads the change → probative


def test_negative_court_control_is_not_candidate_vacuity_input() -> None:
    obligations = (
        VerificationObligation(
            "CLAIM-POSITIVE",
            ("/usr/bin/true",),
            kind=VerificationObligationKind.CANDIDATE_DISCRIMINATION,
        ),
        VerificationObligation(
            "CLAIM-CF-08-CANARY-DISCRIMINATION",
            ("/usr/bin/false",),
            kind=VerificationObligationKind.NEGATIVE_COURT_CONTROL,
        ),
    )

    assert candidate_discrimination_commands(obligations) == (("/usr/bin/true",),)


def test_authoritative_lifecycle_obligation_includes_candidate_composition_test() -> None:
    manifest = load_authoritative_manifest(
        Path("ops/manifests/p1_authoritative_completeness_manifest.json")
    )
    obligation = next(
        item
        for item in manifest.verification_obligations
        if item.claim_id == "CLAIM-CF-11-SOFTLOOP-L11-L13-L16-WIRING"
    )
    assert "tests/runtime/test_p1_production_lifecycle.py" in obligation.argv
    assert "tests/runtime/test_orchestrator.py" in obligation.argv


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


def test_workspace_runner_binds_structured_python_to_workspace_source(tmp_path: Path, monkeypatch) -> None:
    """Structured pytest replay must override editable-install source leakage explicitly."""
    observed: dict[str, object] = {}

    def fake_run(
        argv: tuple[str, ...],
        *,
        cwd: Path,
        environment: dict[str, str],
        **_: object,
    ) -> SandboxResult:
        observed["argv"] = argv
        observed["cwd"] = cwd
        observed["environment"] = environment
        return SandboxResult(
            exit_code=0,
            stdout="",
            timed_out=False,
            stderr="",
            argv=argv,
            cwd=str(cwd),
            environment_fingerprint="e" * 64,
        )

    monkeypatch.setattr("runtime.verification.run_sandboxed_argv", fake_run)
    command = canonical_command(
        ("/usr/bin/true",),
        environment={"PATH": allowlisted_path(), "LC_ALL": "C"},
    )
    result = workspace_runner(tmp_path)(command)
    assert result["exit_code"] == 0
    assert observed["cwd"] == tmp_path
    assert observed["environment"]["PYTHONPATH"] == str(tmp_path)  # type: ignore[index]


def test_structured_workspace_binding_keeps_declared_environment_identity_stable(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    command = canonical_command(
        (str(Path(sys.executable).absolute()), "-V"),
        environment={"PATH": allowlisted_path(), "LC_ALL": "C"},
    )
    first_result = workspace_runner(first)(command)
    second_result = workspace_runner(second)(command)
    assert first_result["environment_fingerprint"] == second_result["environment_fingerprint"]


def test_workspace_snapshot_excludes_live_unix_socket_from_runtime_tree(tmp_path: Path) -> None:
    """RED discriminator for the .03 L13 failure: copytree must not copy runtime IPC sockets."""
    del tmp_path
    repo = Path(tempfile.mkdtemp(prefix="vfy-", dir="/tmp"))
    socket_dir = repo / "ops" / ".trusted-worker"
    socket_dir.mkdir(parents=True)
    (socket_dir / "policy.json").write_text("{}\n")
    socket_path = socket_dir / "launcher.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    try:
        cas = CAS(InMemoryCasStore())
        ws = build_verification_workspace(repo, (), cas)
        try:
            assert (ws / "ops" / ".trusted-worker" / "policy.json").is_file()
            assert not (ws / "ops" / ".trusted-worker" / "launcher.sock").exists()
        finally:
            shutil.rmtree(ws, ignore_errors=True)
    finally:
        listener.close()
        shutil.rmtree(repo, ignore_errors=True)
