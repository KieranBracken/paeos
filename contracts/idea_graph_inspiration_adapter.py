"""Idea Graph and Inspiration Engine Capability Adapter (Migration Wave 7 / W7).

Under the Controlling Target Architecture (FOUNDER_ECOSYSTEM_TARGET_ARCHITECTURE_v0.2.md)
and the Authoritative Migration DAG (07_MIGRATION_DEPENDENCY_DAG.yaml):
- Exposes full Inspiration Engine (LOF) capability through Idea Graph.
- Preserves deterministic experiment lineage, contradiction preservation, and negative evidence.
- Enforces hardened feedback signatures and anti-replay fail-closed guardrails.
- Enforces the non-negotiable invariant: Mock runners cannot certify evidence.
- Constructs rights-aware distillation datasets.
- Proves legacy outcome path differential parity while maintaining zero state mutation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping, Sequence

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from contracts.envelopes import (
    ArtifactRef,
    Criticality,
    DataClass,
    DomainOwner,
    EntityRef,
    EvidenceRef,
    IdeaCandidateEnvelope,
    OutcomeEnvelope,
    TrustLabel,
)
from contracts.kae_lof_federation_adapter import RightsPolicy
from contracts.serialization import canonical_json_bytes, compute_canonical_hash

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")

# Pre-seeded 32-byte Ed25519 keys for deterministic verified tests and operational default keys
DEFAULT_IE_PROV_SEED = b"paeos-inspiration-prov-key-0001!"  # exactly 32 bytes
DEFAULT_IE_SHADOW_SEED = b"paeos-inspiration-shadow-key-02!"  # exactly 32 bytes

IE_PROV_SIGNING_KEY = SigningKey(DEFAULT_IE_PROV_SEED)
IE_SHADOW_SIGNING_KEY = SigningKey(DEFAULT_IE_SHADOW_SEED)


def compute_feedback_canonical_payload(
    *,
    experiment_id: str,
    runner_type: str,
    metrics: Mapping[str, float],
    nonce: str,
    signing_key_id: str,
    context_version: str = "v1",
) -> bytes:
    """Compute deterministic RFC 8785 canonical JSON bytes for feedback outcome signing.

    Binds at minimum:
    - experiment_id
    - runner_type
    - metrics (sorted keys, formatted float representations)
    - nonce
    - signing_key_id (signer/key identity)
    - context_version (relevant context/version)
    """
    canonical_metrics = {k: float(metrics[k]) for k in sorted(metrics.keys())}
    payload_obj = {
        "context_version": context_version,
        "experiment_id": experiment_id,
        "metrics": canonical_metrics,
        "nonce": nonce,
        "runner_type": runner_type,
        "signing_key_id": signing_key_id,
    }
    return json.dumps(payload_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sign_feedback_outcome(
    signing_key: SigningKey,
    *,
    experiment_id: str,
    runner_type: str,
    metrics: Mapping[str, float],
    nonce: str,
    signing_key_id: str,
    context_version: str = "v1",
) -> str:
    """Sign canonical feedback outcome with an Ed25519 signing key, returning 128-character hex signature."""
    payload = compute_feedback_canonical_payload(
        experiment_id=experiment_id,
        runner_type=runner_type,
        metrics=metrics,
        nonce=nonce,
        signing_key_id=signing_key_id,
        context_version=context_version,
    )
    return signing_key.sign(payload).signature.hex()



class InspirationAdapterError(Exception):
    """Base error for Idea Graph / Inspiration Engine adapter."""


class AdapterDisabledError(InspirationAdapterError):
    """Raised when an operation is attempted on a disabled adapter (Rollback Boundary Active)."""


class FeedbackReplayError(InspirationAdapterError):
    """Raised when an outcome or feedback event is replayed with an existing nonce or hash."""


class InvalidSignatureError(InspirationAdapterError):
    """Raised when a feedback signature is invalid, forged, or missing."""


class MockCertificationProhibitedError(InspirationAdapterError):
    """Raised when a mock runner or synthetic stub attempts to issue a certification."""


class ForbiddenAuthorityError(InspirationAdapterError):
    """Raised when an experiment or certification claims unauthorized live or capital authority."""


class RejectionCategory(StrEnum):
    LOW_VALIDITY = "LOW_VALIDITY"
    LOW_CREDIBILITY = "LOW_CREDIBILITY"
    EXTREME_TRANSFER_DISTANCE = "EXTREME_TRANSFER_DISTANCE"
    ANALOGY_CONTAMINATION = "ANALOGY_CONTAMINATION"
    FORBIDDEN_AUTHORITY_LANGUAGE = "FORBIDDEN_AUTHORITY_LANGUAGE"
    RAW_CONTENT_RISK = "RAW_CONTENT_RISK"
    DUPLICATE_LOW_VALUE = "DUPLICATE_LOW_VALUE"
    CONTRADICTION_UNRESOLVED = "CONTRADICTION_UNRESOLVED"
    INSUFFICIENT_PROVENANCE = "INSUFFICIENT_PROVENANCE"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    SENTIUM_BOUNDARY_REJECTED = "SENTIUM_BOUNDARY_REJECTED"


class TestMode(StrEnum):
    __test__ = False
    REPLAY_ONLY = "REPLAY_ONLY"
    SHADOW_ONLY = "SHADOW_ONLY"
    REPLAY_THEN_SHADOW = "REPLAY_THEN_SHADOW"
    HUMAN_REVIEW_ONLY = "HUMAN_REVIEW_ONLY"
    REJECTED_NO_TEST = "REJECTED_NO_TEST"


class CertificationStatus(StrEnum):
    CERTIFIED_FOR_DISTILLATION = "CERTIFIED_FOR_DISTILLATION"
    EVALUATION_ONLY = "EVALUATION_ONLY"
    REJECTED_MOCK_RUNNER = "REJECTED_MOCK_RUNNER"
    REJECTED_SAFETY_VIOLATION = "REJECTED_SAFETY_VIOLATION"
    REJECTED_INSUFFICIENT_SAMPLE = "REJECTED_INSUFFICIENT_SAMPLE"
    REJECTED_UNVERIFIED_OUTCOMES = "REJECTED_UNVERIFIED_OUTCOMES"


FORBIDDEN_AUTHORITY_TERMS = {
    "LIVE_AUTHORITY",
    "EXECUTION",
    "CAPITAL_POLICY",
    "DOCTRINE_PROMOTION",
    "SENTIUM_REPLAY_VALIDATED",
    "SENTIUM_SHADOW_VALIDATED",
}


@dataclass(frozen=True, slots=True)
class TestDesign:
    __test__ = False
    test_mode: TestMode
    target_subsystems: tuple[str, ...]
    primary_metric: str
    required_replay_windows: tuple[str, ...] = ()
    required_datasets: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    safety_constraints: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_mode": self.test_mode.value,
            "target_subsystems": list(self.target_subsystems),
            "primary_metric": self.primary_metric,
            "required_replay_windows": list(self.required_replay_windows),
            "required_datasets": list(self.required_datasets),
            "success_criteria": list(self.success_criteria),
            "safety_constraints": list(self.safety_constraints),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TestDesign:
        return cls(
            test_mode=TestMode(data.get("test_mode", TestMode.REPLAY_ONLY)),
            target_subsystems=tuple(data.get("target_subsystems", ())),
            primary_metric=str(data.get("primary_metric", "ACCURACY")),
            required_replay_windows=tuple(data.get("required_replay_windows", ())),
            required_datasets=tuple(data.get("required_datasets", ())),
            success_criteria=tuple(data.get("success_criteria", ())),
            safety_constraints=tuple(data.get("safety_constraints", ())),
        )


@dataclass(frozen=True, slots=True)
class ExperimentCandidate:
    experiment_id: str
    idea_id: str
    concept_ids: tuple[str, ...]
    source_hashes: tuple[str, ...]
    hypothesis: str
    mechanism_under_test: str
    test_design: TestDesign
    credibility_score: float
    novelty_score: float
    transfer_distance_score: float
    package_hash: str
    created_at: str
    shadow_only: bool = True
    authority_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "idea_id": self.idea_id,
            "concept_ids": list(self.concept_ids),
            "source_hashes": list(self.source_hashes),
            "hypothesis": self.hypothesis,
            "mechanism_under_test": self.mechanism_under_test,
            "test_design": self.test_design.to_dict(),
            "credibility_score": self.credibility_score,
            "novelty_score": self.novelty_score,
            "transfer_distance_score": self.transfer_distance_score,
            "package_hash": self.package_hash,
            "created_at": self.created_at,
            "shadow_only": self.shadow_only,
            "authority_safe": self.authority_safe,
        }


@dataclass(frozen=True, slots=True)
class RejectedKnowledgeRecord:
    rejection_id: str
    idea_id: str
    source_hashes: tuple[str, ...]
    concept_ids: tuple[str, ...]
    contradiction_claim: str
    rejection_reason: str
    rejection_category: RejectionCategory
    evidence_snapshot: dict[str, Any]
    doctrine_pollution_risk: float
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rejection_id": self.rejection_id,
            "idea_id": self.idea_id,
            "source_hashes": list(self.source_hashes),
            "concept_ids": list(self.concept_ids),
            "contradiction_claim": self.contradiction_claim,
            "rejection_reason": self.rejection_reason,
            "rejection_category": self.rejection_category.value,
            "evidence_snapshot": self.evidence_snapshot,
            "doctrine_pollution_risk": self.doctrine_pollution_risk,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class HardenedFeedbackOutcome:
    outcome_id: str
    experiment_id: str
    runner_type: str  # "PRODUCTION_SHADOW", "REPLAY_DETERMINISTIC", "MOCK"
    metrics: dict[str, float]
    signature: str
    signing_key_id: str
    nonce: str
    timestamp: str
    verified: bool = False
    synthetic: bool = False
    context_version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "experiment_id": self.experiment_id,
            "runner_type": self.runner_type,
            "metrics": self.metrics,
            "signature": self.signature,
            "signing_key_id": self.signing_key_id,
            "nonce": self.nonce,
            "timestamp": self.timestamp,
            "verified": self.verified,
            "synthetic": self.synthetic,
            "context_version": self.context_version,
        }


@dataclass(frozen=True, slots=True)
class CertificationReport:
    certification_id: str
    experiment_id: str
    outcome_id: str
    certified: bool
    status: CertificationStatus
    runner_type: str
    quality_score: float
    allowed_use: str  # "DISTILLATION_DATASET", "EVALUATION_ONLY"
    certification_hash: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "certification_id": self.certification_id,
            "experiment_id": self.experiment_id,
            "outcome_id": self.outcome_id,
            "certified": self.certified,
            "status": self.status.value,
            "runner_type": self.runner_type,
            "quality_score": self.quality_score,
            "allowed_use": self.allowed_use,
            "certification_hash": self.certification_hash,
            "timestamp": self.timestamp,
        }


class IdeaGraphInspirationAdapter:
    """Production Adapter exposing Inspiration Engine capability to Idea Graph."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        trusted_keys: Mapping[str, VerifyKey | str | bytes] | None = None,
    ) -> None:
        self._enabled = enabled
        self._experiments: dict[str, ExperimentCandidate] = {}
        self._rejections: dict[str, RejectedKnowledgeRecord] = {}
        self._processed_nonces: set[str] = set()
        self._processed_outcomes: dict[str, HardenedFeedbackOutcome] = {}
        self._certifications: dict[str, CertificationReport] = {}
        self._trusted_keys: dict[str, VerifyKey] = {
            "IE_KEY_001_RSA_PROV": IE_PROV_SIGNING_KEY.verify_key,
            "IE_KEY_002_SHADOW": IE_SHADOW_SIGNING_KEY.verify_key,
        }
        if trusted_keys:
            for k, v in trusted_keys.items():
                self.register_trusted_key(k, v)

    def register_trusted_key(self, key_id: str, key: VerifyKey | str | bytes) -> None:
        """Register or update a trusted Ed25519 verify key."""
        if isinstance(key, VerifyKey):
            self._trusted_keys[key_id] = key
        elif isinstance(key, bytes):
            self._trusted_keys[key_id] = VerifyKey(key)
        elif isinstance(key, str):
            clean = key.strip()
            try:
                self._trusted_keys[key_id] = VerifyKey(bytes.fromhex(clean))
            except (ValueError, TypeError):
                self._trusted_keys[key_id] = VerifyKey(clean.encode("utf-8")[:32])
        else:
            raise TypeError(f"Unsupported key type for {key_id}: {type(key)}")


    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        """Rollback boundary: disable Idea Graph adapters."""
        self._enabled = False

    def _check_enabled(self) -> None:
        if not self._enabled:
            raise AdapterDisabledError("IdeaGraphInspirationAdapter is disabled (Rollback Boundary Active)")

    def create_experiment_candidate(
        self,
        *,
        idea_id: str,
        concept_ids: Sequence[str],
        source_hashes: Sequence[str],
        hypothesis: str,
        mechanism: str,
        test_design: TestDesign | Mapping[str, Any],
        credibility_score: float = 0.8,
        novelty_score: float = 0.75,
        transfer_distance_score: float = 0.3,
    ) -> ExperimentCandidate:
        """Mint deterministic experiment candidate bound to Idea Graph lineage."""
        self._check_enabled()

        if isinstance(test_design, Mapping):
            design = TestDesign.from_dict(test_design)
        else:
            design = test_design

        now_str = datetime.now(timezone.utc).isoformat()
        concept_tuple = tuple(sorted(concept_ids))
        source_tuple = tuple(sorted(source_hashes))

        # Compute deterministic package hash over lineage inputs
        lineage_payload = {
            "idea_id": idea_id,
            "concept_ids": list(concept_tuple),
            "source_hashes": list(source_tuple),
            "hypothesis": hypothesis,
            "mechanism": mechanism,
            "test_design": design.to_dict(),
        }
        pkg_hash = compute_canonical_hash(lineage_payload)
        exp_id = f"EXP-{pkg_hash[:12]}"

        # Check for forbidden authority claims
        for target in design.target_subsystems:
            if target.upper() in FORBIDDEN_AUTHORITY_TERMS:
                raise ForbiddenAuthorityError(f"Target subsystem claims forbidden authority: {target}")

        cand = ExperimentCandidate(
            experiment_id=exp_id,
            idea_id=idea_id,
            concept_ids=concept_tuple,
            source_hashes=source_tuple,
            hypothesis=hypothesis,
            mechanism_under_test=mechanism,
            test_design=design,
            credibility_score=credibility_score,
            novelty_score=novelty_score,
            transfer_distance_score=transfer_distance_score,
            package_hash=pkg_hash,
            created_at=now_str,
            shadow_only=True,
            authority_safe=True,
        )

        self._experiments[exp_id] = cand
        return cand

    def record_contradiction(
        self,
        *,
        idea_id: str,
        source_hashes: Sequence[str],
        concept_ids: Sequence[str],
        contradiction_claim: str,
        rejection_reason: str,
        category: RejectionCategory,
        doctrine_pollution_risk: float = 0.85,
        evidence_snapshot: dict[str, Any] | None = None,
    ) -> RejectedKnowledgeRecord:
        """Preserve contradiction / negative evidence as first-class RejectedKnowledge."""
        self._check_enabled()

        now_str = datetime.now(timezone.utc).isoformat()
        payload = {
            "idea_id": idea_id,
            "source_hashes": sorted(source_hashes),
            "contradiction_claim": contradiction_claim,
            "category": category.value,
        }
        rej_id = f"REJ-{compute_canonical_hash(payload)[:12]}"

        rec = RejectedKnowledgeRecord(
            rejection_id=rej_id,
            idea_id=idea_id,
            source_hashes=tuple(sorted(source_hashes)),
            concept_ids=tuple(sorted(concept_ids)),
            contradiction_claim=contradiction_claim,
            rejection_reason=rejection_reason,
            rejection_category=category,
            evidence_snapshot=evidence_snapshot or {},
            doctrine_pollution_risk=doctrine_pollution_risk,
            created_at=now_str,
        )

        self._rejections[rej_id] = rec
        return rec

    def ingest_feedback_outcome(
        self,
        *,
        experiment_id: str,
        runner_type: str,
        metrics: Mapping[str, float],
        signature: str,
        signing_key_id: str,
        nonce: str,
        context_version: str = "v1",
    ) -> HardenedFeedbackOutcome:
        """Ingest feedback outcome with hardened cryptographic signature and anti-replay verification."""
        self._check_enabled()

        if experiment_id not in self._experiments:
            raise KeyError(f"Unknown experiment_id: {experiment_id}")

        # 1. Anti-Replay Guardrail: nonces must be strictly unique
        if nonce in self._processed_nonces:
            raise FeedbackReplayError(f"Replay detected: nonce {nonce} has already been processed")

        # 2. Key Identity Validation: key must be registered and trusted
        if signing_key_id not in self._trusted_keys:
            raise InvalidSignatureError(f"Untrusted or missing signing key ID: {signing_key_id}")

        verify_key = self._trusted_keys[signing_key_id]

        # 3. Cryptographic Signature Validation: reject placeholder strings, invalid lengths, and forged signatures
        if not signature or not isinstance(signature, str):
            raise InvalidSignatureError("Missing or empty cryptographic signature for outcome")

        clean_sig = signature.strip()
        if clean_sig in ("", "QUARANTINED_PENDING_SIGNATURE_VERIFICATION", "INVALID"):
            raise InvalidSignatureError("Placeholder or invalid cryptographic signature rejected")

        try:
            sig_bytes = bytes.fromhex(clean_sig)
            if len(sig_bytes) != 64:
                raise InvalidSignatureError(
                    f"Invalid signature length: expected 64 bytes (128 hex characters), got {len(sig_bytes)} bytes"
                )
        except ValueError as exc:
            raise InvalidSignatureError(f"Malformed non-hex cryptographic signature rejected: {clean_sig!r}") from exc

        canonical_payload = compute_feedback_canonical_payload(
            experiment_id=experiment_id,
            runner_type=runner_type,
            metrics=metrics,
            nonce=nonce,
            signing_key_id=signing_key_id,
            context_version=context_version,
        )

        try:
            verify_key.verify(canonical_payload, sig_bytes)
        except BadSignatureError as exc:
            raise InvalidSignatureError(f"Cryptographic signature verification failed: {exc}") from exc

        now_str = datetime.now(timezone.utc).isoformat()
        outcome_hash = hashlib.sha256(f"{experiment_id}:{nonce}:{clean_sig}".encode()).hexdigest()
        outcome_id = f"OUT-{outcome_hash[:12]}"

        if outcome_id in self._processed_outcomes:
            raise FeedbackReplayError(f"Replay detected: outcome {outcome_id} already ingested")

        is_synthetic = (runner_type.upper() == "MOCK")

        outcome = HardenedFeedbackOutcome(
            outcome_id=outcome_id,
            experiment_id=experiment_id,
            runner_type=runner_type,
            metrics=dict(metrics),
            signature=clean_sig,
            signing_key_id=signing_key_id,
            nonce=nonce,
            timestamp=now_str,
            verified=True,
            synthetic=is_synthetic,
            context_version=context_version,
        )

        self._processed_nonces.add(nonce)
        self._processed_outcomes[outcome_id] = outcome
        return outcome

    def certify_outcome_for_distillation(
        self,
        outcome_id: str,
    ) -> CertificationReport:
        """Certify an outcome for distillation. Invariant: Mock runners cannot certify."""
        self._check_enabled()

        outcome = self._processed_outcomes.get(outcome_id)
        if outcome is None:
            raise KeyError(f"Unknown outcome_id: {outcome_id}")

        now_str = datetime.now(timezone.utc).isoformat()

        # NON-NEGOTIABLE INVARIANT: Mock runner cannot certify
        if outcome.synthetic or outcome.runner_type.upper() == "MOCK":
            cert_hash = hashlib.sha256(f"REJECTED_MOCK:{outcome_id}".encode()).hexdigest()
            report = CertificationReport(
                certification_id=f"CERT-REJ-{cert_hash[:8]}",
                experiment_id=outcome.experiment_id,
                outcome_id=outcome_id,
                certified=False,
                status=CertificationStatus.REJECTED_MOCK_RUNNER,
                runner_type=outcome.runner_type,
                quality_score=0.0,
                allowed_use="EVALUATION_ONLY",
                certification_hash=cert_hash,
                timestamp=now_str,
            )
            self._certifications[report.certification_id] = report
            raise MockCertificationProhibitedError(
                f"Mock runner '{outcome.runner_type}' cannot certify evidence for distillation or promotion"
            )

        # Production / verified shadow outcome qualification
        quality = outcome.metrics.get("accuracy", outcome.metrics.get("alpha_generation", 0.85))
        cert_hash = hashlib.sha256(f"CERT:{outcome_id}:{quality}".encode()).hexdigest()

        report = CertificationReport(
            certification_id=f"CERT-{cert_hash[:12]}",
            experiment_id=outcome.experiment_id,
            outcome_id=outcome_id,
            certified=True,
            status=CertificationStatus.CERTIFIED_FOR_DISTILLATION,
            runner_type=outcome.runner_type,
            quality_score=quality,
            allowed_use="DISTILLATION_DATASET",
            certification_hash=cert_hash,
            timestamp=now_str,
        )

        self._certifications[report.certification_id] = report
        return report

    def construct_distillation_dataset(
        self,
        certification_id: str,
        *,
        rights_policy: RightsPolicy,
        sample_records: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Construct distillation dataset respecting RightsPolicy and certification bounds."""
        self._check_enabled()

        cert = self._certifications.get(certification_id)
        if cert is None or not cert.certified:
            raise PermissionError("Cannot construct distillation dataset from uncertified evidence")

        samples_out: list[dict[str, Any]] = []
        for rec in sample_records:
            sample_item = {
                "id": rec.get("id"),
                "features": rec.get("features", {}),
            }
            # Rights Policy Enforcement: exclude raw text if train_on_raw_text is False
            if rights_policy.can_train_on_raw_text or rights_policy.is_public_domain:
                sample_item["raw_text"] = rec.get("raw_text")
            else:
                sample_item["raw_text"] = None
                sample_item["rights_notice"] = "RAW_TEXT_EXCLUDED_PER_POLICY"

            samples_out.append(sample_item)

        dataset_hash = compute_canonical_hash({"cert_id": certification_id, "samples": samples_out})
        return {
            "dataset_id": f"DS-{dataset_hash[:12]}",
            "certification_id": certification_id,
            "sample_count": len(samples_out),
            "rights_policy": rights_policy.to_dict(),
            "raw_text_included": bool(rights_policy.can_train_on_raw_text or rights_policy.is_public_domain),
            "samples": samples_out,
            "dataset_hash": dataset_hash,
        }

    def legacy_outcome_ingestion(self, raw_outcome: Mapping[str, Any]) -> dict[str, Any]:
        """Legacy outcome path for differential testing (retained read-only until W7 exit gate)."""
        return {
            "legacy_id": raw_outcome.get("outcome_id"),
            "exp_id": raw_outcome.get("experiment_id"),
            "metrics": raw_outcome.get("metrics", {}),
            "processed": True,
        }


__all__ = [
    "AdapterDisabledError",
    "CertificationReport",
    "CertificationStatus",
    "ExperimentCandidate",
    "FeedbackReplayError",
    "ForbiddenAuthorityError",
    "HardenedFeedbackOutcome",
    "IE_PROV_SIGNING_KEY",
    "IE_SHADOW_SIGNING_KEY",
    "IdeaGraphInspirationAdapter",
    "InspirationAdapterError",
    "InvalidSignatureError",
    "MockCertificationProhibitedError",
    "RejectedKnowledgeRecord",
    "RejectionCategory",
    "TestDesign",
    "TestMode",
    "compute_feedback_canonical_payload",
    "sign_feedback_outcome",
]
