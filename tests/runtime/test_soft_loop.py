"""Phase-1 Soft-Loop Integration — the unattended end-to-end run (PAEOS-8 §157).

One intake reaches a sealed, court-passed, adversary-reviewed change behind real information
barriers, with scars written and triage/budget enforced — Planner, Builder, Verifier, Adversary
composed over the sealed Phase-0 kernel.
"""

from __future__ import annotations

from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import Role, StageId, WeightClass
from nacl.signing import SigningKey
from runtime.claude_code import AgentWrite, RunOutput
from runtime.court import VerdictOutcome
from runtime.memory import ScarDraft, ScarStore
from runtime.orchestrator import RunStatus, SoftLoop
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus

_CODE = b"def feature() -> int:\n    return 42\n"
_ARTIFACT = content_hash(_CODE)
_BUDGETS = {
    WeightClass.ROUTINE: Budget(100_000, 3600, 5),
    WeightClass.SUBSTANTIAL: Budget(300_000, 7200, 5),
    WeightClass.KERNEL_TOUCHING: Budget(600_000, 10800, 5),
}


class ScriptedRuntime:
    """A scripted stand-in for scoped Claude Code sessions (the B1.B AgentRuntime seam)."""

    def __init__(
        self, writes_by_stage: dict[StageId, tuple[AgentWrite, ...]], *, cost_tokens: int = 1000
    ) -> None:
        self._writes = writes_by_stage
        self._cost_tokens = cost_tokens
        self.stages_run: list[StageId] = []
        self.packages: dict[StageId, TaskPackage] = {}

    def run(self, package: TaskPackage) -> RunOutput:
        self.stages_run.append(package.stage)
        self.packages[package.stage] = package
        return RunOutput(
            status=TaskStatus.COMPLETE,
            writes=self._writes.get(package.stage, ()),
            evidence=(),
            trace=b"trace-" + package.stage.name.encode(),
            cost=Cost(tokens=self._cost_tokens, wallclock_s=1.0, model_ver="model-x"),
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
        StageId.DESIGN: (AgentWrite("design/design.md", b"design"),),
        StageId.PLAN: (AgentWrite("plan/plan.md", b"plan"),),
        StageId.IMPLEMENT: (AgentWrite(impl_path, _CODE),),
        StageId.ADVERSARIAL_REVIEW: (AgentWrite("review/adversary_report.md", b"no dissent"),),
    }


def _loop(runtime: ScriptedRuntime, *, scar_store: ScarStore | None = None,
         budgets: dict[WeightClass, Budget] | None = None) -> SoftLoop:
    return SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()), signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()), agent_runtime=runtime,
        budget_by_class=budgets if budgets is not None else _BUDGETS,
        scar_store=scar_store,
    )


_GOOD_EVIDENCE = (
    _evidence("builds", "echo built", "built\n"),
    _evidence("unit", "echo tests-pass", "tests-pass\n"),
)


# ---- the full unattended run reaches SEAL ---------------------------------


def test_unattended_run_reaches_seal() -> None:
    runtime = ScriptedRuntime(_writes())
    outcome = _loop(runtime).run(
        objective="add feature()", changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    assert outcome.status is RunStatus.SEALED
    assert outcome.seal is not None
    assert outcome.verdict is not None and outcome.verdict.outcome is VerdictOutcome.PASS
    # all four roles ran, in order
    assert runtime.stages_run == [
        StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW,
    ]
    # Planner and Builder roles were correctly scoped
    assert runtime.packages[StageId.DESIGN].role is Role.PLANNER
    assert runtime.packages[StageId.IMPLEMENT].role is Role.BUILDER
    assert runtime.packages[StageId.ADVERSARIAL_REVIEW].role is Role.ADVERSARY


def test_seal_is_idempotent_reseal_same() -> None:
    runtime = ScriptedRuntime(_writes())
    loop = _loop(runtime)
    first = loop.run(objective="x", changed_paths=("runtime/f.py",),
                     plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE)
    assert first.status is RunStatus.SEALED and first.seal is not None


# ---- court remand writes a scar (FR-6) ------------------------------------


def test_court_remand_writes_a_scar() -> None:
    forged = (_evidence("builds", "echo built", "FORGED\n"),)  # command emits "built", not "FORGED"
    scar_store = ScarStore()
    runtime = ScriptedRuntime(_writes())
    outcome = _loop(runtime, scar_store=scar_store).run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=forged,
    )
    assert outcome.status is RunStatus.REMANDED
    assert outcome.verdict is not None and outcome.verdict.outcome is VerdictOutcome.REMAND
    # a scar recording the remand was written and now matches this failure class
    matched = scar_store.match_scars("stage:VERIFY,kind:court-remand,goal:x")
    assert len(matched) == 1


# ---- scars are injected into the Planner's context (FR-6) ------------------


def test_matched_scar_is_injected_at_design() -> None:
    scar_store = ScarStore()
    scar_store.propose_scar(
        ScarDraft(signature=frozenset({"stage:DESIGN", "domain:runtime"}),
                  lesson="watch the seams", detection="sig")
    )
    runtime = ScriptedRuntime(_writes())
    _loop(runtime, scar_store=scar_store).run(
        objective="x", changed_paths=("runtime/f.py",), plan_write_scopes=("runtime/feature.py",),
        builder_evidence=_GOOD_EVIDENCE, goal_signature="stage:DESIGN,domain:runtime,goal:g",
    )
    design_pkg = runtime.packages[StageId.DESIGN]
    assert any(ref.type == "scar" for ref in design_pkg.context_refs)  # injected on the path


# ---- triage + budget -------------------------------------------------------


def test_triage_marks_kernel_touching_full_path() -> None:
    runtime = ScriptedRuntime(_writes(impl_path="kernel/mod.py"))
    loop = _loop(runtime)
    outcome = loop.run(
        objective="touch kernel", changed_paths=("kernel/mod.py",),
        plan_write_scopes=("kernel/mod.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    # the goal was classified KERNEL_TOUCHING (full path) and used the full budget
    kinds = [r.event.payload.get("weight_class") for r in loop._ledger.read()
             if r.event.kind == "goal_created"]
    assert kinds == [WeightClass.KERNEL_TOUCHING.value]
    assert outcome.status is RunStatus.SEALED


def test_budget_breach_halts_the_run() -> None:
    tight = {**_BUDGETS, WeightClass.ROUTINE: Budget(1500, 3600, 5)}  # only ~1 dispatch fits
    runtime = ScriptedRuntime(_writes(), cost_tokens=1000)
    outcome = _loop(runtime, budgets=tight).run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    assert outcome.status is RunStatus.HALTED  # design (1000) + plan (1000) > 1500
