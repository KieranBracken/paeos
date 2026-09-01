"""Capability-detected sandbox backends and execution confinement (Gate E Task 5).

Frozen contract: `docs/superpowers/plans/2026-08-26-paeos-taskpackage-worker-confinement.md`
Task 5. The negotiation is **fail-closed over every requested boundary dimension**:
a backend answers `supports(profile)` with True only when it can *enforce* each
dimension the profile requests; otherwise it refuses with typed
`(dimension, missing_mechanism, caveat)` entries. There is deliberately **no weaker
fallback**: no alternate backend, no "closest profile", no silent downgrade — an
unenforceable profile stops at `SandboxProfileUnavailable` and never executes.

Preserved invariants:
- shell-free invocation (explicit argv lists, never a shell string);
- exact PATH/executable binding — the *kernel* resolves the executable against the
  allowlisted PATH and binds the resolved real path; the child's environment PATH
  is never consulted for binding, and a pinned executable is hash-checked both
  pre-fork and inside the pre-exec hook (no path substitution fallback);
- a dedicated process group with a wallclock deadline and a kill-the-whole-group
  teardown ladder, ESRCH-confirmed empty before the run is reported complete;
- conservative error reporting — typed mechanism-authored facts only; unknown or
  ambiguous outcomes are never reported as success; worker-emitted text is opaque
  payload.

Negotiation claims are **probe-backed, not asserted**: a dimension is claimed only
when a cheap probe (or, for heavyweight mechanisms, a process-lifetime-cached
empirical probe with fail-closed caching) demonstrates the enforcement primitive
on this host. Heavyweight probes run bounded sacrificial children *outside* any
worker execution path and are cached per process lifetime; any probe error is
treated as unavailability, never as a silent pass-through.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import os
import resource
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Protocol, cast

from kernel.sandbox import (
    FactKind,
    RunFact,
    SandboxError,
    SandboxResult,
    allowlisted_path,
)

__all__ = [
    "DIMENSIONS",
    "Dimension",
    "EnforcementClaim",
    "NegotiationOutcome",
    "NegotiationResult",
    "NetworkMode",
    "PortableSandboxBackend",
    "ProbeOutcome",
    "RegistryCoverageError",
    "SandboxBackend",
    "SandboxProfile",
    "SandboxProfileUnavailable",
    "SandboxedInvocation",
    "SeatbeltSandboxBackend",
    "UnsupportedDimension",
    "build_claim_registry",
    "negotiate",
]

_MB = 1024 * 1024


# ---------------------------------------------------------------------------
# Dimension taxonomy — the single source of dimension identity. The negotiation
# is *derived* from this taxonomy (never a hand-maintained whitelist), so the
# "CPU+memory only" defect class cannot re-emerge by omission: the registry must
# cover every dimension or construction fails loudly.
# ---------------------------------------------------------------------------


class Dimension(StrEnum):
    CPU = "CPU"
    MEMORY = "MEMORY"
    OPEN_FILES = "OPEN_FILES"
    FILE_SIZE = "FILE_SIZE"
    DISK = "DISK"
    PROCESS_COUNT = "PROCESS_COUNT"
    NETWORK = "NETWORK"
    EXECUTABLE_HASH = "EXECUTABLE_HASH"
    WORKSPACE_WRITE = "WORKSPACE_WRITE"
    WALLCLOCK_GROUP = "WALLCLOCK_GROUP"
    OUTPUT_SIZE = "OUTPUT_SIZE"


DIMENSIONS = frozenset(Dimension)

# Canonical deterministic order so negotiation results are stable and re-runnable.
_DIMENSION_ORDER: tuple[Dimension, ...] = (
    Dimension.CPU,
    Dimension.MEMORY,
    Dimension.OPEN_FILES,
    Dimension.FILE_SIZE,
    Dimension.DISK,
    Dimension.PROCESS_COUNT,
    Dimension.NETWORK,
    Dimension.EXECUTABLE_HASH,
    Dimension.WORKSPACE_WRITE,
    Dimension.WALLCLOCK_GROUP,
    Dimension.OUTPUT_SIZE,
)


class NetworkMode:
    """Profile network modes. Anything other than ALLOWED requests the forbidden
    boundary (unknown values are treated as the strictest request — fail closed)."""

    ALLOWED = "ALLOWED"
    NONE = "NONE"


class RegistryCoverageError(SandboxError):
    """The claim registry does not biject the dimension taxonomy (structural defect)."""


class SandboxProfileUnavailable(SandboxError):
    """Typed stop for an unenforceable profile — production halts with this; it never
    continues with a weaker backend or a downgraded boundary set."""

    def __init__(self, refusals: tuple[UnsupportedDimension, ...]) -> None:
        self.refusals = refusals
        detail = "; ".join(str(entry) for entry in refusals)
        super().__init__(f"SANDBOX_PROFILE_UNAVAILABLE: {detail}")


@dataclass(frozen=True, slots=True)
class SandboxProfile:
    """Immutable confinement request. A dimension is *requested* when its field is
    present/constraining; absent fields mean unbounded-by-explicit-choice — they
    never silently invent a default boundary."""

    profile_id: str
    cpu_seconds: int
    memory_bytes: int
    process_count: int
    open_files: int
    file_size_bytes: int
    disk_bytes: int
    wallclock_seconds: int
    network_mode: str
    allowed_exec_hashes: tuple[tuple[str, str], ...] = ()
    # Dimensions added by the ratified Gate E remediation (absent = unrequested):
    # `workspace_root` requests OS-enforced writes-confined-to-workspace; `output_bytes`
    # requests a per-stream captured-output byte cap.
    workspace_root: str | None = None
    output_bytes: int = 0

    def requested_dimensions(self) -> frozenset[Dimension]:
        requested: set[Dimension] = set()
        if self.cpu_seconds > 0:
            requested.add(Dimension.CPU)
        if self.memory_bytes > 0:
            requested.add(Dimension.MEMORY)
        if self.open_files > 0:
            requested.add(Dimension.OPEN_FILES)
        if self.file_size_bytes > 0:
            requested.add(Dimension.FILE_SIZE)
        if self.disk_bytes > 0:
            requested.add(Dimension.DISK)
        if self.process_count > 0:
            requested.add(Dimension.PROCESS_COUNT)
        if self.network_mode != NetworkMode.ALLOWED:
            requested.add(Dimension.NETWORK)
        if self.allowed_exec_hashes:
            requested.add(Dimension.EXECUTABLE_HASH)
        if self.workspace_root is not None:
            requested.add(Dimension.WORKSPACE_WRITE)
        if self.wallclock_seconds > 0:
            requested.add(Dimension.WALLCLOCK_GROUP)
        if self.output_bytes > 0:
            requested.add(Dimension.OUTPUT_SIZE)
        return frozenset(requested)


@dataclass(frozen=True, slots=True)
class SandboxedInvocation:
    argv: tuple[str, ...]
    cwd: Path
    profile: SandboxProfile
    stdin: bytes = b""
    environment: Mapping[str, str] = field(default_factory=dict[str, str])


class SandboxBackend(Protocol):
    def supports(self, profile: SandboxProfile) -> bool: ...
    def negotiate(self, profile: SandboxProfile) -> NegotiationResult: ...
    def run(self, invocation: SandboxedInvocation) -> SandboxResult: ...


# ---------------------------------------------------------------------------
# Negotiation vocabulary — exactly two terminals; REFUSE is terminal (no API on
# the result leads to execution).
# ---------------------------------------------------------------------------


class NegotiationOutcome(StrEnum):
    ENFORCE = "ENFORCE"
    REFUSE = "REFUSE"


@dataclass(frozen=True, slots=True)
class UnsupportedDimension:
    dimension: Dimension
    missing_mechanism: str
    caveat: str | None = None

    def __str__(self) -> str:
        text = f"{self.dimension.value}: missing {self.missing_mechanism}"
        if self.caveat:
            text += f" (caveat: {self.caveat})"
        return text


@dataclass(frozen=True, slots=True)
class NegotiationResult:
    outcome: NegotiationOutcome
    unsupported: tuple[UnsupportedDimension, ...]
    caveats: tuple[str, ...]

    @property
    def enforceable(self) -> bool:
        return self.outcome is NegotiationOutcome.ENFORCE


# ---------------------------------------------------------------------------
# Probe machinery. Cheap probes run per call; heavyweight empirical probes are
# cached per process lifetime with fail-closed caching (any error or doubt is
# unavailability — never a silent pass-through).
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    available: bool
    detail: str
    caveat: str | None = None


@dataclass(frozen=True, slots=True)
class EnforcementClaim:
    """One registry row: the enforcement mechanism offered for a dimension, the
    probe that earns the claim, and any visible caveat."""

    dimension: Dimension
    mechanism_id: str
    probe: Callable[[], ProbeOutcome]
    caveat: str | None = None


_LIFETIME_PROBE_CACHE: dict[str, ProbeOutcome] = {}


def _lifetime_cached(key: str, fn: Callable[[], ProbeOutcome]) -> Callable[[], ProbeOutcome]:
    """Wrap a heavyweight empirical probe: run once per process, cache the stable
    fact, and treat any internal error as unavailability (fail closed)."""

    def _probe() -> ProbeOutcome:
        if key in _LIFETIME_PROBE_CACHE:
            return _LIFETIME_PROBE_CACHE[key]
        try:
            outcome = fn()
        except Exception as exc:
            outcome = ProbeOutcome(
                available=False,
                detail=f"probe did not complete ({type(exc).__name__}); treated as unavailable",
                caveat="probe-error",
            )
        _LIFETIME_PROBE_CACHE[key] = outcome
        return outcome

    return _probe


def _round_trip_probe(res: int) -> Callable[[], ProbeOutcome]:
    """Set/get round-trip of an rlimit to the *currently inherited* value — the
    honest side-effect-free minimum for CPU/NOFILE/FSIZE class claims."""

    def _probe() -> ProbeOutcome:
        try:
            current = resource.getrlimit(res)
            resource.setrlimit(res, current)
            readback = resource.getrlimit(res)
        except (OSError, ValueError) as exc:
            return ProbeOutcome(False, f"setrlimit round-trip failed: {exc}")
        if readback != current:
            return ProbeOutcome(False, "setrlimit round-trip mismatched")
        return ProbeOutcome(True, "set/get round-trip verified")

    return _probe


def _run_probe_child(argv: list[str], *, timeout: float = 15.0) -> tuple[int, str]:
    """Run a bounded sacrificial probe child (never a worker run; loopback/ephemeral
    resources only). Returns (exit_code, stdout)."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return -1, ""
    return proc.returncode, proc.stdout.strip()


def _memory_probe() -> ProbeOutcome:
    """Empirical RLIMIT_AS probe: a bounded sacrificial child sets a constraining
    address-space cap and then attempts to allocate past it. The claim is earned
    only by an *observed* allocation denial — never a blind set/get round-trip."""
    cap = 64 * _MB
    alloc = 512 * _MB
    child = (
        "import resource,sys\n"
        "try:\n"
        f"    resource.setrlimit(resource.RLIMIT_AS, ({cap}, {cap}))\n"
        "except Exception as exc:\n"
        "    print('SET_FAILED', type(exc).__name__); sys.exit(0)\n"
        "try:\n"
        f"    bytearray({alloc})\n"
        "    print('ALLOC_SUCCEEDED'); sys.exit(0)\n"
        "except MemoryError:\n"
        "    print('ALLOC_DENIED'); sys.exit(0)\n"
    )
    _rc, out = _run_probe_child([sys.executable, "-c", child])
    if out.startswith("SET_FAILED"):
        return ProbeOutcome(
            False,
            f"host rejects constraining RLIMIT_AS ({out.split(' ', 1)[-1]})",
        )
    if out == "ALLOC_DENIED":
        return ProbeOutcome(True, "allocation beyond cap observed denied (MemoryError)")
    return ProbeOutcome(
        False,
        "allocation beyond the cap succeeded: RLIMIT_AS not enforced on this host",
    )


def _portable_network_probe() -> ProbeOutcome:
    return ProbeOutcome(
        False,
        "no portable network-denial primitive exists on this host class",
        caveat="a darwin Seatbelt backend enforces this via /usr/bin/sandbox-exec when present",
    )


def _portable_workspace_write_probe() -> ProbeOutcome:
    return ProbeOutcome(
        False,
        "no portable OS write-confinement primitive exists on this host class",
        caveat="realpath normalization alone is a supervisor-side check, not enforcement",
    )


_SEATBELT_PROBE_PY = "/usr/bin/python3"


def _seatbelt_profiles(sandbox_exec: str) -> ProbeOutcome:
    """Empirical Seatbelt probe (cached process-lifetime): a bounded sacrificial
    child under a deny-default generated profile must observe BOTH loopback
    network denial (EPERM) and out-of-workspace write denial (EPERM). Loopback
    and ephemeral temporary paths only — never the internet."""
    if not (os.path.isfile(sandbox_exec) and os.access(sandbox_exec, os.X_OK)):
        return ProbeOutcome(False, f"{sandbox_exec} absent or not executable")
    if not os.access(_SEATBELT_PROBE_PY, os.X_OK):
        return ProbeOutcome(
            False,
            f"{_SEATBELT_PROBE_PY} unavailable for the enforcement probe child",
        )
    probe_target = str(
        Path(tempfile.gettempdir())
        / f"paeos-seatbelt-probe-{os.getpid()}-{time.monotonic_ns()}.txt"
    )
    child = (
        "import socket,sys\n"
        "try:\n"
        "    socket.create_connection(('127.0.0.1', 9), timeout=2)\n"
        "    print('NET_CONNECTED')\n"
        "except OSError as exc:\n"
        "    print('NET_ERR', exc.errno)\n"
        "try:\n"
        f"    open({probe_target!r}, 'w').write('x')\n"
        "    print('WRITE_SUCCEEDED')\n"
        "except OSError as exc:\n"
        "    print('WRITE_ERR', exc.errno)\n"
    )
    profile = "\n".join(
        [
            "(version 1)",
            "(deny default)",
            "(allow file-read*)",
            "(allow process-exec)",
            "(allow process-fork)",
            "(allow mach-lookup)",
            "(allow signal)",
            "(allow sysctl*)",
            "(deny network*)",
        ]
    )
    rc, out = _run_probe_child([sandbox_exec, "-p", profile, _SEATBELT_PROBE_PY, "-c", child])
    with contextlib.suppress(OSError):
        os.unlink(
            probe_target
        )  # best-effort probe cleanup; a stray probe file is not a confinement fact
    lines = out.splitlines()
    net_line = lines[0].strip() if lines else ""
    write_line = lines[1].strip() if len(lines) > 1 else ""
    if rc != 0 or not net_line.startswith("NET_ERR "):
        return ProbeOutcome(
            False,
            f"sandbox-exec enforcement probe failed (rc={rc}, out={out!r})",
        )
    if net_line.split()[1] != str(errno.EPERM):
        return ProbeOutcome(
            False,
            "loopback connection under seatbelt deny-network was not EPERM "
            f"(got {net_line.split()[1]})",
        )
    if write_line != f"WRITE_ERR {errno.EPERM}":
        return ProbeOutcome(
            False,
            "out-of-workspace write under seatbelt deny-default was not EPERM "
            f"(got {write_line!r})",
        )
    return ProbeOutcome(
        True,
        "observed loopback EPERM and out-of-workspace write EPERM under the generated profile",
        caveat=(
            "enforced via /usr/bin/sandbox-exec (Apple-deprecated Seatbelt interface; "
            "exact-path pinned by the backend)"
        ),
    )


# ---------------------------------------------------------------------------
# Single claim registry — the single source of truth BOTH `supports()` inspects
# and `run()` enforces (inspected == enforced). There is deliberately no walk to
# alternate or weaker substitutes. `sandbox_exec=None` yields the portable claims;
# a concrete `sandbox_exec` path yields the darwin Seatbelt claims for NETWORK,
# WORKSPACE_WRITE, and exec-restricted EXECUTABLE_HASH.
# ---------------------------------------------------------------------------

_PROCESS_COUNT_CAVEAT = (
    "RLIMIT_NPROC applies per real-uid (all processes of the uid), not per worker; "
    "no per-worker process-count primitive is available, so the boundary is refused"
)
_DISK_CAVEAT = (
    "no portable aggregate disk-quota primitive exists; a per-file size cap is not "
    "an aggregate substitute and is never silently used as one"
)
_EXEC_HASH_CAVEAT = (
    "residual fork->exec substitution window: the pre-exec recheck narrows it but no "
    "fd-bound exec (fexecve) is reachable from the Python standard library"
)


def build_claim_registry(
    sandbox_exec: str | None = None,
    overrides: Mapping[Dimension, EnforcementClaim] | None = None,
) -> Mapping[Dimension, EnforcementClaim]:
    """Build the claim registry for a backend. `overrides` exists for test
    injection (crippled registries / stubbed-absent probes) — never for production
    downgrades: an override cannot make an unprobed mechanism claimable."""
    claims: dict[Dimension, EnforcementClaim] = {
        Dimension.CPU: EnforcementClaim(
            Dimension.CPU,
            "rlimit_cpu",
            _round_trip_probe(resource.RLIMIT_CPU),
            caveat="SIGXCPU advisory at soft; enforcement is the hard cap (soft=hard=cap applied)",
        ),
        Dimension.MEMORY: EnforcementClaim(
            Dimension.MEMORY,
            "rlimit_as",
            _lifetime_cached("memory_rlimit_as", _memory_probe),
            caveat="claim requires observed allocation denial at the cap, not a blind set/get",
        ),
        Dimension.OPEN_FILES: EnforcementClaim(
            Dimension.OPEN_FILES,
            "rlimit_nofile",
            _round_trip_probe(resource.RLIMIT_NOFILE),
            caveat=(
                "exact cap enforced; a requested soft limit above the inherited hard "
                "ceiling is refused, never silently mis-capped"
            ),
        ),
        Dimension.FILE_SIZE: EnforcementClaim(
            Dimension.FILE_SIZE,
            "rlimit_fsize",
            _round_trip_probe(resource.RLIMIT_FSIZE),
            caveat="per-file size cap — distinct from any aggregate disk boundary",
        ),
        Dimension.DISK: EnforcementClaim(
            Dimension.DISK,
            "aggregate_disk_quota",
            lambda: ProbeOutcome(
                False, "no aggregate disk-quota primitive on this host", caveat=_DISK_CAVEAT
            ),
            caveat=_DISK_CAVEAT,
        ),
        Dimension.PROCESS_COUNT: EnforcementClaim(
            Dimension.PROCESS_COUNT,
            "rlimit_nproc",
            lambda: ProbeOutcome(
                False,
                "per-uid semantics demonstrated on this host class; not a per-worker boundary",
                caveat=_PROCESS_COUNT_CAVEAT,
            ),
            caveat=_PROCESS_COUNT_CAVEAT,
        ),
    }
    claims.update(_rlimit_independent_claims())
    if sandbox_exec is None:
        claims[Dimension.NETWORK] = EnforcementClaim(
            Dimension.NETWORK,
            "network_confinement_primitive",
            _portable_network_probe,
            caveat="the portable backend cannot deny network access",
        )
        claims[Dimension.WORKSPACE_WRITE] = EnforcementClaim(
            Dimension.WORKSPACE_WRITE,
            "os_write_confinement",
            _portable_workspace_write_probe,
            caveat="the portable backend cannot confine writes to a workspace",
        )
    else:
        claims[Dimension.NETWORK] = EnforcementClaim(
            Dimension.NETWORK,
            "sandbox_exec_net",
            _lifetime_cached(
                f"seatbelt_net:{sandbox_exec}", lambda: _seatbelt_profiles(sandbox_exec)
            ),
            caveat="darwin Seatbelt deny-default generated profile; Apple-deprecated interface",
        )
        claims[Dimension.WORKSPACE_WRITE] = EnforcementClaim(
            Dimension.WORKSPACE_WRITE,
            "sandbox_exec_file_write",
            _lifetime_cached(
                f"seatbelt_ws:{sandbox_exec}", lambda: _seatbelt_profiles(sandbox_exec)
            ),
            caveat=(
                "writes allowed only inside the resolved workspace subpath; "
                "all else denied by default"
            ),
        )
    if overrides:
        for dim, claim in overrides.items():
            claims[dim] = claim
    return claims


def _rlimit_independent_claims() -> dict[Dimension, EnforcementClaim]:
    has_group_primitives = hasattr(os, "setpgrp") and hasattr(os, "killpg")
    return {
        Dimension.EXECUTABLE_HASH: EnforcementClaim(
            Dimension.EXECUTABLE_HASH,
            "exec_double_check",
            lambda: ProbeOutcome(True, "pre-fork + pre-exec hash double-check available"),
            caveat=_EXEC_HASH_CAVEAT,
        ),
        Dimension.WALLCLOCK_GROUP: EnforcementClaim(
            Dimension.WALLCLOCK_GROUP,
            "process_group_deadline",
            lambda: ProbeOutcome(
                has_group_primitives,
                "setsid/killpg process-group supervision available"
                if has_group_primitives
                else "process-group primitives unavailable",
            ),
            caveat=(
                "deadline enforced by supervisor SIGKILL of the dedicated group, then ESRCH confirm"
            ),
        ),
        Dimension.OUTPUT_SIZE: EnforcementClaim(
            Dimension.OUTPUT_SIZE,
            "capped_reader",
            lambda: ProbeOutcome(True, "bounded in-process stream reader with severing"),
            caveat=(
                "streams are severed at the cap; truncation is reported as a fact, "
                "never laundered as success"
            ),
        ),
    }


def assert_registry_covers(
    registry: Mapping[Dimension, EnforcementClaim],
    dimensions: frozenset[Dimension] = DIMENSIONS,
) -> None:
    """Taxonomy <=> registry bijection. Called at import and at every backend
    construction: an unclaimed dimension (or a claim for an unknown dimension)
    fails loudly instead of silently narrowing negotiation."""
    missing = dimensions - frozenset(registry)
    unknown = frozenset(registry) - dimensions
    if missing or unknown:
        raise RegistryCoverageError(
            "claim registry does not cover the dimension taxonomy: "
            f"missing={sorted(getattr(d, 'value', d) for d in missing)} "
            f"unknown={sorted(getattr(d, 'value', d) for d in unknown)}"
        )


# ---------------------------------------------------------------------------
# The negotiation — a pure function of (profile, registry); deterministic and
# re-runnable; monotone by construction (constraining more never ENFORCEs a
# profile whose subset was REFUSEd). The first missing claim short-circuits to
# REFUSE while the refusal still enumerates every requested-but-unavailable pair.
# ---------------------------------------------------------------------------


def negotiate(
    profile: SandboxProfile,
    registry: Mapping[Dimension, EnforcementClaim],
) -> NegotiationResult:
    unsupported: list[UnsupportedDimension] = []
    caveats: list[str] = []
    requested = profile.requested_dimensions()
    for dim in _DIMENSION_ORDER:
        if dim not in requested:
            continue
        claim = registry[dim]
        try:
            outcome = claim.probe()
        except Exception as exc:
            outcome = ProbeOutcome(
                available=False,
                detail=f"probe did not complete ({type(exc).__name__}); treated as unavailable",
                caveat="probe-error",
            )
        parts: list[str] = []
        for c in (claim.caveat, outcome.caveat):
            if c and c not in parts:
                parts.append(c)
        if not outcome.available:
            detail = outcome.detail
            if parts:
                detail = f"{detail}; " + "; ".join(parts)
            unsupported.append(UnsupportedDimension(dim, claim.mechanism_id, caveat=detail))
            continue
        caveats.extend(c for c in parts if c not in caveats)
        # Exactness guard for OPEN_FILES: a claim that would silently clamp the
        # cap below the requested value is a downgrade — refuse instead.
        if dim is Dimension.OPEN_FILES:
            hard = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            if profile.open_files > hard:
                unsupported.append(
                    UnsupportedDimension(
                        dim,
                        claim.mechanism_id,
                        caveat=(
                            f"requested soft limit {profile.open_files} exceeds inherited hard "
                            f"ceiling {hard}; refusing rather than mis-capping"
                        ),
                    )
                )
    return NegotiationResult(
        NegotiationOutcome.REFUSE if unsupported else NegotiationOutcome.ENFORCE,
        tuple(unsupported),
        tuple(caveats),
    )


# ---------------------------------------------------------------------------
# Execution machinery: exact binding, pre-exec plan, capped reader, teardown.
# ---------------------------------------------------------------------------

# Pre-exec sentinel exits (the child aborts *before* exec, so the worker never
# runs): a sentinel exit means the confinement plan itself failed — the parent
# reports a typed enforcement fact, never a task result.
_EXIT_GROUP_FAILED = 96
_EXIT_HASH_MISMATCH = 97
_EXIT_RLIMIT_FAILED = 98


def _resolve_executable(argv0: str, cwd: Path) -> Path:
    """Kernel-side canonical resolution. The child's environment PATH is never
    consulted for binding: a bare name resolves against the allowlisted PATH
    only; an explicit path binds to its resolved real path (symlink residue
    eliminated by realpath). No PATH lookup ever happens for binding."""
    candidate = Path(argv0)
    if not candidate.is_absolute() and "/" not in argv0:
        for directory in allowlisted_path().split(os.pathsep):
            found = Path(directory) / argv0
            if found.is_file() and os.access(found, os.X_OK):
                candidate = found
                break
        else:
            raise SandboxError(f"could not resolve {argv0!r} against the allowlisted PATH")
    elif not candidate.is_absolute():
        candidate = cwd / candidate
    resolved = Path(os.path.realpath(candidate))
    if not (resolved.is_file() and os.access(resolved, os.X_OK)):
        raise SandboxError(f"resolved executable is not runnable: {resolved}")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_pins(pins: tuple[tuple[str, str], ...], cwd: Path) -> dict[Path, str]:
    """Normalize `(exe, sha256_hex)` pins to resolved-path -> digest."""
    normalized: dict[Path, str] = {}
    for exe, digest in pins:
        normalized[_resolve_executable(exe, cwd)] = digest.lower()
    return normalized


def _fact(kind: FactKind, dimension: str | None, mechanism: str | None, os_fact: str) -> RunFact:
    return RunFact(kind=kind, dimension=dimension, mechanism_id=mechanism, os_fact=os_fact)


def _seatbelt_profile_text(
    profile: SandboxProfile,
    pinned_paths: tuple[Path, ...],
) -> str:
    """Generate the darwin Seatbelt profile for a negotiated request. Deny-default;
    every unrequested boundary class is explicitly re-allowed so that
    unbounded-by-explicit-choice stays exactly that (never an invented default)."""
    lines = [
        "(version 1)",
        "(deny default)",
        "(allow file-read*)",
        "(allow process-fork)",
        "(allow mach-lookup)",
        "(allow signal)",
        "(allow sysctl*)",
    ]
    if pinned_paths:
        lines.extend(f'(allow process-exec (path "{path}"))' for path in pinned_paths)
    else:
        lines.append("(allow process-exec)")
    if profile.workspace_root is not None:
        workspace = Path(os.path.realpath(profile.workspace_root))
        lines.append(f'(allow file-write* (subpath "{workspace}"))')
    else:
        lines.append("(allow file-write*)")
    if profile.network_mode == NetworkMode.ALLOWED:
        lines.append("(allow network*)")
    else:
        lines.append("(deny network*)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The confining backend. `supports()` is a thin boolean view of the negotiation;
# `run()` executes the negotiated profile verbatim and is the only execution
# path: it re-negotiates internally, and an unenforceable profile raises the
# typed stop `SandboxProfileUnavailable` — never a weaker substitute run.
# ---------------------------------------------------------------------------


class _ConfiningBackend:
    _registry: Mapping[Dimension, EnforcementClaim]

    def __init__(
        self,
        registry: Mapping[Dimension, EnforcementClaim],
    ) -> None:
        assert_registry_covers(registry)
        self._registry = registry

    # -- negotiation ------------------------------------------------------

    def negotiate(self, profile: SandboxProfile) -> NegotiationResult:
        return negotiate(profile, self._registry)

    def supports(self, profile: SandboxProfile) -> bool:
        return self.negotiate(profile).enforceable

    # -- binding (overridable seams for authoring-time negation tests only) --

    def _pre_fork_binding_checks(self, resolved: Path, pins: dict[Path, str]) -> RunFact | None:
        """Pre-fork hash binding: fast refusal before any child exists. Returns an
        ENFORCEMENT_FAILURE fact when the binding fails, else None. Never falls
        back to an alternate path."""
        if pins and resolved not in pins:
            return _fact(
                FactKind.ENFORCEMENT_FAILURE,
                Dimension.EXECUTABLE_HASH.value,
                "exec_double_check",
                f"executable {resolved} is not pinned by the profile; refusing to run",
            )
        if pins:
            observed = _sha256_file(resolved)
            expected = pins[resolved]
            if observed != expected:
                return _fact(
                    FactKind.ENFORCEMENT_FAILURE,
                    Dimension.EXECUTABLE_HASH.value,
                    "exec_double_check",
                    "executable "
                    f"{resolved} digest mismatch: observed {observed}, expected {expected}",
                )
        return None

    def _make_preexec(
        self,
        rlimit_plan: tuple[tuple[int, int], ...],
        expected_digest: str | None,
        resolved: Path,
    ) -> Callable[[], None]:
        """The single ordered pre-exec plan, applied between fork and exec so the
        first instruction the worker executes is already fully confined and every
        child inherits each boundary. Each step verifies its own application and
        aborts before exec on failure — no step has a weaker substitute."""

        def _preexec() -> None:
            os.setpgrp()
            if os.getpgrp() != os.getpid():
                os._exit(_EXIT_GROUP_FAILED)
            for res, cap in rlimit_plan:
                try:
                    resource.setrlimit(res, (cap, cap))
                    readback = resource.getrlimit(res)
                except (OSError, ValueError):
                    os._exit(_EXIT_RLIMIT_FAILED)
                if readback != (cap, cap):
                    os._exit(_EXIT_RLIMIT_FAILED)
            if expected_digest is not None and _sha256_file(resolved) != expected_digest:
                os._exit(_EXIT_HASH_MISMATCH)

        return _preexec

    # -- the only execution path ------------------------------------------

    def _compose_argv(
        self,
        resolved: Path,
        rest: tuple[str, ...],
        profile: SandboxProfile,
        pinned: tuple[Path, ...],
    ) -> list[str]:
        raise NotImplementedError

    def run(self, invocation: SandboxedInvocation) -> SandboxResult:
        profile = invocation.profile
        negotiation = self.negotiate(profile)
        if not negotiation.enforceable:
            # Fail-closed internal negotiate-and-stop: an un-negotiated or
            # unenforceable call is a typed programming stop, never a weaker run.
            raise SandboxProfileUnavailable(negotiation.unsupported)

        resolved = _resolve_executable(invocation.argv[0], invocation.cwd)
        pins: dict[Path, str] = (
            _normalize_pins(profile.allowed_exec_hashes, invocation.cwd)
            if profile.allowed_exec_hashes
            else {}
        )
        binding_failure = self._pre_fork_binding_checks(resolved, pins)
        if binding_failure is not None:
            # The swapped/baited executable never executes; no alternate path.
            return SandboxResult(exit_code=-1, stdout="", timed_out=False, facts=(binding_failure,))

        rlimit_plan: tuple[tuple[int, int], ...] = tuple(
            (res, cap)
            for res, cap in (
                (resource.RLIMIT_CPU, profile.cpu_seconds),
                (resource.RLIMIT_NOFILE, profile.open_files),
                (resource.RLIMIT_FSIZE, profile.file_size_bytes),
            )
            if cap > 0
        )
        expected_digest = pins.get(resolved) if pins else None
        argv = self._compose_argv(resolved, tuple(invocation.argv[1:]), profile, tuple(pins))
        env = dict(invocation.environment) if invocation.environment else {}
        env.setdefault("PATH", allowlisted_path())
        env.setdefault("LC_ALL", "C")

        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE if invocation.stdin else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=self._make_preexec(rlimit_plan, expected_digest, resolved),
                cwd=str(invocation.cwd),
                env=env,
            )
        except (FileNotFoundError, OSError) as exc:
            raise SandboxError(f"could not launch {argv[0]!r}: {exc}") from exc

        if invocation.stdin and proc.stdin is not None:
            with contextlib.suppress(BrokenPipeError, OSError):
                proc.stdin.write(invocation.stdin)
            with contextlib.suppress(BrokenPipeError, OSError, ValueError):
                proc.stdin.close()

        pgid = proc.pid  # the pre-exec plan put the child in a dedicated group
        cap = profile.output_bytes if profile.output_bytes > 0 else None
        deadline = (
            time.monotonic() + profile.wallclock_seconds if profile.wallclock_seconds > 0 else None
        )
        facts: list[RunFact] = []
        out_buf, err_buf, timed_out = self._capture_streams(proc, cap, deadline, facts)

        if timed_out:
            facts.append(
                _fact(
                    FactKind.CAP_FIRED,
                    Dimension.WALLCLOCK_GROUP.value,
                    "process_group_deadline",
                    f"wallclock deadline {profile.wallclock_seconds}s exceeded; "
                    "group killed via SIGKILL ladder",
                )
            )
            self._kill_group(pgid, facts)
        rc = proc.wait()
        self._teardown_group(pgid, facts)
        out_buf = self._drain(cast(BinaryIO, proc.stdout), out_buf, cap)
        err_buf = self._drain(cast(BinaryIO, proc.stderr), err_buf, cap)
        # Structural invariant: the capped readers never return more than the cap
        # (truncation facts were already emitted at sever time; this is a trim,
        # never a silent truncation).
        if cap is not None:
            del out_buf[cap:]
            del err_buf[cap:]
        self._report_exit(rc, timed_out, resolved, pins.get(resolved), facts)
        return SandboxResult(
            exit_code=-1 if timed_out else rc,
            stdout=bytes(out_buf).decode("utf-8", errors="replace"),
            timed_out=timed_out,
            stderr=bytes(err_buf).decode("utf-8", errors="replace"),
            facts=tuple(facts),
        )

    # -- capped capture: bounded buffering, severing, truncation facts --------

    def _capture_streams(
        self,
        proc: subprocess.Popen[bytes],
        cap: int | None,
        deadline: float | None,
        facts: list[RunFact],
    ) -> tuple[bytearray, bytearray, bool]:
        out_buf = bytearray()
        err_buf = bytearray()
        streams: dict[BinaryIO, tuple[str, bytearray]] = {}
        selector = selectors.DefaultSelector()
        if proc.stdout is not None:
            stdout = cast(BinaryIO, proc.stdout)
            streams[stdout] = ("stdout", out_buf)
            selector.register(stdout, selectors.EVENT_READ)
        if proc.stderr is not None:
            stderr = cast(BinaryIO, proc.stderr)
            streams[stderr] = ("stderr", err_buf)
            selector.register(stderr, selectors.EVENT_READ)

        timed_out = False
        while True:
            if not streams and proc.poll() is not None:
                break
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if proc.poll() is None:
                        timed_out = True
                    break
                timeout = min(0.25, remaining)
            else:
                timeout = 0.25
            events = selector.select(timeout) if streams else []
            if not events:
                if proc.poll() is not None:
                    break  # leader done — never wait on grandchild-inherited write ends
                continue
            for key, _mask in events:
                stream = cast(BinaryIO, key.fileobj)
                name, buf = streams[stream]
                room = (cap - len(buf)) if cap is not None else 65536
                if room <= 0:
                    assert cap is not None
                    self._close_at_cap(stream, name, buf, cap, facts, selector, streams)
                    continue
                chunk = os.read(stream.fileno(), min(65536, room))
                if chunk == b"":
                    self._close_stream(stream, selector, streams)
                    continue
                buf += chunk
                if cap is not None and len(buf) >= cap:
                    self._close_at_cap(stream, name, buf, cap, facts, selector, streams)
        return out_buf, err_buf, timed_out

    def _close_stream(
        self,
        stream: BinaryIO,
        selector: selectors.BaseSelector,
        streams: dict[BinaryIO, tuple[str, bytearray]],
    ) -> None:
        with contextlib.suppress(KeyError, ValueError):
            selector.unregister(stream)
        with contextlib.suppress(OSError, ValueError):
            stream.close()  # type: ignore[attr-defined]
        streams.pop(stream, None)

    def _close_at_cap(
        self,
        stream: BinaryIO,
        name: str,
        buf: bytearray,
        cap: int,
        facts: list[RunFact],
        selector: selectors.BaseSelector,
        streams: dict[BinaryIO, tuple[str, bytearray]],
    ) -> None:
        """The stream reached the cap. Probe once for EOF: a clean EOF at the cap
        is completion; anything else is overflow — reported as a TRUNCATION fact
        and the stream is cut (the writer sees EPIPE). Never unbounded buffering."""
        import select as _select

        readable, _, _ = _select.select([stream.fileno()], [], [], 0.05)
        overflow = False
        if readable:
            extra = os.read(stream.fileno(), 1)
            if extra == b"":
                self._close_stream(stream, selector, streams)
                return
            overflow = True
        facts.append(
            _fact(
                FactKind.TRUNCATION,
                Dimension.OUTPUT_SIZE.value,
                "capped_reader",
                f"{name} cut at cap {cap}: observed "
                f"{'>' if overflow else '>='} {len(buf)} bytes; stream severed",
            )
        )
        self._close_stream(stream, selector, streams)

    def _drain(self, pipe: BinaryIO | None, buf: bytearray, cap: int | None) -> bytearray:
        """After the teardown ladder confirms the group empty every pipe writer is
        dead: drain remaining buffered bytes up to the cap, non-blocking."""
        if pipe is None or pipe.closed:
            return buf
        fd = pipe.fileno()
        with contextlib.suppress(OSError, ValueError):
            os.set_blocking(fd, False)
        try:
            while True:
                room = (cap - len(buf)) if cap is not None else 65536
                if room <= 0:
                    break
                chunk = os.read(fd, min(65536, room))
                if not chunk:
                    break
                buf += chunk
        except (OSError, BlockingIOError):
            pass
        with contextlib.suppress(OSError, ValueError):
            pipe.close()
        return buf

    # -- teardown ladder: kill group -> grace -> confirm empty (ESRCH) --------

    def _kill_group(self, pgid: int, facts: list[RunFact]) -> None:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # already empty — confirmed by the ESRCH probe below
        except OSError as exc:
            facts.append(
                _fact(
                    FactKind.CLEANUP_ERROR,
                    None,
                    "killpg_ladder",
                    f"killpg SIGKILL failed: errno {exc.errno}",
                )
            )

    def _teardown_group(self, pgid: int, facts: list[RunFact], grace: float = 2.0) -> None:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            facts.append(
                _fact(
                    FactKind.COMPLETION,
                    None,
                    "killpg_ladder",
                    "group confirmed empty (ESRCH on killpg probe)",
                )
            )
            return
        except OSError as exc:
            facts.append(
                _fact(
                    FactKind.CLEANUP_ERROR,
                    None,
                    "killpg_ladder",
                    f"killpg probe failed: errno {exc.errno}",
                )
            )
            return
        self._kill_group(pgid, facts)
        end = time.monotonic() + grace
        while True:
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                facts.append(
                    _fact(
                        FactKind.COMPLETION,
                        None,
                        "killpg_ladder",
                        "remaining group members killed; group confirmed empty (ESRCH)",
                    )
                )
                return
            except OSError as exc:
                facts.append(
                    _fact(
                        FactKind.CLEANUP_ERROR,
                        None,
                        "killpg_ladder",
                        f"killpg probe failed: errno {exc.errno}",
                    )
                )
                return
            if time.monotonic() >= end:
                facts.append(
                    _fact(
                        FactKind.CLEANUP_ERROR,
                        None,
                        "killpg_ladder",
                        "group not confirmed empty within teardown grace; survivors may exist",
                    )
                )
                return
            time.sleep(0.05)

    def _report_exit(
        self,
        rc: int,
        timed_out: bool,
        resolved: Path,
        expected_digest: str | None,
        facts: list[RunFact],
    ) -> None:
        """Map the observed exit to typed mechanism facts. Signals and the parent's
        own re-hash are mechanism-observed; worker-emitted text is never parsed."""
        if timed_out:
            return
        if rc == _EXIT_HASH_MISMATCH:
            observed = _sha256_file(resolved)
            if expected_digest is not None and observed != expected_digest:
                facts.append(
                    _fact(
                        FactKind.ENFORCEMENT_FAILURE,
                        Dimension.EXECUTABLE_HASH.value,
                        "exec_double_check",
                        f"pre-exec recheck refused swap of {resolved}: observed {observed}, "
                        f"expected {expected_digest}",
                    )
                )
            else:
                facts.append(
                    _fact(
                        FactKind.CLEANUP_ERROR,
                        Dimension.EXECUTABLE_HASH.value,
                        "exec_double_check",
                        "pre-exec recheck aborted with a matching parent-side digest "
                        "(ambiguous); reported as failure",
                    )
                )
            return
        if rc == _EXIT_GROUP_FAILED:
            facts.append(
                _fact(
                    FactKind.ENFORCEMENT_FAILURE,
                    None,
                    "process_group_deadline",
                    "pre-exec dedicated process-group setup failed; child never executed",
                )
            )
            return
        if rc == _EXIT_RLIMIT_FAILED:
            facts.append(
                _fact(
                    FactKind.ENFORCEMENT_FAILURE,
                    None,
                    "rlimit_preexec",
                    "pre-exec rlimit round-trip failed; child never executed",
                )
            )
            return
        if rc < 0:
            sig = -rc
            if sig == int(signal.SIGXCPU):
                facts.append(
                    _fact(
                        FactKind.CAP_FIRED,
                        Dimension.CPU.value,
                        "rlimit_cpu",
                        "terminated by SIGXCPU at the hard CPU cap",
                    )
                )
            elif sig == int(signal.SIGXFSZ):
                facts.append(
                    _fact(
                        FactKind.CAP_FIRED,
                        Dimension.FILE_SIZE.value,
                        "rlimit_fsize",
                        "terminated by SIGXFSZ at the file-size cap",
                    )
                )
            else:
                facts.append(_fact(FactKind.CAP_FIRED, None, None, f"terminated by signal {sig}"))


# ---------------------------------------------------------------------------
# Concrete backends. Neither consults the other, a "closest profile", or any
# weaker substitute: the caller selects a backend explicitly, and that backend
# enforces the negotiated profile verbatim or refuses.
# ---------------------------------------------------------------------------


class PortableSandboxBackend(_ConfiningBackend):
    """Portable OS resource-limited execution backend. It claims ONLY what its
    probes demonstrate on this host; every requested dimension it cannot enforce
    (process-count, disk, network, workspace-write, and — where the RLIMIT_AS
    probe shows no observable enforcement — memory) yields a typed refusal, and
    `supports(profile)` is False: there is no weaker silent fallback."""

    def __init__(
        self,
        registry: Mapping[Dimension, EnforcementClaim] | None = None,
        overrides: Mapping[Dimension, EnforcementClaim] | None = None,
    ) -> None:
        super().__init__(
            registry if registry is not None else build_claim_registry(overrides=overrides)
        )

    def _compose_argv(
        self,
        resolved: Path,
        rest: tuple[str, ...],
        profile: SandboxProfile,
        pinned: tuple[Path, ...],
    ) -> list[str]:
        # Shell-free by construction: explicit argv, kernel-resolved executable.
        return [str(resolved), *rest]


class SeatbeltSandboxBackend(_ConfiningBackend):
    """darwin Seatbelt backend: exact-path `/usr/bin/sandbox-exec` with a
    generated deny-default profile — network denied when forbidden, writes
    confined to the resolved workspace subpath, and executable paths restricted
    to the profile's pinned executables. The enforcement claims are earned only
    by the empirical Seatbelt probe (loopback EPERM + out-of-workspace write
    EPERM observed under the generated profile); if the primitive is unavailable
    the backend refuses those dimensions."""

    def __init__(
        self,
        sandbox_exec: str = "/usr/bin/sandbox-exec",
        registry: Mapping[Dimension, EnforcementClaim] | None = None,
        overrides: Mapping[Dimension, EnforcementClaim] | None = None,
    ) -> None:
        self._sandbox_exec = sandbox_exec
        super().__init__(
            registry
            if registry is not None
            else build_claim_registry(sandbox_exec=sandbox_exec, overrides=overrides)
        )

    def _compose_argv(
        self,
        resolved: Path,
        rest: tuple[str, ...],
        profile: SandboxProfile,
        pinned: tuple[Path, ...],
    ) -> list[str]:
        profile_text = _seatbelt_profile_text(profile, pinned)
        return [self._sandbox_exec, "-p", profile_text, str(resolved), *rest]


# Import-time taxonomy <=> registry bijection: the "CPU+memory only" defect class
# cannot reappear silently — an unclaimed dimension fails the import loudly.
assert_registry_covers(build_claim_registry())
