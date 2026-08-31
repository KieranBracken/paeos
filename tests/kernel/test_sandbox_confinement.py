"""Tests for capability-detected OS sandbox confinement (Gate E Task 5)."""

from __future__ import annotations

from pathlib import Path


def test_sandbox_profile_and_backend_supports() -> None:
    from kernel.sandbox_backend import (
        PortableSandboxBackend,
        SandboxedInvocation,
        SandboxProfile,
    )

    profile = SandboxProfile(
        profile_id="SP-001",
        cpu_seconds=10,
        memory_bytes=512 * 1024 * 1024,
        process_count=16,
        open_files=128,
        file_size_bytes=32 * 1024 * 1024,
        disk_bytes=100 * 1024 * 1024,
        wallclock_seconds=15,
        network_mode="NONE",
        allowed_exec_hashes=(),
    )
    backend = PortableSandboxBackend()
    assert backend.supports(profile) is True

    inv = SandboxedInvocation(
        argv=("echo", "sandboxed"),
        cwd=Path("."),
        profile=profile,
    )
    res = backend.run(inv)
    assert res.exit_code == 0
    assert "sandboxed" in res.stdout
