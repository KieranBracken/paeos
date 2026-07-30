"""Phase-2 tests for the self-hosting driver (PAEOS-8 §12 R3→R4).

PAEOS pulls a backlog of intakes and runs each through one shared soft loop — scars accumulate
across runs (soft-loop self-improvement), and every run is recorded on the shared ledger.
"""

from __future__ import annotations

from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import Role, StageId, WeightClass
from nacl.signing import SigningKey
from runtime.claude_code import AgentWrite, RunOutput
from runtime.evolution import EvolutionLayer
from runtime.memory import ScarDraft, ScarStore
from runtime.orchestrator import Intake, RunStatus, SelfHostRunner, SoftLoop
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus

_CODE = b"def x() -> int:\n    return 1\n"
_ART = content_hash(_CODE)
_BUDGETS = {
    WeightClass.ROUTINE: Budget(100_000, 3600, 5),
    WeightClass.SUBSTANTIAL: Budget(300_000, 7200, 5),
    WeightClass.KERNEL_TOUCHING: Budget(600_000, 10800, 5),
}


class ScriptedRuntime:
    def __init__(self) -> None:
        self.packages: dict[StageId, TaskPackage] = {}
        self._writes = {
            StageId.DESIGN: (AgentWrite("design/design.md", b"design"),),
            StageId.PLAN: (AgentWrite("plan/plan.md", b"plan"),),
            StageId.IMPLEMENT: (AgentWrite("runtime/x.py", _CODE),),
            StageId.ADVERSARIAL_REVIEW: (AgentWrite("review/adversary_report.md", b"ok"),),
        }

    def run(self, package: TaskPackage) -> RunOutput:
        self.packages[package.stage] = package
        return RunOutput(
            TaskStatus.COMPLETE, self._writes.get(package.stage, ()), (),
            b"trace", Cost(1000, 1.0, "m"),
        )


def _ev(claim_id: str, stdout: str) -> Evidence:
    return Evidence(
        hash=content_hash(f"{claim_id}:{stdout}".encode()), kind=EvidenceKind.TEST,
        claim_id=claim_id, artifact_hash=_ART, environment_hash="e" * 64,
        reproducible_command="echo built",
        producer=EvidenceProducer(role=Role.BUILDER, session="b"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": stdout}, attestation="s",
    )


_GOOD = (_ev("builds", "built\n"),)  # echo built reproduces "built\n" → PASS
_FORGED = (_ev("builds", "FORGED\n"),)  # claims "FORGED" → court remand


def _runner(runtime: ScriptedRuntime, scar_store: ScarStore | None = None) -> SelfHostRunner:
    loop = SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()), signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()), agent_runtime=runtime, budget_by_class=_BUDGETS,
        scar_store=scar_store,
    )
    return SelfHostRunner(loop)


def _intake(evidence: tuple[Evidence, ...], *, signature: str = "domain:runtime,task:t") -> Intake:
    return Intake(
        objective="add x()", changed_paths=("runtime/x.py",),
        plan_write_scopes=("runtime/x.py",), builder_evidence=evidence, goal_signature=signature,
    )


# ---- pulls and runs a backlog ---------------------------------------------


def test_runs_a_backlog_of_goals() -> None:
    runtime = ScriptedRuntime()
    runner = _runner(runtime)
    outcomes = runner.run_backlog([_intake(_GOOD), _intake(_FORGED)])
    assert [o.status for o in outcomes] == [RunStatus.SEALED, RunStatus.REMANDED]
    assert outcomes[0].seal is not None


# ---- L1/L3 boundary: the loop writes no scar; Evolution authors it (B2.G) --


def test_loop_writes_no_scar_and_evolution_authors_it() -> None:
    runner = _runner(ScriptedRuntime())
    sig = "domain:runtime,task:t"  # the default _intake signature
    query = f"{sig},stage:VERIFY,kind:court-remand"
    assert runner.scar_store.match_scars(query) == []
    outcomes = runner.run_backlog([_intake(_FORGED)])  # court remands
    # the operational loop produces only L1 context and authors NO L3 scar (IP-0005 Axiom 1)
    assert outcomes[0].ephemeral_context is not None
    assert runner.scar_store.match_scars(query) == []
    # the Evolution Layer is the sole L3 author (Stage 17)
    EvolutionLayer(scar_store=runner.scar_store).run(
        outcomes[0], goal_signature=sig, changed_paths=("runtime/x.py",)
    )
    assert len(runner.scar_store.match_scars(query)) == 1


def test_stored_scar_is_injected_into_a_later_design() -> None:
    scar_store = ScarStore()
    scar_store.propose_scar(
        ScarDraft(frozenset({"domain:runtime", "kind:seam"}), "watch the seams", "sig")
    )
    runtime = ScriptedRuntime()
    _runner(runtime, scar_store).run_backlog(
        [_intake(_GOOD, signature="domain:runtime,kind:seam,task:t")]
    )
    design_pkg = runtime.packages[StageId.DESIGN]
    assert any(ref.type == "scar" for ref in design_pkg.context_refs)  # prior lesson on the path
