"""Fail-closed OS confinement policy for provider-backed worker processes.

This is the provider composition adapter for the existing PAEOS sandbox capability design in
``kernel.sandbox_backend``.  It supplies the missing read boundary and clean child environment
required by DEBT-0115.  The model prompt is not part of the security boundary.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kernel.sandbox_backend import build_seatbelt_path_profile

__all__ = [
    "WorkerConfinementError",
    "WorkerConfinementPolicy",
    "build_provider_environment",
    "policy_for_worker",
    "prepare_provider_launch",
]


class WorkerConfinementError(RuntimeError):
    """The requested worker authority cannot be enforced; the worker must not launch."""


_PROVIDER_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
_SYSTEM_READ_ROOTS = (
    Path("/System"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
    Path("/Library/Apple"),
    Path("/Library/Developer/CommandLineTools"),
    Path("/private/var/db/dyld"),
    Path("/opt/homebrew"),
    Path("/dev"),
)
_SYSTEM_READ_FILES = (Path("/private/etc/ssl/openssl.cnf"),)


def _canonical_executable(argv0: str) -> str:
    """Resolve one executable against the fixed provider PATH, never the child PATH."""

    supplied = Path(argv0)
    if ".." in supplied.parts:
        raise WorkerConfinementError("provider executable contains traversal")
    if not supplied.is_absolute():
        for directory in _PROVIDER_PATH.split(":"):
            candidate = Path(directory) / supplied
            if candidate.is_file() and os.access(candidate, os.X_OK):
                supplied = candidate
                break
        else:
            raise WorkerConfinementError("provider executable is not on the fixed provider PATH")
    try:
        resolved = supplied.resolve(strict=True)
    except OSError as exc:
        raise WorkerConfinementError("provider executable is unavailable") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise WorkerConfinementError("provider executable is not runnable")
    return str(resolved)


def _canonical_root(path: Path, *, must_exist: bool, label: str) -> Path:
    supplied = Path(path)
    if not supplied.is_absolute() or ".." in supplied.parts:
        raise WorkerConfinementError(f"{label} must be an absolute canonical path")
    absolute = Path(os.path.abspath(supplied))
    if supplied.is_symlink():
        raise WorkerConfinementError(f"{label} cannot be a symlink")
    try:
        resolved = supplied.resolve(strict=must_exist)
    except OSError as exc:
        raise WorkerConfinementError(f"{label} is unavailable") from exc
    if resolved != absolute:
        raise WorkerConfinementError(f"{label} crosses a symlink and is not canonical")
    return resolved


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _lexical_probe_path(path: Path) -> Path:
    """Validate one exact read probe without resolving macOS aliases such as /etc."""

    supplied = Path(path)
    if (
        not supplied.is_absolute()
        or ".." in supplied.parts
        or Path(os.path.abspath(supplied)) != supplied
        or supplied.is_symlink()
    ):
        raise WorkerConfinementError("read probe path must be absolute, exact, and non-symlinked")
    return supplied


def build_provider_environment(
    parent_environment: Mapping[str, str],
    *,
    runtime_home: Path,
    temp_root: Path,
    task_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build ``required_runtime_env U task_scoped_env`` without parent inheritance."""

    home = _canonical_root(runtime_home, must_exist=False, label="runtime home")
    temp = _canonical_root(temp_root, must_exist=False, label="temporary root")
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp.mkdir(mode=0o700, parents=True, exist_ok=True)
    environment = {
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C",
        "PATH": _PROVIDER_PATH,
        "TMPDIR": str(temp),
    }
    if task_environment:
        for key, value in task_environment.items():
            if key in environment or not key.startswith("PAEOS_TASK_"):
                raise WorkerConfinementError("task environment contains a non-task-scoped name")
            if not isinstance(value, str):
                raise WorkerConfinementError("task environment values must be strings")
            environment[key] = value
    return environment


@dataclass(frozen=True, slots=True)
class WorkerConfinementPolicy:
    """Immutable, mechanically enforceable worker launch authority."""

    workspace: Path
    read_roots: tuple[Path, ...]
    write_roots: tuple[Path, ...]
    runtime_home: Path
    temp_root: Path
    sandbox_exec: Path
    seatbelt_profile: str
    loopback_port: int | None = None
    network_hosts: tuple[str, ...] = ()
    preference_domains: tuple[str, ...] = ()
    read_probe_paths: tuple[Path, ...] = ()

    def wrap_argv(self, argv: tuple[str, ...]) -> tuple[str, ...]:
        if not argv or any(not isinstance(item, str) or not item for item in argv):
            raise WorkerConfinementError("provider argv must be explicit and non-empty")
        if _canonical_executable(argv[0]) != argv[0]:
            raise WorkerConfinementError("provider executable must be canonical and non-symlinked")
        mechanism = self.sandbox_exec
        if mechanism != Path("/usr/bin/sandbox-exec"):
            raise WorkerConfinementError("confinement mechanism is unavailable or not pinned")
        if not mechanism.is_file() or not os.access(mechanism, os.X_OK) or mechanism.is_symlink():
            raise WorkerConfinementError("confinement mechanism is unavailable")
        return (str(mechanism), "-p", self.seatbelt_profile, *argv)


def policy_for_worker(
    *,
    workspace: Path,
    read_roots: tuple[Path, ...],
    write_roots: tuple[Path, ...],
    runtime_home: Path,
    temp_root: Path,
    sandbox_exec: Path = Path("/usr/bin/sandbox-exec"),
    allow_network: bool = False,
    loopback_port: int | None = None,
    network_hosts: tuple[str, ...] = (),
    preference_domains: tuple[str, ...] = (),
    read_probe_paths: tuple[Path, ...] = (),
) -> WorkerConfinementPolicy:
    """Compile a canonicalized Seatbelt policy; invalid authority fails before launch."""

    if allow_network:
        raise WorkerConfinementError(
            "unscoped network authority is forbidden; provider endpoint allowlisting is required"
        )
    if not isinstance(network_hosts, tuple) or any(
        not isinstance(host, str) for host in network_hosts
    ):
        raise WorkerConfinementError("network_hosts must be a tuple of host names")
    if not isinstance(preference_domains, tuple) or any(
        not isinstance(domain, str) for domain in preference_domains
    ):
        raise WorkerConfinementError("preference_domains must be a tuple of domain names")
    if isinstance(loopback_port, bool) or (
        loopback_port is not None and not isinstance(loopback_port, int)
    ):
        raise WorkerConfinementError("loopback_port must be an integer or None")
    if loopback_port is not None and not 1 <= loopback_port <= 65535:
        raise WorkerConfinementError("loopback_port must be between 1 and 65535")
    canonical_workspace = _canonical_root(workspace, must_exist=True, label="workspace")
    canonical_reads = tuple(
        dict.fromkeys(
            _canonical_root(path, must_exist=True, label="read root") for path in read_roots
        )
    )
    canonical_writes = tuple(
        dict.fromkeys(
            _canonical_root(path, must_exist=True, label="write root") for path in write_roots
        )
    )
    canonical_home = _canonical_root(runtime_home, must_exist=False, label="runtime home")
    canonical_temp = _canonical_root(temp_root, must_exist=False, label="temporary root")
    canonical_probe_paths = tuple(
        dict.fromkeys(_lexical_probe_path(path) for path in read_probe_paths)
    )
    canonical_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    canonical_temp.mkdir(mode=0o700, parents=True, exist_ok=True)
    for root in (*canonical_writes, canonical_home, canonical_temp):
        if not _within(root, canonical_workspace):
            raise WorkerConfinementError("write authority must remain inside the worker workspace")

    effective_reads = tuple(
        dict.fromkeys((*_SYSTEM_READ_ROOTS, *canonical_reads, canonical_home, canonical_temp))
    )
    effective_writes = tuple(dict.fromkeys((*canonical_writes, canonical_home, canonical_temp)))
    return WorkerConfinementPolicy(
        workspace=canonical_workspace,
        read_roots=effective_reads,
        write_roots=effective_writes,
        runtime_home=canonical_home,
        temp_root=canonical_temp,
        sandbox_exec=Path(sandbox_exec),
        seatbelt_profile=build_seatbelt_path_profile(
            read_roots=effective_reads,
            write_roots=effective_writes,
            allow_network=allow_network,
            loopback_port=loopback_port,
            read_files=_SYSTEM_READ_FILES,
            read_probe_paths=canonical_probe_paths,
            network_hosts=network_hosts,
            preference_domains=preference_domains,
        ),
        loopback_port=loopback_port,
        network_hosts=tuple(sorted(dict.fromkeys(network_hosts))),
        preference_domains=tuple(sorted(dict.fromkeys(preference_domains))),
        read_probe_paths=canonical_probe_paths,
    )


def prepare_provider_launch(
    argv: tuple[str, ...],
    *,
    workspace: Path,
    parent_environment: Mapping[str, str],
    loopback_port: int | None = None,
    network_hosts: tuple[str, ...] = (),
) -> tuple[tuple[str, ...], dict[str, str], WorkerConfinementPolicy]:
    """Compile the mandatory provider launch boundary and clean child environment."""

    runtime_home = workspace / ".paeos-provider-runtime"
    temp_root = workspace / ".paeos-provider-tmp"
    runtime_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    policy = policy_for_worker(
        workspace=workspace,
        read_roots=(workspace,),
        write_roots=(workspace,),
        runtime_home=runtime_home,
        temp_root=temp_root,
        loopback_port=loopback_port,
        network_hosts=network_hosts,
    )
    environment = build_provider_environment(
        parent_environment,
        runtime_home=runtime_home,
        temp_root=temp_root,
    )
    if not argv:
        raise WorkerConfinementError("provider argv must be explicit and non-empty")
    bound_argv = (_canonical_executable(argv[0]), *argv[1:])
    return policy.wrap_argv(bound_argv), environment, policy
