"""R5.1 tests — the vendor-agnostic WorkerTransport boundary + FileWorkerTransport.

The core runtime depends only on WorkerTransport (and its read-only EvidenceSource facet), never a
vendor SDK. FileWorkerTransport satisfies both and drives an autonomous seal on submitted evidence.
"""

from __future__ import annotations

from pathlib import Path

from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import Role, StageId, WeightClass
from nacl.signing import SigningKey
from runtime.claude_code import AgentWrite, RunOutput
from runtime.orchestrator import EvidenceSource, RunStatus, SoftLoop
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus
from runtime.transport import FileWorkerTransport, WorkerTransport

_CODE = b"def feature() -> int:\n    return 42\n"
_ART = content_hash(_CODE)
_BUDGETS = {
    WeightClass.ROUTINE: Budget(100_000, 3600, 5),
    WeightClass.SUBSTANTIAL: Budget(300_000, 7200, 5),
    WeightClass.KERNEL_TOUCHING: Budget(600_000, 10800, 5),
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


def _ev(claim_id: str, stdout: str) -> Evidence:
    return Evidence(
        hash=content_hash(f"{claim_id}:{stdout}".encode()), kind=EvidenceKind.TEST,
        claim_id=claim_id, artifact_hash=_ART, environment_hash="e" * 64,
        reproducible_command="echo built",
        producer=EvidenceProducer(role=Role.BUILDER, session="b"),
        determinism=Determinism.DETERMINISTIC, result={"exit_code": 0, "stdout": stdout},
        attestation="s",
    )


def test_file_worker_transport_three_verbs(tmp_path: Path) -> None:
    t = FileWorkerTransport(tmp_path / "wt")
    assert t.status("r-1").startswith("0 ")
    assert t.receive("r-1") == ()
    t.submit("r-1", _ev("builds", "built\n"))
    assert t.status("r-1").startswith("1 ")
    got = t.receive("r-1")
    assert len(got) == 1 and got[0].claim_id == "builds"


def test_file_worker_transport_satisfies_both_protocols(tmp_path: Path) -> None:
    t = FileWorkerTransport(tmp_path / "wt")
    # structural conformance to the two runtime-facing abstractions (never a vendor SDK)
    assert isinstance(t, WorkerTransport)
    src: EvidenceSource = t  # a transport IS an EvidenceSource (receive == evidence_for)
    assert src.evidence_for("r-x") == ()


def test_soft_loop_seals_on_transport_submitted_evidence(tmp_path: Path) -> None:
    # the autonomous flow through the universal boundary: a worker submits via the transport,
    # the SoftLoop consumes it through the read-only EvidenceSource facet, and seals.
    transport = FileWorkerTransport(tmp_path / "wt")
    transport.submit("r-1", _ev("builds", "built\n"))
    loop = SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()), signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()), agent_runtime=_Runtime(), budget_by_class=_BUDGETS,
    )
    outcome = loop.run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=(),
        evidence_source=transport,
    )
    assert outcome.status is RunStatus.SEALED
