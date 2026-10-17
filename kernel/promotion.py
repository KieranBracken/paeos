"""Single-use exact-ref promotion intent and operation encoding (Gate F Task 5)."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from kernel.cas import is_valid_hash
from kernel.types import DomainTag
from paeos.model_router.a08_enforcer import A08Enforcer
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.types import ModelFamily

CANONICAL_DEBT0249_CANDIDATE_FILES: tuple[str, ...] = (
    "kernel/ledger.py",
    "kernel/ledger_sqlite.py",
    "kernel/promotion.py",
    "kernel/sandbox_backend.py",
    "kernel/types.py",
    "paeos/model_router/a08_enforcer.py",
    "paeos/model_router/auditor_receipt.py",
    "paeos/model_router/privacy.py",
    "paeos/model_router/router.py",
    "paeos/model_router/types.py",
    "reviews/architecture/DEBT_0249_ACCEPTANCE_MANIFEST.json",
    "reviews/architecture/DEBT_0249_PROGRAMME_CONTRACT.md",
    "runtime/arch_verifier.py",
    "runtime/ast_linter.py",
    "runtime/autonomy/authority.py",
    "runtime/autonomy/cycle_detector.py",
    "runtime/autonomy/mission_controller.py",
    "runtime/autonomy/schemas/__init__.py",
    "runtime/autonomy/schemas/architect_cognition.py",
    "runtime/autonomy/weakness_finder/__init__.py",
    "runtime/autonomy/weakness_finder/coordinator.py",
    "runtime/autonomy/weakness_finder/sensor_pack_structural.py",
    "runtime/court/completeness_firewall.py",
    "runtime/critique.py",
    "runtime/orchestrator/__init__.py",
    "tests/runtime/test_executable_law_canaries.py",
)


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
    candidate_root_hash: str | None = None


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
    domain_tag: DomainTag | str = DomainTag.PRODUCTION
    candidate_root_hash: str | None = None


def promotion_operation(intent: PromotionIntent) -> str:
    canonical: dict[str, object] = {
        "repository_id": intent.repository_id,
        "target_ref": intent.target_ref,
        "expected_target_head": intent.expected_target_head,
        "reviewed_commit": intent.reviewed_commit,
        "disposition_hash": intent.disposition_hash,
        "rollback_commit": intent.rollback_commit,
        "health_command_id": intent.health_command_id,
        "expires_seq": intent.expires_seq,
    }
    if intent.candidate_root_hash is not None:
        canonical["candidate_root_hash"] = intent.candidate_root_hash
    return "promote:" + json.dumps(canonical, sort_keys=True, separators=(",", ":"))


_GIT_OID = re.compile(r"^[0-9a-f]{40,64}$")


def _is_valid_uuid(val: str) -> bool:
    try:
        u = uuid.UUID(str(val))
        return str(u).lower() == str(val).lower()
    except Exception:
        return False


def evaluate_promotion(
    intent: PromotionIntent,
    evidence: PromotionEvidence,
    cas: Any | None = None,
    *,
    candidate_files: Sequence[Path | str] | None = None,
    candidate_base_dir: Path | str | None = None,
    require_candidate_root: bool = True,
    canonical_manifest: Sequence[str] | None = None,
    enforce_canonical_manifest: bool = False,
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

    catalog = ModelCatalog()
    enforcer = A08Enforcer(catalog)

    builder = (evidence.builder_family or "").strip().lower()
    auditor = (evidence.auditor_family or "").strip().lower()
    valid_families = {f.value.lower() for f in ModelFamily if f != ModelFamily.UNKNOWN}
    builder_fam = next((f for f in ModelFamily if f != ModelFamily.UNKNOWN and f.value.lower() == builder), None)
    auditor_fam = next((f for f in ModelFamily if f != ModelFamily.UNKNOWN and f.value.lower() == auditor), None)

    if not builder or not auditor:
        reasons.append("AUDITOR_DECORRELATION_UNPROVEN")
    else:
        decorrelation_violated = False
        if builder_fam is None:
            reasons.append("INVALID_BUILDER_FAMILY")
            decorrelation_violated = True
        if auditor_fam is None:
            reasons.append("INVALID_AUDITOR_FAMILY")
            decorrelation_violated = True
        if builder_fam and auditor_fam:
            enforce_res = enforcer.enforce(
                builder_provider="local",
                builder_model_id="builder",
                builder_family=builder_fam,
                auditor_provider="external",
                auditor_model_id="auditor",
                auditor_family=auditor_fam,
            )
            if not enforce_res.passed:
                reasons.append("AUDITOR_SAME_AS_BUILDER_FAMILY")
                decorrelation_violated = True
        elif builder == auditor:
            reasons.append("AUDITOR_SAME_AS_BUILDER_FAMILY")
            decorrelation_violated = True
        if decorrelation_violated:
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

    valid_domains = {d.value for d in DomainTag}
    raw_domain = evidence.domain_tag.value if isinstance(evidence.domain_tag, DomainTag) else str(evidence.domain_tag).strip().upper()
    if raw_domain not in valid_domains:
        reasons.append("DOMAIN_TAG_INVALID")
    elif raw_domain != DomainTag.PRODUCTION.value:
        reasons.append("NON_PRODUCTION_DOMAIN_EVIDENCE")

    effective_manifest = canonical_manifest
    if effective_manifest is None and (enforce_canonical_manifest or intent.repository_id == "paeos"):
        effective_manifest = CANONICAL_DEBT0249_CANDIDATE_FILES

    if require_candidate_root or intent.candidate_root_hash is not None or evidence.candidate_root_hash is not None or candidate_files is not None:
        if not intent.candidate_root_hash or not evidence.candidate_root_hash:
            reasons.append("CANDIDATE_ROOT_MISSING")
        elif not is_valid_hash(intent.candidate_root_hash) or not is_valid_hash(evidence.candidate_root_hash):
            reasons.append("CANDIDATE_ROOT_INVALID")
        elif evidence.candidate_root_hash != intent.candidate_root_hash:
            reasons.append("CANDIDATE_ROOT_MISMATCH")
        if candidate_files is None:
            if require_candidate_root and intent.candidate_root_hash:
                reasons.append("CANDIDATE_FILES_REQUIRED_FOR_ROOT_VERIFICATION")
            if intent.repository_id == "paeos":
                reasons.append("CANDIDATE_FILES_MANDATORY_FOR_PAEOS_PROMOTION")
        else:
            base = Path(candidate_base_dir) if candidate_base_dir is not None else None
            tree = {}
            for p in candidate_files:
                path = Path(p)
                if base is not None and path.is_absolute():
                    try:
                        rel_key = path.resolve().relative_to(base.resolve()).as_posix()
                    except ValueError:
                        rel_key = path.name
                elif path.is_absolute():
                    try:
                        rel_key = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
                    except ValueError:
                        rel_key = path.as_posix().lstrip("/")
                else:
                    rel_key = path.as_posix()
                tree[rel_key] = hashlib.sha256(path.read_bytes()).hexdigest()

            if effective_manifest is not None:
                missing = sorted(set(effective_manifest) - set(tree.keys()))
                if missing:
                    reasons.append("CANDIDATE_MANIFEST_INCOMPLETE")
                extra = sorted(set(tree.keys()) - set(effective_manifest))
                if extra:
                    reasons.append("CANDIDATE_MANIFEST_UNAUTHORIZED_EXPANSION")

            computed_root = hashlib.sha256(json.dumps(tree, sort_keys=True).encode("utf-8")).hexdigest()
            if intent.candidate_root_hash != computed_root or evidence.candidate_root_hash != computed_root:
                reasons.append("CANDIDATE_ROOT_RECOMPUTATION_MISMATCH")
    if evidence.l14_receipt_hash and cas is None:
        reasons.append("CAS_STORE_REQUIRED_FOR_L14_VERIFICATION")
    if cas is not None:
        for name, value in (
            ("L11_CONTRACT_NOT_IN_CAS", evidence.l11_contract_hash),
            ("L13_EVIDENCE_NOT_IN_CAS", evidence.l13_evidence_hash),
            ("L14_RECEIPT_NOT_IN_CAS", evidence.l14_receipt_hash),
            ("L15_DOCUMENT_NOT_IN_CAS", evidence.l15_document_hash),
        ):
            if value and not cas.has(value):
                reasons.append(name)
        if evidence.l11_contract_hash and cas.has(evidence.l11_contract_hash):
            try:
                raw_l11 = cas.get(evidence.l11_contract_hash)
                l11_data = (
                    json.loads(raw_l11.decode("utf-8"))
                    if isinstance(raw_l11, (bytes, bytearray))
                    else raw_l11
                )
                if not isinstance(l11_data, dict):
                    reasons.append("L11_CONTRACT_CORRUPTED")
                else:
                    l11_cand_root = (
                        l11_data.get("candidate_root")
                        or l11_data.get("candidate_root_sha256")
                        or l11_data.get("candidate_sha256")
                    )
                    if not l11_cand_root or (intent.candidate_root_hash and l11_cand_root != intent.candidate_root_hash):
                        reasons.append("L11_CONTRACT_CANDIDATE_ROOT_MISMATCH")
            except Exception:
                reasons.append("L11_CONTRACT_CORRUPTED")
        if evidence.l13_evidence_hash and cas.has(evidence.l13_evidence_hash):
            try:
                raw_l13 = cas.get(evidence.l13_evidence_hash)
                l13_data = (
                    json.loads(raw_l13.decode("utf-8"))
                    if isinstance(raw_l13, (bytes, bytearray))
                    else raw_l13
                )
                if not isinstance(l13_data, dict):
                    reasons.append("L13_BUNDLE_CORRUPTED")
                else:
                    l13_cand_root = l13_data.get("candidate_root") or l13_data.get("candidate_root_sha256")
                    if not l13_cand_root or (intent.candidate_root_hash and l13_cand_root != intent.candidate_root_hash):
                        reasons.append("L13_BUNDLE_CANDIDATE_ROOT_MISMATCH")
            except Exception:
                reasons.append("L13_BUNDLE_CORRUPTED")
        if evidence.l14_receipt_hash and cas.has(evidence.l14_receipt_hash):
            try:
                raw_receipt = cas.get(evidence.l14_receipt_hash)
                receipt_data = (
                    json.loads(raw_receipt.decode("utf-8"))
                    if isinstance(raw_receipt, (bytes, bytearray))
                    else raw_receipt
                )
                if not isinstance(receipt_data, dict):
                    reasons.append("L14_RECEIPT_CORRUPTED")
                else:
                    if receipt_data.get("a08_verdict") != "PASS":
                        reasons.append("L14_RECEIPT_A08_FAILED")
                    r_builder = (receipt_data.get("builder_family") or "").strip().lower()
                    r_auditor = (receipt_data.get("auditor_family") or "").strip().lower()
                    r_b_fam = next((f for f in ModelFamily if f != ModelFamily.UNKNOWN and f.value.lower() == r_builder), None)
                    r_a_fam = next((f for f in ModelFamily if f != ModelFamily.UNKNOWN and f.value.lower() == r_auditor), None)
                    if r_b_fam is None or r_a_fam is None:
                        reasons.append("L14_RECEIPT_A08_VIOLATION")
                    else:
                        r_enforce = enforcer.enforce(
                             builder_provider=receipt_data.get("builder_provider", "local"),
                             builder_model_id=receipt_data.get("builder_model_id", "builder"),
                             builder_family=r_b_fam,
                             auditor_provider=receipt_data.get("auditor_provider", "external"),
                             auditor_model_id=receipt_data.get("auditor_model_id", "auditor"),
                             auditor_family=r_a_fam,
                        )
                        if not r_enforce.passed:
                            reasons.append("L14_RECEIPT_A08_VIOLATION")

                    if r_builder and builder and r_builder != builder:
                        reasons.append("L14_RECEIPT_BUILDER_FAMILY_MISMATCH")
                    if r_auditor and auditor and r_auditor != auditor:
                        reasons.append("L14_RECEIPT_AUDITOR_FAMILY_MISMATCH")

                    gen_id = receipt_data.get("external_generation_id")
                    if not gen_id or not str(gen_id).startswith("gen-") or any(kw in str(gen_id).lower() for kw in ("unknown", "none", "mock", "synthetic")):
                        reasons.append("L14_RECEIPT_EXTERNAL_PROVENANCE_MISSING")

                    host_turn = receipt_data.get("host_turn_uuid")
                    if (
                        not host_turn
                        or not _is_valid_uuid(str(host_turn))
                        or str(host_turn).strip() == "00000000-0000-0000-0000-000000000000"
                        or any(kw in str(host_turn).lower() for kw in ("unknown", "none", "mock", "synthetic", "nil"))
                    ):
                        reasons.append("L14_RECEIPT_HOST_TURN_MISSING")

                    t_req = receipt_data.get("transport_request_sha256")
                    t_res = receipt_data.get("transport_response_sha256")
                    if not t_req or not is_valid_hash(str(t_req)) or not t_res or not is_valid_hash(str(t_res)):
                        reasons.append("L14_RECEIPT_TRANSPORT_HASH_INVALID")

                    r_cand = receipt_data.get("candidate_sha256") or receipt_data.get("candidate_root_sha256")
                    if not r_cand or (intent.candidate_root_hash and r_cand != intent.candidate_root_hash):
                        reasons.append("L14_RECEIPT_CANDIDATE_ROOT_MISMATCH")
                    r_bundle = receipt_data.get("evidence_bundle_sha256")
                    if evidence.l13_evidence_hash:
                        if not r_bundle or r_bundle != evidence.l13_evidence_hash:
                            reasons.append("L14_RECEIPT_EVIDENCE_BUNDLE_MISMATCH")
                    r_report = receipt_data.get("report_sha256")
                    if not r_report or not is_valid_hash(str(r_report)):
                        reasons.append("L14_REPORT_HASH_INVALID")
                    elif not cas.has(str(r_report)):
                        reasons.append("L14_REPORT_NOT_IN_CAS")
                    else:
                        raw_report = cas.get(str(r_report))
                        report_text = raw_report.decode("utf-8") if isinstance(raw_report, (bytes, bytearray)) else str(raw_report)
                        if "AUDIT_COMPLETE: true" not in report_text or "L14_STATUS: PASS" not in report_text:
                            reasons.append("L14_REPORT_STATUS_NOT_PASS")
            except Exception:
                reasons.append("L14_RECEIPT_CORRUPTED")
        if evidence.l15_document_hash and cas.has(evidence.l15_document_hash):
            try:
                raw_l15 = cas.get(evidence.l15_document_hash)
                l15_data = (
                    json.loads(raw_l15.decode("utf-8"))
                    if isinstance(raw_l15, (bytes, bytearray))
                    else raw_l15
                )
                if not isinstance(l15_data, dict):
                    reasons.append("L15_DOCUMENT_CORRUPTED")
                else:
                    l15_cand_root = (
                        l15_data.get("candidate_root")
                        or l15_data.get("candidate_root_sha256")
                        or l15_data.get("candidate_sha256")
                    )
                    if not l15_cand_root or (intent.candidate_root_hash and l15_cand_root != intent.candidate_root_hash):
                        reasons.append("L15_DOCUMENT_CANDIDATE_ROOT_MISMATCH")
            except Exception:
                reasons.append("L15_DOCUMENT_CORRUPTED")
    for value, name in (
        (intent.repository_id, "REPOSITORY_ID_INVALID"),
        (intent.target_ref, "TARGET_REF_INVALID"),
        (intent.expected_target_head, "EXPECTED_HEAD_INVALID"),
        (intent.reviewed_commit, "REVIEWED_COMMIT_INVALID"),
        (intent.rollback_commit, "ROLLBACK_COMMIT_INVALID"),
        (intent.disposition_hash, "DISPOSITION_HASH_INVALID"),
    ):
        if not value.strip() or any(c.isspace() for c in value):
            reasons.append(name)
    for value, name in (
        (intent.expected_target_head, "EXPECTED_HEAD_INVALID"),
        (intent.reviewed_commit, "REVIEWED_COMMIT_INVALID"),
        (intent.rollback_commit, "ROLLBACK_COMMIT_INVALID"),
    ):
        if not _GIT_OID.fullmatch(value):
            reasons.append(name)
    if intent.expires_seq < 0:
        reasons.append("EXPIRY_INVALID")
    if (
        not intent.target_ref.startswith("refs/heads/")
        or ".." in intent.target_ref
        or any(c.isspace() for c in intent.target_ref)
    ):
        reasons.append("TARGET_REF_INVALID")
    return tuple(dict.fromkeys(reasons))
