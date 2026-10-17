"""Antigravity headless supervisor adapter."""

from __future__ import annotations

from pathlib import Path

from runtime.supervisors.headless import HeadlessRunner, HeadlessSupervisorAdapter


class AntigravitySupervisorAdapter(HeadlessSupervisorAdapter):
    def __init__(
        self,
        *,
        runner: HeadlessRunner,
        executable: Path,
        executable_sha256: str,
        cwd: Path,
        environment_keys: tuple[str, ...] = (),
        timeout_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            runner=runner,
            executable=executable,
            executable_sha256=executable_sha256,
            cwd=cwd,
            argv_prefix=("--headless-supervisor", "--json"),
            adapter_id="antigravity-headless",
            adapter_version="1.0.0",
            environment_keys=environment_keys,
            timeout_seconds=timeout_seconds,
        )
