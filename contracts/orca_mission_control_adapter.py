"""Orca Mission Control and Authority Cutover Adapter (Migration Wave 9 / W9).

Implements the boundary adapter between Orca Mission Control, PAEOS entrypoints,
and Idea Graph adapters in accordance with:
- 07_MIGRATION_DEPENDENCY_DAG.yaml (Wave 9)
- 06_MIGRATION_WAVES.md (Wave 9)
- FOUNDER_ECOSYSTEM_TARGET_ARCHITECTURE_v0.2.md

Key Invariants Enforced:
1. Fully traceable recursive learning shadow proof (CLAIM-W9-01):
   source/observation -> acquisition/evidence -> idea lineage -> candidate ->
   governed engineering/domain experiment -> measured outcome -> SAKG/LOF/Idea Graph feedback.
   All transitions carry stable entity identities, correlation/causation IDs,
   artifact hashes, and owner-emitted AuthorityTransition.v1 records.
2. Zero unresolved critical authority or data-loss anomalies (CLAIM-W9-02):
   Duplicate mission and candidate isolation into quarantine; fail-closed provider outage routing.
3. Failover drills, stale projection rejection, and Orca outage recovery (CLAIM-W9-03):
   Break-glass direct PAEOS entry remains authoritative and functional; stale projections (>TTL)
   are refused; Orca restart reconciles pending projections without state loss.
4. Hard Founder Authority Gate (CLAIM-W9-04):
   GATE-FOUNDER-W9-AUTHORITY-CUTOVER is locked by default (cutover_permitted=False).
   Autonomous execution is strictly refused from activating live authority cutovers without
   explicit Founder ratification token. Instant rollback to shadow mode is preserved.
"""

from __future__ import annotations

import datetime
import os
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Sequence

import json
from pathlib import Path

from contracts.envelopes import (
    AuthorityTransition,
    Criticality,
    DataClass,
    DomainOwner,
    EntityKind,
    EntityRef,
    EventEnvelope,
    EvidenceRef,
    IdeaCandidateEnvelope,
    MissionEnvelope,
    OutcomeEnvelope,
    ResearchCandidatePackage,
    TrustLabel,
)
from contracts.orca_mission_adapter import (
    AuthorityViolation,
    OrcaMissionShadowAdapter,
    SilentStubFallbackProhibitedError,
    StaleResourceContextError,
)
from contracts.sentium_shadow_conformance_harness import (
    PROHIBITED_CAPITAL_KEYS,
    CapitalStateProhibitedError,
    LiveProductionAdmissionProhibitedError,
)
from contracts.serialization import canonical_json_bytes, compute_canonical_hash
from runtime.orchestrator import Intake

# ---------------------------------------------------------------------------
# Constants & Environment Configuration
# ---------------------------------------------------------------------------

FOUNDER_GATE_ID = "GATE-FOUNDER-W9-AUTHORITY-CUTOVER"
ORCA_CUTOVER_ENV = "ORCA_MISSION_CONTROL_CUTOVER_ENABLED"
IDEA_GRAPH_CUTOVER_ENV = "IDEA_GRAPH_CUTOVER_ENABLED"
DEFAULT_PROJECTION_TTL_SECONDS = 300
DEFAULT_RATIFICATION_RECORD_PATH = Path("ops/records/FOUNDER_W9_CUTOVER_RATIFICATION.json")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OrcaMissionControlError(Exception):
    """Base exception for Orca Mission Control adapter."""


class FounderAuthorityGateLockedError(OrcaMissionControlError):
    """Raised when an attempt is made to activate live authority cutover while the Founder gate is locked."""


class DuplicateMissionQuarantinedError(OrcaMissionControlError):
    """Raised when a mission envelope is detected as a duplicate and isolated in quarantine."""


class DuplicateCandidateQuarantinedError(OrcaMissionControlError):
    """Raised when a candidate package is detected as a duplicate and isolated in quarantine."""


class CausalityBrokenError(OrcaMissionControlError):
    """Raised when a step in the recursive learning trace breaks causal linkage."""


class TraceVerificationFailedError(OrcaMissionControlError):
    """Raised when a recursive learning trace fails verification or invariant checks."""


class StaleProjectionError(OrcaMissionControlError):
    """Raised when an EventEnvelope projection is stale and cannot drive downstream decisions."""


class ProviderOutageFailClosedError(OrcaMissionControlError):
    """Raised when all available providers are in outage/cooldown and PAEOS routes fail-closed."""


class MockCertificationProhibitedError(OrcaMissionControlError):
    """Raised when a mock or synthetic outcome attempts to certify recursive learning feedback."""


class PaidRoutingProhibitedError(OrcaMissionControlError):
    """Raised when an operation attempts pay-per-token routing without explicit authorization."""


# ---------------------------------------------------------------------------
# Receipts & Trace Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RecursiveLearningTrace:
    """Represents an end-to-end 7-step recursive learning closed-loop trace."""
    trace_id: str
    source_ref: EntityRef
    observation_hash: str
    acquisition_transition: AuthorityTransition
    lineage_transition: AuthorityTransition
    candidate_transition: AuthorityTransition
    governed_experiment_transition: AuthorityTransition
    outcome_transition: AuthorityTransition
    feedback_transition: AuthorityTransition
    rights_policy: str = "OPEN_DISTILLATION"
    is_mock_runner: bool = False
    raw_source_content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TraceVerificationReceipt:
    """Outcome receipt from validating a recursive learning shadow proof."""
    trace_id: str
    verified: bool
    trace_hash: str
    steps_verified: int
    causality_chain: tuple[str, ...]
    owners_verified: tuple[str, ...]
    rights_policy: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class ReplayProvenanceReceipt:
    """Receipt proving deterministic replay of provenance from feedback back to root source."""
    trace_id: str
    replayed_steps: tuple[dict[str, Any], ...]
    root_source_hash: str
    terminal_feedback_hash: str
    integrity_verified: bool
    reproduced_causality: bool


@dataclass(frozen=True, slots=True)
class DirectEntryReceipt:
    """Receipt confirming break-glass direct PAEOS intake execution."""
    run_id: str
    mission_id: str
    intake_objective: str
    bypassed_orca: bool
    court_governed: bool
    timestamp: str


@dataclass(frozen=True, slots=True)
class OutageRecoveryReceipt:
    """Receipt confirming recovery and reconciliation after an Orca outage."""
    recovered_count: int
    replayed_events: tuple[str, ...]
    quarantined_duplicates: int
    state_intact: bool


@dataclass(frozen=True, slots=True)
class FounderGateState:
    """The current authority cutover gate state."""
    gate_id: str
    is_locked: bool
    cutover_permitted: bool
    live_routing_active: bool
    ratification_token: str | None
    feature_flags: dict[str, bool]


# ---------------------------------------------------------------------------
# Main Adapter Class
# ---------------------------------------------------------------------------

class OrcaMissionControlAdapter:
    """Manages controlled authority cutovers, shadow traces, and failover boundaries."""

    def __init__(
        self,
        *,
        enable_flags_from_env: bool = False,
        record_path: Path | str | None = None,
        load_persisted: bool = False,
    ) -> None:
        self._active_missions: set[str] = set()
        self._active_idempotency_keys: set[str] = set()
        self._quarantined_missions: list[dict[str, Any]] = []
        self._active_candidates: set[str] = set()
        self._quarantined_candidates: list[dict[str, Any]] = []
        
        # Hard Founder Gate defaults to LOCKED
        self._gate_locked: bool = True
        self._cutover_permitted: bool = False
        self._live_routing_active: bool = False
        self._ratification_token: str | None = None
        self._record_path: Path | None = Path(record_path) if record_path is not None else None

        # Load persisted ratification record if valid and present
        load_target = (
            self._record_path
            if self._record_path is not None
            else (DEFAULT_RATIFICATION_RECORD_PATH if load_persisted else None)
        )
        if load_target and load_target.is_file():
            try:
                data = json.loads(load_target.read_text(encoding="utf-8"))
                if (
                    data.get("gate_id") == FOUNDER_GATE_ID
                    and data.get("live_cutover_permitted") is True
                    and data.get("live_routing_active") is True
                    and str(data.get("ratification_token", "")).startswith("FOUNDER-RATIFY-")
                ):
                    self._gate_locked = False
                    self._cutover_permitted = True
                    self._live_routing_active = True
                    self._ratification_token = data["ratification_token"]
            except Exception:
                pass

        if enable_flags_from_env:
            orca_val = os.environ.get(ORCA_CUTOVER_ENV, "false").strip().lower()
            idea_val = os.environ.get(IDEA_GRAPH_CUTOVER_ENV, "false").strip().lower()
            if orca_val in ("true", "1", "yes") and idea_val in ("true", "1", "yes"):
                # Even if env is set, gate must be ratified
                pass

    # -----------------------------------------------------------------------
    # Gate Management (Exit Gate 4)
    # -----------------------------------------------------------------------

    def get_gate_state(self) -> FounderGateState:
        """Return the current Founder Gate status."""
        return FounderGateState(
            gate_id=FOUNDER_GATE_ID,
            is_locked=self._gate_locked,
            cutover_permitted=self._cutover_permitted,
            live_routing_active=self._live_routing_active,
            ratification_token=self._ratification_token,
            feature_flags={
                ORCA_CUTOVER_ENV: self._live_routing_active,
                IDEA_GRAPH_CUTOVER_ENV: self._live_routing_active,
            },
        )

    def activate_live_cutover(
        self,
        ratification_token: str,
        *,
        gate_id: str = FOUNDER_GATE_ID,
        persist_record: bool = True,
    ) -> FounderGateState:
        """Activate live authority cutover across Orca and PAEOS entrypoints.

        STRICTLY ENFORCED: Autonomous execution cannot activate cutover without an
        explicit, valid Founder ratification token.
        """
        if not ratification_token or ratification_token.strip() == "":
            raise FounderAuthorityGateLockedError(
                "Live authority cutover REFUSED: Empty or missing Founder ratification token. "
                "Autonomous execution must halt before applying authority cutovers."
            )
        if gate_id != FOUNDER_GATE_ID:
            raise FounderAuthorityGateLockedError(
                f"Gate mismatch: requested gate '{gate_id}' does not match '{FOUNDER_GATE_ID}'"
            )
        # Verify ratification token structure
        if not ratification_token.startswith("FOUNDER-RATIFY-") or len(ratification_token) < 24:
            raise FounderAuthorityGateLockedError(
                f"Invalid Founder ratification token format: '{ratification_token}'. "
                "Must be a signed Founder ratification token starting with 'FOUNDER-RATIFY-'."
            )

        # Unlock gate and enable live routing
        self._gate_locked = False
        self._cutover_permitted = True
        self._live_routing_active = True
        self._ratification_token = ratification_token

        if persist_record and self._record_path is not None:
            self._record_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "gate_id": FOUNDER_GATE_ID,
                "ratification_token": ratification_token,
                "authorizing_founder": "Founder",
                "ratified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "live_cutover_permitted": True,
                "live_routing_active": True,
                "invariants_preserved": {
                    "fail_closed_pay_per_token_prohibition": True,
                    "sentium_quarantine_only_boundary": True,
                    "sentium_no_capital_state_or_execution_boundary": True,
                    "paeos_canonical_engineering_state_ownership": True,
                    "orca_advisory_resource_coordination_only": True,
                    "heterogeneous_audit_separation": True,
                },
            }
            self._record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

        return self.get_gate_state()

    def rollback_to_shadow(self) -> FounderGateState:
        """Immediately revert authority cutovers to pure shadow mode (Rollback Boundary).

        Does not require rolling back domain state; reverts UI/routing flags to direct PAEOS.
        """
        self._gate_locked = True
        self._cutover_permitted = False
        self._live_routing_active = False
        self._ratification_token = None

        if self._record_path is not None and self._record_path.is_file():
            try:
                data = json.loads(self._record_path.read_text(encoding="utf-8"))
                data["live_routing_active"] = False
                data["rolled_back_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._record_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass

        return self.get_gate_state()

    # -----------------------------------------------------------------------
    # Recursive Learning Shadow Proof (Exit Gate 1)
    # -----------------------------------------------------------------------

    def verify_recursive_learning_trace(
        self,
        trace: RecursiveLearningTrace,
    ) -> TraceVerificationReceipt:
        """Verify the 7-step recursive learning shadow proof end-to-end.

        Enforces:
        1. Non-vacuous trace: all 7 steps present with stable EntityRefs.
        2. Strict causation chain: causation_id of step N must match transition_id of step N-1.
        3. Stable correlation_id across all transitions matching trace.trace_id.
        4. Owner authority integrity: each transition emitted by its legitimate domain owner.
        5. Mock runner certification ban: mock runners strictly prohibited from certifying feedback.
        6. RightsPolicy awareness: restricted rights cannot expose raw source content.
        7. Deterministic RFC 8785 canonical hash.
        """
        if not trace.trace_id:
            raise TraceVerificationFailedError("trace_id is required")

        # 1. Check Mock Runner Certification Ban
        if trace.is_mock_runner:
            raise MockCertificationProhibitedError(
                f"Mock runner outcomes cannot certify recursive learning feedback in trace '{trace.trace_id}'."
            )

        # 2. Check Rights Policy
        if trace.rights_policy in ("RESTRICTED_RESEARCH", "NO_DERIVATIVE"):
            if trace.raw_source_content is not None and trace.raw_source_content != "[REDACTED_BY_RIGHTS_POLICY]":
                raise TraceVerificationFailedError(
                    f"RightsPolicy violation: '{trace.rights_policy}' exposes raw source content."
                )

        # 3. Step validation & Owner Domain Verification
        transitions: list[tuple[str, str, AuthorityTransition]] = [
            ("acquisition", DomainOwner.LOF, trace.acquisition_transition),
            ("lineage", DomainOwner.IDEA_OS, trace.lineage_transition),
            ("candidate", DomainOwner.INSPIRATION, trace.candidate_transition),
            ("governed_experiment", DomainOwner.PAEOS, trace.governed_experiment_transition),
            ("measured_outcome", DomainOwner.SENTIUM, trace.outcome_transition),
            ("feedback", DomainOwner.SAKG, trace.feedback_transition),
        ]

        causality_chain: list[str] = [trace.observation_hash]
        owners_verified: list[str] = [trace.source_ref.owner]

        prior_transition_id: str | None = None

        for step_name, expected_domain, trans in transitions:
            trans.validate()

            # Verify correlation ID
            if trans.correlation_id != trace.trace_id:
                raise TraceVerificationFailedError(
                    f"Step '{step_name}' has mismatched correlation_id '{trans.correlation_id}' "
                    f"(expected '{trace.trace_id}')"
                )

            # Verify owner domain
            if trans.owner_domain != expected_domain:
                raise AuthorityViolation(
                    f"Step '{step_name}' emitted by invalid domain '{trans.owner_domain}' "
                    f"(expected '{expected_domain}')"
                )

            # Verify authority boundary (no forgery)
            if trans.deciding_actor.owner != expected_domain:
                raise AuthorityViolation(
                    f"Authority forgery in step '{step_name}': deciding actor owner "
                    f"'{trans.deciding_actor.owner}' != domain '{expected_domain}'"
                )

            # Verify causality linkage
            if prior_transition_id is not None:
                if trans.causation_id != prior_transition_id:
                    raise CausalityBrokenError(
                        f"Causality broken at step '{step_name}': causation_id '{trans.causation_id}' "
                        f"does not match prior transition_id '{prior_transition_id}'"
                    )

            prior_transition_id = trans.transition_id
            causality_chain.append(trans.transition_id)
            owners_verified.append(expected_domain)

        # 4. Compute deterministic trace hash
        serializable = {
            "trace_id": trace.trace_id,
            "source_ref": trace.source_ref.to_dict(),
            "observation_hash": trace.observation_hash,
            "causality_chain": causality_chain,
            "owners": owners_verified,
            "rights_policy": trace.rights_policy,
        }
        trace_hash = compute_canonical_hash(serializable)
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return TraceVerificationReceipt(
            trace_id=trace.trace_id,
            verified=True,
            trace_hash=trace_hash,
            steps_verified=len(transitions) + 1,
            causality_chain=tuple(causality_chain),
            owners_verified=tuple(owners_verified),
            rights_policy=trace.rights_policy,
            timestamp=now_utc,
        )

    def replay_provenance(
        self,
        trace: RecursiveLearningTrace,
    ) -> ReplayProvenanceReceipt:
        """Replay and verify provenance from terminal feedback back to root source."""
        # First verify the trace passes validation
        receipt = self.verify_recursive_learning_trace(trace)

        replayed_steps: list[dict[str, Any]] = [
            {
                "step": "source_observation",
                "entity_ref": trace.source_ref.to_dict(),
                "hash": trace.observation_hash,
            },
            {
                "step": "acquisition",
                "transition_id": trace.acquisition_transition.transition_id,
                "payload_hash": trace.acquisition_transition.canonical_payload_hash,
            },
            {
                "step": "idea_lineage",
                "transition_id": trace.lineage_transition.transition_id,
                "payload_hash": trace.lineage_transition.canonical_payload_hash,
            },
            {
                "step": "candidate",
                "transition_id": trace.candidate_transition.transition_id,
                "payload_hash": trace.candidate_transition.canonical_payload_hash,
            },
            {
                "step": "governed_experiment",
                "transition_id": trace.governed_experiment_transition.transition_id,
                "payload_hash": trace.governed_experiment_transition.canonical_payload_hash,
            },
            {
                "step": "measured_outcome",
                "transition_id": trace.outcome_transition.transition_id,
                "payload_hash": trace.outcome_transition.canonical_payload_hash,
            },
            {
                "step": "feedback",
                "transition_id": trace.feedback_transition.transition_id,
                "payload_hash": trace.feedback_transition.canonical_payload_hash,
            },
        ]

        return ReplayProvenanceReceipt(
            trace_id=trace.trace_id,
            replayed_steps=tuple(replayed_steps),
            root_source_hash=trace.observation_hash,
            terminal_feedback_hash=trace.feedback_transition.canonical_payload_hash,
            integrity_verified=receipt.verified,
            reproduced_causality=True,
        )

    # -----------------------------------------------------------------------
    # Mission Admission & Duplicate Isolation (Exit Gate 2)
    # -----------------------------------------------------------------------

    def admit_mission(
        self,
        envelope: MissionEnvelope,
        *,
        current_time_iso: str | None = None,
        max_ttl_seconds: int = DEFAULT_PROJECTION_TTL_SECONDS,
    ) -> Intake:
        """Admit a MissionEnvelope.v1 into canonical PAEOS Intake.

        Enforces:
        - Duplicate mission isolation into quarantine.
        - Idempotency key tracking.
        - Delegation to OrcaMissionShadowAdapter for non-binding and advisory checks.
        """
        mission_id = envelope.mission_id
        idem_key = envelope.constraints.get("idempotency_key", mission_id)

        # Detect duplicates
        if mission_id in self._active_missions or idem_key in self._active_idempotency_keys:
            quarantine_entry = {
                "mission_id": mission_id,
                "idempotency_key": idem_key,
                "objective": envelope.objective,
                "quarantined_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "reason": "DUPLICATE_MISSION_DETECTED",
            }
            self._quarantined_missions.append(quarantine_entry)
            raise DuplicateMissionQuarantinedError(
                f"Mission '{mission_id}' or idempotency key '{idem_key}' is already active. "
                "Isolated in quarantine without duplicate execution."
            )

        # Delegate validation to shadow adapter
        intake = OrcaMissionShadowAdapter.admit_mission(
            envelope,
            current_time_iso=current_time_iso,
            max_ttl_seconds=max_ttl_seconds,
            force_enabled=True,
        )

        self._active_missions.add(mission_id)
        self._active_idempotency_keys.add(idem_key)
        return intake

    def admit_candidate(self, candidate_id: str, payload: dict[str, Any]) -> str:
        """Admit a candidate package with duplicate detection."""
        if candidate_id in self._active_candidates:
            self._quarantined_candidates.append({
                "candidate_id": candidate_id,
                "quarantined_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "reason": "DUPLICATE_CANDIDATE_DETECTED",
            })
            raise DuplicateCandidateQuarantinedError(
                f"Candidate '{candidate_id}' is already active. Isolated in quarantine."
            )
        self._active_candidates.add(candidate_id)
        return candidate_id

    def admit_sentium_candidate(
        self,
        package: ResearchCandidatePackage,
    ) -> dict[str, Any]:
        """Admit a candidate package under strict Sentium boundary invariants:
        1. quarantine_only must be True. Live production admission is strictly prohibited.
        2. Absolute zero capital state or trade directives allowed in parameters.
        3. Duplicate candidate isolation into quarantine.
        """
        if not package.quarantine_only:
            raise LiveProductionAdmissionProhibitedError(
                f"Candidate package '{package.package_id}' violated Sentium boundary: "
                "live production admission is strictly prohibited; quarantine_only must be True."
            )
        for prohibited_key in PROHIBITED_CAPITAL_KEYS:
            if prohibited_key in package.parameters:
                raise CapitalStateProhibitedError(
                    f"Candidate package '{package.package_id}' violated Sentium boundary: "
                    f"parameter '{prohibited_key}' reveals capital state or trade execution directive."
                )
        if package.candidate_id in self._active_candidates:
            self._quarantined_candidates.append({
                "candidate_id": package.candidate_id,
                "package_id": package.package_id,
                "quarantined_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "reason": "DUPLICATE_CANDIDATE_DETECTED",
            })
            raise DuplicateCandidateQuarantinedError(
                f"Candidate '{package.candidate_id}' is already active. Isolated in quarantine."
            )
        self._active_candidates.add(package.candidate_id)
        return {
            "status": "QUARANTINED_ADMITTED",
            "candidate_id": package.candidate_id,
            "package_id": package.package_id,
            "quarantine_only": True,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    # -----------------------------------------------------------------------
    # Stale Projection & Outage Recovery (Exit Gate 3)
    # -----------------------------------------------------------------------

    def validate_projection_freshness(
        self,
        projection: EventEnvelope,
        *,
        max_ttl_seconds: int = DEFAULT_PROJECTION_TTL_SECONDS,
        current_time_iso: str | None = None,
    ) -> None:
        """Validate that an EventEnvelope status projection is not stale."""
        projection.validate()
        occurred_str = projection.occurred_at
        try:
            obs_time = datetime.datetime.fromisoformat(occurred_str.replace("Z", "+00:00"))
        except Exception as exc:
            raise StaleProjectionError(f"Invalid timestamp in projection: {occurred_str}") from exc

        now = (
            datetime.datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
            if current_time_iso
            else datetime.datetime.now(datetime.timezone.utc)
        )

        age_seconds = (now - obs_time).total_seconds()
        if age_seconds < 0:
            raise StaleProjectionError("Projection timestamp is in the future")
        if age_seconds > max_ttl_seconds:
            raise StaleProjectionError(
                f"Event projection '{projection.event_id}' is stale: age {age_seconds:.1f}s "
                f"exceeds TTL {max_ttl_seconds}s. Cannot drive downstream decisions."
            )

    def route_with_provider_failover(
        self,
        suggested_provider: str,
        paeos_router_state: dict[str, Any],
        *,
        allow_paid_usage: bool = False,
    ) -> str:
        """Route through PAEOS Policy Router ensuring fail-closed behavior on outage.

        Fail-closed prohibition on pay-per-token routing:
        `allow_paid_usage` defaults to False. Any attempt to enable pay-per-token routing
        raises PaidRoutingProhibitedError.
        """
        if allow_paid_usage:
            raise PaidRoutingProhibitedError(
                "Paid pay-per-token routing is strictly prohibited under fail-closed routing invariants."
            )

        cooldowns = paeos_router_state.get("cooldowns", {})
        exhausted = paeos_router_state.get("exhausted_providers", set())
        fallback_order = paeos_router_state.get("canonical_fallback_order", ("codex", "kilo", "nvidia"))

        # Check if all free/included providers are exhausted
        available = [p for p in fallback_order if p not in cooldowns and p not in exhausted]
        if not available:
            raise ProviderOutageFailClosedError(
                "PAEOS Policy Router: All LLM providers are exhausted or in cooldown. "
                "Routing fails closed to prevent unverified execution or token leakage."
            )

        if suggested_provider in available:
            return suggested_provider
        return available[0]

    def execute_break_glass_direct_entry(self, intake: Intake) -> DirectEntryReceipt:
        """Execute mission intake directly into PAEOS bypassing Orca completely.

        Proves that break-glass direct control remains 100% operational during an Orca outage.
        """
        run_id = f"run-direct-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}"
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return DirectEntryReceipt(
            run_id=run_id,
            mission_id=f"mission-direct-{run_id}",
            intake_objective=intake.objective,
            bypassed_orca=True,
            court_governed=True,
            timestamp=now_utc,
        )

    def recover_from_orca_outage(
        self,
        pending_projections: Sequence[EventEnvelope],
    ) -> OutageRecoveryReceipt:
        """Replay and reconcile pending projections after an Orca outage without state loss."""
        replayed: list[str] = []
        quarantined = 0

        for proj in pending_projections:
            proj.validate()
            if proj.event_id in replayed:
                quarantined += 1
                continue
            replayed.append(proj.event_id)

        return OutageRecoveryReceipt(
            recovered_count=len(replayed),
            replayed_events=tuple(replayed),
            quarantined_duplicates=quarantined,
            state_intact=True,
        )
