"""Test Suite for Idea Graph and Inspiration Engine Capability Adapter (Migration Wave 7 / W7).

Validates all required Wave 7 exit gates:
1. deterministic_experiment_lineage (CLAIM-W7-01)
2. contradiction_preservation (CLAIM-W7-02)
3. feedback_signature_and_replay_rejection (CLAIM-W7-03)
4. mock_runner_cannot_certify (CLAIM-W7-04)
5. rights_aware_dataset_construction (CLAIM-W7-05)
6. legacy_outcome_path_differential_parity (CLAIM-W7-06)
7. rollback_boundary_verification (CLAIM-W7-07)
"""

from __future__ import annotations

import hashlib
import json
import pytest

from nacl.signing import SigningKey

from contracts.idea_graph_inspiration_adapter import (
    AdapterDisabledError,
    CertificationReport,
    CertificationStatus,
    ExperimentCandidate,
    FeedbackReplayError,
    ForbiddenAuthorityError,
    HardenedFeedbackOutcome,
    IE_PROV_SIGNING_KEY,
    IE_SHADOW_SIGNING_KEY,
    IdeaGraphInspirationAdapter,
    InvalidSignatureError,
    MockCertificationProhibitedError,
    RejectedKnowledgeRecord,
    RejectionCategory,
    TestDesign,
    TestMode,
    compute_feedback_canonical_payload,
    sign_feedback_outcome,
)
from contracts.kae_lof_federation_adapter import RightsPolicy


@pytest.fixture
def adapter() -> IdeaGraphInspirationAdapter:
    return IdeaGraphInspirationAdapter()


# ---------------------------------------------------------------------------
# CLAIM-W7-01: Deterministic Experiment Lineage
# ---------------------------------------------------------------------------

def test_experiment_lineage(adapter: IdeaGraphInspirationAdapter):
    """Exit Gate 1: Proves deterministic experiment candidate creation bound to Idea Graph lineage."""
    idea_id = "01KZ79K17AGCKCPAGFFSY07HT8"
    concepts = ["C-HURST-01", "C-REGIME-02"]
    source_hashes = ["0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"]

    design = TestDesign(
        test_mode=TestMode.REPLAY_ONLY,
        target_subsystems=("market_microstructure_eval", "volatility_regime_model"),
        primary_metric="ALPHA_GENERATION",
        required_replay_windows=("PAST_3_MONTHS", "CRISIS_2020"),
        safety_constraints=("MAX_DRAWDOWN_2PCT", "ZERO_LEVERAGE"),
    )

    cand = adapter.create_experiment_candidate(
        idea_id=idea_id,
        concept_ids=concepts,
        source_hashes=source_hashes,
        hypothesis="Hurst exponents predict regime shifts prior to volatility explosion",
        mechanism="MECH_HURST_ADAPTIVE_FILTER",
        test_design=design,
        credibility_score=0.92,
        novelty_score=0.85,
    )

    # 1. Lineage binding and deterministic hash
    assert cand.idea_id == idea_id
    assert cand.concept_ids == ("C-HURST-01", "C-REGIME-02")
    assert cand.source_hashes == tuple(source_hashes)
    assert len(cand.package_hash) == 64
    assert cand.experiment_id.startswith("EXP-")
    assert cand.shadow_only is True
    assert cand.authority_safe is True

    # 2. Re-creating with exact same lineage inputs yields byte-exact identical package hash
    cand_repeat = adapter.create_experiment_candidate(
        idea_id=idea_id,
        concept_ids=concepts,
        source_hashes=source_hashes,
        hypothesis="Hurst exponents predict regime shifts prior to volatility explosion",
        mechanism="MECH_HURST_ADAPTIVE_FILTER",
        test_design=design,
    )
    assert cand_repeat.package_hash == cand.package_hash
    assert cand_repeat.experiment_id == cand.experiment_id

    # 3. Forbidden authority claims in test design must fail closed
    forbidden_design = TestDesign(
        test_mode=TestMode.REPLAY_ONLY,
        target_subsystems=("market_microstructure_eval", "LIVE_AUTHORITY"),
        primary_metric="ALPHA_GENERATION",
    )
    with pytest.raises(ForbiddenAuthorityError, match="claims forbidden authority"):
        adapter.create_experiment_candidate(
            idea_id=idea_id,
            concept_ids=concepts,
            source_hashes=source_hashes,
            hypothesis="Unauthorized attempt",
            mechanism="ILLEGAL_CLAIM",
            test_design=forbidden_design,
        )


# ---------------------------------------------------------------------------
# CLAIM-W7-02: Contradiction & Negative Evidence Preservation
# ---------------------------------------------------------------------------

def test_contradiction_preservation(adapter: IdeaGraphInspirationAdapter):
    """Exit Gate 2: Contradictions are explicitly preserved as RejectedKnowledge records."""
    rec = adapter.record_contradiction(
        idea_id="01KZ79K17AGCKCPAGFFSY07HT8",
        source_hashes=["abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"],
        concept_ids=["C-FAILED-01"],
        contradiction_claim="Zero statistical significance under out-of-sample stress test",
        rejection_reason="Fails p-value threshold (p=0.42 > 0.05) on 10-year tick replay",
        category=RejectionCategory.CONTRADICTION_UNRESOLVED,
        doctrine_pollution_risk=0.90,
    )

    assert rec.rejection_id.startswith("REJ-")
    assert rec.rejection_category == RejectionCategory.CONTRADICTION_UNRESOLVED
    assert rec.doctrine_pollution_risk == 0.90
    assert "Zero statistical significance" in rec.contradiction_claim
    assert rec.concept_ids == ("C-FAILED-01",)


# ---------------------------------------------------------------------------
# CLAIM-W7-03: Hardened Feedback Signatures & Anti-Replay Fail-Closed
# ---------------------------------------------------------------------------

def test_feedback_signature_replay(adapter: IdeaGraphInspirationAdapter):
    """Exit Gate 3: Feedback signatures validated; replayed nonces and forged keys rejected."""
    # First create two experiment candidates for lineage binding tests
    cand1 = adapter.create_experiment_candidate(
        idea_id="IDEA-001",
        concept_ids=["C-01"],
        source_hashes=["h1" * 32],
        hypothesis="H1",
        mechanism="M1",
        test_design=TestDesign(test_mode=TestMode.SHADOW_ONLY, target_subsystems=("eval",), primary_metric="SHARPE"),
    )
    cand2 = adapter.create_experiment_candidate(
        idea_id="IDEA-002",
        concept_ids=["C-02"],
        source_hashes=["h2" * 32],
        hypothesis="H2",
        mechanism="M2",
        test_design=TestDesign(test_mode=TestMode.SHADOW_ONLY, target_subsystems=("eval",), primary_metric="SHARPE"),
    )

    valid_key = "IE_KEY_001_RSA_PROV"
    valid_metrics = {"alpha_generation": 0.88, "sharpe_ratio": 2.1}
    valid_nonce = "nonce-uuid-1001"

    # 1. Valid signature ingestion
    valid_sig = sign_feedback_outcome(
        IE_PROV_SIGNING_KEY,
        experiment_id=cand1.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=valid_metrics,
        nonce=valid_nonce,
        signing_key_id=valid_key,
    )
    outcome = adapter.ingest_feedback_outcome(
        experiment_id=cand1.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=valid_metrics,
        signature=valid_sig,
        signing_key_id=valid_key,
        nonce=valid_nonce,
    )
    assert outcome.verified is True
    assert outcome.outcome_id.startswith("OUT-")
    assert outcome.metrics["sharpe_ratio"] == 2.1

    # 2. Negative: Replay of same nonce must fail closed
    with pytest.raises(FeedbackReplayError, match="Replay detected: nonce"):
        adapter.ingest_feedback_outcome(
            experiment_id=cand1.experiment_id,
            runner_type="PRODUCTION_SHADOW",
            metrics=valid_metrics,
            signature=valid_sig,
            signing_key_id=valid_key,
            nonce=valid_nonce,
        )

    # 3. Negative: Random non-empty signature (e.g. legacy placeholder string SIG_PROD_12345)
    with pytest.raises(InvalidSignatureError, match="Malformed non-hex cryptographic signature"):
        adapter.ingest_feedback_outcome(
            experiment_id=cand1.experiment_id,
            runner_type="PRODUCTION_SHADOW",
            metrics=valid_metrics,
            signature="SIG_PROD_12345",
            signing_key_id=valid_key,
            nonce="nonce-uuid-1002",
        )

    # 3b. Negative: Random 128 hex character forged signature
    forged_hex_sig = "a" * 128
    with pytest.raises(InvalidSignatureError, match="Cryptographic signature verification failed"):
        adapter.ingest_feedback_outcome(
            experiment_id=cand1.experiment_id,
            runner_type="PRODUCTION_SHADOW",
            metrics=valid_metrics,
            signature=forged_hex_sig,
            signing_key_id=valid_key,
            nonce="nonce-uuid-1003",
        )

    # 4. Negative: Modified metrics after signing
    tampered_metrics = {"alpha_generation": 0.88, "sharpe_ratio": 2.2}  # 2.2 instead of 2.1
    sig_before_tamper = sign_feedback_outcome(
        IE_PROV_SIGNING_KEY,
        experiment_id=cand1.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=valid_metrics,
        nonce="nonce-uuid-tamper-metrics",
        signing_key_id=valid_key,
    )
    with pytest.raises(InvalidSignatureError, match="Cryptographic signature verification failed"):
        adapter.ingest_feedback_outcome(
            experiment_id=cand1.experiment_id,
            runner_type="PRODUCTION_SHADOW",
            metrics=tampered_metrics,
            signature=sig_before_tamper,
            signing_key_id=valid_key,
            nonce="nonce-uuid-tamper-metrics",
        )

    # 5. Negative: Modified experiment ID
    sig_for_cand1 = sign_feedback_outcome(
        IE_PROV_SIGNING_KEY,
        experiment_id=cand1.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=valid_metrics,
        nonce="nonce-uuid-tamper-exp",
        signing_key_id=valid_key,
    )
    with pytest.raises(InvalidSignatureError, match="Cryptographic signature verification failed"):
        adapter.ingest_feedback_outcome(
            experiment_id=cand2.experiment_id,  # Submitted against cand2 instead of cand1
            runner_type="PRODUCTION_SHADOW",
            metrics=valid_metrics,
            signature=sig_for_cand1,
            signing_key_id=valid_key,
            nonce="nonce-uuid-tamper-exp",
        )

    # 6. Negative: Wrong key (signed with SHADOW key, presented as PROV key)
    sig_wrong_key = sign_feedback_outcome(
        IE_SHADOW_SIGNING_KEY,
        experiment_id=cand1.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=valid_metrics,
        nonce="nonce-uuid-wrong-key",
        signing_key_id=valid_key,
    )
    with pytest.raises(InvalidSignatureError, match="Cryptographic signature verification failed"):
        adapter.ingest_feedback_outcome(
            experiment_id=cand1.experiment_id,
            runner_type="PRODUCTION_SHADOW",
            metrics=valid_metrics,
            signature=sig_wrong_key,
            signing_key_id=valid_key,
            nonce="nonce-uuid-wrong-key",
        )

    # 7. Negative: Unknown key ID
    with pytest.raises(InvalidSignatureError, match="Untrusted or missing signing key"):
        adapter.ingest_feedback_outcome(
            experiment_id=cand1.experiment_id,
            runner_type="PRODUCTION_SHADOW",
            metrics=valid_metrics,
            signature=valid_sig,
            signing_key_id="UNKNOWN_KEY_999",
            nonce="nonce-uuid-unknown-key",
        )

    # 8. Negative: Empty or quarantined placeholder signature
    with pytest.raises(InvalidSignatureError, match="Missing or empty cryptographic signature"):
        adapter.ingest_feedback_outcome(
            experiment_id=cand1.experiment_id,
            runner_type="PRODUCTION_SHADOW",
            metrics=valid_metrics,
            signature="",
            signing_key_id=valid_key,
            nonce="nonce-uuid-empty-sig",
        )

    with pytest.raises(InvalidSignatureError, match="Placeholder or invalid cryptographic signature"):
        adapter.ingest_feedback_outcome(
            experiment_id=cand1.experiment_id,
            runner_type="PRODUCTION_SHADOW",
            metrics=valid_metrics,
            signature="QUARANTINED_PENDING_SIGNATURE_VERIFICATION",
            signing_key_id=valid_key,
            nonce="nonce-uuid-quarantine-sig",
        )


# ---------------------------------------------------------------------------
# CLAIM-W7-04: Non-Negotiable Invariant: Mock Runner Cannot Certify
# ---------------------------------------------------------------------------

def test_mock_runner_cannot_certify(adapter: IdeaGraphInspirationAdapter):
    """Exit Gate 4: Mock runners cannot certify evidence for distillation or promotion."""
    cand = adapter.create_experiment_candidate(
        idea_id="IDEA-002",
        concept_ids=["C-02"],
        source_hashes=["h2" * 32],
        hypothesis="H2",
        mechanism="M2",
        test_design=TestDesign(test_mode=TestMode.REPLAY_ONLY, target_subsystems=("eval",), primary_metric="ACC"),
    )

    # Ingest mock outcome with genuine Ed25519 signature
    mock_metrics = {"accuracy": 0.99}
    mock_sig = sign_feedback_outcome(
        IE_PROV_SIGNING_KEY,
        experiment_id=cand.experiment_id,
        runner_type="MOCK",
        metrics=mock_metrics,
        nonce="nonce-mock-01",
        signing_key_id="IE_KEY_001_RSA_PROV",
    )
    mock_outcome = adapter.ingest_feedback_outcome(
        experiment_id=cand.experiment_id,
        runner_type="MOCK",
        metrics=mock_metrics,
        signature=mock_sig,
        signing_key_id="IE_KEY_001_RSA_PROV",
        nonce="nonce-mock-01",
    )
    assert mock_outcome.synthetic is True

    # Attempting to certify mock outcome MUST raise MockCertificationProhibitedError
    with pytest.raises(MockCertificationProhibitedError, match="Mock runner 'MOCK' cannot certify"):
        adapter.certify_outcome_for_distillation(mock_outcome.outcome_id)

    # Real shadow outcome CAN be certified
    real_metrics = {"accuracy": 0.91}
    real_sig = sign_feedback_outcome(
        IE_PROV_SIGNING_KEY,
        experiment_id=cand.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=real_metrics,
        nonce="nonce-real-01",
        signing_key_id="IE_KEY_001_RSA_PROV",
    )
    real_outcome = adapter.ingest_feedback_outcome(
        experiment_id=cand.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=real_metrics,
        signature=real_sig,
        signing_key_id="IE_KEY_001_RSA_PROV",
        nonce="nonce-real-01",
    )

    cert = adapter.certify_outcome_for_distillation(real_outcome.outcome_id)
    assert cert.certified is True
    assert cert.status == CertificationStatus.CERTIFIED_FOR_DISTILLATION
    assert cert.allowed_use == "DISTILLATION_DATASET"


# ---------------------------------------------------------------------------
# CLAIM-W7-05: Rights-Aware Dataset Construction
# ---------------------------------------------------------------------------

def test_rights_aware_dataset(adapter: IdeaGraphInspirationAdapter):
    """Exit Gate 5: Distillation datasets respect RightsPolicy and exclude raw text when restricted."""
    cand = adapter.create_experiment_candidate(
        idea_id="IDEA-003",
        concept_ids=["C-03"],
        source_hashes=["h3" * 32],
        hypothesis="H3",
        mechanism="M3",
        test_design=TestDesign(test_mode=TestMode.SHADOW_ONLY, target_subsystems=("eval",), primary_metric="ACC"),
    )

    ds_metrics = {"accuracy": 0.89}
    ds_sig = sign_feedback_outcome(
        IE_PROV_SIGNING_KEY,
        experiment_id=cand.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=ds_metrics,
        nonce="nonce-dataset-01",
        signing_key_id="IE_KEY_001_RSA_PROV",
    )
    outcome = adapter.ingest_feedback_outcome(
        experiment_id=cand.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=ds_metrics,
        signature=ds_sig,
        signing_key_id="IE_KEY_001_RSA_PROV",
        nonce="nonce-dataset-01",
    )
    cert = adapter.certify_outcome_for_distillation(outcome.outcome_id)

    raw_samples = [
        {"id": "S1", "raw_text": "Sensitive proprietary proprietary market report.", "features": {"f1": 0.42}},
        {"id": "S2", "raw_text": "Another private observation.", "features": {"f1": 0.88}},
    ]

    # Case A: train_on_raw_text = False
    restricted_policy = RightsPolicy(can_train_on_raw_text=False, can_train_on_features=True)
    dataset_a = adapter.construct_distillation_dataset(
        cert.certification_id,
        rights_policy=restricted_policy,
        sample_records=raw_samples,
    )
    assert dataset_a["raw_text_included"] is False
    assert dataset_a["sample_count"] == 2
    for s in dataset_a["samples"]:
        assert s["raw_text"] is None
        assert s["rights_notice"] == "RAW_TEXT_EXCLUDED_PER_POLICY"
        assert "features" in s

    # Case B: train_on_raw_text = True
    permissive_policy = RightsPolicy(can_train_on_raw_text=True, is_public_domain=True)
    dataset_b = adapter.construct_distillation_dataset(
        cert.certification_id,
        rights_policy=permissive_policy,
        sample_records=raw_samples,
    )
    assert dataset_b["raw_text_included"] is True
    assert dataset_b["samples"][0]["raw_text"] == "Sensitive proprietary proprietary market report."


# ---------------------------------------------------------------------------
# CLAIM-W7-06: Legacy Outcome Path Differential Parity
# ---------------------------------------------------------------------------

def test_legacy_outcome_path_differential(adapter: IdeaGraphInspirationAdapter):
    """Exit Gate 6: Differential tests between legacy and hardened typed outcome paths."""
    cand = adapter.create_experiment_candidate(
        idea_id="IDEA-004",
        concept_ids=["C-04"],
        source_hashes=["h4" * 32],
        hypothesis="H4",
        mechanism="M4",
        test_design=TestDesign(test_mode=TestMode.SHADOW_ONLY, target_subsystems=("eval",), primary_metric="ACC"),
    )

    metrics = {"alpha_generation": 0.94, "loss": 0.06}
    raw_payload = {
        "outcome_id": "OUT-RAW-001",
        "experiment_id": cand.experiment_id,
        "metrics": metrics,
    }

    # Legacy path produces basic dictionary mapping
    legacy_res = adapter.legacy_outcome_ingestion(raw_payload)
    assert legacy_res["processed"] is True
    assert legacy_res["metrics"] == metrics

    # Hardened path verifies metrics parity while strictly enforcing cryptographic security
    diff_sig = sign_feedback_outcome(
        IE_PROV_SIGNING_KEY,
        experiment_id=cand.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=metrics,
        nonce="nonce-diff-01",
        signing_key_id="IE_KEY_001_RSA_PROV",
    )
    hardened_res = adapter.ingest_feedback_outcome(
        experiment_id=cand.experiment_id,
        runner_type="PRODUCTION_SHADOW",
        metrics=metrics,
        signature=diff_sig,
        signing_key_id="IE_KEY_001_RSA_PROV",
        nonce="nonce-diff-01",
    )
    # Differential assertion: metrics are identical
    assert hardened_res.metrics == legacy_res["metrics"]
    # Enhanced security: hardened path has verified signature and non-synthetic flag
    assert hardened_res.verified is True
    assert hardened_res.synthetic is False


# ---------------------------------------------------------------------------
# Rollback Boundary Verification
# ---------------------------------------------------------------------------

def test_rollback_boundary(adapter: IdeaGraphInspirationAdapter):
    """Rollback boundary: disabling adapter halts operations without mutating LOF."""
    assert adapter.is_enabled is True
    adapter.disable()
    assert adapter.is_enabled is False

    with pytest.raises(AdapterDisabledError, match="Rollback Boundary Active"):
        adapter.create_experiment_candidate(
            idea_id="I", concept_ids=[], source_hashes=[], hypothesis="", mechanism="",
            test_design=TestDesign(test_mode=TestMode.SHADOW_ONLY, target_subsystems=(), primary_metric="M"),
        )

    adapter.enable()
    assert adapter.is_enabled is True
