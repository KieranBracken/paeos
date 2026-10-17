"""Test Suite for Sentium Shadow Conformance Harness (Migration Wave 8 / W8).

Validates all required Wave 8 exit gates:
1. signed_package_conformance_matrix (CLAIM-W8-01)
2. forbidden_action_and_authority_language_rejection (CLAIM-W8-02)
3. quarantine_only_and_zero_production_admission (CLAIM-W8-03)
4. no_capital_state_and_redacted_signed_outcomes (CLAIM-W8-04)
5. durable_replay_and_audit_design (CLAIM-W8-05)
6. rollback_boundary_verification (CLAIM-W8-06)
"""

from __future__ import annotations

import datetime
from dataclasses import replace
from pathlib import Path
import pytest

from contracts.adapters import LofSentiumContextAdapter
from contracts.envelopes import (
    ArtifactRef,
    EntityRef,
    EvidenceRef,
    ExecutionStage,
    DecisionStatus,
    IdeaCandidateEnvelope,
    OutcomeEnvelope,
    RedactionLevel,
    ResearchCandidatePackage,
    TrustLabel,
)
from contracts.sentium_shadow_conformance_harness import (
    CapitalStateProhibitedError,
    ForbiddenActionOrLanguageError,
    HarnessDisabledError,
    LiveProductionAdmissionProhibitedError,
    PackageValidationReceipt,
    ReplayDetectedError,
    SentiumShadowConformanceHarness,
    ShadowOutcomeReceipt,
    SignatureVerificationFailedError,
    UnauthorizedContextError,
)


@pytest.fixture
def harness(tmp_path: Path) -> SentiumShadowConformanceHarness:
    log_file = tmp_path / "shadow_audit.jsonl"
    return SentiumShadowConformanceHarness(storage_path=log_file)


@pytest.fixture
def sample_candidate() -> IdeaCandidateEnvelope:
    artifact = ArtifactRef(
        algorithm="sha256",
        digest="a" * 64,
        media_type="application/json",
        byte_length=1024,
        owner="lof",
        locator="cas://sha256/" + "a" * 64,
    )
    evidence = EvidenceRef(
        artifact=artifact,
        claim="CLAIM-ALPHA-MICROSTRUCTURE",
        producer=EntityRef(kind="experiment", owner="lof", local_id="exp-42"),
        observed_at="2026-09-06T00:00:00Z",
        derivation="backtest_replay",
        reverification_recipe="run_replay",
        trust_label=TrustLabel.PROBATIVE.value,
    )
    return IdeaCandidateEnvelope(
        candidate_id="cand-sentium-w8-001",
        idea_lineage_refs=(EntityRef(kind="idea", owner="idea_os", local_id="idea-101"),),
        summary="Empirical microstructure alpha from order book queue imbalance",
        claims=("Information ratio > 1.5 in replay simulation",),
        mechanisms=("Multi-level queue depth imbalance filter",),
        assumptions=("Simulated latency within 5ms",),
        novelty_assessment={"novelty_score": 0.88},
        credibility_assessment={"credibility_score": 0.94},
        evidence_refs=(evidence,),
        failure_modes=("Adverse selection in extreme regime shifts",),
        rights_labels=("PROPRIETARY_RESEARCH",),
        destination_domain="sentium",
        candidate_only=True,
    )


# ---------------------------------------------------------------------------
# CLAIM-W8-01: Signed Package Conformance Matrix (Valid, Tampered, Key, Context, Replay)
# ---------------------------------------------------------------------------

def test_vectors_and_tamper(harness: SentiumShadowConformanceHarness, sample_candidate: IdeaCandidateEnvelope):
    """Exit Gate 1: Signed package conformance matrix validates legitimate packages and rejects anomalies."""
    secret = b"my-special-sentium-secret-32-bytes!"
    
    # 1. Valid generation and validation
    pkg = harness.generate_candidate_package(
        candidate=sample_candidate,
        package_id="pkg-w8-001",
        author="idea_graph_harness",
        secret_key=secret,
        environment="simulation",
        network_id="sim-harness",
    )
    assert pkg.quarantine_only is True
    receipt = harness.validate_candidate_package(pkg, secret_key=secret)
    assert receipt.status == "QUARANTINED_CONFORMANT"
    assert receipt.signature_verified is True
    assert receipt.quarantine_only is True
    assert len(receipt.package_hash) == 64

    # 2. Replay of same package_id must fail closed
    with pytest.raises(ReplayDetectedError, match="has already been processed"):
        harness.validate_candidate_package(pkg, secret_key=secret)

    # 3. Tampered payload fails closed
    pkg2 = harness.generate_candidate_package(
        candidate=sample_candidate,
        package_id="pkg-w8-002",
        author="idea_graph_harness",
        secret_key=secret,
    )
    tampered_params = dict(pkg2.parameters)
    tampered_params["summary"] = "Tampered summary after signing"
    tampered_pkg = replace(pkg2, parameters=tampered_params)
    with pytest.raises(SignatureVerificationFailedError, match="invalid key or tampered payload"):
        harness.validate_candidate_package(tampered_pkg, secret_key=secret)

    # 4. Wrong secret key fails closed
    pkg3 = harness.generate_candidate_package(
        candidate=sample_candidate,
        package_id="pkg-w8-003",
        author="idea_graph_harness",
        secret_key=secret,
    )
    wrong_key = b"wrong-key-that-does-not-match-32!!"
    with pytest.raises(SignatureVerificationFailedError, match="invalid key or tampered payload"):
        harness.validate_candidate_package(pkg3, secret_key=wrong_key)

    # 5. Wrong environment / network fails closed
    pkg4 = harness.generate_candidate_package(
        candidate=sample_candidate,
        package_id="pkg-w8-004",
        author="idea_graph_harness",
        secret_key=secret,
    )
    bad_env_pkg = replace(pkg4, environment="illegal_mainnet_unauthorized")
    with pytest.raises(UnauthorizedContextError, match="Unauthorized signing context"):
        harness.validate_candidate_package(bad_env_pkg, secret_key=secret)

    bad_net_pkg = replace(pkg4, network_id="unauthorized-net-999")
    with pytest.raises(UnauthorizedContextError, match="Unauthorized signing context"):
        harness.validate_candidate_package(bad_net_pkg, secret_key=secret)


# ---------------------------------------------------------------------------
# CLAIM-W8-02: Forbidden Action and Authority Language Rejection
# ---------------------------------------------------------------------------

def test_forbidden_authority_language(harness: SentiumShadowConformanceHarness, sample_candidate: IdeaCandidateEnvelope):
    """Exit Gate 2: Any forbidden authority language or execution directives fail closed."""
    # Attempting to generate a package with forbidden authority in candidate summary
    bad_candidate = replace(sample_candidate, summary="Requesting LIVE_AUTHORITY on Sentium network")
    with pytest.raises(ForbiddenActionOrLanguageError, match="forbidden authority language"):
        harness.generate_candidate_package(candidate=bad_candidate, package_id="pkg-w8-bad-01", author="bad_actor")

    # In parameters
    bad_params_cand = replace(sample_candidate, mechanisms=("Bypass validation via BYPASS_QUARANTINE directive",))
    with pytest.raises(ForbiddenActionOrLanguageError, match="forbidden authority language"):
        harness.generate_candidate_package(candidate=bad_params_cand, package_id="pkg-w8-bad-02", author="bad_actor")


# ---------------------------------------------------------------------------
# CLAIM-W8-03: Quarantine-Only and Zero Production Admission
# ---------------------------------------------------------------------------

def test_quarantine_only(harness: SentiumShadowConformanceHarness, sample_candidate: IdeaCandidateEnvelope):
    """Exit Gate 3: Live production admission is strictly blocked; only quarantine reception allowed."""
    valid_pkg = harness.generate_candidate_package(
        candidate=sample_candidate,
        package_id="pkg-w8-live-probe",
        author="idea_graph_harness",
    )
    assert valid_pkg.quarantine_only is True

    # Manually creating a package attempting live production (quarantine_only=False)
    live_pkg = replace(valid_pkg, package_id="pkg-w8-live-illegal", quarantine_only=False)
    with pytest.raises(LiveProductionAdmissionProhibitedError, match="Live production admission is strictly prohibited"):
        harness.validate_candidate_package(live_pkg)


# ---------------------------------------------------------------------------
# CLAIM-W8-04: No Capital State in Outcomes & Redacted Signed Outcomes
# ---------------------------------------------------------------------------

def test_no_capital_state(harness: SentiumShadowConformanceHarness):
    """Exit Gate 4: Outcomes must never contain capital state, balances, or trade commands."""
    secret = b"shadow-outcome-signing-key-32b!!"
    valid_metrics = {
        "sharpe_ratio": 1.95,
        "information_ratio": 1.42,
        "max_drawdown_pct": 0.038,
        "p_value": 0.0012,
        "sample_size": 50000,
    }

    # 1. Clean scientific outcome
    outcome = OutcomeEnvelope(
        outcome_id="out-w8-shadow-001",
        source_candidate_refs=(EntityRef(kind="candidate", owner="sentium", local_id="cand-sentium-w8-001"),),
        owner_domain="sentium",
        stage=ExecutionStage.SHADOW.value,
        decision_status=DecisionStatus.REJECTED.value,
        metric_refs=valid_metrics,
        observation_window={"start": "2026-08-01T00:00:00Z", "end": "2026-09-01T00:00:00Z"},
        timestamp="2026-09-06T00:00:00Z",
        evidence_hashes=("b" * 64,),
        signer_context={"signer": "sentium_shadow_runner", "mode": "SIMULATION"},
        redaction_level=RedactionLevel.REDACTED.value,
    )
    sig = harness.sign_outcome(outcome, nonce="nonce-out-001", secret_key=secret)
    receipt = harness.ingest_shadow_outcome(outcome, signature=sig, secret_key=secret, nonce="nonce-out-001")
    assert receipt.status == "SHADOW_ACCEPTED"
    assert receipt.signature_verified is True
    assert receipt.metrics["sharpe_ratio"] == 1.95

    # 2. Replay of same nonce fails closed
    with pytest.raises(ReplayDetectedError, match="nonce 'nonce-out-001' has already been consumed"):
        harness.ingest_shadow_outcome(outcome, signature=sig, secret_key=secret, nonce="nonce-out-001")

    # 3. Capital state leakage fails closed
    capital_leaking_metrics = dict(valid_metrics)
    capital_leaking_metrics["account_balance"] = 1000000.0  # Prohibited capital key!
    leaking_outcome = OutcomeEnvelope(
        outcome_id="out-w8-shadow-leak",
        source_candidate_refs=(EntityRef(kind="candidate", owner="sentium", local_id="cand-sentium-w8-001"),),
        owner_domain="sentium",
        stage=ExecutionStage.SHADOW.value,
        decision_status=DecisionStatus.REJECTED.value,
        metric_refs=capital_leaking_metrics,
        observation_window={"start": "2026-08-01T00:00:00Z", "end": "2026-09-01T00:00:00Z"},
        timestamp="2026-09-06T00:00:00Z",
        evidence_hashes=("b" * 64,),
        signer_context={"signer": "sentium_shadow_runner"},
        redaction_level=RedactionLevel.REDACTED.value,
    )
    leak_sig = harness.sign_outcome(leaking_outcome, nonce="nonce-leak-01", secret_key=secret)
    with pytest.raises(CapitalStateProhibitedError, match="prohibited capital/execution keys"):
        harness.ingest_shadow_outcome(leaking_outcome, signature=leak_sig, secret_key=secret, nonce="nonce-leak-01")


# ---------------------------------------------------------------------------
# CLAIM-W8-05: Durable Replay & Restart Audit Design
# ---------------------------------------------------------------------------

def test_durable_replay(harness: SentiumShadowConformanceHarness, sample_candidate: IdeaCandidateEnvelope):
    """Exit Gate 5: Persisted audit log deterministically reproduces shadow state upon restart."""
    pkg = harness.generate_candidate_package(
        candidate=sample_candidate,
        package_id="pkg-w8-replay-test",
        author="idea_graph_harness",
    )
    receipt = harness.validate_candidate_package(pkg)
    assert receipt.status == "QUARANTINED_CONFORMANT"

    # Read back from storage
    replayed = harness.replay_audit_log()
    assert len(replayed) >= 1
    assert replayed[-1].entry_type == "PACKAGE_VALIDATION"
    assert replayed[-1].payload["package_id"] == "pkg-w8-replay-test"
    assert replayed[-1].payload["package_hash"] == receipt.package_hash


# ---------------------------------------------------------------------------
# CLAIM-W8-06: Rollback Boundary Verification
# ---------------------------------------------------------------------------

def test_rollback_boundary(harness: SentiumShadowConformanceHarness, sample_candidate: IdeaCandidateEnvelope):
    """Rollback boundary: disabling harness halts operations without mutating state."""
    assert harness.is_enabled is True
    harness.disable()
    assert harness.is_enabled is False

    with pytest.raises(HarnessDisabledError, match="Rollback Boundary Active"):
        harness.generate_candidate_package(candidate=sample_candidate, package_id="p", author="a")

    harness.enable()
    assert harness.is_enabled is True
