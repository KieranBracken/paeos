"""Sentium Shadow Conformance Harness and External Adapter (Migration Wave 8 / W8).

Proves Sentium interfaces without modifying Sentium by providing an external conformance harness
and shadow consumer. Enforces:
1. Signed package conformance matrix (valid, tampered, wrong key, wrong env, wrong network, replay)
2. Quarantine-only and forbidden action/language rejection
3. Redacted signed outcome vectors with zero capital state
4. Durable replay and restart audit ledger
5. Rollback boundary via simple harness deactivation
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

from contracts.adapters import LofSentiumContextAdapter
from contracts.envelopes import (
    EntityRef,
    IdeaCandidateEnvelope,
    OutcomeEnvelope,
    RedactionLevel,
    ResearchCandidatePackage,
)
from contracts.serialization import canonical_json_bytes, compute_canonical_hash

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class HarnessError(Exception):
    """Base exception for Sentium shadow conformance harness."""


class HarnessDisabledError(HarnessError):
    """Raised when an operation is attempted while the harness is disabled (Rollback Boundary Active)."""


class LiveProductionAdmissionProhibitedError(HarnessError):
    """Raised when a package attempts live production admission (quarantine_only is False)."""


class ForbiddenActionOrLanguageError(HarnessError):
    """Raised when a package or outcome contains forbidden authority language or actions."""


class SignatureVerificationFailedError(HarnessError):
    """Raised when cryptographic signature verification fails or payload is tampered."""


class UnauthorizedContextError(HarnessError):
    """Raised when signing context (environment or network_id) is invalid or mismatched."""


class ReplayDetectedError(HarnessError):
    """Raised when a package or outcome nonce/identifier is replayed."""


class CapitalStateProhibitedError(HarnessError):
    """Raised when an outcome reveals capital state, portfolio balance, or execution directives."""


# ---------------------------------------------------------------------------
# Constants & Forbidden Terms
# ---------------------------------------------------------------------------

FORBIDDEN_AUTHORITY_PATTERNS = (
    r"\bLIVE_AUTHORITY\b",
    r"\bCAPITAL_POLICY\b",
    r"\bTRADE_DISPATCH\b",
    r"\bSENTIUM_LIVE_VALIDATED\b",
    r"\bBYPASS_QUARANTINE\b",
    r"\bPROMOTE_TO_PRODUCTION\b",
    r"\bEXECUTION_DIRECTIVE\b",
)

PROHIBITED_CAPITAL_KEYS = frozenset({
    "account_balance",
    "capital_allocation",
    "portfolio_nav",
    "order_id",
    "live_trade",
    "position_size",
    "pnl_dollar",
    "broker_credentials",
    "order_execution_directive",
    "wallet_private_key",
})


# ---------------------------------------------------------------------------
# Receipts & Log Entries
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PackageValidationReceipt:
    __test__ = False
    package_id: str
    candidate_id: str
    environment: str
    network_id: str
    status: str  # "QUARANTINED_CONFORMANT"
    quarantine_only: bool
    package_hash: str
    verified_at: str
    signature_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ShadowOutcomeReceipt:
    __test__ = False
    outcome_id: str
    candidate_refs: tuple[str, ...]
    status: str  # "SHADOW_ACCEPTED"
    redaction_level: str
    metrics: dict[str, Any]
    outcome_hash: str
    verified_at: str
    signature_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "candidate_refs": list(self.candidate_refs),
            "status": self.status,
            "redaction_level": self.redaction_level,
            "metrics": self.metrics,
            "outcome_hash": self.outcome_hash,
            "verified_at": self.verified_at,
            "signature_verified": self.signature_verified,
        }


@dataclass(frozen=True, slots=True)
class ShadowLogEntry:
    __test__ = False
    entry_id: str
    entry_type: str  # "PACKAGE_VALIDATION", "OUTCOME_INGESTION"
    timestamp: str
    canonical_hash: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Main Harness Class
# ---------------------------------------------------------------------------

class SentiumShadowConformanceHarness:
    """External Conformance Harness & Shadow Consumer for Sentium Interfaces (Wave 8)."""

    def __init__(
        self,
        *,
        default_secret: bytes = b"sentium-conformance-secret-key-32b!",
        storage_path: Path | None = None,
        enabled: bool = True,
    ) -> None:
        self._secret = default_secret
        self._storage_path = storage_path
        self._enabled = enabled

        # In-memory shadow state
        self._seen_package_ids: set[str] = set()
        self._seen_outcome_ids: set[str] = set()
        self._seen_nonces: set[str] = set()
        self._quarantined_packages: dict[str, ResearchCandidatePackage] = {}
        self._shadow_outcomes: dict[str, ShadowOutcomeReceipt] = {}
        self._audit_log: list[ShadowLogEntry] = []

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        """Rollback boundary: disable external harness without mutating Sentium state."""
        self._enabled = False

    def _check_enabled(self) -> None:
        if not self._enabled:
            raise HarnessDisabledError("SentiumShadowConformanceHarness is disabled (Rollback Boundary Active)")

    def _check_forbidden_language(self, text_or_dict: Any) -> None:
        raw_text = json.dumps(text_or_dict) if not isinstance(text_or_dict, str) else text_or_dict
        for pat in FORBIDDEN_AUTHORITY_PATTERNS:
            if re.search(pat, raw_text, re.IGNORECASE):
                raise ForbiddenActionOrLanguageError(f"Package contains forbidden authority language matching '{pat}'")

    def _check_capital_leakage(self, data: Mapping[str, Any]) -> None:
        keys = set(data.keys())
        leakage = keys.intersection(PROHIBITED_CAPITAL_KEYS)
        if leakage:
            raise CapitalStateProhibitedError(f"Outcome contains prohibited capital/execution keys: {sorted(leakage)}")
        for k, v in data.items():
            if isinstance(v, dict):
                self._check_capital_leakage(v)

    def generate_candidate_package(
        self,
        *,
        candidate: IdeaCandidateEnvelope,
        package_id: str,
        author: str,
        secret_key: bytes | None = None,
        environment: str = "simulation",
        network_id: str = "sim-harness",
    ) -> ResearchCandidatePackage:
        """Generate a conformant, signed Sentium-native ResearchCandidatePackage."""
        self._check_enabled()
        candidate.validate()

        # Check candidate envelope fields for forbidden language
        self._check_forbidden_language(candidate.summary)
        self._check_forbidden_language(candidate.claims)
        self._check_forbidden_language(candidate.mechanisms)

        key = secret_key or self._secret
        ctx = LofSentiumContextAdapter.normalize_signing_context({"environment": environment, "network_id": network_id})

        parameters = {
            "summary": candidate.summary,
            "claims": list(candidate.claims),
            "mechanisms": list(candidate.mechanisms),
            "assumptions": list(candidate.assumptions),
            "novelty": candidate.novelty_assessment,
            "credibility": candidate.credibility_assessment,
            "failure_modes": list(candidate.failure_modes),
            "rights": list(candidate.rights_labels),
        }
        self._check_forbidden_language(parameters)

        evidence_hashes = tuple(ev.artifact.digest for ev in candidate.evidence_refs)
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        signature = LofSentiumContextAdapter.compute_signature(
            parameters,
            key,
            environment=ctx["environment"],
            network_id=ctx["network_id"],
        )

        pkg = ResearchCandidatePackage(
            package_id=package_id,
            candidate_id=candidate.candidate_id,
            author=author,
            submission_timestamp=now_utc,
            strategy_class="IDEA_GRAPH_RESEARCH_CANDIDATE",
            parameters=parameters,
            evidence_hashes=evidence_hashes,
            signature=signature,
            environment=ctx["environment"],
            network_id=ctx["network_id"],
            quarantine_only=True,
        )
        pkg.validate()
        return pkg

    def validate_candidate_package(
        self,
        pkg: ResearchCandidatePackage,
        *,
        secret_key: bytes | None = None,
    ) -> PackageValidationReceipt:
        """Validate candidate package against conformance matrix and admit into quarantine."""
        self._check_enabled()

        # 1. Non-negotiable Quarantine-Only invariant
        if not pkg.quarantine_only:
            raise LiveProductionAdmissionProhibitedError(
                f"Package '{pkg.package_id}' specifies quarantine_only=False. Live production admission is strictly prohibited."
            )

        # 2. Replay detection on package_id
        if pkg.package_id in self._seen_package_ids:
            raise ReplayDetectedError(f"Replay detected: package_id '{pkg.package_id}' has already been processed")

        # 3. Forbidden authority language check
        self._check_forbidden_language(pkg.parameters)
        self._check_forbidden_language(pkg.strategy_class)

        # 4. Context normalization & verification
        try:
            ctx = LofSentiumContextAdapter.normalize_signing_context({
                "environment": pkg.environment,
                "network_id": pkg.network_id,
            })
        except ValueError as e:
            raise UnauthorizedContextError(f"Unauthorized signing context: {e}") from e

        # 5. Cryptographic signature check
        key = secret_key or self._secret
        is_valid = LofSentiumContextAdapter.verify_signature(
            payload=pkg.parameters,
            signature=pkg.signature,
            secret_key=key,
            environment=ctx["environment"],
            network_id=ctx["network_id"],
        )
        if not is_valid:
            raise SignatureVerificationFailedError(
                f"Signature verification failed for package '{pkg.package_id}' (invalid key or tampered payload)"
            )

        # Package passes all conformance gates
        self._seen_package_ids.add(pkg.package_id)
        self._quarantined_packages[pkg.package_id] = pkg

        pkg_hash = compute_canonical_hash(pkg.to_dict())
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        receipt = PackageValidationReceipt(
            package_id=pkg.package_id,
            candidate_id=pkg.candidate_id,
            environment=pkg.environment,
            network_id=pkg.network_id,
            status="QUARANTINED_CONFORMANT",
            quarantine_only=True,
            package_hash=pkg_hash,
            verified_at=now_utc,
            signature_verified=True,
        )

        log_entry = ShadowLogEntry(
            entry_id=f"LOG-PKG-{pkg.package_id}",
            entry_type="PACKAGE_VALIDATION",
            timestamp=now_utc,
            canonical_hash=pkg_hash,
            payload=receipt.to_dict(),
        )
        self._audit_log.append(log_entry)
        self._persist_entry(log_entry)

        return receipt

    def ingest_shadow_outcome(
        self,
        outcome: OutcomeEnvelope,
        *,
        signature: str,
        secret_key: bytes | None = None,
        nonce: str,
    ) -> ShadowOutcomeReceipt:
        # 1. Capital state prohibition check
        self._check_capital_leakage(outcome.metric_refs)
        self._check_capital_leakage(outcome.observation_window)
        self._check_capital_leakage(outcome.signer_context)

        # 2. Envelope validation
        try:
            outcome.validate()
        except ValueError as e:
            if "leaks prohibited capital/execution keys" in str(e):
                raise CapitalStateProhibitedError(str(e)) from e
            raise

        # 3. Nonce and outcome_id replay detection
        if nonce in self._seen_nonces:
            raise ReplayDetectedError(f"Replay detected: outcome nonce '{nonce}' has already been consumed")
        if outcome.outcome_id in self._seen_outcome_ids:
            raise ReplayDetectedError(f"Replay detected: outcome_id '{outcome.outcome_id}' has already been processed")

        # 4. Forbidden action check
        self._check_forbidden_language(outcome.metric_refs)
        self._check_forbidden_language(outcome.signer_context)

        # 4. Cryptographic signature verification over outcome canonical bytes + nonce
        key = secret_key or self._secret
        signed_body = {
            "outcome": outcome.to_dict(),
            "nonce": nonce,
        }
        b = canonical_json_bytes(signed_body)
        expected_sig = hmac.new(key, b, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_sig, signature):
            raise SignatureVerificationFailedError("Cryptographic signature verification failed for shadow outcome")

        self._seen_nonces.add(nonce)
        self._seen_outcome_ids.add(outcome.outcome_id)

        outcome_hash = compute_canonical_hash(outcome.to_dict())
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        receipt = ShadowOutcomeReceipt(
            outcome_id=outcome.outcome_id,
            candidate_refs=tuple(r.local_id for r in outcome.source_candidate_refs),
            status="SHADOW_ACCEPTED",
            redaction_level=outcome.redaction_level,
            metrics=outcome.metric_refs,
            outcome_hash=outcome_hash,
            verified_at=now_utc,
            signature_verified=True,
        )
        self._shadow_outcomes[outcome.outcome_id] = receipt

        log_entry = ShadowLogEntry(
            entry_id=f"LOG-OUT-{outcome.outcome_id}",
            entry_type="OUTCOME_INGESTION",
            timestamp=now_utc,
            canonical_hash=outcome_hash,
            payload=receipt.to_dict(),
        )
        self._audit_log.append(log_entry)
        self._persist_entry(log_entry)

        return receipt

    def sign_outcome(
        self,
        outcome: OutcomeEnvelope,
        *,
        nonce: str,
        secret_key: bytes | None = None,
    ) -> str:
        """Helper to generate HMAC signature for shadow outcome."""
        key = secret_key or self._secret
        signed_body = {
            "outcome": outcome.to_dict(),
            "nonce": nonce,
        }
        b = canonical_json_bytes(signed_body)
        return hmac.new(key, b, hashlib.sha256).hexdigest()

    def _persist_entry(self, entry: ShadowLogEntry) -> None:
        if self._storage_path is not None:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self._storage_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

    def replay_audit_log(self, from_file: Path | None = None) -> list[ShadowLogEntry]:
        """Durable replay: reconstruct shadow state deterministically from persisted log."""
        self._check_enabled()
        target = from_file or self._storage_path
        if target is None or not target.is_file():
            return list(self._audit_log)

        replayed_log: list[ShadowLogEntry] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            replayed_log.append(ShadowLogEntry(
                entry_id=data["entry_id"],
                entry_type=data["entry_type"],
                timestamp=data["timestamp"],
                canonical_hash=data["canonical_hash"],
                payload=data["payload"],
            ))
        return replayed_log
