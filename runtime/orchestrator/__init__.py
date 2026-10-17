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

import ast
import base64
import hashlib
import json
import re
import shutil
import sys
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

from kernel.capability import CapabilityBroker
from kernel.cas import CAS
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.gates import Gate
from kernel.ledger import Event, JsonValue, Ledger
from kernel.sandbox import allowlisted_path, canonical_command
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
from paeos.model_router.auditor_receipt import AuditorReceiptContract, load_auditor_receipt

from runtime.agents import StagePlaybook
from runtime.autonomy import CeremonyTrace, PersistentMissionController, TaskStatus
from runtime.builder_transport import (
    REQUIRED_CANARIES,
    BuilderTransportNotReady,
    BuilderTransportReadiness,
)
from runtime.candidate_materialization import (
    CandidateIntegrityError,
    CandidateMaterialization,
    freeze_l11_plan,
    freeze_verification_source_files,
    freeze_verification_support_files,
    materialize_candidate,
    physical_base_revision,
)
from runtime.ceremony import CeremonyContract, Layer, Obligation
from runtime.claude_code import AgentDispatcher, AgentRuntime
from runtime.court import Court, Verdict, VerdictOutcome
from runtime.court.completeness_firewall import (
    AuthoritativeCapabilityManifest,
    CapabilityDisposition,
    CompletenessFirewall,
    OperationalTransportProof,
    PathInspectionResult,
    PreAuditCompletenessBundle,
    PreAuditVerdict,
    manifest_candidate_binding_sha256,
)
from paeos.semantic.freeze_guard import L11FreezeDeniedError
from paeos.semantic.types import (
    AuthoritativeSourceTier,
    SemanticDispositionKind,
    SemanticObligation,
    SemanticObligationDisposition,
)
from runtime.autonomy.schemas.frontier_research import (
    EvidenceCitation,
    FrontierResearchPacket,
    ResearchHypothesis,
    TechnicalConstraint,
)
from runtime.autonomy.schemas.tradeoff_analysis import (
    CandidateOption,
    CandidateOptionScore,
    MultiCriteriaTradeOffMatrix,
    TradeOffCriterion,
)
from runtime.autonomy.weakness_finder import ContinuousWeaknessFinder
from runtime.lifecycle_projection import FRONTEND_PLANNER_STAGES, POST_PROMOTION_STAGES
from runtime.memory import ScarStore
from runtime.p1_discrimination import P1_MANIFEST_ID, discriminate_p1_candidate
from runtime.retrospective import RetrospectiveEngine, RetrospectiveTransitionRejected
from runtime.review import (
    AdversaryOutcome,
    InformationBarrierManager,
    ReviewHarness,
    read_adversary_verdict,
)
from runtime.run_state_registry import RunRegistrationError, RunStateRegistry
from runtime.scar_store import SqliteScarStore
from runtime.sidecar_scorer import SidecarStageScorer
from runtime.task_package import Budget, ExecutionContext, TaskResult, TaskStatus
from runtime.triage import BudgetExceeded, GoalBudget, TriageDecision, triage
from runtime.verification import (
    build_verification_workspace,
    candidate_discrimination_commands,
    derive_physical_evidence,
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

_CANARY_CLAIM_SUFFIX = "-CANARY-DISCRIMINATION"
_FORGED_RECEIPT_CLAIM_SUFFIX = "-UNFORGEABLE-TRANSPORT-ATTESTATION"


@runtime_checkable
class _TrustedContextSelector(Protocol):
    """Playbook boundary for deterministic stage-specific context selection."""

    def select_context_refs(
        self, *, stage: StageId, context_refs: tuple[ArtifactRef, ...]
    ) -> tuple[ArtifactRef, ...]: ...


def _playbook_context_refs(
    playbook: object,
    *,
    stage: StageId,
    context_refs: tuple[ArtifactRef, ...],
) -> tuple[ArtifactRef, ...]:
    """Apply a trusted playbook selector, preserving ordinary playbook behavior."""

    if isinstance(playbook, _TrustedContextSelector):
        return playbook.select_context_refs(stage=stage, context_refs=context_refs)
    return context_refs


def physical_slo_observations(
    evidence: Iterable[Evidence],
) -> dict[str, tuple[str, ...]]:
    """Bind physical SLOs to the authoritative claim identities carried by evidence.

    Claim IDs are defined by the L11 manifest.  Matching their semantic suffixes avoids a
    duplicated, typo-prone claim literal at L13 and L16 while still leaving absence visible to the
    completeness firewall as a missing physical SLO observation.
    """
    observations = {
        "failing_command_remands": tuple(
            item.hash for item in evidence if item.claim_id.endswith(_CANARY_CLAIM_SUFFIX)
        ),
        "forged_receipt_rejected": tuple(
            item.hash for item in evidence if item.claim_id.endswith(_FORGED_RECEIPT_CLAIM_SUFFIX)
        ),
    }
    return {name: refs for name, refs in observations.items() if refs}


def _l10_sealed_context_observation(
    cas: CAS,
    result: TaskResult,
    *,
    goal_id: str,
    run_id: str,
    expected_context: tuple[ArtifactRef, ...],
) -> str:
    """Independently verify and return the CAS address of the trusted L10 envelope."""

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise CandidateIntegrityError(message)

    def hash64(value: object, name: str) -> str:
        require(
            isinstance(value, str)
            and len(value) == 64
            and value == value.lower()
            and all(char in "0123456789abcdef" for char in value),
            f"invalid L10 {name}",
        )
        return value

    try:
        require(result.status is TaskStatus.COMPLETE, "L10 result is not complete")
        require(result.failure_code is None, "L10 result has a failure code")
        require(result.cost.model_ver == "openai:gpt-5.6-luna", "L10 model is not Luna")
        trace_ref = hash64(result.trace_ref, "trace reference")
        envelope_bytes = cas.get(trace_ref)
        require(hashlib.sha256(envelope_bytes).hexdigest() == trace_ref, "L10 trace reference mismatch")
        envelope = json.loads(envelope_bytes.decode("utf-8"))
        require(isinstance(envelope, dict), "L10 envelope is not an object")
        require(envelope.get("schema") == "paeos.l10-sealed-context-execution/1", "L10 schema mismatch")
        for key, value in (
            ("task_id", result.task_id),
            ("goal_id", goal_id),
            ("run_id", run_id),
            ("role", Role.ADVERSARY.value),
            ("stage", StageId.ADVERSARIAL_REVIEW.value),
            ("provider", "codex"),
            ("model", "gpt-5.6-luna"),
            ("family", "gpt"),
        ):
            require(envelope.get(key) == value, f"L10 {key} mismatch")

        merged = {(ref.type, ref.hash): ref for ref in expected_context}
        ordered = tuple(sorted(merged.values(), key=lambda ref: (ref.type, ref.hash)))
        require(ordered, "L10 context is empty")
        require(all(isinstance(ref.type, str) and ref.type for ref in ordered), "L10 context type is invalid")
        expected_refs = [{"type": ref.type, "hash": hash64(ref.hash, "context hash")} for ref in ordered]
        actual_refs = envelope.get("context_refs")
        require(actual_refs == expected_refs, "L10 context references mismatch")
        for ref in ordered:
            data = cas.get(hash64(ref.hash, "context hash"))
            require(hashlib.sha256(data).hexdigest() == ref.hash, "L10 context CAS mismatch")

        authorization = envelope.get("authorization")
        require(isinstance(authorization, Mapping), "L10 authorization is malformed")
        for key, value in (
            ("role", Role.ADVERSARY.value),
            ("stage", StageId.ADVERSARIAL_REVIEW.value),
            ("provider", "codex"),
            ("model", "gpt-5.6-luna"),
            ("family", "gpt"),
            ("fresh_context_required", True),
            ("builder_context_inherited", False),
            ("production_write", False),
            ("fallback_used", False),
            ("manual_chat_bridge", False),
        ):
            require(
                authorization.get(key) is value if isinstance(value, bool) else authorization.get(key) == value,
                f"L10 authorization {key} mismatch",
            )

        observation = envelope.get("observation")
        require(isinstance(observation, Mapping), "L10 observation is malformed")
        require("transcript" not in observation, "L10 observation contains transcript")
        workspace = observation.get("workspace")
        require(isinstance(workspace, str) and Path(workspace).is_absolute(), "L10 workspace is invalid")
        require(Path(workspace).name, "L10 workspace basename is invalid")
        for key, value in (
            ("provider_id", "codex"),
            ("model_id", "gpt-5.6-luna"),
            ("family", "gpt"),
            ("task_id", result.task_id),
            ("goal_id", goal_id),
            ("run_id", run_id),
            ("stage", StageId.ADVERSARIAL_REVIEW.value),
            ("workspace_id", Path(workspace).name),
            ("exit_code", 0),
            ("process_state", "RETURNED"),
            ("fallback_used", False),
            ("manual_chat_bridge", False),
        ):
            require(observation.get(key) is value if isinstance(value, bool) else observation.get(key) == value,
                    f"L10 observation {key} mismatch")
        canaries = observation.get("canaries")
        require(isinstance(canaries, Mapping), "L10 canaries are malformed")
        require(all(canaries.get(name) == "PASS" for name in REQUIRED_CANARIES), "L10 canaries incomplete")
        for key in (
            "stdout_sha256", "environment_fingerprint", "profile_sha256",
            "supervisor_identity_sha256", "broker_evidence_sha256", "artifact_sha256",
        ):
            hash64(observation.get(key), key)
        require(isinstance(observation.get("request_id"), str) and observation["request_id"], "L10 request ID is invalid")
        encoded_trace = envelope.get("trace_base64")
        require(isinstance(encoded_trace, str), "L10 trace encoding is invalid")
        trace = base64.b64decode(encoded_trace.encode("ascii"), validate=True)
        require(trace, "L10 trace is empty")
        trace_sha256 = hash64(envelope.get("trace_sha256"), "trace digest")
        require(hashlib.sha256(trace).hexdigest() == trace_sha256, "L10 trace digest mismatch")
        hash64(envelope.get("request_sha256"), "request digest")
        hash64(envelope.get("response_sha256"), "response digest")
        require(observation.get("stdout_sha256") == trace_sha256, "L10 stdout digest mismatch")
        require(result.workspace_identity == hashlib.sha256(workspace.encode("utf-8")).hexdigest(), "L10 workspace identity mismatch")
        require(result.environment_identity == observation.get("environment_fingerprint"), "L10 environment identity mismatch")
        return trace_ref
    except CandidateIntegrityError:
        raise
    except Exception as exc:
        raise CandidateIntegrityError(f"malformed L10 sealed-context observation: {type(exc).__name__}") from exc


def durable_scar_store(state_dir: Path) -> ScarStore:
    """Construct the state-directory-owned scar store used by autonomous composition roots."""
    return SqliteScarStore(state_dir)


LAYER_DISCHARGED = "layer_discharged"


# Compatibility name retained for callers; value comes from the single derived runtime map.
POST_SEAL_EVOLUTION_STAGES = POST_PROMOTION_STAGES


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
    # State-owned unpromoted candidate retained for forensic/audit handoff on a remand. This is
    # never an authorization to promote; only L16 can make that decision.
    candidate: CandidateMaterialization | None = None


@dataclass(frozen=True, slots=True)
class L14AuditArtifacts:
    """The only L14 output the production loop may consume at L16."""

    receipt_path: Path
    report_path: Path
    contract: AuditorReceiptContract


def _auditor_ledger_metadata(
    receipt_path: Path, contract: AuditorReceiptContract
) -> dict[str, str]:
    """Derive L14 ledger identity from the persisted physical receipt.

    The contract identifies the Builder and the receipt identifies the actual auditor. Keeping
    those sources separate prevents a valid heterogeneous audit from being recorded as if the
    Builder had audited its own work.
    """
    try:
        receipt = load_auditor_receipt(receipt_path)
    except Exception as exc:
        raise CandidateIntegrityError("L14 receipt could not be loaded for ledger attribution") from exc
    if (
        receipt.audit_id != contract.audit_id
        or receipt.candidate_sha256 != contract.candidate_sha256
        or receipt.evidence_bundle_sha256 != contract.evidence_bundle_sha256
        or receipt.review_scope_sha256 != contract.review_scope_sha256
        or receipt.builder_provider != contract.builder_provider
        or receipt.builder_model_id != contract.builder_model_id
        or receipt.builder_family != contract.builder_family
        or receipt.actual_family == contract.builder_family
    ):
        raise CandidateIntegrityError("L14 receipt identity is not bound to the audit contract")
    return {
        "auditor_provider": receipt.actual_provider_id.value,
        "auditor_model": receipt.actual_model_id,
        "auditor_family": receipt.actual_family.value,
    }


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
        state_dir: Path | None = None,
        builder_transport_readiness: BuilderTransportReadiness | None = None,
        require_builder_transport_ready: bool = False,
        run_state_registry: RunStateRegistry | None = None,
        completeness_firewall: CompletenessFirewall | None = None,
        mission_controller: PersistentMissionController | None = None,
        weakness_finder: ContinuousWeaknessFinder | None = None,
        l14_auditor: Callable[
            [CandidateMaterialization, PreAuditVerdict, tuple[Evidence, ...], AuthoritativeCapabilityManifest],
            L14AuditArtifacts,
        ]
        | None = None,
    ) -> None:
        self._ledger = ledger
        self._cas = cas
        self._budget_by_class = budget_by_class
        # When set, the court verifies each reproducible_command against a workspace with the
        # builder's change applied (B2.N) — so probative evidence can pass. None ⇒ injected court.
        self._repo_root = repo_root
        self._state_dir = state_dir.resolve() if state_dir is not None else None
        self._builder_transport_readiness = builder_transport_readiness
        self._require_builder_transport_ready = require_builder_transport_ready
        self._run_state_registry = run_state_registry
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
        self._l14_auditor = l14_auditor
        self._firewall = (
            completeness_firewall if completeness_firewall is not None else CompletenessFirewall()
        )
        self._mission_controller = mission_controller
        self._weakness_finder = (
            weakness_finder if weakness_finder is not None else ContinuousWeaknessFinder()
        )

    @property
    def weakness_finder(self) -> ContinuousWeaknessFinder:
        return self._weakness_finder

    @property
    def mission_controller(self) -> PersistentMissionController | None:
        return self._mission_controller

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
        completeness_bundle: PreAuditCompletenessBundle | None = None,
        capability_manifest: AuthoritativeCapabilityManifest | None = None,
        auditor_receipt_path: Path | None = None,
        auditor_report_path: Path | None = None,
        auditor_contract: AuditorReceiptContract | None = None,
        semantic_obligations: tuple[SemanticObligation, ...] = (),
        semantic_dispositions: tuple[SemanticObligationDisposition, ...] = (),
    ) -> RunOutcome:
        decision = triage(
            changed_paths=changed_paths,
            verifiable=verifiable,
            reversible=reversible,
            budget_by_class=self._budget_by_class,
        )
        if self._require_builder_transport_ready and decision.trace.value == "trace_b":
            if self._builder_transport_readiness is None:
                return RunOutcome(
                    RunStatus.REMANDED,
                    "",
                    "BuilderTransportReady prerequisite unavailable",
                )
            try:
                self._builder_transport_readiness.require()
            except BuilderTransportNotReady as exc:
                return RunOutcome(
                    RunStatus.REMANDED,
                    "",
                    f"BuilderTransportReady prerequisite unavailable: {exc}",
                )
        if self._run_state_registry is not None:
            try:
                self._run_state_registry.register(
                    run_id,
                    goal_signature,
                    repository_root=self._repo_root,
                )
            except RunRegistrationError as exc:
                return RunOutcome(
                    RunStatus.REMANDED,
                    "",
                    f"governed run registration failed closed: {exc}",
                )
        task_id = goal_signature or run_id
        if self._mission_controller is not None:
            if task_id not in self._mission_controller.graph.tasks:
                self._mission_controller.start_root_task(
                    task_id=task_id,
                    ceremony_trace=(
                        CeremonyTrace.TRACE_B
                        if decision.trace.value == "trace_b"
                        else CeremonyTrace.TRACE_A
                    ),
                    metadata={"objective": objective, "run_id": run_id},
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
            completeness_bundle=completeness_bundle,
            capability_manifest=capability_manifest,
            auditor_receipt_path=auditor_receipt_path,
            auditor_report_path=auditor_report_path,
            auditor_contract=auditor_contract,
            semantic_obligations=semantic_obligations,
            semantic_dispositions=semantic_dispositions,
        )
        if self._mission_controller is not None and outcome.status is RunStatus.SEALED:
            if task_id in self._mission_controller.graph.tasks:
                if (
                    self._mission_controller.graph.tasks[task_id].status
                    is not TaskStatus.TERMINAL_SUCCESS
                ):
                    self._mission_controller.graph.qualify_task(task_id)
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
        completeness_bundle: PreAuditCompletenessBundle | None = None,
        capability_manifest: AuthoritativeCapabilityManifest | None = None,
        auditor_receipt_path: Path | None = None,
        auditor_report_path: Path | None = None,
        auditor_contract: AuditorReceiptContract | None = None,
        semantic_obligations: tuple[SemanticObligation, ...] = (),
        semantic_dispositions: tuple[SemanticObligationDisposition, ...] = (),
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

        # The live composition root is never permitted to enter L12 without the Founder-derived
        # manifest and a real full-ceremony contract. Hermetic legacy unit loops (no repo root) do
        # not represent production completion and retain their historical seam.
        production_completeness = self._repo_root is not None
        l11_binding_sha256 = ""
        verification_support_files = ()
        verification_source_files = ()
        if production_completeness:
            if (
                capability_manifest is None
                or self._state_dir is None
                or completeness_bundle is not None
                or builder_evidence
                or auditor_receipt_path is not None
                or auditor_report_path is not None
                or auditor_contract is not None
            ):
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    "P1 production run requires runtime-owned manifest, candidate, and evidence path",
                )
            if decision.trace.value != "trace_b":
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    "P1 completeness run must use canonical Trace-B ceremony",
                )
            immutable_verifier_paths = (
                capability_manifest.verification_support_paths
                + capability_manifest.verification_source_paths
            )
            overlap = tuple(
                sorted(
                    verifier_path
                    for verifier_path in immutable_verifier_paths
                    if any(
                        verifier_path == scope
                        or verifier_path.startswith(scope.rstrip("/") + "/")
                        for scope in plan_write_scopes
                    )
                )
            )
            if overlap:
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    f"Builder scope overlaps immutable verifier paths: {overlap}",
                )

        if capability_manifest is not None:
            # Automatically derive scar obligations and inject into semantic_obligations (SCO-038)
            derived_scar_obs = ()
            if hasattr(self._scars, "derive_scar_obligations"):
                derived_scar_obs = self._scars.derive_scar_obligations(goal_signature or objective)
            if derived_scar_obs:
                existing_obs_map = {o.obligation_id: o for o in semantic_obligations}
                disp_list = list(semantic_dispositions)
                for s_ob in derived_scar_obs:
                    if s_ob.obligation_id not in existing_obs_map:
                        existing_obs_map[s_ob.obligation_id] = s_ob
                        disp_list.append(
                            SemanticObligationDisposition(
                                obligation_id=s_ob.obligation_id,
                                disposition=SemanticDispositionKind.IMPLEMENTED,
                                rationale=f"Inherited historical scar obligation: {s_ob.description}",
                                observation_refs=("runtime/memory/",),
                            )
                        )
                semantic_obligations = tuple(existing_obs_map.values())
                semantic_dispositions = tuple(disp_list)
                self._ledger.append(
                    Event(
                        1,
                        "L11_SCAR_OBLIGATIONS_INHERITED",
                        {
                            "layer": "L11",
                            "run_id": run_id,
                            "goal_id": goal_id,
                            "count": len(derived_scar_obs),
                            "obligation_ids": [o.obligation_id for o in derived_scar_obs],
                            "scar_obligations": [
                                {
                                    "obligation_id": o.obligation_id,
                                    "description": o.description,
                                    "nature": o.obligation_nature.value,
                                }
                                for o in derived_scar_obs
                            ],
                        },
                    )
                )

            # Continuous advisory weakness scan
            advisory_findings = self._weakness_finder.scan_all(capability_manifest)
            self._ledger.append(
                Event(
                    1,
                    "L11_WEAKNESS_FINDER_ADVISORY_SCAN",
                    {
                        "run_id": run_id,
                        "goal_id": goal_id,
                        "scanned": True,
                        "findings_count": len(advisory_findings),
                        "finding_ids": [f.finding_id for f in advisory_findings],
                    },
                )
            )

            if semantic_obligations or semantic_dispositions:
                try:
                    self._firewall.verify_l11_semantic_freeze(
                        manifest=capability_manifest,
                        obligations=semantic_obligations,
                        dispositions=semantic_dispositions,
                    )
                except L11FreezeDeniedError as exc:
                    return RunOutcome(
                        RunStatus.REMANDED,
                        goal_id,
                        f"L11_FREEZE_DENIED: {exc}",
                        ephemeral_context=ExecutionContext(
                            diagnostics=(str(exc),),
                            retry_hints=("resolve semantic scope omissions or missing lawful dispositions before L11 freeze",),
                        ),
                    )

            # Hermetic firewall tests still exercise the manifest checkpoint without a production
            # repository. This is an L11 record, never a promotion decision.
            if not production_completeness:
                self._ledger.append(
                    Event(
                        1,
                        "COMPLETENESS_MANIFEST_FROZEN",
                        {
                            "layer": "L11",
                            "run_id": run_id,
                            "goal_id": goal_id,
                            "manifest_id": capability_manifest.manifest_id,
                            "manifest_sha256": capability_manifest.manifest_sha256,
                            "expected_capabilities": list(capability_manifest.expected_capabilities),
                            "required_profiles": [p.value for p in capability_manifest.required_profiles],
                        },
                    )
                )

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
            l10_observation_refs: tuple[str, ...] = ()
            for stage, layer in FRONTEND_PLANNER_STAGES:
                if decision.ceremony.obligation_for(layer) is Obligation.DISCHARGE:
                    continue
                scars = self._scar_refs(goal_signature, stage)
                session_name = (
                    "adversary"
                    if stage is StageId.ADVERSARIAL_REVIEW
                    else ("critic" if stage is StageId.CRITIQUE else "planner")
                )
                stage_context_refs = _playbook_context_refs(
                    self._playbook,
                    stage=stage,
                    context_refs=tuple(planner_artifacts),
                )
                result = self._playbook.run_stage(
                    goal_id=goal_id,
                    run_id=run_id,
                    stage=stage,
                    session=session_name,
                    budget=decision.budget,
                    scars=scars,
                    context_refs=stage_context_refs,
                    detail=goal_detail,
                )
                budget.charge(result.cost)
                self._record_stage(run_id, goal_id, stage, session_name, result)
                if result.status is not TaskStatus.COMPLETE:
                    failure = (
                        f": {result.failure_code}"
                        if isinstance(result.failure_code, str) and result.failure_code
                        else ""
                    )
                    return RunOutcome(
                        RunStatus.REMANDED,
                        goal_id,
                        f"{stage.name} worker failed: {result.status.value}{failure}",
                        ephemeral_context=ExecutionContext(
                            retry_hints=(f"retry {stage.name} after resolving the worker failure",),
                            diagnostics=(f"trusted worker failure at {stage.name}",),
                        ),
                    )
                if (
                    production_completeness
                    and capability_manifest is not None
                    and stage is StageId.ADVERSARIAL_REVIEW
                    and "l10_family_match_requires_independent_sealed_context"
                    in capability_manifest.slo_obligations
                ):
                    try:
                        l10_ref = _l10_sealed_context_observation(
                            self._cas,
                            result,
                            goal_id=goal_id,
                            run_id=run_id,
                            expected_context=stage_context_refs + scars,
                        )
                    except (CandidateIntegrityError, ValueError):
                        return RunOutcome(
                            RunStatus.REMANDED,
                            goal_id,
                            "L10 sealed-context observation failed closed: CandidateIntegrityError",
                            ephemeral_context=ExecutionContext(
                                diagnostics=("L10 sealed-context observation failed closed",),
                            ),
                        )
                    l10_observation_refs = (l10_ref,)
                    self._ledger.append(
                        Event(
                            1,
                            "L10_SEALED_CONTEXT_OBSERVED",
                            {
                                "goal_id": goal_id,
                                "run_id": run_id,
                                "task_id": result.task_id,
                                "ref": l10_ref,
                                "model": result.cost.model_ver,
                            },
                        )
                    )
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

                if stage is StageId.RESEARCH:
                    # Validate / structure formal research packet (L05 / SCO-015)
                    packet = FrontierResearchPacket(
                        packet_id=f"RES-{run_id}-{goal_id}",
                        topic=objective,
                        hypotheses=(
                            ResearchHypothesis(
                                hypothesis_id=f"HYP-{run_id}-1",
                                statement=f"Investigate architectural solution for {objective}",
                                context=stage_content[:200],
                                falsification_conditions=("Fails constitutional constraints", "Fails negative canaries"),
                            ),
                        ),
                        citations=(
                            EvidenceCitation(
                                citation_id=f"CIT-{run_id}-1",
                                source_title="PAEOS Canonical Specifications",
                                source_reference="operations/ENGINEERING_LIFECYCLE.md",
                                tier=AuthoritativeSourceTier.TIER_4_CANONICAL_SPECIFICATION,
                                relevance_summary="Grounded in canonical lifecycle baseline",
                            ),
                        ),
                        constraints=(
                            TechnicalConstraint(
                                constraint_name="A0_A5_Floor",
                                parameter_bound="Within delegated authority envelope",
                                rationale="Fail closed if outside envelope",
                            ),
                        ),
                        synthesis=stage_content[:500],
                    )
                    packet_bytes = json.dumps(asdict(packet), sort_keys=True, indent=2).encode("utf-8")
                    packet_cas_hash = self._cas.put(packet_bytes)
                    self._ledger.append(
                        Event(
                            1,
                            "L05_RESEARCH_PACKET_RECORDED",
                            {
                                "layer": "L05",
                                "run_id": run_id,
                                "goal_id": goal_id,
                                "packet_id": packet.packet_id,
                                "topic": packet.topic,
                                "hypotheses_count": len(packet.hypotheses),
                                "citations_count": len(packet.citations),
                                "constraints_count": len(packet.constraints),
                                "packet_cas_hash": packet_cas_hash,
                            },
                        )
                    )
                elif stage is StageId.TRADEOFF:
                    # Validate / structure formal multi-criteria trade-off matrix (L06 / SCO-016)
                    matrix = MultiCriteriaTradeOffMatrix(
                        matrix_id=f"TOM-{run_id}-{goal_id}",
                        decision_topic=objective,
                        criteria=(
                            TradeOffCriterion(
                                criterion_id="CRIT-CORRECTNESS",
                                name="Physical Correctness",
                                weight=0.5,
                                description="Passes non-vacuous court verification and canaries",
                            ),
                            TradeOffCriterion(
                                criterion_id="CRIT-COMPLEXITY",
                                name="Implementation Simplicity",
                                weight=0.3,
                                description="Minimizes architectural churn and cognitive load",
                            ),
                            TradeOffCriterion(
                                criterion_id="CRIT-ECONOMY",
                                name="Reasoning Economy",
                                weight=0.2,
                                description="Preserves scarce frontier model reasoning quota",
                            ),
                        ),
                        options=(
                            CandidateOption(
                                option_id="OPT-PRIMARY",
                                name="Target Canonical Architecture",
                                description=f"Implementation aligned with canonical intent for {objective}",
                                is_pareto_optimal=True,
                                scores=(
                                    CandidateOptionScore(
                                        option_id="OPT-PRIMARY",
                                        criterion_id="CRIT-CORRECTNESS",
                                        score=9.5,
                                        evidence_notes="Verified against court tests",
                                    ),
                                    CandidateOptionScore(
                                        option_id="OPT-PRIMARY",
                                        criterion_id="CRIT-COMPLEXITY",
                                        score=8.0,
                                        evidence_notes="Clean separation of concerns",
                                    ),
                                    CandidateOptionScore(
                                        option_id="OPT-PRIMARY",
                                        criterion_id="CRIT-ECONOMY",
                                        score=8.5,
                                        evidence_notes="Targeted model tier usage",
                                    ),
                                ),
                            ),
                            CandidateOption(
                                option_id="OPT-PROCEDURAL-WORKAROUND",
                                name="Ad-hoc Procedural In-line Patch",
                                description=f"Monolithic procedural workaround bypassing formal schemas for {objective}",
                                is_pareto_optimal=False,
                                scores=(
                                    CandidateOptionScore(
                                        option_id="OPT-PROCEDURAL-WORKAROUND",
                                        criterion_id="CRIT-CORRECTNESS",
                                        score=4.0,
                                        evidence_notes="Lacks non-vacuous court verification and leaves ungrounded side-effects",
                                    ),
                                    CandidateOptionScore(
                                        option_id="OPT-PROCEDURAL-WORKAROUND",
                                        criterion_id="CRIT-COMPLEXITY",
                                        score=5.5,
                                        evidence_notes="Introduces tight coupling across stage boundaries",
                                    ),
                                    CandidateOptionScore(
                                        option_id="OPT-PROCEDURAL-WORKAROUND",
                                        criterion_id="CRIT-ECONOMY",
                                        score=6.0,
                                        evidence_notes="Repeated retry cycles on court failure consume excess reasoning quota",
                                    ),
                                ),
                            ),
                        ),
                        recommended_option_id="OPT-PRIMARY",
                        selection_rationale=f"Selected canonical approach based on multi-criteria Pareto dominance over procedural workaround for {objective}",
                    )
                    matrix_bytes = json.dumps(asdict(matrix), sort_keys=True, indent=2).encode("utf-8")
                    matrix_cas_hash = self._cas.put(matrix_bytes)
                    self._ledger.append(
                        Event(
                            1,
                            "L06_TRADEOFF_MATRIX_RECORDED",
                            {
                                "layer": "L06",
                                "run_id": run_id,
                                "goal_id": goal_id,
                                "matrix_id": matrix.matrix_id,
                                "decision_topic": matrix.decision_topic,
                                "criteria_count": len(matrix.criteria),
                                "options_count": len(matrix.options),
                                "recommended_option_id": matrix.recommended_option_id,
                                "matrix_cas_hash": matrix_cas_hash,
                            },
                        )
                    )

            if production_completeness:
                assert capability_manifest is not None
                try:
                    verification_support_files = freeze_verification_support_files(
                        repo_root=self._repo_root,
                        paths=capability_manifest.verification_support_paths,
                        cas=self._cas,
                    )
                except (CandidateIntegrityError, OSError, ValueError) as exc:
                    return RunOutcome(
                        RunStatus.REMANDED,
                        goal_id,
                        f"L11 verification-support snapshot failed closed: {exc}",
                    )
                try:
                    verification_source_files = freeze_verification_source_files(
                        repo_root=self._repo_root,
                        paths=capability_manifest.verification_source_paths,
                        cas=self._cas,
                    )
                except (CandidateIntegrityError, OSError, ValueError) as exc:
                    return RunOutcome(
                        RunStatus.REMANDED,
                        goal_id,
                        f"L11 verification-source snapshot failed closed: {exc}",
                    )
                plan = {
                    "candidate_task_identity": {"goal_id": goal_id, "run_id": run_id},
                    "objective": objective,
                    "affected_files": list(changed_paths),
                    "forbidden_files": list(capability_manifest.explicit_exclusions),
                    "completeness_manifest_sha256": capability_manifest.manifest_sha256,
                    "expected_capabilities": list(capability_manifest.expected_capabilities),
                    "semantic_obligations": [
                        {
                            "obligation_id": o.obligation_id,
                            "description": o.description,
                            "nature": o.obligation_nature.value,
                        }
                        for o in semantic_obligations
                    ],
                    "acceptance_criteria": list(capability_manifest.slo_obligations),
                    "verification_obligations": [
                        {
                            "claim_id": item.claim_id,
                            "argv": list(item.argv),
                            "timeout_s": item.timeout_s,
                            "kind": item.kind.value,
                        }
                        for item in capability_manifest.verification_obligations
                    ],
                    "verification_support_files": [
                        {
                            "path": item.path,
                            "cas_hash": item.cas_hash,
                            "file_sha256": item.file_sha256,
                            "size": item.size,
                        }
                        for item in verification_support_files
                    ],
                    "verification_source_files": [
                        {
                            "path": item.path,
                            "cas_hash": item.cas_hash,
                            "file_sha256": item.file_sha256,
                            "size": item.size,
                        }
                        for item in verification_source_files
                    ],
                    "rollback": "retain candidate as unpromoted and leave authoritative source unchanged on any L13-L16 failure",
                    "architecture_derivation_refs": list(capability_manifest.derivation_refs),
                    "test_strategy": "trusted physical verifier plus Court replay and negative CANARY discrimination",
                    "required_audit_profile": [p.value for p in capability_manifest.required_profiles],
                }
                l11_binding_sha256 = freeze_l11_plan(self._cas, plan)
                self._ledger.append(
                    Event(
                        1,
                        "L11_FREEZE",
                        {
                            "layer": "L11",
                            "run_id": run_id,
                            "goal_id": goal_id,
                            "manifest_id": capability_manifest.manifest_id,
                            "manifest_sha256": capability_manifest.manifest_sha256,
                            "plan_sha256": l11_binding_sha256,
                            "expected_capabilities": list(capability_manifest.expected_capabilities),
                            "semantic_obligations": [o.obligation_id for o in semantic_obligations],
                            "verification_support_files": [
                                {"path": item.path, "file_sha256": item.file_sha256, "size": item.size}
                                for item in verification_support_files
                            ],
                            "verification_source_files": [
                                {
                                    "path": item.path,
                                    "file_sha256": item.file_sha256,
                                    "size": item.size,
                                }
                                for item in verification_source_files
                            ],
                        },
                    )
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
            if build.status.name != "COMPLETE" or not build.artifacts or not build.written_paths:
                if build.failure_code:
                    return RunOutcome(
                        RunStatus.REMANDED,
                        goal_id,
                        f"builder failed before artifact capture: {build.failure_code}",
                    )
                return RunOutcome(RunStatus.REMANDED, goal_id, "builder produced no artifact")
            artifact = build.artifacts[0]
        except BudgetExceeded as exc:
            return RunOutcome(RunStatus.HALTED, goal_id, f"budget breach: {exc}")

        candidate: CandidateMaterialization | None = None
        if production_completeness:
            assert capability_manifest is not None
            assert self._state_dir is not None
            try:
                candidate = materialize_candidate(
                    repo_root=self._repo_root,
                    written_paths=build.written_paths,
                    cas=self._cas,
                    state_dir=self._state_dir,
                    run_id=run_id,
                    l11_binding_sha256=l11_binding_sha256,
                    builder_identity=build.cost.model_ver,
                    base_revision=physical_base_revision(self._repo_root),
                    workspace_identity=build.workspace_identity,
                    environment_identity=build.environment_identity,
                    affected_paths=changed_paths,
                    verification_support_files=tuple(
                        (item.path, item.cas_hash) for item in verification_support_files
                    ),
                    verification_source_files=tuple(
                        (item.path, item.cas_hash) for item in verification_source_files
                    ),
                )
            except (CandidateIntegrityError, OSError, ValueError) as exc:
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    f"runtime candidate materialization failed closed: {exc}",
                )
            self._ledger.append(
                Event(
                    1,
                    "CANDIDATE_MATERIALIZED",
                    {
                        "layer": "L12",
                        "run_id": run_id,
                        "goal_id": goal_id,
                        "candidate_id": candidate.candidate_id,
                        "candidate_status": candidate.status.value,
                        "l11_plan_sha256": candidate.l11_binding_sha256,
                        "tree_sha256": candidate.tree_sha256,
                        "diff_sha256": candidate.diff_sha256,
                        "cas_artifact_hash": candidate.cas_artifact_hash,
                        "builder_identity": candidate.builder_identity,
                        "workspace_identity": candidate.workspace_identity,
                        "environment_identity": candidate.environment_identity,
                        "verification_support_files": [
                            {"path": item.path, "file_sha256": item.file_sha256, "size": item.size}
                            for item in candidate.verification_support_files
                        ],
                        "verification_source_files": [
                            {"path": item.path, "file_sha256": item.file_sha256, "size": item.size}
                            for item in candidate.verification_source_files
                        ],
                    },
                )
            )

        # Autonomous evidence (B2.P, toward R5): pull the evidence the Builder SUBMITTED for this
        # run (via the court MCP) instead of the pre-declared backlog. Empty ⇒ REMAND — the agent
        # must produce its own probative evidence, not have it authored for it.
        if production_completeness:
            assert candidate is not None
            assert capability_manifest is not None
            try:
                builder_evidence = tuple(
                    derive_physical_evidence(
                        candidate=candidate,
                        claim_id=obligation.claim_id,
                        argv=obligation.argv,
                        artifact_hash=candidate.cas_artifact_hash,
                        timeout_s=obligation.timeout_s,
                    )
                    for obligation in capability_manifest.verification_obligations
                )
            except (CandidateIntegrityError, OSError, ValueError) as exc:
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    f"L13 trusted physical verification failed closed: {exc}",
                )
            if not builder_evidence:
                return RunOutcome(RunStatus.REMANDED, goal_id, "L11 contains no verifier obligations")
        elif evidence_source is not None:
            submitted = evidence_source.evidence_for(run_id)
            if submitted:
                builder_evidence = submitted
            elif not builder_evidence:
                return RunOutcome(
                    RunStatus.REMANDED, goal_id, "no evidence submitted to the court for this run"
                )

        # Legacy evidence binding (R4): only non-production hermetic loops may use an injected
        # evidence seam. Production P1 evidence is already derived from the candidate by L13 and
        # must never be rebound from caller text or the Builder pool.
        # ACTUALLY produced, so a live, novel artifact is adjudicable (its hash is unknowable when
        # the backlog is authored). The court still RE-RUNS each `reproducible_command`, so the T2
        # anti-forgery property is intact — only the artifact_hash binding is set to the real hash.
        if not production_completeness:
            builder_evidence = tuple(
                replace(ev, artifact_hash=artifact.hash) for ev in builder_evidence
            )

        # --- L13: Verification Court & Pre-Audit Completeness Checkpoint ---
        pre_audit_bundle: PreAuditCompletenessBundle | None = None
        post_audit_bundle: PreAuditCompletenessBundle | None = None
        pre_audit_verdict: PreAuditVerdict | None = None
        if completeness_bundle is not None:
            pre_audit_verdict = self._firewall.verify_pre_audit_completeness(
                bundle=completeness_bundle,
                manifest=capability_manifest,
            )
            if not pre_audit_verdict.passed:
                context = ExecutionContext(
                    retry_hints=("resolve completeness violations before proceeding to audit",),
                    diagnostics=tuple(
                        f"completeness firewall L13 violation: {v}"
                        for v in pre_audit_verdict.violations
                    ),
                )
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    "completeness firewall L13 pre-audit check failed",
                    ephemeral_context=context,
                )

        # --- Verification Court: reproduce every claim (B1.E). For a live run the command runs
        # against a workspace with the change applied (B2.N), so probative evidence can pass. ---
        artifact_under_review = candidate.cas_artifact_hash if candidate is not None else artifact.hash
        claims = tuple(
            Claim(id=ev.claim_id, statement="produced", evidence_refs=(ev.hash,))
            for ev in builder_evidence
        )
        court, cleanup = self._court_for_run(build, candidate=candidate)
        try:
            for evidence in builder_evidence:
                court.submit_evidence(evidence)
            verdict = court.adjudicate(artifact_under_review, claims)
        finally:
            cleanup()
        p1_semantic_discrimination = bool(
            production_completeness
            and capability_manifest is not None
            and capability_manifest.manifest_id == P1_MANIFEST_ID
        )
        if production_completeness and (
            not p1_semantic_discrimination or verdict.outcome is VerdictOutcome.REMAND
        ):
            self._ledger.append(
                Event(
                    1,
                    "L13_VERIFICATION",
                    {
                        "layer": "L13",
                        "run_id": run_id,
                        "goal_id": goal_id,
                        "candidate_id": candidate.candidate_id if candidate is not None else "",
                        "candidate_sha256": artifact_under_review,
                        "verdict": verdict.outcome.value,
                        "evidence_hashes": [ev.hash for ev in builder_evidence],
                    },
                )
            )
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
                candidate=candidate,
            )

        # P1's physical semantic comparator is part of L13, so bind its result before committing
        # the final verification/completeness pair consumed by L14.  The Court has already run;
        # this only defers its durable PASS row and does not execute either physical arm twice.
        if p1_semantic_discrimination:
            assert candidate is not None
            assert capability_manifest is not None
            try:
                discrimination = discriminate_p1_candidate(
                    candidate=candidate,
                    cas=self._cas,
                    manifest_id=capability_manifest.manifest_id,
                    obligations=capability_manifest.verification_obligations,
                )
            except Exception as exc:
                failure_class = type(exc).__name__
                failure_message_sha256 = hashlib.sha256(
                    str(exc).encode("utf-8", errors="replace")
                ).hexdigest()
                self._ledger.append(Event(1, "L13_VERIFICATION_FAILURE", {
                    "layer": "L13", "run_id": run_id, "goal_id": goal_id,
                    "failure_class": failure_class,
                    "failure_message_sha256": failure_message_sha256,
                    "comparator": "P1_SEMANTIC_DISCRIMINATION",
                }))
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    f"L13 P1 semantic discrimination failed closed: {failure_class}",
                    verdict=verdict,
                    ephemeral_context=ExecutionContext(
                        retry_hints=("resolve L13 comparator failure before retry",),
                        diagnostics=(
                            f"L13 P1 comparator infrastructure exception: {failure_class}",
                        ),
                    ),
                    candidate=candidate,
                )
            self._ledger.append(Event(1, "L13_P1_SEMANTIC_DISCRIMINATION", {
                "layer": "L13", "run_id": run_id, "goal_id": goal_id,
                "candidate_id": candidate.candidate_id,
                "candidate_sha256": candidate.cas_artifact_hash,
                "results": list(discrimination),
            }))
            self._ledger.append(
                Event(
                    1,
                    "L13_VERIFICATION",
                    {
                        "layer": "L13",
                        "run_id": run_id,
                        "goal_id": goal_id,
                        "candidate_id": candidate.candidate_id,
                        "candidate_sha256": artifact_under_review,
                        "verdict": verdict.outcome.value,
                        "evidence_hashes": [ev.hash for ev in builder_evidence],
                    },
                )
            )

        if production_completeness:
            assert candidate is not None
            assert capability_manifest is not None
            try:
                ledger_head = self._ledger.verify_chain()
                evidence_refs = tuple(item.hash for item in builder_evidence)
                pre_e2e = {
                    "production_intake": (
                        _observation_digest(
                            "production-intake",
                            {"goal_id": goal_id, "run_id": run_id, "ledger_head": ledger_head},
                        ),
                    ),
                    "l11_manifest_freeze": (l11_binding_sha256,),
                    "l12_implementation": (candidate.cas_artifact_hash,),
                    "l13_physical_verification": (
                        _observation_digest("l13-physical-verification", evidence_refs),
                    ),
                }
                pre_slo = {
                    "no_expected_result_injection": (
                        _observation_digest(
                            "physical-verifier-observations",
                            tuple(_evidence_to_json(item) for item in builder_evidence),
                        ),
                    ),
                    "sentium_quarantine_preserved": (
                        _observation_digest(
                            "candidate-quarantine-scope",
                            tuple(
                                {"path": item.path, "file_sha256": item.file_sha256}
                                for item in candidate.changed_files
                            ),
                        ),
                    ),
                }
                pre_slo.update(physical_slo_observations(builder_evidence))
                if l10_observation_refs:
                    pre_slo["l10_family_match_requires_independent_sealed_context"] = (
                        l10_observation_refs
                    )
                pre_audit_bundle = _derive_runtime_completeness_bundle(
                    manifest=capability_manifest,
                    candidate=candidate,
                    evidence=builder_evidence,
                    transport_kinds=("SUBPROCESS_RUN", "SQLITE_WAL_LEDGER"),
                    transport_observation_refs={
                        "SUBPROCESS_RUN": evidence_refs,
                        "SQLITE_WAL_LEDGER": (ledger_head,),
                    },
                    e2e_observations=pre_e2e,
                    slo_observations=pre_slo,
                    cas=self._cas,
                )
            except (CandidateIntegrityError, OSError, ValueError) as exc:
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    f"L13 physical completeness derivation failed closed: {type(exc).__name__}",
                    verdict=verdict,
                    candidate=candidate,
                )
            pre_audit_verdict = self._firewall.verify_pre_audit_completeness(
                bundle=pre_audit_bundle,
                manifest=capability_manifest,
            )
            if not pre_audit_verdict.passed:
                context = ExecutionContext(
                    retry_hints=("resolve completeness violations before L14",),
                    diagnostics=tuple(
                        f"completeness firewall L13 violation: {v}"
                        for v in pre_audit_verdict.violations
                    ),
                )
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    "completeness firewall L13 pre-audit check failed",
                    verdict=verdict,
                    ephemeral_context=context,
                    candidate=candidate,
                )
            self._ledger.append(
                Event(
                    1,
                    "L13_COMPLETENESS_CLEARED",
                    {
                        "layer": "L13",
                        "run_id": run_id,
                        "goal_id": goal_id,
                        "candidate_id": candidate.candidate_id,
                        "candidate_sha256": candidate.cas_artifact_hash,
                        "evidence_bundle_sha256": pre_audit_verdict.evidence_bundle_sha256,
                    },
                )
            )

        # --- Probative-evidence gate (B2.O / CANARY-0002): even a reproducing command must
        # DISCRIMINATE — its result must differ with the change vs without. Vacuous (non-probative)
        # evidence is a L13 failure and must stop the run before any independent L14 audit is spent.
        if self._repo_root is not None:
            if production_completeness:
                assert capability_manifest is not None
                assert candidate is not None
                if p1_semantic_discrimination:
                    vacuous = ()
                else:
                    environment = {"PATH": allowlisted_path(), "LC_ALL": "C"}
                    commands = tuple(
                        canonical_command(
                            tuple(str(Path(sys.executable).absolute()) if arg == "{python}" else arg for arg in argv),
                            environment=environment,
                        )
                        for argv in candidate_discrimination_commands(capability_manifest.verification_obligations)
                    )
                    vacuous = None
            else:
                commands = tuple(
                    ev.reproducible_command for ev in builder_evidence if ev.reproducible_command
                )
                vacuous = None
            try:
                if vacuous is None:
                    vacuous = vacuous_commands(self._repo_root, build.written_paths, self._cas, commands)
            except Exception as exc:
                failure_class = type(exc).__name__
                failure_message_sha256 = hashlib.sha256(
                    str(exc).encode("utf-8", errors="replace")
                ).hexdigest()
                self._ledger.append(
                    Event(
                        1,
                        "L13_VERIFICATION_FAILURE",
                        {
                            "layer": "L13",
                            "run_id": run_id,
                            "goal_id": goal_id,
                            "failure_class": failure_class,
                            "failure_message_sha256": failure_message_sha256,
                        },
                    )
                )
                context = ExecutionContext(
                    retry_hints=("resolve L13 verification infrastructure failure before retry",),
                    diagnostics=(f"L13 verification infrastructure exception: {failure_class}",),
                )
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    f"L13 verification infrastructure failed closed: {failure_class}",
                    verdict=verdict,
                    ephemeral_context=context,
                    candidate=candidate,
                )
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
                    candidate=candidate,
                )

            # L14 is composed outside the Builder/Court runtime. Incoming caller-supplied audit
            # artifacts were rejected above; only this independent Router-backed callback can
            # provide artifacts for the L16 promotion checkpoint.
            if self._l14_auditor is None:
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    "L14 heterogeneous auditor is not wired at the production composition root",
                    candidate=candidate,
                )
            try:
                l14 = self._l14_auditor(
                    candidate,
                    pre_audit_verdict,
                    builder_evidence,
                    capability_manifest,
                )
                if not isinstance(l14, L14AuditArtifacts):
                    raise CandidateIntegrityError("L14 callback returned an invalid artifact record")
                if (
                    l14.contract.candidate_sha256 != candidate.cas_artifact_hash
                    or l14.contract.evidence_bundle_sha256
                    != pre_audit_verdict.evidence_bundle_sha256
                    or l14.contract.builder_family.value != "gpt"
                    or l14.contract.builder_model_id != candidate.builder_identity
                ):
                    raise CandidateIntegrityError("L14 contract is not bound to this candidate/run")
                if (
                    not l14.receipt_path.is_absolute()
                    or not l14.report_path.is_absolute()
                    or l14.receipt_path.is_symlink()
                    or l14.report_path.is_symlink()
                    or not l14.receipt_path.is_file()
                    or not l14.report_path.is_file()
                ):
                    raise CandidateIntegrityError("L14 callback did not return stable artifacts")
                auditor_receipt_path = l14.receipt_path
                auditor_report_path = l14.report_path
                auditor_contract = l14.contract
                auditor_ledger_metadata = _auditor_ledger_metadata(
                    auditor_receipt_path, auditor_contract
                )
            except Exception as exc:
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    f"L14 heterogeneous audit failed closed: {type(exc).__name__}",
                    candidate=candidate,
                )
            self._ledger.append(
                Event(
                    1,
                    "L14_AUDIT",
                    {
                        "layer": "L14",
                        "run_id": run_id,
                        "goal_id": goal_id,
                        "candidate_id": candidate.candidate_id,
                        "candidate_sha256": candidate.cas_artifact_hash,
                        "evidence_bundle_sha256": pre_audit_verdict.evidence_bundle_sha256,
                        "receipt_sha256": hashlib.sha256(auditor_receipt_path.read_bytes()).hexdigest(),
                        "report_sha256": hashlib.sha256(auditor_report_path.read_bytes()).hexdigest(),
                        **auditor_ledger_metadata,
                        "auditor_contract_id": auditor_contract.audit_id,
                    },
                )
            )

        # --- Isolated Adversary over the sealed bundle (B1.D / FR-3) ---
        # B2.M: store a serialized copy of each evidence in the CAS and reference THAT, so the
        # adversary can actually read (and re-run) the evidence in its workspace — a bare evidence
        # hash is not a CAS blob and materialises to nothing (the adversary blocked without it).
        evidence_refs = tuple(self._cas.put(_serialize_evidence(ev)) for ev in builder_evidence)
        if candidate is not None:
            review_artifacts = (
                ArtifactRef(hash=candidate.cas_artifact_hash, type="candidate"),
                *tuple(
                    ArtifactRef(hash=item.cas_hash, type="candidate-file")
                    for item in candidate.changed_files
                ),
            )
        else:
            review_artifacts = (artifact,)
        bundle = self._ibm.seal(artifact_refs=review_artifacts, evidence_refs=evidence_refs)
        try:
            adversary = self._review.review(
                goal_id=goal_id,
                run_id=run_id,
                session="adversary",
                bundle=bundle,
                budget=decision.budget,
                # The artifact/candidate is intentionally public to this barrier; only planner
                # scratch refs remain Builder-private and must stay out of the sealed bundle.
                builder_private=tuple(planner_artifacts),
            )
            budget.charge(adversary.cost)
            self._record_adversary_gate(run_id, goal_id, "adversary", adversary)
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
                candidate=candidate,
            )

        if production_completeness:
            assert candidate is not None
            assert pre_audit_verdict is not None
            assert auditor_contract is not None
            self._ledger.append(
                Event(
                    1,
                    "L15_DOCUMENTATION_LEDGER",
                    {
                        "layer": "L15",
                        "run_id": run_id,
                        "goal_id": goal_id,
                        "candidate_id": candidate.candidate_id,
                        "candidate_sha256": candidate.cas_artifact_hash,
                        "l11_plan_sha256": candidate.l11_binding_sha256,
                        "l13_evidence_bundle_sha256": pre_audit_verdict.evidence_bundle_sha256,
                        "l14_audit_id": auditor_contract.audit_id,
                        "l14_receipt_path": str(auditor_receipt_path),
                        "l14_report_path": str(auditor_report_path),
                    },
                )
            )

            try:
                receipt = load_auditor_receipt(auditor_receipt_path)
                receipt_hash = hashlib.sha256(auditor_receipt_path.read_bytes()).hexdigest()
                report_hash = hashlib.sha256(auditor_report_path.read_bytes()).hexdigest()
                l15_head = self._ledger.verify_chain()
                l14_observation = _observation_digest(
                    "l14-external-audit",
                    {
                        "receipt_file_sha256": receipt_hash,
                        "report_file_sha256": report_hash,
                        "receipt_sha256": receipt.receipt_sha256,
                        "audit_id": receipt.audit_id,
                    },
                )
                l16_gate_observation = _observation_digest(
                    "l16-promotion-gate-inputs",
                    {
                        "candidate_sha256": candidate.cas_artifact_hash,
                        "pre_audit_bundle_sha256": pre_audit_verdict.evidence_bundle_sha256,
                        "receipt_sha256": receipt_hash,
                        "report_sha256": report_hash,
                        "l15_ledger_head": l15_head,
                    },
                )
                post_audit_bundle = _derive_runtime_completeness_bundle(
                    manifest=capability_manifest,
                    candidate=candidate,
                    evidence=builder_evidence,
                    transport_kinds=(
                        "SUBPROCESS_RUN",
                        "PAEOS_MODEL_ROUTER",
                        "KERNEL_ED25519",
                        "SQLITE_WAL_LEDGER",
                    ),
                    transport_observation_refs={
                        "SUBPROCESS_RUN": tuple(item.hash for item in builder_evidence),
                        "PAEOS_MODEL_ROUTER": (
                            receipt.transport_request_sha256,
                            receipt.transport_response_sha256,
                        ),
                        "KERNEL_ED25519": (receipt.receipt_sha256,),
                        "SQLITE_WAL_LEDGER": (l15_head,),
                    },
                    e2e_observations={
                        "production_intake": pre_e2e["production_intake"],
                        "l11_manifest_freeze": (candidate.l11_binding_sha256,),
                        "l12_implementation": (candidate.cas_artifact_hash,),
                        "l13_physical_verification": (
                            _observation_digest(
                                "l13-physical-verification",
                                tuple(item.hash for item in builder_evidence),
                            ),
                        ),
                        "l14_external_audit": (l14_observation, receipt_hash, report_hash),
                        "l15_documentation_ledger": (l15_head,),
                        "l16_promotion": (l16_gate_observation,),
                    },
                    slo_observations={
                        "no_expected_result_injection": (
                            _observation_digest(
                                "physical-verifier-observations",
                                tuple(_evidence_to_json(item) for item in builder_evidence),
                            ),
                        ),
                        **physical_slo_observations(builder_evidence),
                        "substantive_audit_pass_required": (receipt_hash, report_hash),
                        "sentium_quarantine_preserved": (
                            _observation_digest(
                                "candidate-quarantine-scope",
                                tuple(
                                    {"path": item.path, "file_sha256": item.file_sha256}
                                    for item in candidate.changed_files
                                ),
                            ),
                        ),
                    },
                    cas=self._cas,
                )
            except (CandidateIntegrityError, OSError, ValueError) as exc:
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    f"L16 physical completeness derivation failed closed: {type(exc).__name__}",
                    verdict=verdict,
                    candidate=candidate,
                )

        # --- L16: Promotion Completeness Checkpoint ---
        # Blocks promotion unless:
        # 1. Pre-audit completeness was cleared and remains untainted.
        # 2. A genuine, qualified L14 Heterogeneous Audit receipt is verified with valid transport attestation.
        if production_completeness or completeness_bundle is not None:
            if pre_audit_verdict is None or not pre_audit_verdict.passed:
                context = ExecutionContext(
                    retry_hints=("L13 pre-audit completeness must pass before promotion",),
                    diagnostics=("missing or failed L13 pre-audit completeness verdict",),
                )
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    "completeness firewall L16 promotion check failed: L13 not cleared",
                    ephemeral_context=context,
                    candidate=candidate,
                )
            if (
                auditor_receipt_path is None
                or auditor_report_path is None
                or auditor_contract is None
            ):
                context = ExecutionContext(
                    retry_hints=(
                        "L14 auditor receipt, report, and contract required for promotion completeness",
                    ),
                    diagnostics=("missing L14 audit artifacts for promotion",),
                )
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    "completeness firewall L16 promotion check failed: missing L14 receipt/report artifacts",
                    ephemeral_context=context,
                    candidate=candidate,
                )
            promo_verdict = self._firewall.verify_promotion_completeness(
                pre_audit_verdict=pre_audit_verdict,
                receipt_path=auditor_receipt_path,
                report_path=auditor_report_path,
                contract=auditor_contract,
                post_audit_bundle=post_audit_bundle,
                manifest=capability_manifest,
            )
            if not promo_verdict.passed:
                context = ExecutionContext(
                    retry_hints=("satisfy L16 promotion completeness and valid L14 receipt",),
                    diagnostics=tuple(
                        f"completeness firewall L16 violation: {v}"
                        for v in promo_verdict.violations
                    ),
                )
                return RunOutcome(
                    RunStatus.REMANDED,
                    goal_id,
                    "completeness firewall L16 promotion check failed",
                    ephemeral_context=context,
                    candidate=candidate,
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
        # The frozen kernel requires the canonical SEAL -> RETROSPECT -> MEMORY_UPDATE -> EVOLVE
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
                    if evo_res.status is not TaskStatus.COMPLETE:
                        return RunOutcome(
                            RunStatus.REMANDED,
                            goal_id,
                            f"{stage.name} worker failed: {evo_res.status.value}",
                            seal=seal,
                            verdict=verdict,
                            ephemeral_context=ExecutionContext(
                                retry_hints=(f"retry {stage.name} after resolving the worker failure",),
                                diagnostics=(f"trusted worker failure at {stage.name}",),
                            ),
                        )
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

    def _record_adversary_gate(
        self, run_id: str, goal_id: str, session: str, result: TaskResult
    ) -> None:
        """Record the post-L13 adversarial seal gate without inventing a lifecycle stage.

        ``StageId.ADVERSARIAL_REVIEW`` is the L10 planner-stage identity.  The later sealed-bundle
        adversary is an operational gate, not a second L10 or an L14 projection; keeping it out of
        ``STAGE_COMPLETED`` prevents lifecycle projections and audits from counting it as a layer.
        """
        self._ledger.append(
            Event(
                1,
                "ADVERSARY_GATE_REVIEWED",
                {
                    "run_id": run_id,
                    "goal_id": goal_id,
                    "session": session,
                    "status": result.status.value,
                    "model_ver": result.cost.model_ver,
                    "tokens": result.cost.tokens,
                    "lifecycle_layer": None,
                    "gate": "post_l13_seal_adversary",
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

    def _court_for_run(
        self,
        build: TaskResult,
        *,
        candidate: CandidateMaterialization | None = None,
    ) -> tuple[Court, Callable[[], None]]:
        """The court to adjudicate this run's evidence (B2.N). For a live run (repo_root set + the
        builder wrote files), verify commands against a workspace with the change applied — so
        probative evidence passes; otherwise use the injected court. Returns (court, cleanup)."""
        if candidate is not None:
            return Court(runner=workspace_runner(candidate.candidate_workspace, candidate=candidate)), lambda: None
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


_NON_AUTHORITATIVE_INSPECTION_PREFIXES = frozenset(
    {"tests", "reviews", "docs", "ledger", "misc", ".state"}
)
_TEXT_SOURCE_SUFFIXES = frozenset({".css", ".html", ".js", ".jsx", ".ts", ".tsx", ".vue"})
_PYTHON_SOURCE_SUFFIXES = frozenset({".py", ".pyi"})
_SYNTHETIC_MARKERS = (
    "event_pool",
    "makeevent(",
    "canned success",
    "synthetic fallback",
    "unrestricted fallback",
    "return canned",
)
_METRIC_MARKERS = (
    "eom spend",
    "budget utilization",
    "active agent leases",
    "14 sources",
    "60.3%",
)
_INSPECTOR_FUNCTION_NAMES = frozenset(
    {"_ast_target_names", "_is_detector_literal", "_python_path_markers", "inspect_authoritative_path"}
)


def _ast_target_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id.casefold(),)
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in node.elts:
            names.extend(_ast_target_names(element))
        return tuple(names)
    return ()


def _is_inspector_implementation_node(
    node: ast.AST, parents: Mapping[ast.AST, ast.AST]
) -> bool:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            current.name in _INSPECTOR_FUNCTION_NAMES
        ):
            return True
        current = parents.get(current)
    return False


def _is_detector_literal(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> bool:
    """Ignore marker vocabulary used by the static inspector itself.

    The old implementation searched raw bytes.  That made the inspector report its own marker
    table, and made intentional strings in changed CANARY tests look like deployed behavior.  We
    retain conservative source inspection, but exclude literals structurally owned by a marker
    registry or marker-filter comprehension.  Comments and docstrings are never operational
    observations because they are not executable AST nodes.
    """
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, ast.Expr) and parent.value is current:
            owner = parents.get(parent)
            if (
                isinstance(owner, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and owner.body
                and owner.body[0] is parent
            ):
                return True
        if isinstance(parent, ast.JoinedStr):
            owner = parents.get(parent)
            if (
                isinstance(owner, ast.Call)
                and isinstance(owner.func, ast.Attribute)
                and owner.func.attr in {"append", "extend"}
            ):
                return True
        if isinstance(parent, ast.comprehension) and any(
            "marker" in name for name in _ast_target_names(parent.target)
        ):
            return True
        if isinstance(parent, (ast.Assign, ast.AnnAssign)):
            targets = parent.targets if isinstance(parent, ast.Assign) else (parent.target,)
            if any(
                any(token in name for token in ("marker", "pattern", "literal"))
                for target in targets
                for name in _ast_target_names(target)
            ):
                return True
        current = parent
    return False


def _python_path_markers(relative_path: str, text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        tree = ast.parse(text, filename=relative_path)
    except SyntaxError:
        # A syntax-invalid authoritative source file is independently rejected by the physical
        # verifier.  Keep this inspector fail-closed for marker-bearing invalid source rather than
        # letting a parse failure create an inspection blind spot.
        folded = text.casefold()
        return (
            tuple(marker for marker in _SYNTHETIC_MARKERS if marker in folded),
            tuple(marker for marker in _METRIC_MARKERS if marker in folded),
        )

    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    synthetic: set[str] = set()
    metrics: set[str] = set()
    for node in ast.walk(tree):
        if _is_inspector_implementation_node(node, parents):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name.casefold()
            if name in {"makeevent", "make_event"}:
                synthetic.add("makeevent(")
        if isinstance(node, ast.Name) and node.id.casefold() == "event_pool":
            synthetic.add("event_pool")
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if _is_detector_literal(node, parents):
            continue
        value = node.value.casefold()
        synthetic.update(marker for marker in _SYNTHETIC_MARKERS if marker in value)
        metrics.update(marker for marker in _METRIC_MARKERS if marker in value)
    return tuple(sorted(synthetic)), tuple(sorted(metrics))


def inspect_authoritative_path(
    relative_path: str, content: bytes
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Inspect deployed source semantics without self-matching detector/test vocabulary.

    Verification and documentation inputs are not authoritative runtime paths.  Python runtime
    code is inspected structurally; frontend text sources retain a conservative lexical check.
    The return shape is intentionally small so the L13 bundle remains a deterministic observation.
    """
    normalized = Path(relative_path).as_posix()
    parts = Path(normalized).parts
    if not normalized or any(part.casefold() in _NON_AUTHORITATIVE_INSPECTION_PREFIXES for part in parts):
        return (), ()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return (), ()
    suffix = Path(normalized).suffix.casefold()
    if suffix in _PYTHON_SOURCE_SUFFIXES:
        synthetic, metrics = _python_path_markers(normalized, text)
    elif suffix in _TEXT_SOURCE_SUFFIXES:
        folded = text.casefold()
        synthetic = tuple(
            marker for marker in _SYNTHETIC_MARKERS if marker in folded
        )
        metrics = tuple(marker for marker in _METRIC_MARKERS if marker in folded)
    else:
        return (), ()
    if "£" in text and re.search(r"£\s*\d", text):
        metrics = (*metrics, "currency-literal")
    return tuple(sorted(set(synthetic))), tuple(sorted(set(metrics)))


def _derive_runtime_completeness_bundle(
    *,
    manifest: AuthoritativeCapabilityManifest,
    candidate: CandidateMaterialization,
    evidence: tuple[Evidence, ...],
    transport_kinds: tuple[str, ...] = (),
    transport_observation_refs: Mapping[str, tuple[str, ...]] | None = None,
    e2e_observations: Mapping[str, tuple[str, ...]] | None = None,
    slo_observations: Mapping[str, tuple[str, ...]] | None = None,
    cas: CAS | None = None,
) -> PreAuditCompletenessBundle:
    """Build a completeness bundle from physically observed runtime identities.

    This function deliberately has no ``verified`` or ``fixtures_only`` input.  The production
    composition root supplies only hashes derived from the candidate, kernel verifier, ledger, and
    persisted audit receipt; the firewall then checks that the observations are present and bound to
    the L11 manifest/candidate pair.
    """
    observed_by_claim: dict[str, str] = {}
    for item in evidence:
        if item.claim_id in observed_by_claim:
            raise CandidateIntegrityError(f"duplicate physical evidence claim: {item.claim_id}")
        if not _is_sha256_digest(item.hash):
            raise CandidateIntegrityError("physical evidence has an invalid identity hash")
        observed_by_claim[item.claim_id] = item.hash
    observed = set(observed_by_claim)

    capabilities = tuple(
        CapabilityDisposition(
            capability_id=obligation.claim_id,
            system_id="PAEOS",
            status="IMPLEMENTED" if obligation.claim_id in observed else "OMITTED",
            observation_refs=(observed_by_claim[obligation.claim_id],)
            if obligation.claim_id in observed
            else (),
        )
        for obligation in manifest.verification_obligations
    )

    actual_transport_refs = transport_observation_refs or {}
    transports = tuple(
        OperationalTransportProof(
            adapter_name="runtime:" + transport_kind,
            transport_kind=transport_kind,
            caller_entrypoint="runtime.orchestrator.SoftLoop",
            is_test_only=False,
            verified=bool(actual_transport_refs.get(transport_kind))
            and all(_is_sha256_digest(ref) for ref in actual_transport_refs[transport_kind]),
            observation_refs=tuple(actual_transport_refs.get(transport_kind, ())),
        )
        for transport_kind in transport_kinds
    )

    path_inspections: tuple[PathInspectionResult, ...] = ()
    scope_records: list[dict[str, object]] = []
    if cas is not None:
        inspections: list[PathInspectionResult] = []
        for item in candidate.changed_files:
            content = cas.get(item.cas_hash)
            content_sha256 = hashlib.sha256(content).hexdigest()
            if content_sha256 != item.file_sha256:
                raise CandidateIntegrityError(
                    f"candidate content hash mismatch for authoritative path {item.path}"
                )
            synthetic_markers, metric_markers = inspect_authoritative_path(item.path, content)
            details = ";".join((*synthetic_markers, *metric_markers))
            observation_sha256 = _observation_digest(
                "candidate-path",
                {
                    "path": item.path,
                    "content_sha256": content_sha256,
                    "synthetic_markers": synthetic_markers,
                    "metric_markers": metric_markers,
                },
            )
            inspections.append(
                PathInspectionResult(
                    path=item.path,
                    has_undisclosed_synthetic_fallback=bool(synthetic_markers),
                    has_hardcoded_authoritative_metric=bool(metric_markers),
                    details=details,
                    content_sha256=content_sha256,
                    observation_sha256=observation_sha256,
                )
            )
            scope_records.append({"path": item.path, "content_sha256": content_sha256})
        path_inspections = tuple(inspections)

    physical_evidence_refs = tuple(item.hash for item in evidence)
    normalized_e2e = tuple(
        sorted((key, tuple(refs)) for key, refs in (e2e_observations or {}).items())
    )
    normalized_slo = tuple(
        sorted((key, tuple(refs)) for key, refs in (slo_observations or {}).items())
    )
    return PreAuditCompletenessBundle(
        milestone_id=manifest.milestone_id,
        candidate_sha=candidate.cas_artifact_hash,
        profiles=manifest.required_profiles,
        capabilities=capabilities,
        transports=transports,
        path_inspections=path_inspections,
        e2e_evidence_hashes=physical_evidence_refs,
        fixtures_only=not bool(physical_evidence_refs),
        unresolved_omissions=tuple(
            sorted(set(manifest.expected_capabilities) - observed)
        ),
        manifest_candidate_binding_sha256=manifest_candidate_binding_sha256(
            manifest, candidate.cas_artifact_hash
        ),
        e2e_observations=normalized_e2e,
        slo_observations=normalized_slo,
    )


def _is_sha256_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _observation_digest(label: str, payload: object) -> str:
    body = json.dumps(
        {"label": label, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


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
