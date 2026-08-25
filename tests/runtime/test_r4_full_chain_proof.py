"""R4 Full-Chain Proof — Evidence Package

This test demonstrates the complete PAEOS runtime from L01 through terminal lifecycle state.
"""

from __future__ import annotations

from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import Role, StageId, WeightClass
from nacl.signing import SigningKey

from runtime.claude_code import AgentWrite, RunOutput
from runtime.ceremony import Layer
from runtime.court import VerdictOutcome
from runtime.memory import ScarStore
from runtime.orchestrator import RunStatus, SoftLoop
from runtime.sidecar_scorer import SidecarStageScorer
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus


# === TEST FIXTURES ===
_CODE = b"def feature() -> int:\n    return 42\n"
_ARTIFACT = content_hash(_CODE)

_BUDGETS = {
    WeightClass.ROUTINE: Budget(100_000, 3600, 5),
    WeightClass.SUBSTANTIAL: Budget(300_000, 7200, 5),
    WeightClass.KERNEL_TOUCHING: Budget(600_000, 10800, 5),
}


class ScriptedRuntime:
    """A scripted stand-in for scoped Claude Code sessions."""

    def __init__(
        self, writes_by_stage: dict[StageId, tuple[AgentWrite, ...]],
        *, cost_tokens: int = 1000,
        builder_model: str = "gemini-3.6-flash",
        auditor_model: str = "glm-4",
    ) -> None:
        self._writes = writes_by_stage
        self._cost_tokens = cost_tokens
        self.stages_run: list[StageId] = []
        self.packages: dict[StageId, TaskPackage] = {}
        self.builder_model = builder_model
        self.auditor_model = auditor_model

    def run(self, package: TaskPackage) -> RunOutput:
        self.stages_run.append(package.stage)
        self.packages[package.stage] = package
        model = self.auditor_model if package.role == Role.ADVERSARY else self.builder_model
        return RunOutput(
            status=TaskStatus.COMPLETE,
            writes=self._writes.get(package.stage, ()),
            evidence=(),
            trace=b"trace-" + package.stage.name.encode(),
            cost=Cost(tokens=self._cost_tokens, wallclock_s=1.0, model_ver=model),
        )


def _evidence(claim_id: str, command: str, stdout: str) -> Evidence:
    return Evidence(
        hash=content_hash(f"{claim_id}:{command}".encode()),
        kind=EvidenceKind.TEST, claim_id=claim_id, artifact_hash=_ARTIFACT,
        environment_hash="e" * 64, reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session="builder"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": stdout}, attestation="sig",
    )


def _writes(impl_path: str = "runtime/feature.py") -> dict[StageId, tuple[AgentWrite, ...]]:
    return {
        StageId.RE_DERIVE: (AgentWrite("derive/derive.md", b"derivation"),),
        StageId.IDEATE: (AgentWrite("ideate/ideate.md", b"ideation"),),
        StageId.RESEARCH: (AgentWrite("research/research.md", b"research"),),
        StageId.TRADEOFF: (AgentWrite("tradeoff/tradeoff.md", b"tradeoff"),),
        StageId.MITIGATION: (AgentWrite("mitigation/mitigation.md", b"mitigation"),),
        StageId.DESIGN: (AgentWrite("design/design.md", b"design"),),
        StageId.CRITIQUE: (AgentWrite("critique/critique.md", b"critique"),),
        StageId.PLAN: (AgentWrite("plan/plan.md", b"plan"),),
        StageId.IMPLEMENT: (AgentWrite(impl_path, _CODE),),
        StageId.ADVERSARIAL_REVIEW: (
            AgentWrite("review/adversary_report.md", b"no dissent\nVERDICT: PASS\n"),
        ),
        StageId.RETROSPECT: (AgentWrite("retrospect/retro.md", b"retrospect"),),
        StageId.MEMORY_UPDATE: (AgentWrite("memory/scar.md", b"scar"),),
    }


def _loop(runtime: ScriptedRuntime, *, scar_store: ScarStore | None = None) -> SoftLoop:
    return SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()),
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()),
        agent_runtime=runtime,
        budget_by_class=_BUDGETS,
        scar_store=scar_store,
        sidecar_scorer=SidecarStageScorer(None),  # DEBT-0057: explicitly non-persistent
    )


_GOOD_EVIDENCE = (
    _evidence("builds", "echo built", "built\n"),
    _evidence("unit", "echo tests-pass", "tests-pass\n"),
)
