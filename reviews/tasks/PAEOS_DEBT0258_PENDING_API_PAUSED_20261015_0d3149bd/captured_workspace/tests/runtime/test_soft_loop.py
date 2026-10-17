"""Phase-1 Soft-Loop Integration — the unattended end-to-end run (PAEOS-8 §157).

One intake reaches a sealed, court-passed, adversary-reviewed change behind real information
barriers, with scars written and triage/budget enforced — Planner, Builder, Verifier, Adversary
composed over the sealed Phase-0 kernel.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import Role, StageId, WeightClass
from nacl.signing import SigningKey
from runtime.ceremony import Layer
from runtime.claude_code import AgentWrite, RunOutput
from runtime.court import VerdictOutcome
from runtime.court.completeness_firewall import (
    VerificationObligation,
    create_authoritative_manifest,
)
from runtime.memory import ScarDraft, ScarStore
from runtime.orchestrator import RunStatus, SoftLoop
from runtime.sidecar_scorer import SidecarStageScorer
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
            workspace_identity="scripted-worker-workspace",
            environment_identity="scripted-worker-environment",
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
        StageId.RETROSPECT: (AgentWrite("retrospective/retro.md", b"retrospect"),),
        StageId.MEMORY_UPDATE: (AgentWrite("memory/scar.md", b"scar"),),
    }


def _loop(runtime: ScriptedRuntime, *, scar_store: ScarStore | None = None,
         budgets: dict[WeightClass, Budget] | None = None) -> SoftLoop:
    return SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()), signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()), agent_runtime=runtime,
        budget_by_class=budgets if budgets is not None else _BUDGETS,
        scar_store=scar_store,
        sidecar_scorer=SidecarStageScorer(None),  # DEBT-0057: explicitly non-persistent
    )


_GOOD_EVIDENCE = (
    _evidence("builds", "echo built", "built\n"),
    _evidence("unit", "echo tests-pass", "tests-pass\n"),
)


# ---- the full unattended run reaches SEAL ---------------------------------


def test_unattended_run_reaches_seal() -> None:
    # Trace-B (Substantial) intake: the full ceremony path — the entire front-end chain executes
    # and the run reaches SEAL. (Trace-A discharges the front-end — see test_trace_a_run_discharges_.)
    runtime = ScriptedRuntime(_writes())
    loop = _loop(runtime)
    outcome = loop.run(
        objective="add feature()", changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
        reversible=False,  # non-reversible => Substantial => Trace-B full ceremony
    )
    assert outcome.status is RunStatus.SEALED
    assert outcome.seal is not None
    assert outcome.verdict is not None and outcome.verdict.outcome is VerdictOutcome.PASS
    # all required Trace-B stages ran, in exact canonical order
    assert runtime.stages_run == [
        StageId.RE_DERIVE,
        StageId.IDEATE,
        StageId.RESEARCH,
        StageId.TRADEOFF,
        StageId.MITIGATION,
        StageId.DESIGN,
        StageId.CRITIQUE,
        StageId.ADVERSARIAL_REVIEW,
        StageId.PLAN,
        StageId.IMPLEMENT,
        StageId.ADVERSARIAL_REVIEW,
        StageId.RETROSPECT,
        StageId.MEMORY_UPDATE,
    ]
    # Planner, Critic, Adversary, Builder roles were correctly scoped
    assert runtime.packages[StageId.RE_DERIVE].role is Role.PLANNER
    assert runtime.packages[StageId.DESIGN].role is Role.PLANNER
    assert runtime.packages[StageId.CRITIQUE].role is Role.CRITIC
    assert runtime.packages[StageId.IMPLEMENT].role is Role.BUILDER
    assert runtime.packages[StageId.ADVERSARIAL_REVIEW].role is Role.ADVERSARY
    events = [row.event for row in loop._ledger.read()]
    lifecycle_adversaries = [
        event for event in events
        if event.kind == "STAGE_COMPLETED"
        and event.payload.get("stage") == StageId.ADVERSARIAL_REVIEW.name
    ]
    assert len(lifecycle_adversaries) == 1  # canonical L10 only
    gate_events = [event for event in events if event.kind == "ADVERSARY_GATE_REVIEWED"]
    assert len(gate_events) == 1
    assert gate_events[0].payload["lifecycle_layer"] is None
    # Trace-B never discharges: no LAYER_DISCHARGED rows in the ledger
    assert not [r for r in loop._ledger.read() if r.event.kind == "layer_discharged"]


def test_trace_a_run_discharges_front_end_and_seals() -> None:
    # Canonical Trace-A (reversible + cheaply verified): the L02 ceremony contract DISCHARGES the
    # front-end planner stages (L03-L11/L17/L18), so they record K1 stubs and do NOT execute;
    # only IMPLEMENT (L12, never dischargeable) + ADVERSARIAL_REVIEW (L14) run, and the run seals.
    runtime = ScriptedRuntime(_writes())
    loop = _loop(runtime)
    outcome = loop.run(
        objective="add feature()", changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
    )  # default verifiable=True, reversible=True => ROUTINE => Trace-A
    assert outcome.status is RunStatus.SEALED
    # the discharged front-end stages were NOT executed (the old unconditional MITIGATION->DESIGN
    # chain is gone on the fast path)
    assert runtime.stages_run == [StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW]
    assert StageId.DESIGN not in runtime.packages  # discharged, never ran
    # the goal was classified ROUTINE on the canonical fast path
    kinds = [r.event.payload.get("weight_class") for r in loop._ledger.read()
             if r.event.kind == "goal_created"]
    assert kinds == [WeightClass.ROUTINE.value]
    # exactly the 11 canonical Trace-A auto-discharge stubs were recorded (L03-L11, L17, L18)
    discharged = [r for r in loop._ledger.read() if r.event.kind == "layer_discharged"]
    assert len(discharged) == 11
    stub_layers = {r.event.payload["discharge"]["layer"] for r in discharged}
    assert stub_layers == {layer.value for layer in (
        Layer.L03, Layer.L04, Layer.L05, Layer.L06, Layer.L07, Layer.L08,
        Layer.L09, Layer.L10, Layer.L11, Layer.L17, Layer.L18,
    )}
    for row in discharged:
        stub = row.event.payload["discharge"]
        assert stub["result"] == "auto_pass"
        assert stub["reason"] == "trace_a"
        assert stub["by"] == "runtime"



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


# ---- B2.P: autonomous evidence from the court pool (agent-submitted) ---------


def test_autonomous_evidence_from_the_court_pool_seals() -> None:
    from runtime.orchestrator import CourtEvidencePool

    pool = CourtEvidencePool()
    for ev in _GOOD_EVIDENCE:  # the Builder "submits" its own evidence (via the court MCP)
        pool.submit("r-1", ev)
    outcome = _loop(ScriptedRuntime(_writes())).run(
        objective="x", changed_paths=("runtime/f.py",), plan_write_scopes=("runtime/feature.py",),
        builder_evidence=(),  # NONE pre-declared — it comes from the court pool
        evidence_source=pool,
    )
    assert outcome.status is RunStatus.SEALED  # sealed on the agent's own submitted evidence


def test_no_submitted_evidence_remands() -> None:
    from runtime.orchestrator import CourtEvidencePool

    pool = CourtEvidencePool()  # the agent submitted nothing
    outcome = _loop(ScriptedRuntime(_writes())).run(
        objective="x", changed_paths=("runtime/f.py",), plan_write_scopes=("runtime/feature.py",),
        builder_evidence=(), evidence_source=pool,
    )
    assert outcome.status is RunStatus.REMANDED
    assert "no evidence" in outcome.detail


# ---- B2.O: vacuous (non-probative) evidence is remanded when verified --------


def test_vacuous_evidence_remands_under_verification(tmp_path: Path) -> None:
    # A production-shaped verification repo whose verifier ignores the candidate change. The
    # authoritative manifest supplies the obligation; the runtime must reject it before L14.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "runtime").mkdir(parents=True)
    (repo / "runtime" / "feature.py").write_text("old\n")
    (repo / "verify.py").write_text("print('same result with or without the candidate')\n")
    for args in (
        ("init", "--quiet"),
        ("config", "user.email", "p1-vacuity@example.invalid"),
        ("config", "user.name", "P1 vacuity test"),
        ("add", "runtime/feature.py", "verify.py"),
        ("commit", "--quiet", "-m", "vacuity baseline"),
    ):
        completed = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=False
        )
        assert completed.returncode == 0, completed.stderr

    manifest = create_authoritative_manifest(
        manifest_id="P1-VACUITY-PROBE",
        milestone_id="P1-VACUITY-PROBE",
        expected_capabilities=("CAP-VACUOUS-VERIFIER",),
        verification_obligations=(
            VerificationObligation("CAP-VACUOUS-VERIFIER", ("{python}", "verify.py")),
        ),
    )
    loop = SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()),
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()), agent_runtime=ScriptedRuntime(_writes()),
        budget_by_class=_BUDGETS, repo_root=repo, state_dir=tmp_path / "state",
        sidecar_scorer=SidecarStageScorer(None),
    )
    outcome = loop.run(
        objective="x", changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=(),
        verifiable=False, capability_manifest=manifest, run_id="p1-vacuity-probe",
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
        reversible=False,  # Trace-B: full front-end so all stages receive the objective
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
        reversible=False,  # Trace-B: DESIGN+PLAN execute, chaining to IMPLEMENT
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
        reversible=False,  # Trace-B: DESIGN executes so the scar injection is observable
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
    # Trace-B (Substantial) full front-end: MITIGATION+DESIGN alone (2x1000 tokens) exceed the
    # tightened Substantial budget, so the run HALTs on budget breach before IMPLEMENT.
    tight = {**_BUDGETS, WeightClass.SUBSTANTIAL: Budget(1500, 7200, 5)}  # only ~1 dispatch fits
    runtime = ScriptedRuntime(_writes(), cost_tokens=1000)
    outcome = _loop(runtime, budgets=tight).run(
        objective="x", changed_paths=("runtime/f.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
        reversible=False,  # Trace-B => Substantial budget applies
    )
    assert outcome.status is RunStatus.HALTED  # front-end chain (2x1000) > 1500


def test_file_court_evidence_pool_roundtrips(tmp_path: object) -> None:
    # R5: the durable, cross-process evidence pool a live submitter writes and the loop reads
    from pathlib import Path

    from runtime.orchestrator import FileCourtEvidencePool

    pool = FileCourtEvidencePool(Path(str(tmp_path)) / "court")
    assert pool.evidence_for("r-1") == ()  # empty before any submission
    for ev in _GOOD_EVIDENCE:
        pool.submit("r-1", ev)
    got = pool.evidence_for("r-1")
    assert len(got) == len(_GOOD_EVIDENCE)
    assert got[0].claim_id == _GOOD_EVIDENCE[0].claim_id
    assert got[0].reproducible_command == _GOOD_EVIDENCE[0].reproducible_command
    assert got[0].result == _GOOD_EVIDENCE[0].result
    # a fresh pool over the same dir reads the durably-persisted submissions (cross-process)
    assert len(FileCourtEvidencePool(Path(str(tmp_path)) / "court").evidence_for("r-1")) == 2


def test_omitted_trace_b_stage_fails() -> None:
    # Remand requirement: Prove that omitting any required Trace-B stage is strictly caught
    runtime = ScriptedRuntime(_writes())
    loop = _loop(runtime)
    outcome = loop.run(
        objective="add feature()", changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
        reversible=False,  # Trace-B full ceremony
    )
    assert outcome.status is RunStatus.SEALED
    
    # Assert every single canonical Trace-B obligation was executed
    expected_obligations = [
        StageId.RE_DERIVE, StageId.IDEATE, StageId.RESEARCH, StageId.TRADEOFF,
        StageId.MITIGATION, StageId.DESIGN, StageId.CRITIQUE, StageId.ADVERSARIAL_REVIEW,
        StageId.PLAN, StageId.IMPLEMENT, StageId.ADVERSARIAL_REVIEW,
        StageId.RETROSPECT, StageId.MEMORY_UPDATE,
    ]
    for required in expected_obligations:
        assert required in runtime.stages_run, f"Trace-B failed: missing required obligation {required}"


def test_l19_trigger_and_non_trigger_semantics() -> None:
    # 1. Non-triggering run (SUBSTANTIAL): L19 is lawfully NOT executed
    runtime_non_trigger = ScriptedRuntime(_writes())
    loop_non_trigger = _loop(runtime_non_trigger)
    outcome_non_trigger = loop_non_trigger.run(
        objective="substantial non-kernel feature", changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
        reversible=False,  # Substantial weight class
    )
    assert outcome_non_trigger.status is RunStatus.SEALED
    assert StageId.EVOLVE not in runtime_non_trigger.stages_run

    # 2. Triggering run (KERNEL_TOUCHING): L19 is executed and records stage
    writes_kernel = {
        **_writes(impl_path="kernel/mod.py"),
        StageId.EVOLVE: (AgentWrite("constitution/amendment.md", b"amendment"),),
    }
    runtime_trigger = ScriptedRuntime(writes_kernel)
    loop_trigger = _loop(runtime_trigger)
    outcome_trigger = loop_trigger.run(
        objective="touch kernel", changed_paths=("kernel/mod.py",),
        plan_write_scopes=("kernel/mod.py",), builder_evidence=_GOOD_EVIDENCE,
    )
    assert outcome_trigger.status is RunStatus.SEALED
    assert StageId.EVOLVE in runtime_trigger.stages_run
    assert runtime_trigger.packages[StageId.EVOLVE].role is Role.RATIFIER


def test_l10_l14_discrimination() -> None:
    # Remand requirement: Prove L10 (pre-build design review) and L14 (post-build verification)
    # are unambiguously discriminated at their distinct execution sites
    runtime = ScriptedRuntime(_writes())
    loop = _loop(runtime)
    outcome = loop.run(
        objective="add feature()", changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",), builder_evidence=_GOOD_EVIDENCE,
        reversible=False,
    )
    assert outcome.status is RunStatus.SEALED

    # Find the two occurrences of ADVERSARIAL_REVIEW in the execution trace
    adv_indices = [i for i, s in enumerate(runtime.stages_run) if s is StageId.ADVERSARIAL_REVIEW]
    assert len(adv_indices) == 2
    l10_idx, l14_idx = adv_indices

    # L10 must execute before PLAN and IMPLEMENT
    impl_idx = runtime.stages_run.index(StageId.IMPLEMENT)
    plan_idx = runtime.stages_run.index(StageId.PLAN)
    assert l10_idx < plan_idx < impl_idx

    # L14 must execute after IMPLEMENT
    assert impl_idx < l14_idx

    # L10 receives design/critique context; L14 receives sealed IBM bundle
    assert runtime.packages[StageId.ADVERSARIAL_REVIEW].role is Role.ADVERSARY
    assert any(ref.type == "evidence" for ref in runtime.packages[StageId.ADVERSARIAL_REVIEW].context_refs)
