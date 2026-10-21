"""Vendor-neutral evidence transport; observations do not establish authority.

This compatibility boundary delegates to the current FileCourtEvidencePool.
Directories must be parent-controlled temporary or otherwise protected roots;
run-label validation is not symlink-race isolation or execution custody.
No provider client, worker launch, evidence adjudication or enrollment occurs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol, runtime_checkable

from kernel.evidence import Evidence

__all__ = ["FileWorkerTransport", "WorkerTransport"]

_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


def _validated_run_id(run_id: str) -> str:
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        raise ValueError("run_id must be one bounded ASCII path component")
    return run_id


@runtime_checkable
class WorkerTransport(Protocol):
    """Submit observations, query their count and receive a run's evidence."""

    def submit(self, run_id: str, evidence: Evidence) -> None: ...
    def status(self, run_id: str) -> str: ...
    def receive(self, run_id: str) -> tuple[Evidence, ...]: ...


class FileWorkerTransport:
    """File-backed compatibility adapter, preserving current pool taint semantics."""

    def __init__(self, directory: Path) -> None:
        # Delay the existing runtime dependency until explicit construction.
        # Importing the protocol alone neither creates a pool nor launches work.
        from runtime.orchestrator import FileCourtEvidencePool

        self._pool = FileCourtEvidencePool(directory)

    def submit(self, run_id: str, evidence: Evidence) -> None:
        self._pool.submit(_validated_run_id(run_id), evidence)

    def status(self, run_id: str) -> str:
        rows = self.receive(run_id)
        return f"{len(rows)} evidence submitted for run {run_id}"

    def receive(self, run_id: str) -> tuple[Evidence, ...]:
        return self._pool.evidence_for(_validated_run_id(run_id))

    def evidence_for(self, run_id: str) -> tuple[Evidence, ...]:
        """Read-only EvidenceSource facet; it does not adjudicate observations."""
        return self.receive(run_id)
