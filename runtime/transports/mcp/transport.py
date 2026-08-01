"""McpWorkerTransport (R5.3) — the MCP-backed `WorkerTransport`.

Submissions arrive over MCP: a live worker calls the `submit_evidence` tool on the court server
(`court_server.py`, launched by `claude --mcp-config`), which writes them into a durable
`FileCourtEvidencePool`. The runtime reads through this transport's `receive`/`evidence_for`.

Satisfies `WorkerTransport` and `EvidenceSource`. The **core runtime never imports the MCP SDK** —
only the server module does; this transport is a plain pool reader + config generator. Adding MCP
therefore touched **zero core-runtime code** — the CER-1 / R5.1 payoff, realised.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kernel.evidence import Evidence

from runtime.orchestrator import FileCourtEvidencePool

__all__ = ["McpWorkerTransport"]


class McpWorkerTransport:
    """The MCP-backed `WorkerTransport`/`EvidenceSource`, over a durable `FileCourtEvidencePool` the
    court MCP server writes into. `mcp_config()` produces the `--mcp-config` the live `claude` uses
    to launch that server against this pool."""

    def __init__(self, pool_dir: str | Path, *, server_name: str = "paeos-court") -> None:
        self._dir = Path(pool_dir)
        self._pool = FileCourtEvidencePool(self._dir)
        self._server_name = server_name

    def submit(self, run_id: str, evidence: Evidence) -> None:
        self._pool.submit(run_id, evidence)

    def status(self, run_id: str) -> str:
        return f"{len(self._pool.evidence_for(run_id))} evidence submitted for run {run_id}"

    def receive(self, run_id: str) -> tuple[Evidence, ...]:
        return self._pool.evidence_for(run_id)

    def evidence_for(self, run_id: str) -> tuple[Evidence, ...]:
        return self._pool.evidence_for(run_id)

    def mcp_config(self) -> dict[str, object]:
        """The `--mcp-config` for `claude`: launch the court server against this pool over stdio."""
        return {
            "mcpServers": {
                self._server_name: {
                    "command": sys.executable,
                    "args": ["-m", "runtime.transports.mcp.court_server", str(self._dir)],
                }
            }
        }
