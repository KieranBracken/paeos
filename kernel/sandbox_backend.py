"""Capability-detected sandbox backends and execution confinement (Gate E Task 5)."""

from __future__ import annotations

import contextlib
import os
import resource
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from kernel.sandbox import SandboxLimits, SandboxResult


@dataclass(frozen=True, slots=True)
class SandboxProfile:
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


@dataclass(frozen=True, slots=True)
class SandboxedInvocation:
    argv: tuple[str, ...]
    cwd: Path
    profile: SandboxProfile
    stdin: bytes = b""
    environment: Mapping[str, str] = field(default_factory=dict[str, str])



class SandboxBackend(Protocol):
    def supports(self, profile: SandboxProfile) -> bool: ...
    def run(self, invocation: SandboxedInvocation) -> SandboxResult: ...


class PortableSandboxBackend:
    """Portable OS resource-limited execution backend using setrlimit and subprocess."""

    def supports(self, profile: SandboxProfile) -> bool:
        # Portable backend supports basic resource bounding
        return profile.cpu_seconds > 0 and profile.memory_bytes > 0

    def run(self, invocation: SandboxedInvocation) -> SandboxResult:
        lim = SandboxLimits(
            cpu_seconds=invocation.profile.cpu_seconds,
            memory_bytes=invocation.profile.memory_bytes,
            file_size_bytes=invocation.profile.file_size_bytes,
            open_files=invocation.profile.open_files,
            wallclock_s=invocation.profile.wallclock_seconds,
        )

        def _preexec() -> None:
            # Set process group
            os.setpgrp()
            for res, soft in (
                (resource.RLIMIT_CPU, lim.cpu_seconds),
                (resource.RLIMIT_AS, lim.memory_bytes),
                (resource.RLIMIT_FSIZE, lim.file_size_bytes),
                (resource.RLIMIT_NOFILE, lim.open_files),
            ):
                with contextlib.suppress(ValueError, OSError):
                    resource.setrlimit(res, (soft, soft))

        home_cargo = str(Path.home() / ".cargo" / "bin")
        home_local = str(Path.home() / ".local" / "bin")
        allowlisted_path = f"{home_cargo}:{home_local}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        env = dict(invocation.environment) if invocation.environment else {}
        env.setdefault("PATH", allowlisted_path)
        env.setdefault("LC_ALL", "C")

        stdin_text = (
            invocation.stdin.decode("utf-8", errors="replace")
            if invocation.stdin
            else None
        )
        try:
            proc = subprocess.run(
                list(invocation.argv),
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=lim.wallclock_s,
                check=False,
                preexec_fn=_preexec,
                cwd=str(invocation.cwd),
                env=env,
            )

            return SandboxResult(exit_code=proc.returncode, stdout=proc.stdout, timed_out=False)
        except subprocess.TimeoutExpired:
            return SandboxResult(exit_code=-1, stdout="", timed_out=True)
        except (FileNotFoundError, OSError):
            return SandboxResult(exit_code=-1, stdout="", timed_out=False)
