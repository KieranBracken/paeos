"""Single-use exact-ref promotion intent and operation encoding (Gate F Task 5)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from kernel.cas import is_valid_hash


@dataclass(frozen=True, slots=True)
class PromotionIntent:
    repository_id: str
    target_ref: str
    expected_target_head: str
    reviewed_commit: str
    disposition_hash: str
    rollback_commit: str
    health_command_id: str
    expires_seq: int


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    """Correlated prerequisites supplied by the later bootstrap ceremony.

    Defaults are deliberately unsafe.  A caller must present a Founder-bound
    bootstrap fact, complete L11/L13/L14/L15 hashes, heterogeneous provenance,
    and a clean rollback/reconciliation state before a token can be used.
    """

    bootstrap_verified: bool = False
    trace: str = "TRACE_A"
    protected_paths: bool = False
    l11_contract_hash: str | None = None
    l13_evidence_hash: str | None = None
    l14_receipt_hash: str | None = None
    l15_document_hash: str | None = None
    builder_family: str | None = None
    auditor_family: str | None = None
    blocking_debt: bool = False
    incident_open: bool = False
    reconciliation_required: bool = False
    rollback_verified: bool = False
    health_passed: bool = False


def promotion_operation(intent: PromotionIntent) -> str:
    canonical = {
        "repository_id": intent.repository_id,
        "target_ref": intent.target_ref,
        "expected_target_head": intent.expected_target_head,
        "reviewed_commit": intent.reviewed_commit,
        "disposition_hash": intent.disposition_hash,
        "rollback_commit": intent.rollback_commit,
        "health_command_id": intent.health_command_id,
        "expires_seq": intent.expires_seq,
    }
    return "promote:" + json.dumps(canonical, sort_keys=True, separators=(",", ":"))


_GIT_OID = re.compile(r"^[0-9a-f]{40,64}$")


def evaluate_promotion(
    intent: PromotionIntent, evidence: PromotionEvidence
) -> tuple[str, ...]:
    """Return deterministic denial reasons for a proposed automatic promotion."""

    if not evidence.bootstrap_verified:
        return ("FOUNDER_BOOTSTRAP_REQUIRED",)

    reasons: list[str] = []
    if evidence.trace != "TRACE_A":
        reasons.append("TRACE_B_NOT_ELIGIBLE")
    if evidence.protected_paths or intent.target_ref in {
        "refs/heads/main",
        "refs/heads/master",
        "refs/heads/trunk",
    }:
        reasons.append("PROTECTED_PATH")
    for name, value in (
        ("L11_CONTRACT_MISSING", evidence.l11_contract_hash),
        ("L13_EVIDENCE_MISSING", evidence.l13_evidence_hash),
        ("L14_RECEIPT_MISSING", evidence.l14_receipt_hash),
        ("L15_DOCUMENT_MISSING", evidence.l15_document_hash),
    ):
        if value is None or not is_valid_hash(value):
            reasons.append(name)
    builder = (evidence.builder_family or "").strip().lower()
    auditor = (evidence.auditor_family or "").strip().lower()
    if (
        not builder
        or not auditor
        or builder in {"unknown", "none"}
        or auditor in {"unknown", "none"}
        or builder == auditor
    ):
        reasons.append("AUDITOR_DECORRELATION_UNPROVEN")
    if evidence.blocking_debt:
        reasons.append("BLOCKING_DEBT_PRESENT")
    if evidence.incident_open:
        reasons.append("INCIDENT_OPEN")
    if evidence.reconciliation_required:
        reasons.append("RECONCILIATION_REQUIRED")
    if not evidence.rollback_verified:
        reasons.append("ROLLBACK_PLAN_MISSING")
    if not evidence.health_passed:
        reasons.append("HEALTH_CHECK_MISSING")
    for value, name in (
        (intent.repository_id, "REPOSITORY_ID_INVALID"),
        (intent.target_ref, "TARGET_REF_INVALID"),
        (intent.expected_target_head, "EXPECTED_HEAD_INVALID"),
        (intent.reviewed_commit, "REVIEWED_COMMIT_INVALID"),
        (intent.rollback_commit, "ROLLBACK_COMMIT_INVALID"),
        (intent.disposition_hash, "DISPOSITION_HASH_INVALID"),
    ):
        if not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value):
            reasons.append(name)
    for value, name in (
        (intent.expected_target_head, "EXPECTED_HEAD_INVALID"),
        (intent.reviewed_commit, "REVIEWED_COMMIT_INVALID"),
        (intent.rollback_commit, "ROLLBACK_COMMIT_INVALID"),
    ):
        if isinstance(value, str) and not _GIT_OID.fullmatch(value):
            reasons.append(name)
    if not isinstance(intent.expires_seq, int) or intent.expires_seq < 0:
        reasons.append("EXPIRY_INVALID")
    if (
        not isinstance(intent.target_ref, str)
        or not intent.target_ref.startswith("refs/heads/")
        or ".." in intent.target_ref
        or any(c.isspace() for c in intent.target_ref)
    ):
        reasons.append("TARGET_REF_INVALID")
    return tuple(dict.fromkeys(reasons))
