"""Soft-loop orchestrator — the unattended end-to-end run (PAEOS-8 §157 / R2→R3).

This is the Phase-1 capstone: it *composes* the whole spine into one autonomous run. An intake is
triaged (B1.G), a goal is opened on the ledger, and the run walks the build chain with scoped agent
sessions (B1.B/C) — Planner (DESIGN, PLAN) → Builder (IMPLEMENT), matched scars injected (B1.F) —
then the **Verification Court** reproduces the evidence (B1.E), an **isolated Adversary** reviews
only the sealed bundle behind the information barrier (B1.D), and the change is **sealed** (B0.9).
Budget is charged and halts on breach (B1.G); a court remand writes a scar (B1.F). The runtime
*holds no opinions* — every decision is made by the kernel/court/gate it composes.

Agent sessions run behind the B1.B `AgentRuntime` seam (validated by the DEBT-0002 spike); the real
Claude Agent SDK adapter implements it, tests script it. Nothing here can grant authority it lacks.
"""

from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from kernel.capability import CapabilityBroker
from kernel.cas import CAS
from kernel.evidence import Evidence
from kernel.ledger import Event, Ledger
from kernel.seal import SealAuthority, SealRecord
from kernel.types import ArtifactRef, Claim, StageId, WeightClass
from nacl.signing import SigningKey

from runtime.agents import StagePlaybook
from runtime.claude_code import AgentDispatcher, AgentRuntime
from runtime.court import Court, Verdict, VerdictOutcome
from runtime.memory import ScarStore
from runtime.review import (
    AdversaryOutcome,
    InformationBarrierManager,
    ReviewHarness,
    read_adversary_verdict,
)
from runtime.task_package import Budget, ExecutionContext, TaskResult
from runtime.triage import BudgetExceeded, GoalBudget, triage
from runtime.verification import (
    build_verification_workspace,
    vacuous_commands,
    workspace_runner,
)

__all__ = [
    "CourtEvidencePool",
    "Intake",
    "RunOutcome",
    "RunStatus",
    "SelfHostRunner",
    "SoftLoop",
]

GOAL_CREATED = "goal_created"


class CourtEvidencePool:
    """The autonomous evidence source (B2.P, toward R5): evidence the Builder **submits per run**,
    replacing the pre-declared backlog. In deployment the live Builder submits via the `CourtServer`
    MCP (`mcp:court:write`); this pool records submissions by `run_id` and the `SoftLoop` pulls what
    was submitted for its run — so the agent produces its own evidence, never authored for it."""

    def __init__(self) -> None:
        self._by_run: dict[str, list[Evidence]] = {}

    def submit(self, run_id: str, evidence: Evidence) -> None:
        self._by_run.setdefault(run_id, []).append(evidence)

    def evidence_for(self, run_id: str) -> tuple[Evidence, ...]:
        return tuple(self._by_run.get(run_id, ()))


class RunStatus(Enum):
    SEALED = "SEALED"
    REMANDED = "REMANDED"
    HALTED = "HALTED"  # budget breach


@dataclass(frozen=True, slots=True)
class RunOutcome:
    status: RunStatus
    goal_id: str
    detail: str
    seal: SealRecord | None = None
    verdict: Verdict | None = None
    # L1 Ephemeral Execution Context (IP-0004/0006): run-scoped operational state produced on a
    # remand (retry hints/diagnostics), NOT institutional memory. Never promoted in place — the
    # Evolution Layer authors the L3 scar out-of-band at Stage 17.
    ephemeral_context: ExecutionContext | None = None


class SoftLoop:
    """Runs one intake to a sealed (or remanded/halted) change, unattended."""

    def __init__(
        self,
        *,
        ledger: Ledger,
        signing_key: SigningKey,
        cas: CAS,
        agent_runtime: AgentRuntime,
        budget_by_class: Mapping[WeightClass, Budget],
        court: Court | None = None,
        scar_store: ScarStore | None = None,
        ibm: InformationBarrierManager | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._ledger = ledger
        self._cas = cas
        self._budget_by_class = budget_by_class
        # When set, the court verifies each reproducible_command against a workspace with the
        # builder's change applied (B2.N) — so probative evidence can pass. None ⇒ injected court.
        self._repo_root = repo_root
        broker = CapabilityBroker(signing_key)
        dispatcher = AgentDispatcher(broker, cas, agent_runtime, clock=self._now)
        self._playbook = StagePlaybook(dispatcher)
        self._court = court if court is not None else Court()
        self._ibm = ibm if ibm is not None else InformationBarrierManager()
        self._review = ReviewHarness(self._ibm, dispatcher)
        self._scars = scar_store if scar_store is not None else ScarStore()
        self._seal = SealAuthority(signing_key, ledger)

    @property
    def scar_store(self) -> ScarStore:
        """The shared scar store — scars written across runs accumulate here (self-improvement)."""
        return self._scars

    def _now(self) -> int:
        head = self._ledger.head()
        return head.seq if head is not None else 0

    def run(
        self,
        *,
        objective: str,
        changed_paths: tuple[str, ...],
        plan_write_scopes: tuple[str, ...],
        builder_evidence: tuple[Evidence, ...],
        verifiable: bool = True,
        reversible: bool = True,
        goal_signature: str = "",
        run_id: str = "r-1",
        evidence_source: Callable[[str], tuple[Evidence, ...]] | None = None,
    ) -> RunOutcome:
        decision = triage(
            changed_paths=changed_paths,
            verifiable=verifiable,
            reversible=reversible,
            budget_by_class=self._budget_by_class,
        )
        budget = GoalBudget(decision.budget)
        goal_id = "g-" + uuid.uuid4().hex[:12]
        self._ledger.append(
            Event(
                1, GOAL_CREATED,
                {"goal_id": goal_id, "weight_class": decision.weight_class.value},
            )
        )

        try:
            # --- Planner: DESIGN then PLAN (matched scars injected, FR-6) ---
            # Stage context chains forward (B2.J): PLAN sees DESIGN, IMPLEMENT sees design + plan —
            # so the live Builder has a plan to implement against (it blocked without one).
            # The goal objective is threaded into every stage (B2.L) so DESIGN designs FOR it, PLAN
            # plans FOR it, and the Builder is told the specific change — without it each stage got
            # only a generic role objective and the Builder had nothing concrete to implement.
            goal_detail = f"Goal objective: {objective}"
            planner_artifacts: list[ArtifactRef] = []
            for stage in (StageId.DESIGN, StageId.PLAN):
                scars = self._scar_refs(goal_signature, stage)
                result = self._playbook.run_stage(
                    goal_id=goal_id, run_id=run_id, stage=stage, session="planner",
                    budget=decision.budget, scars=scars, context_refs=tuple(planner_artifacts),
                    detail=goal_detail,
                )
                budget.charge(result.cost)
                planner_artifacts.extend(result.artifacts)

            # --- Builder: IMPLEMENT on the plan scopes, with design + plan as context (B2.J) ---
            build = self._playbook.run_stage(
                goal_id=goal_id, run_id=run_id, stage=StageId.IMPLEMENT, session="builder",
                budget=decision.budget, write_scopes=plan_write_scopes,
                context_refs=tuple(planner_artifacts), detail=goal_detail,
            )
            budget.charge(build.cost)
            if not build.artifacts:
                return RunOutcome(RunStatus.REMANDED, goal_id, "builder produced no artifact")
            artifact = build.artifacts[0]
        except BudgetExceeded as exc:
            return RunOutcome(RunStatus.HALTED, goal_id, f"budget breach: {exc}")

        # Autonomous evidence (B2.P, toward R5): pull the evidence the Builder SUBMITTED for this
        # run (via the court MCP) instead of the pre-declared backlog. Empty ⇒ REMAND — the agent
        # must produce its own probative evidence, not have it authored for it.
        if evidence_source is not None:
            builder_evidence = evidence_source(run_id)
            if not builder_evidence:
                return RunOutcome(
                    RunStatus.REMANDED, goal_id, "no evidence submitted to the court for this run"
                )

        # Live evidence binding (R4): bind the declared evidence to the artifact the builder
        # ACTUALLY produced, so a live, novel artifact is adjudicable (its hash is unknowable when
        # the backlog is authored). The court still RE-RUNS each `reproducible_command`, so the T2
        # anti-forgery property is intact — only the artifact_hash binding is set to the real hash.
        builder_evidence = tuple(
            replace(ev, artifact_hash=artifact.hash) for ev in builder_evidence
        )

        # --- Verification Court: reproduce every claim (B1.E). For a live run the command runs
        # against a workspace with the change applied (B2.N), so probative evidence can pass. ---
        claims = tuple(
            Claim(id=ev.claim_id, statement="produced", evidence_refs=(ev.hash,))
            for ev in builder_evidence
        )
        court, cleanup = self._court_for_run(build)
        try:
            for evidence in builder_evidence:
                court.submit_evidence(evidence)
            verdict = court.adjudicate(artifact.hash, claims)
        finally:
            cleanup()
        if verdict.outcome is VerdictOutcome.REMAND:
            # L1/L3 boundary (IP-0005/0006, B2.G): the operational loop does NOT author or commit
            # an L3 scar — that is the Evolution Layer's Stage-17 authority. The loop records only
            # L1 Ephemeral Execution Context (run-scoped retry hints), never institutional memory.
            context = ExecutionContext(
                retry_hints=("re-run and fix the unmet claims the court could not reproduce",),
                diagnostics=(f"court remanded {goal_id}: unmet {verdict.unmet_claims}",),
            )
            return RunOutcome(
                RunStatus.REMANDED, goal_id, "court remanded",
                verdict=verdict, ephemeral_context=context,
            )

        # --- Probative-evidence gate (B2.O / CANARY-0002): even a reproducing command must
        # DISCRIMINATE — its result must differ with the change vs without. Vacuous (non-probative)
        # evidence remands, mechanising the vacuous-evidence defect the live Adversary caught. ---
        if self._repo_root is not None:
            commands = tuple(
                ev.reproducible_command for ev in builder_evidence if ev.reproducible_command
            )
            vacuous = vacuous_commands(self._repo_root, build.written_paths, self._cas, commands)
            if vacuous:
                context = ExecutionContext(
                    retry_hints=("evidence must exercise the change — a command with the same "
                                 "result with and without it proves nothing; supply a real test",),
                    diagnostics=(f"non-probative (vacuous) evidence: {vacuous}",),
                )
                return RunOutcome(
                    RunStatus.REMANDED, goal_id, "non-probative (vacuous) evidence",
                    verdict=verdict, ephemeral_context=context,
                )

        # --- Isolated Adversary over the sealed bundle (B1.D / FR-3) ---
        # B2.M: store a serialized copy of each evidence in the CAS and reference THAT, so the
        # adversary can actually read (and re-run) the evidence in its workspace — a bare evidence
        # hash is not a CAS blob and materialises to nothing (the adversary blocked without it).
        evidence_refs = tuple(self._cas.put(_serialize_evidence(ev)) for ev in builder_evidence)
        bundle = self._ibm.seal(artifact_refs=(artifact,), evidence_refs=evidence_refs)
        try:
            adversary = self._review.review(
                goal_id=goal_id, run_id=run_id, session="adversary", bundle=bundle,
                budget=decision.budget,
            )
            budget.charge(adversary.cost)
        except BudgetExceeded as exc:
            return RunOutcome(RunStatus.HALTED, goal_id, f"budget breach at review: {exc}")

        # --- Adversary gate (B2.K / IP-0007, FR-3): a seal requires an adversarial PASS.
        # Fail-closed: no report (adversary could not review), or a BLOCK verdict, REMANDS. ---
        if adversary.artifacts:
            adversary_outcome = read_adversary_verdict(self._cas.get(adversary.artifacts[0].hash))
        else:
            adversary_outcome = AdversaryOutcome.BLOCK
        if adversary_outcome is AdversaryOutcome.BLOCK:
            context = ExecutionContext(
                retry_hints=("the adversary filed a blocking dissent — fix the defect, re-review",),
                diagnostics=(f"adversary BLOCK on goal {goal_id} at ADVERSARIAL_REVIEW",),
            )
            return RunOutcome(
                RunStatus.REMANDED, goal_id, "adversary blocked the seal",
                verdict=verdict, ephemeral_context=context,
            )

        # --- Seal (B0.9): idempotent, over the bundle + verdict + adversary + ledger head ---
        verdict_ref = self._cas.put(_canonical(verdict).encode("ascii"))
        seal = self._seal.seal(
            goal_id=goal_id, run_id=run_id, artifact_bundle=bundle.bundle_hash,
            verdict_ref=verdict_ref, adversary_ref=adversary.trace_ref,
        )
        return RunOutcome(RunStatus.SEALED, goal_id, "sealed", seal=seal, verdict=verdict)

    def _court_for_run(self, build: TaskResult) -> tuple[Court, Callable[[], None]]:
        """The court to adjudicate this run's evidence (B2.N). For a live run (repo_root set + the
        builder wrote files), verify commands against a workspace with the change applied — so
        probative evidence passes; otherwise use the injected court. Returns (court, cleanup)."""
        if self._repo_root is None or not build.written_paths:
            return self._court, lambda: None
        workspace = build_verification_workspace(self._repo_root, build.written_paths, self._cas)
        return (
            Court(runner=workspace_runner(workspace)),
            lambda: shutil.rmtree(workspace, ignore_errors=True),
        )

    def _scar_refs(self, goal_signature: str, stage: StageId) -> tuple[ArtifactRef, ...]:
        refs: list[ArtifactRef] = []
        for scar in self._scars.injected_scars(signature=goal_signature, stage=stage):
            content = json.dumps(
                {"id": scar.id, "lesson": scar.lesson, "detection": scar.detection},
                sort_keys=True,
            ).encode("ascii")
            refs.append(ArtifactRef(hash=self._cas.put(content), type="scar"))
        return tuple(refs)


def _serialize_evidence(ev: Evidence) -> bytes:
    """A readable copy of an evidence for the adversary's workspace (B2.M) — the claim, the command
    to re-run, the claimed result, and the artifact it binds to."""
    return json.dumps(
        {
            "claim_id": ev.claim_id,
            "kind": ev.kind.name,
            "reproducible_command": ev.reproducible_command,
            "result": ev.result,
            "artifact_hash": ev.artifact_hash,
        },
        sort_keys=True,
        indent=2,
    ).encode("utf-8")


def _canonical(verdict: Verdict) -> str:
    return json.dumps(
        {
            "outcome": verdict.outcome.value,
            "artifact_hash": verdict.artifact_hash,
            "unmet": sorted(verdict.unmet_claims),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True)
class Intake:
    """One backlog item — the intake a self-hosting run consumes."""

    objective: str
    changed_paths: tuple[str, ...]
    plan_write_scopes: tuple[str, ...]
    builder_evidence: tuple[Evidence, ...]
    goal_signature: str = ""
    verifiable: bool = True
    reversible: bool = True


class SelfHostRunner:
    """Pulls goals from a backlog and runs each through one shared `SoftLoop` (§12 R3→R4).

    The loop is shared, so **scars accumulate across runs** and the ledger records every run — the
    soft-loop self-improvement the R3→R4 rung requires. A live run uses a live `AgentRuntime`; the
    composition (and the learning across runs) is the same either way.
    """

    def __init__(self, loop: SoftLoop) -> None:
        self._loop = loop

    @property
    def scar_store(self) -> ScarStore:
        return self._loop.scar_store

    def run_backlog(self, backlog: Iterable[Intake]) -> list[RunOutcome]:
        outcomes: list[RunOutcome] = []
        for intake in backlog:
            outcomes.append(
                self._loop.run(
                    objective=intake.objective,
                    changed_paths=intake.changed_paths,
                    plan_write_scopes=intake.plan_write_scopes,
                    builder_evidence=intake.builder_evidence,
                    goal_signature=intake.goal_signature,
                    verifiable=intake.verifiable,
                    reversible=intake.reversible,
                )
            )
        return outcomes
