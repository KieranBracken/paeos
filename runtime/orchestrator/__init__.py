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

import hashlib
import json
import shutil
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Protocol, cast

from kernel.capability import CapabilityBroker
from kernel.cas import CAS
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.gates import Gate
from kernel.ledger import Event, JsonValue, Ledger
from kernel.seal import SealAuthority, SealRecord
from kernel.types import (
    ArtifactRef,
    Claim,
    Role,
    StageId,
    TransitionRequest,
    ValidationClaim,
    WeightClass,
)
from nacl.signing import SigningKey

from runtime.agents import StagePlaybook
from runtime.ceremony import CeremonyContract, Layer, Obligation
from runtime.claude_code import AgentDispatcher, AgentRuntime
from runtime.court import Court, Verdict, VerdictOutcome
from runtime.memory import ScarStore
from runtime.retrospective import RetrospectiveEngine, RetrospectiveTransitionRejected
from runtime.review import (
    AdversaryOutcome,
    InformationBarrierManager,
    ReviewHarness,
    read_adversary_verdict,
)
from runtime.scar_store import SqliteScarStore
from runtime.sidecar_scorer import SidecarStageScorer
from runtime.task_package import Budget, ExecutionContext, TaskResult
from runtime.triage import BudgetExceeded, GoalBudget, TriageDecision, triage
from runtime.verification import (
    build_verification_workspace,
    vacuous_commands,
    workspace_runner,
)

__all__ = [
    "CourtEvidencePool",
    "EvidenceSource",
    "FileCourtEvidencePool",
    "Intake",
    "RunOutcome",
    "RunStatus",
    "SelfHostRunner",
    "SoftLoop",
]

GOAL_CREATED = "goal_created"


def durable_scar_store(state_dir: Path) -> ScarStore:
    """Construct the state-directory-owned scar store used by autonomous composition roots."""
    return SqliteScarStore(state_dir)


LAYER_DISCHARGED = "layer_discharged"


# Canonical front-end planner stages -> their lifecycle Layer (L03-L11).
# Driven by the L02 ceremony contract (EL L24-28): a DISCHARGE obligation records its
# K1 stub and does NOT execute; only EXECUTE obligations run.
FRONTEND_PLANNER_STAGES: tuple[tuple[StageId, Layer], ...] = (
    (StageId.RE_DERIVE, Layer.L03),
    (StageId.IDEATE, Layer.L04),
    (StageId.RESEARCH, Layer.L05),
    (StageId.TRADEOFF, Layer.L06),
    (StageId.MITIGATION, Layer.L07),
    (StageId.DESIGN, Layer.L08),
    (StageId.CRITIQUE, Layer.L09),
    (StageId.ADVERSARIAL_REVIEW, Layer.L10),
    (StageId.PLAN, Layer.L11),
)

# Canonical post-seal evolution stages -> their lifecycle Layer (L17-L18).
POST_SEAL_EVOLUTION_STAGES: tuple[tuple[StageId, Layer], ...] = (
    (StageId.RETROSPECT, Layer.L17),
    (StageId.MEMORY_UPDATE, Layer.L18),
)


class EvidenceSource(Protocol):
    """The stable interface the runtime depends on for a run's evidence (CER-1 amendment).

    The `SoftLoop` pulls a run's evidence through THIS and nothing else — it never imports or knows
    about MCP. `CourtEvidencePool` (in-memory), `FileCourtEvidencePool` (durable, cross-process),
    and a future MCP-backed source all satisfy it. **MCP is one transport *behind* this interface,
    not a runtime dependency** — the invariant, now named and pyright-enforced."""

    def evidence_for(self, run_id: str) -> tuple[Evidence, ...]: ...


class FileCourtEvidencePool:
    """A **durable, cross-process** evidence pool (R5): the sink a live evidence submitter writes to
    and the `SoftLoop` reads from, in separate processes. Evidence for a run lands in
    `<dir>/<run_id>.jsonl` (one JSON evidence per line). This is the substrate a `CourtServer` MCP —
    or a file-writing Builder session — binds to; the `SoftLoop` pulls via `evidence_for`.

    Taint index (CRITICAL-002 remediation, notebook Entry 140/141): rows listed in
    `<dir>/.tainted.json` (a mapping of line hash → reason, where line hash is sha256 of the exact
    JSON line) are fabricated or unbound evidence (e.g. the `dummy_hash_for_now` / 64-zero-hash
    classes). `evidence_for` SKIPS them — the pool record is preserved for forensics (append-only
    files are never rewritten) but tainted evidence can no longer feed any gate. Taint is keyed by
    the full line content (not the Evidence's own hash, which covers only claim+command and is
    shared across runs), so an identical claim/command submitted honestly elsewhere is unaffected.
    """

    _TAINT_INDEX = ".tainted.json"

    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.jsonl"

    def _tainted(self) -> frozenset[str]:
        index = self._dir / self._TAINT_INDEX
        if not index.is_file():
            return frozenset()
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A corrupt index is treated as absent: the pool stays usable and the index can be
            # repaired by the auditor. Taint is an additive deny-list — rows only ever enter it
            # via an explicit auditor action, never implicitly.
            return frozenset()
        if not isinstance(data, dict):
            return frozenset()
        return frozenset(data.keys())

    def submit(self, run_id: str, evidence: Evidence) -> None:
        line = json.dumps(_evidence_to_json(evidence), sort_keys=True)
        with self._path(run_id).open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def evidence_for(self, run_id: str) -> tuple[Evidence, ...]:
        path = self._path(run_id)
        if not path.is_file():
            return ()
        tainted = self._tainted()
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        kept = [ln for ln in lines if hashlib.sha256(ln.encode("utf-8")).hexdigest() not in tainted]
        return tuple(_evidence_from_json(json.loads(ln)) for ln in kept)


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
    # Actual spend on this run, on EVERY exit path (seal, remand, halt) — the metering the
    # EconomicGovernor settles against (M2): it refunds the unspent allocation so Σ tracked = Σ
    # actual, tightening K11 from ceiling-conservative to exact. Set centrally in `run()`.
    spent_tokens: int = 0
    spent_wallclock_s: float = 0.0
    # RB-0008 §3: high-leverage (>5x) friction repair intake for immediate queue insertion
    high_leverage_intake: Intake | None = None


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
        # DEBT-0057: persistence is explicit at the composition root — the loop never
        # constructs its own scorer, so no repository-relative default can reappear here.
        sidecar_scorer: SidecarStageScorer,
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
        self._broker = broker
        self._transition_evidence: dict[str, Evidence] = {}
        self._gate = Gate(broker, self._transition_evidence.__getitem__)
        dispatcher = AgentDispatcher(broker, cas, agent_runtime, clock=self._now)
        self._playbook = StagePlaybook(dispatcher)
        self._court = court if court is not None else Court()
        self._ibm = ibm if ibm is not None else InformationBarrierManager()
        self._review = ReviewHarness(self._ibm, dispatcher)
        self._scars = scar_store if scar_store is not None else ScarStore()
        self._seal = SealAuthority(signing_key, ledger)
        self._sidecar_scorer = sidecar_scorer  # DEBT-0057: injected — never self-constructed

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
        evidence_source: EvidenceSource | None = None,
    ) -> RunOutcome:
        decision = triage(
            changed_paths=changed_paths,
            verifiable=verifiable,
            reversible=reversible,
            budget_by_class=self._budget_by_class,
        )
        # Reserve-then-settle metering (M2): the run consumes a GoalBudget; whatever it ACTUALLY
        # spent — on any exit path (seal, remand, or halt) — is reported on the RunOutcome here, in
        # ONE place, so the EconomicGovernor can refund the unspent allocation and keep K11
        # accounting exact rather than charging the weight-class ceiling for every run.
        budget = GoalBudget(decision.budget)
        outcome = self._run_body(
            budget=budget,
            decision=decision,
            objective=objective,
            changed_paths=changed_paths,
            plan_write_scopes=plan_write_scopes,
            builder_evidence=builder_evidence,
            goal_signature=goal_signature,
            run_id=run_id,
            evidence_source=evidence_source,
        )
        return replace(
            outcome,
            spent_tokens=budget.spent_tokens,
            spent_wallclock_s=budget.spent_wallclock,
        )

    def _run_body(
        self,
        *,
        budget: GoalBudget,
        decision: TriageDecision,
        objective: str,
        changed_paths: tuple[str, ...],
        plan_write_scopes: tuple[str, ...],
        builder_evidence: tuple[Evidence, ...],
        goal_signature: str,
        run_id: str,
        evidence_source: EvidenceSource | None,
    ) -> RunOutcome:
        goal_id = "g-" + uuid.uuid4().hex[:12]
        self._ledger.append(
            Event(
                1,
                GOAL_CREATED,
                {"goal_id": goal_id, "weight_class": decision.weight_class.value},
            )
        )

        # Step 4 — lawful Trace-A discharge evidence (K1): emit one canonical LAYER_DISCHARGED row
        # per auto-discharged layer (L03-L11, L17, L18) so every discharged transition still carries
        # evidence instead of vanishing. Trace-B contracts discharge nothing, so this is a no-op on
        # the full-ceremony path. (No v/r scoring invented here -- ceremony only consumes triage's
        # trace; the v/r mechanics remain RB-CEREMONY-DEPTH-001's open edge case.)
        self._record_discharges(run_id, goal_id, decision.ceremony)

        try:
            # --- Planner: ceremony-resolved obligation graph (EL L24-28) ---
            # The front-end stages are gated by the L02 ceremony contract: a DISCHARGE obligation
            # (Trace-A) records its K1 stub above and does NOT execute, so the unconditional
            # MITIGATION->DESIGN->CRITIQUE->PLAN chain disappears on the fast path (the prior
            # "MISPLACED" execution of L07/L08/L09/L11 without a ceremony decision). Only EXECUTE
            # obligations run; IMPLEMENT/Court/Adversary/Seal always run (never dischargeable).
            # Stage context chains forward (B2.J): PLAN sees DESIGN, IMPLEMENT sees design + plan,
            # so the live Builder has a plan to implement against (it blocked without one). The goal
            # objective is threaded into every stage (B2.L) so DESIGN designs FOR it, PLAN plans FOR
            # it, and the Builder is told the specific change.
            goal_detail = f"Goal objective: {objective}"
            planner_artifacts: list[ArtifactRef] = []
            for stage, layer in FRONTEND_PLANNER_STAGES:
                if decision.ceremony.obligation_for(layer) is Obligation.DISCHARGE:
                    continue
                scars = self._scar_refs(goal_signature, stage)
                session_name = (
                    "adversary"
                    if stage is StageId.ADVERSARIAL_REVIEW
                    else ("critic" if stage is StageId.CRITIQUE else "planner")
                )
                result = self._playbook.run_stage(
                    goal_id=goal_id,
                    run_id=run_id,
                    stage=stage,
                    session=session_name,
                    budget=decision.budget,
                    scars=scars,
                    context_refs=tuple(planner_artifacts),
                    detail=goal_detail,
                )
                budget.charge(result.cost)
                self._record_stage(run_id, goal_id, stage, session_name, result)
                planner_artifacts.extend(result.artifacts)
                # Entry 143: score the ARTIFACT the stage produced (not the goal objective,
                # which is identical every stage and made all scores identical), and record
                # the model that actually ran the stage (result.cost.model_ver).
                stage_content = (
                    self._cas.get(result.artifacts[0].hash).decode("utf-8", errors="replace")
                    if result.artifacts
                    else goal_detail
                )
                self._sidecar_scorer.score_stage(
                    run_id=run_id,
                    stage=stage,
                    primary_model=result.cost.model_ver,
                    artifact_content=stage_content,
                )

            # --- Builder: IMPLEMENT on the plan scopes, with design + plan as context (B2.J) ---
            build = self._playbook.run_stage(
                goal_id=goal_id,
                run_id=run_id,
                stage=StageId.IMPLEMENT,
                session="builder",
                budget=decision.budget,
                write_scopes=plan_write_scopes,
                context_refs=tuple(planner_artifacts),
                detail=goal_detail,
            )
            budget.charge(build.cost)
            self._record_stage(run_id, goal_id, StageId.IMPLEMENT, "builder", build)
            self._sidecar_scorer.score_stage(
                run_id=run_id,
                stage=StageId.IMPLEMENT,
                primary_model=build.cost.model_ver,
                artifact_content=(
                    self._cas.get(build.artifacts[0].hash).decode("utf-8", errors="replace")
                    if build.artifacts
                    else goal_detail
                ),
            )
            if not build.artifacts:
                return RunOutcome(RunStatus.REMANDED, goal_id, "builder produced no artifact")
            artifact = build.artifacts[0]
        except BudgetExceeded as exc:
            return RunOutcome(RunStatus.HALTED, goal_id, f"budget breach: {exc}")

        # Autonomous evidence (B2.P, toward R5): pull the evidence the Builder SUBMITTED for this
        # run (via the court MCP) instead of the pre-declared backlog. Empty ⇒ REMAND — the agent
        # must produce its own probative evidence, not have it authored for it.
        if evidence_source is not None:
            submitted = evidence_source.evidence_for(run_id)
            if submitted:
                builder_evidence = submitted
            elif not builder_evidence:
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
                RunStatus.REMANDED,
                goal_id,
                "court remanded",
                verdict=verdict,
                ephemeral_context=context,
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
                    retry_hints=(
                        "evidence must exercise the change — a command with the same "
                        "result with and without it proves nothing; supply a real test",
                    ),
                    diagnostics=(f"non-probative (vacuous) evidence: {vacuous}",),
                )
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    "non-probative (vacuous) evidence",
                    verdict=verdict,
                    ephemeral_context=context,
                )

        # --- Isolated Adversary over the sealed bundle (B1.D / FR-3) ---
        # B2.M: store a serialized copy of each evidence in the CAS and reference THAT, so the
        # adversary can actually read (and re-run) the evidence in its workspace — a bare evidence
        # hash is not a CAS blob and materialises to nothing (the adversary blocked without it).
        evidence_refs = tuple(self._cas.put(_serialize_evidence(ev)) for ev in builder_evidence)
        bundle = self._ibm.seal(artifact_refs=(artifact,), evidence_refs=evidence_refs)
        try:
            adversary = self._review.review(
                goal_id=goal_id,
                run_id=run_id,
                session="adversary",
                bundle=bundle,
                budget=decision.budget,
            )
            budget.charge(adversary.cost)
            self._record_stage(run_id, goal_id, StageId.ADVERSARIAL_REVIEW, "adversary", adversary)
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
                RunStatus.REMANDED,
                goal_id,
                "adversary blocked the seal",
                verdict=verdict,
                ephemeral_context=context,
            )

        # --- Seal (B0.9): idempotent, over the bundle + verdict + adversary + ledger head ---
        verdict_ref = self._cas.put(_canonical(verdict).encode("ascii"))
        seal = self._seal.seal(
            goal_id=goal_id,
            run_id=run_id,
            artifact_bundle=bundle.bundle_hash,
            verdict_ref=verdict_ref,
            adversary_ref=adversary.trace_ref,
        )

        # --- Gate-routed L17 retrospective (EL L17): report is CAS-bound before stage execution.
        # The frozen kernel requires the canonical SEAL -> RETROSPECT -> EVOLVE -> MEMORY_UPDATE
        # chain; this request exercises only the first edge and does not bypass Gate.propose_transition.
        try:
            if decision.ceremony.obligation_for(Layer.L17) is Obligation.EXECUTE:
                retrospective = RetrospectiveEngine(self._cas)
                retro_report = retrospective.build_report(
                    RunOutcome(RunStatus.SEALED, goal_id, "sealed", seal=seal, verdict=verdict),
                    run_id=run_id,
                    objective=objective,
                    goal_signature=goal_signature,
                    changed_paths=changed_paths,
                )
                retro_hash = retrospective.emit_report(retro_report)
                evidence_hash = hashlib.sha256(("l17-evidence:" + retro_hash).encode()).hexdigest()
                self._transition_evidence[evidence_hash] = Evidence(
                    hash=evidence_hash,
                    kind=EvidenceKind.PROOF,
                    claim_id="l17_retrospective",
                    artifact_hash=retro_hash,
                    environment_hash=hashlib.sha256(b"paeos-l17-retrospective").hexdigest(),
                    reproducible_command=None,
                    producer=EvidenceProducer(role=Role.DOC, session="retrospective-" + run_id),
                    determinism=Determinism.NONDETERMINISTIC,
                    result={"status": "report-emitted", "artifact_hash": retro_hash},
                    attestation="l17-runtime",
                )
                head = self._ledger.head()
                current_seq = head.seq if head is not None else 0
                token = self._broker.mint(
                    goal_id=goal_id,
                    run_id=run_id,
                    stage=StageId.SEAL,
                    role=Role.DOC,
                    session="retrospective-" + run_id,
                    operations=("propose_transition",),
                    issued_seq=current_seq,
                    expires_seq=current_seq + 1800,
                )
                request = TransitionRequest(
                    authority=token,
                    goal_id=goal_id,
                    run_id=run_id,
                    from_state=StageId.SEAL,
                    to_state=StageId.RETROSPECT,
                    evidence=(evidence_hash,),
                    validation=ValidationClaim(
                        gate_id="G-L17-RETROSPECT",
                        claims=(
                            Claim("l17_retrospective", "CAS report emitted", (evidence_hash,)),
                        ),
                        producer=Role.DOC,
                        produced_against=retro_hash,
                    ),
                )
                _ = retrospective.route_transition(
                    self._gate,
                    request,
                    weight_class=decision.weight_class,
                    current_seq=current_seq,
                    artifact_hash=retro_hash,
                )
                self._ledger.append(
                    Event(
                        1,
                        "RETROSPECTIVE_TRANSITION",
                        {  # type: ignore[arg-type]
                            "run_id": run_id,
                            "goal_id": goal_id,
                            "from": StageId.SEAL.name,
                            "to": StageId.RETROSPECT.name,
                            "outcome": "COMMITTED",
                            "report_hash": retro_hash,
                        },
                    )
                )
        except RetrospectiveTransitionRejected as exc:
            return RunOutcome(
                RunStatus.REMANDED,
                goal_id,
                f"L17 retrospective gate rejected: {exc}",
                seal=seal,
                verdict=verdict,
            )

        # --- Post-Seal Evolution Stages (EL L17-L18 / Trace-B): Retrospect & Memory Update ---
        try:
            for stage, layer in POST_SEAL_EVOLUTION_STAGES:
                if decision.ceremony.obligation_for(layer) is Obligation.EXECUTE:
                    evo_res = self._playbook.run_stage(
                        goal_id=goal_id,
                        run_id=run_id,
                        stage=stage,
                        session="evolution",
                        budget=decision.budget,
                        context_refs=(ArtifactRef(hash=seal.seal_hash, type="seal"),),
                        detail=goal_detail,
                    )
                    budget.charge(evo_res.cost)
                    self._record_stage(run_id, goal_id, stage, "evolution", evo_res)
                    self._sidecar_scorer.score_stage(
                        run_id=run_id,
                        stage=stage,
                        primary_model=evo_res.cost.model_ver,
                        artifact_content=(
                            self._cas.get(evo_res.artifacts[0].hash).decode(
                                "utf-8", errors="replace"
                            )
                            if evo_res.artifacts
                            else goal_detail
                        ),
                    )

            # --- L19 (EVOLVE): Constitutional Evolution (Triggered for KERNEL_TOUCHING) ---
            if decision.weight_class is WeightClass.KERNEL_TOUCHING:
                evolve_res = self._playbook.run_stage(
                    goal_id=goal_id,
                    run_id=run_id,
                    stage=StageId.EVOLVE,
                    session="ratifier",
                    budget=decision.budget,
                    context_refs=(ArtifactRef(hash=seal.seal_hash, type="seal"),),
                    detail=goal_detail,
                )
                budget.charge(evolve_res.cost)
                self._record_stage(run_id, goal_id, StageId.EVOLVE, "ratifier", evolve_res)
                self._sidecar_scorer.score_stage(
                    run_id=run_id,
                    stage=StageId.EVOLVE,
                    primary_model=evolve_res.cost.model_ver,
                    artifact_content=(
                        self._cas.get(evolve_res.artifacts[0].hash).decode(
                            "utf-8", errors="replace"
                        )
                        if evolve_res.artifacts
                        else goal_detail
                    ),
                )
        except BudgetExceeded as exc:
            return RunOutcome(
                RunStatus.HALTED,
                goal_id,
                f"budget breach at evolution: {exc}",
                seal=seal,
                verdict=verdict,
            )

        return RunOutcome(RunStatus.SEALED, goal_id, "sealed", seal=seal, verdict=verdict)

    def _record_stage(
        self, run_id: str, goal_id: str, stage: StageId, session: str, result: TaskResult
    ) -> None:
        """Ledger model attribution (MEDIUM-003 remediation, notebook Entry 142): every executed
        stage appends a STAGE_COMPLETED row naming the model that actually ran it
        (``cost.model_ver``, populated by the runtime's transcript parser — cline run_result or
        Claude JSON). This is what makes a posteriori session-log cross-checks possible: the
        ledger now *claims* which model ran each stage, so the claim can be verified against
        host CLI session logs instead of being an unverifiable assertion."""
        self._ledger.append(
            Event(
                1,
                "STAGE_COMPLETED",
                {
                    "run_id": run_id,
                    "goal_id": goal_id,
                    "stage": stage.name,
                    "session": session,
                    "status": result.status.value,
                    "model_ver": result.cost.model_ver,
                    "tokens": result.cost.tokens,
                },
            )
        )

    def _record_discharges(self, run_id: str, goal_id: str, ceremony: CeremonyContract) -> None:
        """Emit the K1 evidence stubs for every layer the ceremony contract discharges.

        Auto-discharge is NOT a skip (EL L29-30 / WSM L70-72): each discharged layer appends one
        ``LAYER_DISCHARGED`` row carrying the canonical DischargeStub record
        ``{layer, result: auto_pass, reason: trace_a, by: runtime}``. Trace-B contracts discharge
        nothing, so this records zero rows on the full-ceremony path.
        """
        for stub in ceremony.discharge_stubs():
            self._ledger.append(
                Event(
                    1,
                    LAYER_DISCHARGED,
                    cast(
                        dict[str, JsonValue],
                        {
                            "run_id": run_id,
                            "goal_id": goal_id,
                            "discharge": stub.to_record(),
                        },
                    ),
                )
            )

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


def _evidence_to_json(ev: Evidence) -> dict[str, JsonValue]:
    """A round-trippable JSON view of an evidence (for the durable/cross-process pool, R5)."""
    return {
        "hash": ev.hash,
        "kind": ev.kind.name,
        "claim_id": ev.claim_id,
        "artifact_hash": ev.artifact_hash,
        "environment_hash": ev.environment_hash,
        "reproducible_command": ev.reproducible_command,
        "result": ev.result,
        "producer_role": ev.producer.role.name,
        "producer_session": ev.producer.session,
        "determinism": ev.determinism.name,
        "attestation": ev.attestation,
    }


def _evidence_from_json(d: Mapping[str, JsonValue]) -> Evidence:
    command = d.get("reproducible_command")
    return Evidence(
        hash=str(d["hash"]),
        kind=EvidenceKind[str(d["kind"])],
        claim_id=str(d["claim_id"]),
        artifact_hash=str(d["artifact_hash"]),
        environment_hash=str(d["environment_hash"]),
        reproducible_command=str(command) if isinstance(command, str) else None,
        producer=EvidenceProducer(
            role=Role[str(d["producer_role"])], session=str(d["producer_session"])
        ),
        determinism=Determinism[str(d["determinism"])],
        result=d["result"],
        attestation=str(d["attestation"]),
    )


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
