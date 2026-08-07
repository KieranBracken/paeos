"""The Court MCP server (R5.3) — the vendor edge where a live worker submits evidence over MCP.

A worker (a live `claude` session connected via `claude --mcp-config`) calls the `submit_evidence`
tool; the server writes the evidence into a durable `FileCourtEvidencePool` (`<dir>/<run_id>.jsonl`)
that the `SoftLoop` reads through `McpWorkerTransport` (an `EvidenceSource`). This module — and only
this one — imports the official MCP SDK: it is the **vendor boundary** under `runtime/transports/`.
The core runtime never imports MCP (AI-001, scoped to exclude the transports layer).

Deployment: `python -m runtime.transports.mcp.court_server <pool_dir>` is the stdio server the
`--mcp-config` launches. Tests drive `submit_evidence` in-process via `MCPServer.call_tool`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.types import Role
from mcp.server import MCPServer

from runtime.orchestrator import FileCourtEvidencePool

__all__ = ["build_court_mcp_server", "main"]

_ENV_HASH = content_hash(b"paeos-mcp-court-env")


def build_court_mcp_server(pool_dir: str | Path) -> MCPServer:
    """An MCP server exposing `submit_evidence`, writing into the pool at `pool_dir`. The worker
    submits; the evidence is inert until the kernel adjudicates (SI-2)."""
    server = MCPServer("paeos-court")
    pool = FileCourtEvidencePool(Path(pool_dir))

    @server.tool()
    def submit_evidence(
        run_id: str,
        claim_id: str,
        command: str,
        artifact_hash: str,
        exit_code: int = 0,
        stdout: str = "",
    ) -> str:
        """Submit one piece of deterministic evidence for a run (reproduced by the Court later)."""
        pool.submit(
            run_id,
            Evidence(
                hash=content_hash(f"{claim_id}:{command}".encode()),
                kind=EvidenceKind.TEST,
                claim_id=claim_id,
                artifact_hash=artifact_hash,
                environment_hash=_ENV_HASH,
                reproducible_command=command,
                producer=EvidenceProducer(role=Role.BUILDER, session="mcp"),
                determinism=Determinism.DETERMINISTIC,
                result={"exit_code": exit_code, "stdout": stdout},
                attestation="pending-kernel-sig",
            ),
        )
        return f"submitted {claim_id} for run {run_id}"

    return server


def main() -> None:  # pragma: no cover - the live stdio entrypoint
    pool_dir = sys.argv[1] if len(sys.argv) > 1 else "ops/state/court"
    build_court_mcp_server(pool_dir).run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
