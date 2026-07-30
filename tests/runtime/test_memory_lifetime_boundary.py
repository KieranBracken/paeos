"""B2.G tests — the L1/L3 constitutional memory-lifetime boundary (IP-0004/0005/0006).

The operational SoftLoop owns only **L1** Ephemeral Execution Context (run-scoped remand notes,
never persisted). **L3** Institutional Memory (scars) is authored EXCLUSIVELY by the Evolution Layer
at Stage 17. This suite proves the boundary holds and that the self-improvement loop still closes
across a backlog through the driver — without the loop ever authoring memory.
"""

from __future__ import annotations

from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import Role, StageId
from nacl.signing import SigningKey
from runtime.claude_code import AgentWrite, RunOutput
from runtime.orchestrator import Intake, RunOutcome, RunStatus
from runtime.selfhost import run_backlog
from runtime.task_package import Cost, ExecutionContext, TaskPackage, TaskStatus

_CODE = b"def x() -> int:\n    return 1\n"
_ART = content_hash(_CODE)


def _ev(claim_id: str, stdout: str) -> Evidence:
    return Evidence(
        hash=content_hash(f"{claim_id}:{stdout}".encode()), kind=EvidenceKind.TEST,
        claim_id=claim_id, artifact_hash=_ART, environment_hash="e" * 64,
        reproducible_command="echo built",
        producer=EvidenceProducer(role=Role.BUILDER, session="b"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": stdout}, attestation="s",
    )


_GOOD = (_ev("builds", "built\n"),)
_FORGED = (_ev("builds", "FORGED\n"),)


class _Recorder:
    """Scripts a run and records every DESIGN package it is handed (to inspect scar injection)."""

    def __init__(self) -> None:
        self.design_packages: list[TaskPackage] = []
        self._writes = {
            StageId.DESIGN: (AgentWrite("design/d.md", b"d"),),
            StageId.PLAN: (AgentWrite("plan/p.md", b"p"),),
            StageId.IMPLEMENT: (AgentWrite("runtime/x.py", _CODE),),
            StageId.ADVERSARIAL_REVIEW: (AgentWrite("review/adversary_report.md", b"ok"),),
        }

    def run(self, package: TaskPackage) -> RunOutput:
        if package.stage is StageId.DESIGN:
            self.design_packages.append(package)
        return RunOutput(TaskStatus.COMPLETE, self._writes.get(package.stage, ()), (),
                         b"t", Cost(100, 1.0, "m"))


def _intake(evidence: tuple[Evidence, ...], *, signature: str) -> Intake:
    return Intake(
        objective="add x()", changed_paths=("runtime/x.py",),
        plan_write_scopes=("runtime/x.py",), builder_evidence=evidence, goal_signature=signature,
    )


def _run(backlog: list[Intake], runtime: _Recorder) -> list[RunOutcome]:
    return run_backlog(
        backlog,
        ledger=Ledger(InMemoryLedgerStore()),
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()),
        agent_runtime=runtime,
    )


def test_remanded_run_carries_l1_execution_context_not_a_seal() -> None:
    outcomes = _run([_intake(_FORGED, signature="domain:runtime,task:t")], _Recorder())
    assert outcomes[0].status is RunStatus.REMANDED
    assert isinstance(outcomes[0].ephemeral_context, ExecutionContext)  # L1, run-scoped
    assert outcomes[0].ephemeral_context.retry_hints  # a retry hint, not institutional memory
    assert outcomes[0].seal is None


def test_evolution_authored_scar_is_injected_into_a_later_run() -> None:
    # intake 1 remands → Evolution authors an L3 scar (Stage 17); intake 2 shares the signature, so
    # the scar is injected into its DESIGN — the self-improvement loop closes through the driver,
    # with the operational loop never authoring memory.
    sig = "domain:runtime,task:t,stage:VERIFY,kind:court-remand"
    runtime = _Recorder()
    outcomes = _run([_intake(_FORGED, signature=sig), _intake(_GOOD, signature=sig)], runtime)
    assert [o.status for o in outcomes] == [RunStatus.REMANDED, RunStatus.SEALED]
    # the SECOND run's DESIGN package received the scar authored from the FIRST run's remand
    second_design = runtime.design_packages[-1]
    assert any(ref.type == "scar" for ref in second_design.context_refs)
