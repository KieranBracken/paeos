"""Discriminative tests for capability-detected OS sandbox confinement.

Frozen contract: `docs/superpowers/plans/2026-08-26-paeos-taskpackage-worker-confinement.md`
Task 5 Step 5.1. Every behavioral row runs a *real adversarial subprocess* under the
real host mechanisms (loopback-only fixtures; the suite never touches the internet).
Each row is discriminative: its negation toggles live only in test code (injected
crippled registries / overridden seams) and the row fails under the toggle.

The 14-row matrix:
  1  executable-hash substitution -> enforcement failure, swapped file never runs
  2  hostile-PATH shadow never runs (exact kernel-side binding)
  3  child-process fanout -> dedicated group, no survivors after cleanup
  4  CPU exhaustion -> terminated at cap, fact names CPU
  5  memory boundary -> probe-verified: REFUSED on this host (strong form)
  6  open-file exhaustion -> OS-level EMFILE at the cap
  7  file-size exhaustion -> OS-level EFBIG at the cap
  8  disk boundary -> REFUSED (no weaker FSIZE-as-disk substitute)
  9  wallclock deadline fires
  10 forbidden network mode -> seatbelt-deny vs allowed control discriminate
  11 timeout -> whole process group cleaned, confirm-empty, no survivors
  12 output caps -> truncation fact + severed stream, bounded payload
  13 unavailable backend -> three shapes refuse with typed (dimension, mechanism)
  14 no-weaker-fallback -> tempting substitutes exist, substitution never occurs
plus structural rows: taxonomy/registry bijection, monotonicity, refusal honesty,
caveat visibility.
"""

from __future__ import annotations

import errno
import hashlib
import shutil
import signal
import socket
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from kernel.sandbox import FactKind, RunFact, SandboxResult
from kernel.sandbox_backend import (
    Dimension,
    EnforcementClaim,
    NegotiationOutcome,
    NetworkMode,
    PortableSandboxBackend,
    ProbeOutcome,
    RegistryCoverageError,
    SandboxBackend,
    SandboxedInvocation,
    SandboxProfile,
    SandboxProfileUnavailable,
    SeatbeltSandboxBackend,
    UnsupportedDimension,
    assert_registry_covers,
    build_claim_registry,
)

PY = sys.executable


def portable_profile(**overrides: object) -> SandboxProfile:
    """A profile whose requested dimensions are exactly the enforceable portable
    set, with a bounded wallclock on every run. Override per row."""
    base: dict[str, object] = {
        "profile_id": "SP-TEST",
        "cpu_seconds": 5,
        "memory_bytes": 0,
        "process_count": 0,
        "open_files": 0,
        "file_size_bytes": 0,
        "disk_bytes": 0,
        "wallclock_seconds": 8,
        "network_mode": NetworkMode.ALLOWED,
    }
    base.update(overrides)
    return SandboxProfile(**base)  # type: ignore[arg-type]


def run_portable(
    backend: SandboxBackend,
    argv: tuple[str, ...],
    profile: SandboxProfile,
    tmp: Path,
    environment: dict[str, str] | None = None,
) -> SandboxResult:
    return backend.run(
        SandboxedInvocation(
            argv=argv,
            cwd=tmp,
            profile=profile,
            environment=environment if environment is not None else {},
        )
    )


def digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


HEARTBEAT = """import sys, time
path = sys.argv[1]
end = time.time() + 6
while time.time() < end:
    with open(path, "a") as f:
        f.write("x")
    time.sleep(0.1)
"""

FANOUT_LEADER = """import subprocess, sys
subprocess.Popen([sys.executable, "-c", SCRIPT, sys.argv[1]])
"""

SLEEPING_FANOUT_LEADER = """import subprocess, sys, time
subprocess.Popen([sys.executable, "-c", SCRIPT, sys.argv[1]])
time.sleep(30)
"""


def heartbeat_growth_stops(path: Path, window: float = 0.7) -> bool:
    """True iff the heartbeat file stops being written (no surviving writers)."""
    size_a = path.stat().st_size if path.exists() else 0
    time.sleep(window)
    size_b = path.stat().st_size if path.exists() else 0
    return size_b == size_a


# ---------------------------------------------------------------------------
# Behavioral rows 1-2: executable hash / exact PATH binding
# ---------------------------------------------------------------------------


def test_row1_executable_hash_substitution_refused(tmp_path: Path) -> None:
    """Row 1: swap/bait the pinned executable -> the run is refused as an
    enforcement failure naming path + observed/expected digests; the swapped
    file never executes; there is no fallback path."""
    backend = PortableSandboxBackend()
    worker = tmp_path / "worker.sh"
    worker.write_text("#!/bin/sh\nexit 0\n")
    worker.chmod(0o755)
    pinned = digest_of(worker)
    profile = portable_profile(allowed_exec_hashes=((str(worker), pinned),))
    assert backend.supports(profile) is True

    marker = tmp_path / "bait-ran"
    worker.write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")  # bait: substitute content
    worker.chmod(0o755)

    result = run_portable(backend, (str(worker),), profile, tmp_path)
    assert result.exit_code == -1
    assert result.stdout == ""
    assert marker.exists() is False  # the swapped file never executed
    failures = [f for f in result.facts if f.kind is FactKind.ENFORCEMENT_FAILURE]
    assert len(failures) == 1
    assert failures[0].dimension == Dimension.EXECUTABLE_HASH.value
    assert str(worker) in failures[0].os_fact
    assert pinned in failures[0].os_fact
    assert digest_of(worker) in failures[0].os_fact


def test_row1_negation_pre_exec_recheck_is_load_bearing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Authoring-time negation for row 1: forcing the pre-exec digest observation
    to mismatch aborts before exec (sentinel + enforcement failure); removing
    the recheck lets the child exec. The discriminator is load-bearing."""
    from kernel import sandbox_backend as sb

    worker = tmp_path / "worker.sh"
    worker.write_text("#!/bin/sh\nexit 0\n")
    worker.chmod(0o755)
    pinned = digest_of(worker)
    profile = portable_profile(allowed_exec_hashes=((str(worker), pinned),))

    calls: list[str] = []

    def lying_after_first(path: Path) -> str:
        calls.append(str(path))
        return digest_of(path) if len(calls) <= 1 else "0" * 64

    monkeypatch.setattr(sb, "_sha256_file", lying_after_first)
    backend = PortableSandboxBackend()
    result = run_portable(backend, (str(worker),), profile, tmp_path)
    assert result.exit_code == sb._EXIT_HASH_MISMATCH
    assert any(
        f.kind is FactKind.ENFORCEMENT_FAILURE and "pre-exec recheck refused" in f.os_fact
        for f in result.facts
    )

    class _NoRecheckBackend(PortableSandboxBackend):
        def _make_preexec(self, rlimit_plan, expected_digest, resolved):  # type: ignore[no-untyped-def]
            return super()._make_preexec(rlimit_plan, None, resolved)

    backend_no_recheck = _NoRecheckBackend()
    calls.clear()
    result_no_recheck = run_portable(backend_no_recheck, (str(worker),), profile, tmp_path)
    # with the recheck removed the (genuine) pinned file execs: exit 0
    assert result_no_recheck.exit_code == 0


def test_row2_hostile_path_shadow_never_runs(tmp_path: Path) -> None:
    """Row 2: a hostile PATH shadows the target name -> the shadow never runs;
    the executed file is the kernel-resolved allowlisted binary."""
    evil_dir = tmp_path / "evil"
    evil_dir.mkdir()
    shadow = evil_dir / "true"
    shadow.write_text("#!/bin/sh\nexit 42\n")
    shadow.chmod(0o755)

    backend = PortableSandboxBackend()
    result = run_portable(
        backend,
        ("true",),
        portable_profile(),
        tmp_path,
        environment={"PATH": str(evil_dir)},
    )
    # /usr/bin/true exits 0; the shadow would have exited 42
    assert result.exit_code == 0
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# Behavioral rows 3-7: process fanout, CPU/memory/open-file/file-size exhaustion
# ---------------------------------------------------------------------------


def test_row3_child_fanout_group_cleanup(tmp_path: Path) -> None:
    """Row 3: grandchildren try to outlive the worker -> the whole tree is inside
    the dedicated group and none survive cleanup."""
    backend = PortableSandboxBackend()
    heartbeat = tmp_path / "hb"
    leader_script = FANOUT_LEADER.replace("SCRIPT", repr(HEARTBEAT))
    result = run_portable(
        backend, (PY, "-c", leader_script, str(heartbeat)), portable_profile(), tmp_path
    )
    assert result.exit_code == 0
    assert any(
        f.kind is FactKind.COMPLETION and "confirmed empty" in f.os_fact for f in result.facts
    )
    assert heartbeat_growth_stops(heartbeat)


def test_row3_negation_no_group_teardown_leaves_survivor(tmp_path: Path) -> None:
    """Authoring-time negation for row 3: with group teardown removed the
    grandchild survives and keeps writing — the row fails under the toggle."""

    class _NoTeardownBackend(PortableSandboxBackend):
        def _teardown_group(self, pgid, facts, grace: float = 2.0) -> None:  # type: ignore[no-untyped-def]
            facts.append(
                RunFact(
                    kind=FactKind.CLEANUP_ERROR,
                    dimension=None,
                    mechanism_id=None,
                    os_fact="teardown disabled by test negation",
                )
            )

    backend = _NoTeardownBackend()
    heartbeat = tmp_path / "hb"
    leader_script = FANOUT_LEADER.replace("SCRIPT", repr(HEARTBEAT))
    result = run_portable(
        backend, (PY, "-c", leader_script, str(heartbeat)), portable_profile(), tmp_path
    )
    assert result.exit_code == 0
    size_a = heartbeat.stat().st_size
    time.sleep(0.5)
    assert heartbeat.stat().st_size > size_a  # survivor still writing


def test_row4_cpu_exhaustion_fires_at_cap(tmp_path: Path) -> None:
    """Row 4: busy-loop past the cap -> terminated at the cap; fact names CPU."""
    backend = PortableSandboxBackend()
    profile = portable_profile(cpu_seconds=2, wallclock_seconds=10)
    result = run_portable(backend, (PY, "-c", "while True: pass"), profile, tmp_path)
    assert result.timed_out is False
    assert result.exit_code == -int(signal.SIGXCPU)
    assert any(
        f.kind is FactKind.CAP_FIRED
        and f.dimension == Dimension.CPU.value
        and "SIGXCPU" in f.os_fact
        for f in result.facts
    )


def test_row4_negation_no_cap_deadline_enforces(tmp_path: Path) -> None:
    """Authoring-time negation for row 4: with the CPU cap unrequested the same
    busy-loop is stopped only by the wallclock deadline — a different outcome,
    proving the rlimit is the CPU enforcement."""
    backend = PortableSandboxBackend()
    profile = portable_profile(cpu_seconds=0, wallclock_seconds=2)
    result = run_portable(backend, (PY, "-c", "while True: pass"), profile, tmp_path)
    assert result.timed_out is True
    assert result.exit_code == -1


def test_row5_memory_boundary_refused_strong_form(tmp_path: Path) -> None:
    """Row 5 (strong form on this host): the RLIMIT_AS probe shows the host
    rejects constraining address-space limits, so the memory boundary is REFUSED
    with a typed (MEMORY, rlimit_as) refusal — never a blind claim."""
    backend = PortableSandboxBackend()
    profile = portable_profile(memory_bytes=512 * 1024 * 1024)
    assert backend.supports(profile) is False
    negotiation = backend.negotiate(profile)
    assert negotiation.outcome is NegotiationOutcome.REFUSE
    assert any(
        u.dimension is Dimension.MEMORY and u.missing_mechanism == "rlimit_as"
        for u in negotiation.unsupported
    )
    again = backend.negotiate(profile)  # deterministic and re-runnable
    assert again == negotiation

    marker = tmp_path / "ran"
    with pytest.raises(SandboxProfileUnavailable) as excinfo:
        run_portable(backend, (PY, "-c", f"open({str(marker)!r}, 'w')"), profile, tmp_path)
    assert "SANDBOX_PROFILE_UNAVAILABLE" in str(excinfo.value)
    assert "MEMORY" in str(excinfo.value)
    assert marker.exists() is False  # no execution happened at all


def test_row6_open_file_exhaustion(tmp_path: Path) -> None:
    """Row 6: open FDs past the cap -> the child's open fails at OS level (EMFILE)."""
    backend = PortableSandboxBackend()
    child = (
        "import os,sys\n"
        "n=0\n"
        "try:\n"
        "    while True:\n"
        "        os.open('/dev/null', os.O_RDONLY); n+=1\n"
        "except OSError as exc:\n"
        "    print('EMFILE_AT', n)\n"
        "    sys.exit(exc.errno)\n"
    )
    result = run_portable(backend, (PY, "-c", child), portable_profile(open_files=64), tmp_path)
    assert result.exit_code == errno.EMFILE
    assert "EMFILE_AT" in result.stdout


def test_row7_file_size_exhaustion(tmp_path: Path) -> None:
    """Row 7: grow a file past the cap -> the write fails at OS level (EFBIG)."""
    backend = PortableSandboxBackend()
    target = tmp_path / "big.bin"
    child = (
        "import sys\n"
        "try:\n"
        f"    with open({str(target)!r}, 'wb') as f:\n"
        "        f.write(b'x' * (1024*1024))\n"
        "except OSError as exc:\n"
        "    sys.exit(exc.errno)\n"
    )
    result = run_portable(
        backend, (PY, "-c", child), portable_profile(file_size_bytes=4096), tmp_path
    )
    assert result.exit_code == errno.EFBIG
    assert target.stat().st_size <= 4096


# ---------------------------------------------------------------------------
# Behavioral rows 8-12: disk, wallclock, network, timeout cleanup, output caps
# ---------------------------------------------------------------------------


def test_row8_disk_refused_no_fsize_substitute(tmp_path: Path) -> None:
    """Row 8: no aggregate disk-quota primitive exists -> REFUSED naming DISK; the
    enforceable per-file size cap (the tempting weaker substitute) is never
    silently accepted as an aggregate boundary."""
    backend = PortableSandboxBackend()
    profile = portable_profile(disk_bytes=100 * 1024 * 1024, file_size_bytes=8 * 1024 * 1024)
    assert backend.supports(profile) is False
    negotiation = backend.negotiate(profile)
    assert any(
        u.dimension is Dimension.DISK and u.missing_mechanism == "aggregate_disk_quota"
        for u in negotiation.unsupported
    )
    assert Dimension.FILE_SIZE not in {u.dimension for u in negotiation.unsupported}
    marker = tmp_path / "ran"
    with pytest.raises(SandboxProfileUnavailable) as excinfo:
        run_portable(backend, (PY, "-c", f"open({str(marker)!r}, 'w')"), profile, tmp_path)
    assert "DISK" in str(excinfo.value)
    assert marker.exists() is False


def test_row9_wallclock_deadline_fires(tmp_path: Path) -> None:
    """Row 9: the supervisor deadline terminates a slow child."""
    backend = PortableSandboxBackend()
    result = run_portable(backend, ("sleep", "10"), portable_profile(wallclock_seconds=2), tmp_path)
    assert result.timed_out is True
    assert result.exit_code == -1
    assert any(
        f.kind is FactKind.CAP_FIRED and f.dimension == Dimension.WALLCLOCK_GROUP.value
        for f in result.facts
    )


def test_row10_forbidden_network_mode_discriminates(tmp_path: Path) -> None:
    """Row 10: loopback-only control — the same connect script succeeds under an
    allowed network profile and is denied under the forbidden mode via the
    Seatbelt backend; differing outcomes prove the boundary discriminates. The
    portable backend refuses the forbidden mode."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    port = listener.getsockname()[1]
    try:
        child = (
            "import socket,sys\n"
            "try:\n"
            f"    socket.create_connection(('127.0.0.1', {port}), timeout=3)\n"
            "    print('CONNECTED'); sys.exit(0)\n"
            "except OSError as exc:\n"
            "    print('NET_ERRNO', exc.errno); sys.exit(3)\n"
        )
        # control arm: network unbounded by explicit choice -> connects
        portable = PortableSandboxBackend()
        allowed = run_portable(portable, (PY, "-c", child), portable_profile(), tmp_path)
        assert allowed.exit_code == 0
        assert "CONNECTED" in allowed.stdout

        # the portable backend cannot enforce a forbidden mode: refused
        forbidden_profile = portable_profile(network_mode=NetworkMode.NONE)
        assert portable.supports(forbidden_profile) is False
        assert any(
            u.dimension is Dimension.NETWORK
            for u in portable.negotiate(forbidden_profile).unsupported
        )

        # treatment arm: seatbelt backend enforces the forbidden mode
        seatbelt = SeatbeltSandboxBackend()
        assert seatbelt.supports(forbidden_profile) is True
        denied = run_portable(seatbelt, (PY, "-c", child), forbidden_profile, tmp_path)
        assert denied.exit_code == 3
        assert "NET_ERRNO" in denied.stdout
        assert "CONNECTED" not in denied.stdout
    finally:
        listener.close()


def test_row11_timeout_process_group_cleanup_no_survivors(tmp_path: Path) -> None:
    """Row 11: timeout fires with children alive -> the whole group is cleaned,
    no survivors, cleanup reported honestly."""
    backend = PortableSandboxBackend()
    heartbeat = tmp_path / "hb"
    leader_script = SLEEPING_FANOUT_LEADER.replace("SCRIPT", repr(HEARTBEAT))
    result = run_portable(
        backend,
        (PY, "-c", leader_script, str(heartbeat)),
        portable_profile(wallclock_seconds=2),
        tmp_path,
    )
    assert result.timed_out is True
    assert result.exit_code == -1
    assert any(
        f.kind is FactKind.CAP_FIRED and f.dimension == Dimension.WALLCLOCK_GROUP.value
        for f in result.facts
    )
    assert any(
        f.kind is FactKind.COMPLETION and "confirmed empty" in f.os_fact for f in result.facts
    )
    assert heartbeat_growth_stops(heartbeat)


def test_row12_output_caps_truncation_fact(tmp_path: Path) -> None:
    """Row 12: emit beyond the cap -> output is truncated, a TRUNCATION fact is
    reported (never laundered as success), the stream is severed, the payload is
    bounded; no unbounded buffering."""
    backend = PortableSandboxBackend()
    child = (
        "import sys,time\n"
        "for _ in range(40):\n"
        "    sys.stdout.write('x' * (64*1024)); sys.stdout.flush()\n"
        "    time.sleep(0.05)\n"
    )
    profile = portable_profile(output_bytes=64 * 1024, wallclock_seconds=8)
    result = run_portable(backend, (PY, "-c", child), profile, tmp_path)
    assert len(result.stdout) <= 64 * 1024
    assert any(
        f.kind is FactKind.TRUNCATION
        and f.dimension == Dimension.OUTPUT_SIZE.value
        and f.mechanism_id == "capped_reader"
        for f in result.facts
    )


def test_row12_negation_unbounded_capture_when_cap_unrequested(tmp_path: Path) -> None:
    """Authoring-time negation for row 12: with the output cap unrequested the
    full ~2.5MB payload is captured with no truncation fact — proving the cap is
    what bounds the payload (and that absence is honored, never invented)."""
    backend = PortableSandboxBackend()
    child = "import sys\nfor _ in range(40):\n    sys.stdout.write('x' * (64*1024))\n"
    profile = portable_profile(output_bytes=0, wallclock_seconds=8)
    result = run_portable(backend, (PY, "-c", child), profile, tmp_path)
    assert result.exit_code == 0
    assert len(result.stdout) == 40 * 64 * 1024
    assert not any(f.kind is FactKind.TRUNCATION for f in result.facts)


# ---------------------------------------------------------------------------
# Rows 13-14: unavailable backend shapes; no-weaker-fallback
# ---------------------------------------------------------------------------


def test_row13_unavailable_backend_three_shapes(tmp_path: Path) -> None:
    """Row 13: all three unavailability shapes refuse with precise
    (dimension, missing_mechanism) and NO execution happens at all."""
    # shape (a): constructor failure — a registry that does not cover the
    # taxonomy fails loudly at construction (structural, never a silent subset)
    crippled = dict(build_claim_registry())
    del crippled[Dimension.CPU]
    with pytest.raises(RegistryCoverageError):
        PortableSandboxBackend(registry=crippled)

    # shape (b): supports() == False -> run raises the typed stop; no execution
    portable = PortableSandboxBackend()
    disk_profile = portable_profile(disk_bytes=100 * 1024 * 1024)
    assert portable.supports(disk_profile) is False
    marker = tmp_path / "ran"
    with pytest.raises(SandboxProfileUnavailable) as excinfo:
        run_portable(portable, (PY, "-c", f"open({str(marker)!r}, 'w')"), disk_profile, tmp_path)
    assert "DISK" in str(excinfo.value)
    assert marker.exists() is False

    # shape (c): OS-primitive absence — the Seatbelt primitive is absent, so its
    # dimensions are refused with their mechanism named
    absent = SeatbeltSandboxBackend(sandbox_exec="/nonexistent/sandbox-exec-xyz")
    net_profile = portable_profile(network_mode=NetworkMode.NONE)
    assert absent.supports(net_profile) is False
    refusal = absent.negotiate(net_profile)
    assert any(
        u.dimension is Dimension.NETWORK and u.missing_mechanism == "sandbox_exec_net"
        for u in refusal.unsupported
    )
    with pytest.raises(SandboxProfileUnavailable):
        run_portable(absent, (PY, "-c", "pass"), net_profile, tmp_path)


def test_row14_no_weaker_fallback(tmp_path: Path) -> None:
    """Row 14: a weaker substitute (the enforceable per-file size cap) is available
    and configured tempting, but the aggregate DISK request is never downgraded:
    the refusal names the missing dimension and no execution occurs."""
    calls: list[Dimension] = []

    def _counting(dim: Dimension, probe: Callable[[], ProbeOutcome]) -> Callable[[], ProbeOutcome]:
        def _wrapped() -> ProbeOutcome:
            calls.append(dim)
            return probe()

        return _wrapped

    registry = build_claim_registry()
    overrides = {
        dim: EnforcementClaim(
            dim,
            claim.mechanism_id,
            _counting(dim, claim.probe),
            caveat=claim.caveat,
        )
        for dim, claim in registry.items()
    }
    backend = PortableSandboxBackend(overrides=overrides)

    profile = portable_profile(disk_bytes=100 * 1024 * 1024)
    assert backend.supports(profile) is False
    # the weaker substitute (FILE_SIZE claim) was never consulted for the DISK
    # refusal — no cross-dimension substitution happened
    assert Dimension.FILE_SIZE not in calls
    refusal = backend.negotiate(profile)
    assert refusal.unsupported == (
        UnsupportedDimension(
            Dimension.DISK, "aggregate_disk_quota", caveat=refusal.unsupported[0].caveat
        ),
    )
    marker = tmp_path / "ran"
    with pytest.raises(SandboxProfileUnavailable):
        run_portable(backend, (PY, "-c", f"open({str(marker)!r}, 'w')"), profile, tmp_path)
    assert marker.exists() is False

    # the weaker (file-size-only) profile is enforceable, but that fact never
    # substitutes for the aggregate profile: run() refuses the profile it was given
    weaker = portable_profile(file_size_bytes=8 * 1024 * 1024)
    assert backend.supports(weaker) is True


# ---------------------------------------------------------------------------
# Structural rows: bijection, monotonicity, refusal honesty
# ---------------------------------------------------------------------------


def test_taxonomy_registry_bijection_fails_loudly() -> None:
    """An unclaimed dimension added to the taxonomy makes the coverage assertion
    fail loudly — the 'CPU+memory only' defect class cannot re-emerge silently."""
    from kernel.sandbox_backend import DIMENSIONS

    bogus_taxonomy = frozenset(set(DIMENSIONS) | {"BOGUS_DIMENSION"})
    with pytest.raises(RegistryCoverageError):
        assert_registry_covers(build_claim_registry(), bogus_taxonomy)  # type: ignore[arg-type]

    crippled = dict(build_claim_registry())
    del crippled[Dimension.CPU]
    with pytest.raises(RegistryCoverageError):
        assert_registry_covers(crippled)


def test_monotonicity_constraining_more_never_enforces() -> None:
    """P subset-of Q and supports(Q) => supports(P): constraining more never
    turns a refusal into an enforcement."""
    backend = PortableSandboxBackend()
    assert backend.supports(portable_profile()) is True  # sanity: empty request enforces
    refused_additions: list[dict[str, object]] = [
        {"memory_bytes": 512 * 1024 * 1024},
        {"disk_bytes": 100 * 1024 * 1024},
        {"process_count": 16},
        {"network_mode": NetworkMode.NONE},
        {"workspace_root": "/tmp"},
    ]
    for addition in refused_additions:
        assert backend.supports(portable_profile(**addition)) is False
    # a refused superset stays refused even though its enforceable subset is fine
    assert (
        backend.supports(
            portable_profile(disk_bytes=100 * 1024 * 1024, file_size_bytes=8 * 1024 * 1024)
        )
        is False
    )
    assert backend.supports(portable_profile(file_size_bytes=8 * 1024 * 1024)) is True


def test_refusal_honesty_probe_errors_never_pass_through() -> None:
    """An injected transient probe error must REFUSE naming the dimension —
    never free text, never a silent pass-through to execution."""

    def _exploding() -> ProbeOutcome:
        raise RuntimeError("transient infrastructure error")

    overrides = {Dimension.CPU: EnforcementClaim(Dimension.CPU, "rlimit_cpu", _exploding)}
    backend = PortableSandboxBackend(overrides=overrides)
    refusal = backend.negotiate(portable_profile(cpu_seconds=5))
    assert refusal.outcome is NegotiationOutcome.REFUSE
    assert len(refusal.unsupported) == 1
    entry = refusal.unsupported[0]
    assert entry.dimension is Dimension.CPU
    assert entry.missing_mechanism == "rlimit_cpu"
    assert entry.caveat is not None and "probe did not complete" in entry.caveat


# ---------------------------------------------------------------------------
# Caveat visibility, workspace-write enforcement, happy path, defect fix
# ---------------------------------------------------------------------------


def test_caveat_visibility() -> None:
    """Caveats surface where they must: the per-uid PROCESS_COUNT refusal and
    the seatbelt deprecation caveat are visible strings, never silent."""
    portable = PortableSandboxBackend()
    refusal = portable.negotiate(portable_profile(process_count=16))
    nproc = [u for u in refusal.unsupported if u.dimension is Dimension.PROCESS_COUNT]
    assert nproc and "per real-uid" in (nproc[0].caveat or "")

    seatbelt = SeatbeltSandboxBackend()
    net = seatbelt.negotiate(portable_profile(network_mode=NetworkMode.NONE))
    assert net.outcome is NegotiationOutcome.ENFORCE
    assert any("deprecated" in c for c in net.caveats)


def test_workspace_write_confined_by_seatbelt(tmp_path: Path) -> None:
    """WORKSPACE_WRITE: the portable backend refuses it (no primitive); the
    Seatbelt backend enforces it — inside writes succeed, outside writes are
    denied at the OS level."""
    portable = PortableSandboxBackend()
    ws_profile = portable_profile(workspace_root=str(tmp_path))
    assert portable.supports(ws_profile) is False
    assert any(
        u.dimension is Dimension.WORKSPACE_WRITE for u in portable.negotiate(ws_profile).unsupported
    )

    seatbelt = SeatbeltSandboxBackend()
    assert seatbelt.supports(ws_profile) is True
    outside = Path(
        tempfile.mkdtemp(prefix="paeos-ws-outside-")
    )  # genuinely outside the workspace subpath
    try:
        child = (
            "import sys\n"
            "inside_ok = False\n"
            "try:\n"
            f"    open({str(tmp_path / 'inside.txt')!r}, 'w').write('x'); inside_ok = True\n"
            "except OSError:\n"
            "    pass\n"
            "print('INSIDE_OK' if inside_ok else 'INSIDE_DENIED')\n"
            "try:\n"
            f"    open({str(outside / 'leak.txt')!r}, 'w').write('x'); "
            "print('OUTSIDE_WRITE_SUCCEEDED')\n"
            "except OSError as exc:\n"
            "    print('OUTSIDE_DENIED', exc.errno)\n"
        )
        result = run_portable(seatbelt, (PY, "-c", child), ws_profile, tmp_path)
        assert result.exit_code == 0
        assert "INSIDE_OK" in result.stdout
        assert "OUTSIDE_DENIED" in result.stdout
        assert "OUTSIDE_WRITE_SUCCEEDED" not in result.stdout
        assert (outside / "leak.txt").exists() is False
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def test_enforceable_profile_runs_and_reports_completion(tmp_path: Path) -> None:
    """Happy path (the defect fix in the positive direction): a profile whose
    requested dimensions are exactly the enforceable set runs and reports a
    group-confirmed-empty completion fact."""
    backend = PortableSandboxBackend()
    profile = portable_profile(
        cpu_seconds=5,
        open_files=128,
        file_size_bytes=8 * 1024 * 1024,
        output_bytes=1 * 1024 * 1024,
    )
    assert backend.supports(profile) is True
    result = run_portable(backend, ("echo", "sandboxed"), profile, tmp_path)
    assert result.exit_code == 0
    assert "sandboxed" in result.stdout
    assert any(f.kind is FactKind.COMPLETION for f in result.facts)
    assert not any(f.kind is FactKind.TRUNCATION for f in result.facts)


def test_supports_false_for_full_boundary_profile() -> None:
    """The exact defect: a profile requesting every boundary the old
    implementation ignored (memory, process-count, disk, forbidden network)
    must be REFUSED — the old `cpu>0 and mem>0` answer is gone."""
    backend = PortableSandboxBackend()
    profile = SandboxProfile(
        profile_id="SP-FULL",
        cpu_seconds=10,
        memory_bytes=512 * 1024 * 1024,
        process_count=16,
        open_files=128,
        file_size_bytes=32 * 1024 * 1024,
        disk_bytes=100 * 1024 * 1024,
        wallclock_seconds=15,
        network_mode=NetworkMode.NONE,
    )
    assert backend.supports(profile) is False
    refused = {u.dimension for u in backend.negotiate(profile).unsupported}
    assert {
        Dimension.MEMORY,
        Dimension.DISK,
        Dimension.PROCESS_COUNT,
        Dimension.NETWORK,
    } <= refused
