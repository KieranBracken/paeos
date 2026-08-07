"""R5.3 tests — the MCP court server + McpWorkerTransport.

A worker calls the `submit_evidence` MCP tool (exercised in-process); the evidence lands in the pool
and the SoftLoop reads it via McpWorkerTransport (EvidenceSource) and seals. The MCP SDK is imported
ONLY under runtime/transports/mcp/ — the vendor boundary; the core runtime never imports it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from kernel.cas import CAS, InMemoryCasStore
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import StageId, WeightClass
from nacl.signing import SigningKey
from runtime.claude_code import AgentWrite, RunOutput
from runtime.orchestrator import EvidenceSource, RunStatus, SoftLoop
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus
from runtime.transport import WorkerTransport
from runtime.transports.mcp.court_server import build_court_mcp_server
from runtime.transports.mcp.transport import McpWorkerTransport

_CODE = b"def feature() -> int:\n    return 42\n"
_BUDGETS = {
    WeightClass.ROUTINE: Budget(100_000, 3600, 5),
    WeightClass.SUBSTANTIAL: Budget(300_000, 7200, 5),
    WeightClass.KERNEL_TOUCHING: Budget(600_000, 10800, 5),
}
_ARGS = {
    "run_id": "r-1", "claim_id": "builds", "command": "echo built",
    "artifact_hash": "0" * 64, "exit_code": 0, "stdout": "built\n",
}


class _Runtime:
    def run(self, package: TaskPackage) -> RunOutput:
        writes = {
            StageId.DESIGN: (AgentWrite("design/d.md", b"d"),),
            StageId.PLAN: (AgentWrite("plan/p.md", b"p"),),
            StageId.IMPLEMENT: (AgentWrite("runtime/feature.py", _CODE),),
            StageId.ADVERSARIAL_REVIEW: (
                AgentWrite("review/adversary_report.md", b"ok\nVERDICT: PASS\n"),
            ),
        }.get(package.stage, ())
        return RunOutput(TaskStatus.COMPLETE, writes, (), b"t", Cost(100, 1.0, "m"))


def test_mcp_submit_evidence_reaches_the_transport(tmp_path: Path) -> None:
    pool_dir = tmp_path / "court"
    server = build_court_mcp_server(pool_dir)
    asyncio.run(server.call_tool("submit_evidence", dict(_ARGS)))  # a worker submits over MCP
    transport = McpWorkerTransport(pool_dir)
    assert isinstance(transport, WorkerTransport)
    src: EvidenceSource = transport  # also an EvidenceSource
    got = transport.receive("r-1")
    assert len(got) == 1
    assert got[0].claim_id == "builds"
    assert got[0].reproducible_command == "echo built"
    assert src.evidence_for("r-1") == got


def test_mcp_config_launches_the_court_server_against_the_pool(tmp_path: Path) -> None:
    cfg = McpWorkerTransport(tmp_path / "court").mcp_config()
    servers = cfg["mcpServers"]
    assert isinstance(servers, dict) and "paeos-court" in servers
    spec = servers["paeos-court"]
    assert isinstance(spec, dict)
    assert "runtime.transports.mcp.court_server" in spec["args"]


def test_soft_loop_seals_on_mcp_submitted_evidence(tmp_path: Path) -> None:
    pool_dir = tmp_path / "court"
    server = build_court_mcp_server(pool_dir)
    asyncio.run(server.call_tool("submit_evidence", dict(_ARGS)))  # evidence arrives over MCP
    transport = McpWorkerTransport(pool_dir)
    loop = SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()), signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()), agent_runtime=_Runtime(), budget_by_class=_BUDGETS,
    )
    outcome = loop.run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=(),
        evidence_source=transport,
    )
    assert outcome.status is RunStatus.SEALED  # sealed on evidence the worker submitted over MCP
