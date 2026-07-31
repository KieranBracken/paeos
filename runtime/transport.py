"""Vendor-agnostic worker transport (R5.1) — the universal boundary between the core runtime and
how workers are driven and how their evidence comes back.

The CER-1 `EvidenceSource` review proved the runtime already depends on an *abstraction*, not on any
vendor (it imports no MCP). R5.1 generalises that into one named boundary: **`WorkerTransport`**
with three verbs — `submit` a worker's evidence for a run, query `status`, `receive` the submitted
evidence. Every transport satisfies it:

  * **`FileWorkerTransport`** (R5.1) — durable, cross-process, file-backed. No vendor SDK.
  * **`ClaudeCliWorkerTransport`** (R5.2) — wraps the `claude` CLI behind `WorkerTransport`.
  * **`McpWorkerTransport`** (R5.3) — wraps the official MCP SDK (now that the namespace is free).

The **core runtime depends only on `WorkerTransport` (and its read-only facet `EvidenceSource`),
never on a vendor SDK** — the architectural invariant, generalised from CER-1. A `WorkerTransport`
also satisfies `EvidenceSource` (its `receive` *is* `evidence_for`), so the `SoftLoop` consumes a
transport through the minimal *read-only* interface (AI-003); the driver uses the full transport.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from kernel.evidence import Evidence

from runtime.orchestrator import FileCourtEvidencePool

__all__ = ["FileWorkerTransport", "WorkerTransport"]


@runtime_checkable
class WorkerTransport(Protocol):
    """The vendor-agnostic worker boundary: `submit` evidence for a run, query `status`, `receive`
    the submitted evidence. The core runtime talks to workers through THIS and nothing else — never
    the `claude` CLI or the MCP SDK directly. `receive` is the read-only facet the `SoftLoop`
    consumes (it is also `evidence_for`, so a transport satisfies `EvidenceSource`)."""

    def submit(self, run_id: str, evidence: Evidence) -> None: ...
    def status(self, run_id: str) -> str: ...
    def receive(self, run_id: str) -> tuple[Evidence, ...]: ...


class FileWorkerTransport:
    """The file-based `WorkerTransport` (R5.1): submissions land in a durable, cross-process
    `FileCourtEvidencePool` (`<dir>/<run_id>.jsonl`). A worker (or a live session writing an
    file) submits; the runtime receives. Satisfies both `WorkerTransport` and `EvidenceSource`
    (`evidence_for == receive`), with **no vendor dependency**."""

    def __init__(self, directory: Path) -> None:
        self._pool = FileCourtEvidencePool(directory)

    def submit(self, run_id: str, evidence: Evidence) -> None:
        self._pool.submit(run_id, evidence)

    def status(self, run_id: str) -> str:
        return f"{len(self._pool.evidence_for(run_id))} evidence submitted for run {run_id}"

    def receive(self, run_id: str) -> tuple[Evidence, ...]:
        return self._pool.evidence_for(run_id)

    def evidence_for(self, run_id: str) -> tuple[Evidence, ...]:
        """The `EvidenceSource` read the `SoftLoop` consumes — identical to `receive`."""
        return self._pool.evidence_for(run_id)
