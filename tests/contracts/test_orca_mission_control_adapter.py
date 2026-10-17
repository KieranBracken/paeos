"""Tests for Orca Mission Control and Controlled Authority Cutover Adapter (Migration Wave 9 / W9).

Verifies exit gates from 07_MIGRATION_DEPENDENCY_DAG.yaml and claims in ops/backlogs/intake-migration-w9.json:
1. CLAIM-W9-01: test_recursive_learning_trace
2. CLAIM-W9-02: test_zero_critical_anomalies
3. CLAIM-W9-03: test_failover_recovery
4. CLAIM-W9-04: test_founder_gate_blocks_cutover
"""

from __future__ import annotations

import datetime
import hashlib
import pytest

from contracts.envelopes import (
    AuthorityTransition,
    Criticality,
    DataClass,
    DomainOwner,
    EntityKind,
    EntityRef,
    EventEnvelope,
    MissionEnvelope,
    ResearchCandidatePackage,
)
from contracts.orca_mission_adapter import AuthorityViolation
from contracts.orca_mission_control_adapter import (
    CausalityBrokenError,
    DirectEntryReceipt,
    DuplicateCandidateQuarantinedError,
    DuplicateMissionQuarantinedError,
    FOUNDER_GATE_ID,
    FounderAuthorityGateLockedError,
    MockCertificationProhibitedError,
    OrcaMissionControlAdapter,
    OutageRecoveryReceipt,
    PaidRoutingProhibitedError,
    ProviderOutageFailClosedError,
    RecursiveLearningTrace,
    StaleProjectionError,
    TraceVerificationFailedError,
)
from contracts.sentium_shadow_conformance_harness import (
    CapitalStateProhibitedError,
    LiveProductionAdmissionProhibitedError,
)
from contracts.serialization import compute_canonical_hash
from runtime.orchestrator import Intake


def _make_dummy_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _build_valid_trace(trace_id: str = "trace-w9-closed-loop-01") -> RecursiveLearningTrace:
    obs_hash = _make_dummy_hash(f"{trace_id}:source_obs")
    now_iso = "2026-09-06T00:00:00Z"

    source_ref = EntityRef(kind="source.document", owner=DomainOwner.LOF, local_id="doc-entropy-arxiv-2026")
    
    # Step 1: Acquisition (emitted by LOF)
    acq_trans = AuthorityTransition(
        transition_id="trans-01-acq",
        subject=source_ref,
        owner_domain=DomainOwner.LOF,
        from_class="RAW_TEXT",
        to_class="VERIFIED_CITATION",
        governing_rule="RULE_LOF_ACQUISITION_VERIFICATION",
        deciding_actor=EntityRef(kind="service", owner=DomainOwner.LOF, local_id="acquisition-engine"),
        evidence_refs=(_make_dummy_hash("acq_ev"),),
        correlation_id=trace_id,
        decision_timestamp=now_iso,
        canonical_payload_hash=_make_dummy_hash("payload-acq"),
        causation_id=None,
    )

    # Step 2: Idea Lineage (emitted by IDEA_OS)
    lineage_trans = AuthorityTransition(
        transition_id="trans-02-lineage",
        subject=EntityRef(kind=EntityKind.IDEA, owner=DomainOwner.IDEA_OS, local_id="idea-entropy-distill"),
        owner_domain=DomainOwner.IDEA_OS,
        from_class="RAW_CONCEPT",
        to_class="LINEAGE_ANCHORED_IDEA",
        governing_rule="RULE_IDEA_OS_LINEAGE_ANCHOR",
        deciding_actor=EntityRef(kind="service", owner=DomainOwner.IDEA_OS, local_id="lifecycle-manager"),
        evidence_refs=(_make_dummy_hash("lineage_ev"),),
        correlation_id=trace_id,
        decision_timestamp=now_iso,
        canonical_payload_hash=_make_dummy_hash("payload-lineage"),
        causation_id="trans-01-acq",
    )

    # Step 3: Candidate (emitted by INSPIRATION)
    candidate_trans = AuthorityTransition(
        transition_id="trans-03-candidate",
        subject=EntityRef(kind="candidate.package", owner=DomainOwner.INSPIRATION, local_id="cand-pkg-entropy-42"),
        owner_domain=DomainOwner.INSPIRATION,
        from_class="UNVALIDATED_CANDIDATE",
        to_class="PROVENANCED_CANDIDATE",
        governing_rule="RULE_INSPIRATION_TYPED_CANDIDATE",
        deciding_actor=EntityRef(kind="service", owner=DomainOwner.INSPIRATION, local_id="graph-adapter"),
        evidence_refs=(_make_dummy_hash("candidate_ev"),),
        correlation_id=trace_id,
        decision_timestamp=now_iso,
        canonical_payload_hash=_make_dummy_hash("payload-candidate"),
        causation_id="trans-02-lineage",
    )

    # Step 4: Governed Experiment (emitted by PAEOS)
    governed_exp_trans = AuthorityTransition(
        transition_id="trans-04-experiment",
        subject=EntityRef(kind=EntityKind.PAEOS_RUN, owner=DomainOwner.PAEOS, local_id="run-exp-governed-001"),
        owner_domain=DomainOwner.PAEOS,
        from_class="ADVISORY_PROPOSAL",
        to_class="GOVERNED_EXECUTION",
        governing_rule="RULE_PAEOS_ROUTER_COURT_DISPOSITION",
        deciding_actor=EntityRef(kind="service", owner=DomainOwner.PAEOS, local_id="orchestrator"),
        evidence_refs=(_make_dummy_hash("court_seal_ev"),),
        correlation_id=trace_id,
        decision_timestamp=now_iso,
        canonical_payload_hash=_make_dummy_hash("payload-governed-exp"),
        causation_id="trans-03-candidate",
    )

    # Step 5: Measured Outcome (emitted by SENTIUM)
    outcome_trans = AuthorityTransition(
        transition_id="trans-05-outcome",
        subject=EntityRef(kind="experiment.outcome", owner=DomainOwner.SENTIUM, local_id="outcome-measured-alpha"),
        owner_domain=DomainOwner.SENTIUM,
        from_class="RAW_METRIC",
        to_class="SIGNED_OUTCOME_VECTOR",
        governing_rule="RULE_SENTIUM_OUTCOME_REDACTION",
        deciding_actor=EntityRef(kind="service", owner=DomainOwner.SENTIUM, local_id="shadow-verifier"),
        evidence_refs=(_make_dummy_hash("outcome_ev"),),
        correlation_id=trace_id,
        decision_timestamp=now_iso,
        canonical_payload_hash=_make_dummy_hash("payload-outcome"),
        causation_id="trans-04-experiment",
    )

    # Step 6: Feedback & Distillation (emitted by SAKG)
    feedback_trans = AuthorityTransition(
        transition_id="trans-06-feedback",
        subject=EntityRef(kind=EntityKind.SAKG_NODE, owner=DomainOwner.SAKG, local_id="node-distill-update-99"),
        owner_domain=DomainOwner.SAKG,
        from_class="MEASURED_EVIDENCE",
        to_class="DISTILLED_KNOWLEDGE",
        governing_rule="RULE_SAKG_DISTILLATION_UPDATE",
        deciding_actor=EntityRef(kind="service", owner=DomainOwner.SAKG, local_id="knowledge-store"),
        evidence_refs=(_make_dummy_hash("feedback_ev"),),
        correlation_id=trace_id,
        decision_timestamp=now_iso,
        canonical_payload_hash=_make_dummy_hash("payload-feedback"),
        causation_id="trans-05-outcome",
    )

    return RecursiveLearningTrace(
        trace_id=trace_id,
        source_ref=source_ref,
        observation_hash=obs_hash,
        acquisition_transition=acq_trans,
        lineage_transition=lineage_trans,
        candidate_transition=candidate_trans,
        governed_experiment_transition=governed_exp_trans,
        outcome_transition=outcome_trans,
        feedback_transition=feedback_trans,
        rights_policy="OPEN_DISTILLATION",
        is_mock_runner=False,
    )


# ---------------------------------------------------------------------------
# Claim 1: CLAIM-W9-01-RECURSIVE-LEARNING-SHADOW-TRACE
# ---------------------------------------------------------------------------

def test_recursive_learning_trace():
    """Verify fully traceable recursive learning shadow proof and non-vacuous discrimination."""
    adapter = OrcaMissionControlAdapter()
    trace = _build_valid_trace()

    # 1. Positive: valid trace verifies cleanly
    receipt = adapter.verify_recursive_learning_trace(trace)
    assert receipt.verified is True
    assert receipt.trace_id == trace.trace_id
    assert receipt.steps_verified == 7
    assert len(receipt.causality_chain) == 7
    assert len(receipt.trace_hash) == 64

    # 2. Replay provenance verifies deterministically
    replay = adapter.replay_provenance(trace)
    assert replay.integrity_verified is True
    assert replay.reproduced_causality is True
    assert len(replay.replayed_steps) == 7
    assert replay.root_source_hash == trace.observation_hash
    assert replay.terminal_feedback_hash == trace.feedback_transition.canonical_payload_hash

    # 3. Discrimination: Broken causality link
    broken_step = AuthorityTransition(
        transition_id="trans-03-candidate",
        subject=trace.candidate_transition.subject,
        owner_domain=DomainOwner.INSPIRATION,
        from_class=trace.candidate_transition.from_class,
        to_class=trace.candidate_transition.to_class,
        governing_rule=trace.candidate_transition.governing_rule,
        deciding_actor=trace.candidate_transition.deciding_actor,
        evidence_refs=trace.candidate_transition.evidence_refs,
        correlation_id=trace.trace_id,
        decision_timestamp=trace.candidate_transition.decision_timestamp,
        canonical_payload_hash=trace.candidate_transition.canonical_payload_hash,
        causation_id="trans-wrong-causation-id",  # Broken link!
    )
    broken_trace = RecursiveLearningTrace(
        trace_id=trace.trace_id,
        source_ref=trace.source_ref,
        observation_hash=trace.observation_hash,
        acquisition_transition=trace.acquisition_transition,
        lineage_transition=trace.lineage_transition,
        candidate_transition=broken_step,
        governed_experiment_transition=trace.governed_experiment_transition,
        outcome_transition=trace.outcome_transition,
        feedback_transition=trace.feedback_transition,
    )
    with pytest.raises(CausalityBrokenError, match="Causality broken at step 'candidate'"):
        adapter.verify_recursive_learning_trace(broken_trace)

    # 4. Discrimination: Mock runner certification ban
    mock_trace = RecursiveLearningTrace(
        trace_id=trace.trace_id,
        source_ref=trace.source_ref,
        observation_hash=trace.observation_hash,
        acquisition_transition=trace.acquisition_transition,
        lineage_transition=trace.lineage_transition,
        candidate_transition=trace.candidate_transition,
        governed_experiment_transition=trace.governed_experiment_transition,
        outcome_transition=trace.outcome_transition,
        feedback_transition=trace.feedback_transition,
        is_mock_runner=True,  # Mock runner cannot certify!
    )
    with pytest.raises(MockCertificationProhibitedError, match="Mock runner outcomes cannot certify"):
        adapter.verify_recursive_learning_trace(mock_trace)

    # 5. Discrimination: Authority forgery (wrong deciding actor domain)
    forged_step = AuthorityTransition(
        transition_id="trans-04-experiment",
        subject=trace.governed_experiment_transition.subject,
        owner_domain=DomainOwner.PAEOS,
        from_class="ADVISORY_PROPOSAL",
        to_class="GOVERNED_EXECUTION",
        governing_rule="RULE_FORGED_ORCA_RUN",
        deciding_actor=EntityRef(kind="service", owner=DomainOwner.ORCA, local_id="orca-intruder"),  # Forgery!
        evidence_refs=trace.governed_experiment_transition.evidence_refs,
        correlation_id=trace.trace_id,
        decision_timestamp=trace.governed_experiment_transition.decision_timestamp,
        canonical_payload_hash=trace.governed_experiment_transition.canonical_payload_hash,
        causation_id="trans-03-candidate",
    )
    forged_trace = RecursiveLearningTrace(
        trace_id=trace.trace_id,
        source_ref=trace.source_ref,
        observation_hash=trace.observation_hash,
        acquisition_transition=trace.acquisition_transition,
        lineage_transition=trace.lineage_transition,
        candidate_transition=trace.candidate_transition,
        governed_experiment_transition=forged_step,
        outcome_transition=trace.outcome_transition,
        feedback_transition=trace.feedback_transition,
    )
    with pytest.raises(ValueError, match="Authority forgery detected"):
        adapter.verify_recursive_learning_trace(forged_trace)


# ---------------------------------------------------------------------------
# Claim 2: CLAIM-W9-02-ZERO-CRITICAL-DATA-LOSS-ANOMALIES
# ---------------------------------------------------------------------------

def test_zero_critical_anomalies():
    """Verify duplicate mission/candidate quarantine isolation and fail-closed provider outage routing."""
    adapter = OrcaMissionControlAdapter()

    mission_env = MissionEnvelope(
        mission_id="mis-unique-100",
        objective="Governed engineering task",
        requested_outcome="Clean artifacts",
        repository_scope={"primary": "paeos", "paths": ["contracts/adapters.py"]},
        constraints={"idempotency_key": "idem-unique-100"},
        data_class="INTERNAL",
        criticality="ROUTINE",
        budget_ceiling={"max_cost_usd": 0.0},
        advisory_resource_context={
            "is_advisory": True,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "suggested_provider": "codex",
        },
        required_worker_capabilities=("python",),
        approval_policy="AUTO",
    )

    # 1. First admission succeeds
    intake = adapter.admit_mission(mission_env)
    assert intake.objective == "Governed engineering task"

    # 2. Duplicate mission submission is isolated in quarantine
    with pytest.raises(DuplicateMissionQuarantinedError, match="is already active. Isolated in quarantine"):
        adapter.admit_mission(mission_env)

    assert len(adapter._quarantined_missions) == 1
    assert adapter._quarantined_missions[0]["mission_id"] == "mis-unique-100"

    # 3. Duplicate candidate submission is isolated in quarantine
    assert adapter.admit_candidate("cand-unique-200", {"param": 1}) == "cand-unique-200"
    with pytest.raises(DuplicateCandidateQuarantinedError, match="is already active. Isolated in quarantine"):
        adapter.admit_candidate("cand-unique-200", {"param": 1})
    assert len(adapter._quarantined_candidates) == 1

    # 4. Provider outage: fail-closed behavior
    # All providers exhausted or in cooldown
    outage_router_state = {
        "cooldowns": {"codex": 300, "kilo": 300, "nvidia": 300},
        "exhausted_providers": {"codex", "kilo", "nvidia"},
        "canonical_fallback_order": ("codex", "kilo", "nvidia"),
    }
    with pytest.raises(ProviderOutageFailClosedError, match="All LLM providers are exhausted or in cooldown"):
        adapter.route_with_provider_failover("codex", outage_router_state)


# ---------------------------------------------------------------------------
# Claim 3: CLAIM-W9-03-FAILOVER-AND-STALE-PROJECTION-RECOVERY
# ---------------------------------------------------------------------------

def test_failover_recovery():
    """Verify break-glass direct PAEOS entry, stale projection rejection, and Orca outage recovery."""
    adapter = OrcaMissionControlAdapter()

    # 1. Break-glass direct entry works when Orca is unreachable
    direct_intake = Intake(
        objective="Break-glass hotfix while Orca is down",
        changed_paths=("runtime/orchestrator.py",),
        plan_write_scopes=("runtime/orchestrator.py",),
        builder_evidence=(),
        goal_signature="direct:paeos:hotfix",
        verifiable=True,
        reversible=True,
    )
    direct_receipt = adapter.execute_break_glass_direct_entry(direct_intake)
    assert direct_receipt.bypassed_orca is True
    assert direct_receipt.court_governed is True
    assert "Break-glass" in direct_receipt.intake_objective

    # 2. Stale projection rejection
    stale_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=600)).isoformat()
    stale_payload = {"status": "complete"}
    stale_projection = EventEnvelope(
        event_id="evt-stale-001",
        event_type="paeos.mission.completed",
        schema_version="1.0",
        occurred_at=stale_time,
        producer=EntityRef(kind="runtime", owner=DomainOwner.PAEOS, local_id="orchestrator"),
        subject_refs=(EntityRef(kind="run", owner=DomainOwner.PAEOS, local_id="run-001"),),
        correlation_id="mis-001",
        authority_domain="paeos",
        authority_class="ADVISORY_PROJECTION",
        artifact_refs=(),
        evidence_refs=(),
        payload_hash=compute_canonical_hash(stale_payload),
        idempotency_key="idem-001",
        payload=stale_payload,
    )
    with pytest.raises(StaleProjectionError, match="is stale: age .* exceeds TTL 300s"):
        adapter.validate_projection_freshness(stale_projection, max_ttl_seconds=300)

    # 3. Fresh projection passes
    fresh_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fresh_payload = {"status": "complete"}
    fresh_projection = EventEnvelope(
        event_id="evt-fresh-002",
        event_type="paeos.mission.completed",
        schema_version="1.0",
        occurred_at=fresh_time,
        producer=EntityRef(kind="runtime", owner=DomainOwner.PAEOS, local_id="orchestrator"),
        subject_refs=(EntityRef(kind="run", owner=DomainOwner.PAEOS, local_id="run-002"),),
        correlation_id="mis-002",
        authority_domain="paeos",
        authority_class="ADVISORY_PROJECTION",
        artifact_refs=(),
        evidence_refs=(),
        payload_hash=compute_canonical_hash(fresh_payload),
        idempotency_key="idem-002",
        payload=fresh_payload,
    )
    adapter.validate_projection_freshness(fresh_projection, max_ttl_seconds=300)

    # 4. Outage recovery reconciles pending events and deduplicates
    events = [fresh_projection, fresh_projection]  # duplicate in batch
    recovery_receipt = adapter.recover_from_orca_outage(events)
    assert recovery_receipt.recovered_count == 1
    assert recovery_receipt.quarantined_duplicates == 1
    assert recovery_receipt.state_intact is True


# ---------------------------------------------------------------------------
# Claim 4: CLAIM-W9-04-FOUNDER-GATE-ENFORCEMENT
# ---------------------------------------------------------------------------

def test_founder_gate_blocks_cutover():
    """Verify that authority cutover is strictly locked and cannot be activated without Founder ratification."""
    adapter = OrcaMissionControlAdapter()

    # 1. Initial state: Gate is locked
    gate_state = adapter.get_gate_state()
    assert gate_state.is_locked is True
    assert gate_state.cutover_permitted is False
    assert gate_state.live_routing_active is False
    assert gate_state.gate_id == FOUNDER_GATE_ID

    # 2. Activating without token fails closed
    with pytest.raises(FounderAuthorityGateLockedError, match="Empty or missing Founder ratification token"):
        adapter.activate_live_cutover("")

    # 3. Activating with malformed token fails closed
    with pytest.raises(FounderAuthorityGateLockedError, match="Invalid Founder ratification token format"):
        adapter.activate_live_cutover("bogus-token")

    # 4. Activating with mismatched gate ID fails closed
    with pytest.raises(FounderAuthorityGateLockedError, match="Gate mismatch"):
        adapter.activate_live_cutover(
            "FOUNDER-RATIFY-W9-AUTHORITY-CUTOVER-TOKEN-9999",
            gate_id="GATE-WRONG-ID",
        )

    # 5. Activating with valid Founder ratification token unlocks the gate
    valid_token = "FOUNDER-RATIFY-W9-AUTHORITY-CUTOVER-20260906-ALPHA"
    unlocked_state = adapter.activate_live_cutover(valid_token)
    assert unlocked_state.is_locked is False
    assert unlocked_state.cutover_permitted is True
    assert unlocked_state.live_routing_active is True
    assert unlocked_state.ratification_token == valid_token

    # 6. Instant rollback boundary drill: Reverting to shadow mode relocks the gate
    rolled_back_state = adapter.rollback_to_shadow()
    assert rolled_back_state.is_locked is True
    assert rolled_back_state.cutover_permitted is False
    assert rolled_back_state.live_routing_active is False
    assert rolled_back_state.ratification_token is None


# ---------------------------------------------------------------------------
# Claim 5: CLAIM-W9-06-PAID-ROUTING-PROHIBITED
# ---------------------------------------------------------------------------

def test_paid_routing_fail_closed_prohibition():
    """Verify that pay-per-token paid routing is strictly prohibited under fail-closed invariants."""
    adapter = OrcaMissionControlAdapter()
    paeos_router_state = {
        "cooldowns": {},
        "exhausted_providers": set(),
        "canonical_fallback_order": ("codex", "kilo", "nvidia"),
    }

    # Attempting paid routing raises PaidRoutingProhibitedError fail-closed
    with pytest.raises(PaidRoutingProhibitedError, match="Paid pay-per-token routing is strictly prohibited"):
        adapter.route_with_provider_failover("codex", paeos_router_state, allow_paid_usage=True)

    # Standard free/included routing works as expected
    provider = adapter.route_with_provider_failover("codex", paeos_router_state, allow_paid_usage=False)
    assert provider == "codex"


# ---------------------------------------------------------------------------
# Claim 6: CLAIM-W9-07-SENTIUM-QUARANTINE-AND-NO-CAPITAL-PRESERVED
# ---------------------------------------------------------------------------

def test_sentium_quarantine_and_no_capital_boundary_preserved():
    """Verify that candidate admission preserves Sentium quarantine-only and zero-capital state."""
    adapter = OrcaMissionControlAdapter()

    valid_pkg = ResearchCandidatePackage(
        package_id="pkg-sentium-quarantine-001",
        candidate_id="cand-sentium-001",
        author="LOF_RESEARCH",
        submission_timestamp="2026-09-06T00:00:00Z",
        strategy_class="STATISTICAL_ARBITRAGE_RESEARCH",
        parameters={"alpha_hypothesis": "mean_reversion_entropy", "sample_size": 1000},
        evidence_hashes=(_make_dummy_hash("ev1"),),
        signature=_make_dummy_hash("sig1"),
        environment="simulation",
        network_id="sim-harness",
        quarantine_only=True,
    )

    # 1. Valid quarantined candidate admits cleanly
    receipt = adapter.admit_sentium_candidate(valid_pkg)
    assert receipt["status"] == "QUARANTINED_ADMITTED"
    assert receipt["quarantine_only"] is True
    assert receipt["candidate_id"] == "cand-sentium-001"

    # 2. Duplicate candidate is isolated in quarantine
    with pytest.raises(DuplicateCandidateQuarantinedError, match="is already active. Isolated in quarantine"):
        adapter.admit_sentium_candidate(valid_pkg)

    # 3. Violation: Attempting live production admission (quarantine_only=False) fails closed
    live_pkg = ResearchCandidatePackage(
        package_id="pkg-sentium-live-002",
        candidate_id="cand-sentium-002",
        author="LOF_RESEARCH",
        submission_timestamp="2026-09-06T00:00:00Z",
        strategy_class="STATISTICAL_ARBITRAGE_RESEARCH",
        parameters={"alpha_hypothesis": "mean_reversion_entropy"},
        evidence_hashes=(_make_dummy_hash("ev2"),),
        signature=_make_dummy_hash("sig2"),
        environment="simulation",
        network_id="sim-harness",
        quarantine_only=False,  # Forbidden!
    )
    with pytest.raises(LiveProductionAdmissionProhibitedError, match="live production admission is strictly prohibited"):
        adapter.admit_sentium_candidate(live_pkg)

    # 4. Violation: Parameter contains capital state or order execution directive fails closed
    capital_pkg = ResearchCandidatePackage(
        package_id="pkg-sentium-capital-003",
        candidate_id="cand-sentium-003",
        author="LOF_RESEARCH",
        submission_timestamp="2026-09-06T00:00:00Z",
        strategy_class="STATISTICAL_ARBITRAGE_RESEARCH",
        parameters={"account_balance": 1000000.0, "position_size": 50},  # Forbidden!
        evidence_hashes=(_make_dummy_hash("ev3"),),
        signature=_make_dummy_hash("sig3"),
        environment="simulation",
        network_id="sim-harness",
        quarantine_only=True,
    )
    with pytest.raises(CapitalStateProhibitedError, match="reveals capital state or trade execution directive"):
        adapter.admit_sentium_candidate(capital_pkg)


# ---------------------------------------------------------------------------
# Claim 7: CLAIM-W9-08-FOUNDER-RATIFIED-CUTOVER-ACTIVE
# ---------------------------------------------------------------------------

def test_live_cutover_activation_and_persistence(tmp_path):
    """Verify that Founder ratification token unlocks live routing and persists state."""
    rec_file = tmp_path / "test_ratification.json"
    adapter = OrcaMissionControlAdapter(record_path=rec_file)

    token = "FOUNDER-RATIFY-W9-AUTHORITY-CUTOVER-20260906T020813"
    state = adapter.activate_live_cutover(token, persist_record=True)
    assert state.is_locked is False
    assert state.cutover_permitted is True
    assert state.live_routing_active is True
    assert state.ratification_token == token

    # Check persistence: fresh adapter instance with same record_path loads ratified state
    fresh_adapter = OrcaMissionControlAdapter(record_path=rec_file)
    fresh_state = fresh_adapter.get_gate_state()
    assert fresh_state.is_locked is False
    assert fresh_state.cutover_permitted is True
    assert fresh_state.live_routing_active is True
    assert fresh_state.ratification_token == token
