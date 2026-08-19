"""R5.2 tests — ClaudeCliWorkerTransport: the worker executes AND declares its own evidence.

Running a session captures the evidence it wrote (evidence.jsonl) into the transport's pool; the
SoftLoop uses one object as both agent_runtime (execution) and evidence_source (the evidence)
and seals autonomously — no pre-declared backlog evidence.
"""

from __future__ import annotations

from pathlib import Path

from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import StageId, WeightClass
from nacl.signing import SigningKey
from runtime.claude_code import AgentWrite, RunOutput
from runtime.orchestrator import RunStatus, SoftLoop
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus
from runtime.transport import WorkerTransport
from runtime.transports.claude_cli import ClaudeCliWorkerTransport

_CODE = b"def feature() -> int:\n    return 42\n"
_EVIDENCE_DECL = (
    b'{"claim_id": "builds", "kind": "TEST", "command": "echo built", '
    b'"artifact_hash": "0000000000000000000000000000000000000000000000000000000000000000", '
    b'"exit_code": 0, "stdout": "built\\n"}\n'
)
_BUDGETS = {
    WeightClass.ROUTINE: Budget(100_000, 3600, 5),
    WeightClass.SUBSTANTIAL: Budget(300_000, 7200, 5),
    WeightClass.KERNEL_TOUCHING: Budget(600_000, 10800, 5),
}


class _Inner:
    """Scripted inner AgentRuntime: on IMPLEMENT the session writes code AND declares evidence."""

    def run(self, package: TaskPackage) -> RunOutput:
        writes = {
            StageId.DESIGN: (AgentWrite("design/d.md", b"d"),),
            StageId.PLAN: (AgentWrite("plan/p.md", b"p"),),
            StageId.IMPLEMENT: (
                AgentWrite("runtime/feature.py", _CODE),
                AgentWrite("evidence.jsonl", _EVIDENCE_DECL),  # session declares its own evidence
            ),
            StageId.ADVERSARIAL_REVIEW: (
                AgentWrite("review/adversary_report.md", b"ok\nVERDICT: PASS\n"),
            ),
        }.get(package.stage, ())
        return RunOutput(TaskStatus.COMPLETE, writes, (), b"t", Cost(100, 1.0, "m"))


def _package(run_id: str = "r-1", stage: StageId = StageId.IMPLEMENT) -> TaskPackage:
    from kernel.capability import CapabilityBroker
    from kernel.types import Role

    broker = CapabilityBroker(SigningKey.generate())
    from runtime.task_package import Permissions

    token = broker.mint(
        goal_id="g", run_id=run_id, stage=stage, role=Role.BUILDER, session="s",
        operations=(), issued_seq=0, expires_seq=100,
    )
    return TaskPackage(
        task_id="t", goal_id="g", run_id=run_id, stage=stage, role=Role.BUILDER,
        objective="x", capability=token,
        permissions=Permissions(("evidence.jsonl", "runtime/feature.py"), (), ()),
        required_evidence=(), context_refs=(), budget=Budget(100000, 60, 1),
    )


def test_transport_captures_declared_evidence(tmp_path: Path) -> None:
    t = ClaudeCliWorkerTransport(_Inner(), tmp_path / "wt")
    assert isinstance(t, WorkerTransport)
    assert t.receive("r-1") == ()
    t.run(_package("r-1"))  # the IMPLEMENT session declares evidence.jsonl
    got = t.receive("r-1")
    assert len(got) == 1
    assert got[0].claim_id == "builds"
    assert got[0].reproducible_command == "echo built"
    assert t.evidence_for("r-1") == got  # EvidenceSource facet agrees


def test_soft_loop_seals_autonomously_via_claude_cli_transport(tmp_path: Path) -> None:
    transport = ClaudeCliWorkerTransport(_Inner(), tmp_path / "wt")
    loop = SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()), signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()), agent_runtime=transport, budget_by_class=_BUDGETS,
    )
    outcome = loop.run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py", "evidence.jsonl"),
        builder_evidence=(),  # NONE pre-declared — the agent produced its own (captured)
        evidence_source=transport,
    )
    assert outcome.status is RunStatus.SEALED
    assert content_hash(_CODE)  # sanity: the produced artifact exists
