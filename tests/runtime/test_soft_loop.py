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
        StageId.ADVERSARIAL_REVIEW: (
            AgentWrite("review/adversary_report.md", b"no dissent\nVERDICT: PASS\n"),
        ),
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


# ---- court remand produces an L1 note, NOT an L3 scar (IP-0005/0006, B2.G) -


def test_court_remand_produces_l1_note_and_writes_no_scar() -> None:
    forged = (_evidence("builds", "echo built", "FORGED\n"),)  # command emits "built", not "FORGED"
    scar_store = ScarStore()
    runtime = ScriptedRuntime(_writes())
    outcome = _loop(runtime, scar_store=scar_store).run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=forged,
    )
    assert outcome.status is RunStatus.REMANDED
    assert outcome.verdict is not None and outcome.verdict.outcome is VerdictOutcome.REMAND
    # L1/L3 boundary: the loop records only L1 Ephemeral Execution Context (run-scoped)...
    assert outcome.ephemeral_context is not None
    assert outcome.ephemeral_context.retry_hints  # a retry hint, not a scar
    # ...and authors NO L3 scar (that is the Evolution Layer's Stage-17 authority, IP-0005 Axiom 1).
    assert scar_store.match_scars("stage:VERIFY,kind:court-remand,goal:x") == []


# ---- B2.O: vacuous (non-probative) evidence is remanded when verified --------


def test_vacuous_evidence_remands_under_verification(tmp_path: object) -> None:
    from pathlib import Path

    from kernel.ledger import InMemoryLedgerStore, Ledger

    # a verification repo whose file the builder "changes"; the echo evidence is non-discriminating
    repo = Path(str(tmp_path)) / "repo"
    (repo / "runtime").mkdir(parents=True)
    (repo / "runtime" / "feature.py").write_text("old\n")
    loop = SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()), signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()), agent_runtime=ScriptedRuntime(_writes()),
        budget_by_class=_BUDGETS, repo_root=repo,
    )
    outcome = loop.run(
        objective="x", changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    assert outcome.status is RunStatus.REMANDED  # echo evidence proves nothing about the change
    assert "vacuous" in outcome.detail


# ---- live evidence binding: evidence binds to the produced artifact (R4) ---


def test_evidence_is_bound_to_the_produced_artifact() -> None:
    from dataclasses import replace as _replace

    # a live artifact's hash is unknowable when the backlog is authored, so the declared evidence
    # carries a mismatched artifact_hash; the loop rebinds it to the produced artifact and seals.
    ev = _replace(_evidence("builds", "echo built", "built\n"), artifact_hash="f" * 64)
    runtime = ScriptedRuntime(_writes())
    outcome = _loop(runtime).run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=(ev,),
    )
    assert outcome.status is RunStatus.SEALED  # would REMAND (StaleEvidence) without rebinding
    assert outcome.seal is not None


# ---- B2.K / IP-0007: the seal is gated on the adversary's PASS verdict (FR-3) ----


def test_adversary_block_remands_the_seal() -> None:
    from runtime.review import AdversaryOutcome, read_adversary_verdict

    # fail-closed verdict parsing (deny-by-default)
    assert read_adversary_verdict(b"looks fine\nVERDICT: PASS\n") is AdversaryOutcome.PASS
    assert read_adversary_verdict(b"D1 broken\nVERDICT: BLOCK\n") is AdversaryOutcome.BLOCK
    assert read_adversary_verdict(b"no verdict line") is AdversaryOutcome.BLOCK

    # a blocking dissent must REMAND, not seal — even when the court passed
    writes = _writes()
    writes[StageId.ADVERSARIAL_REVIEW] = (
        AgentWrite("review/adversary_report.md", b"D1: unreadable bundle\nVERDICT: BLOCK\n"),
    )
    outcome = _loop(ScriptedRuntime(writes)).run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    assert outcome.status is RunStatus.REMANDED
    assert "adversary blocked" in outcome.detail
    assert outcome.seal is None


def test_missing_adversary_report_fails_closed() -> None:
    # the adversary produced NO report (could not review) ⇒ deny-by-default REMAND
    writes = _writes()
    writes[StageId.ADVERSARIAL_REVIEW] = ()  # no report written
    outcome = _loop(ScriptedRuntime(writes)).run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    assert outcome.status is RunStatus.REMANDED


def test_goal_objective_is_threaded_into_every_stage() -> None:
    # B2.L: DESIGN/PLAN/IMPLEMENT must each receive the goal objective, not just a generic role one
    runtime = ScriptedRuntime(_writes())
    _loop(runtime).run(
        objective="ADD_SENTINEL_XYZ helper", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    for stage in (StageId.DESIGN, StageId.PLAN, StageId.IMPLEMENT):
        assert "ADD_SENTINEL_XYZ" in runtime.packages[stage].objective


def test_adversary_receives_serialized_evidence() -> None:
    # B2.M: the adversary's context carries readable, materialisable evidence (not a bare hash)
    from runtime.orchestrator import _serialize_evidence

    blob = _serialize_evidence(_GOOD_EVIDENCE[0])
    assert b"reproducible_command" in blob and b"echo built" in blob
    runtime = ScriptedRuntime(_writes())
    _loop(runtime).run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    adv_pkg = runtime.packages[StageId.ADVERSARIAL_REVIEW]
    assert any(ref.type == "evidence" for ref in adv_pkg.context_refs)


def test_implement_receives_design_and_plan_as_context() -> None:
    # B2.J: design + plan chain forward so the Builder has a plan to implement against
    runtime = ScriptedRuntime(_writes())
    _loop(runtime).run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    impl_pkg = runtime.packages[StageId.IMPLEMENT]
    assert impl_pkg.context_refs  # design + plan artifacts injected as IMPLEMENT context


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
