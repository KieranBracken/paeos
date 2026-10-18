#!/usr/bin/env python3
"""Compose the production P1 L14 audit from a candidate and physical L13 observations.

This module is a composition-root adapter.  It has no promotion authority: the SoftLoop invokes it
only after Court and the L13 Completeness Firewall have passed, and L16 independently validates its
persisted receipt/report pair.  The model response is never used as physical evidence.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import os
import re
import sqlite3
from dataclasses import fields
from enum import Enum
from pathlib import Path

from kernel.cas import CAS, FilesystemCasStore
from kernel.evidence import Evidence
from kernel.ledger import GENESIS_HASH, Event, compute_row_hash
from paeos.model_router.audit_prompt import build_substantive_audit_prompt
from paeos.model_router.auditor_receipt import (
    AuditorReceiptContract,
    AuditorReceiptError,
    AuditorReportStatus,
    bind_auditor_report,
    capture_auditor_interaction,
    load_auditor_receipt,
    persist_auditor_receipt,
    persist_auditor_report,
    request_fingerprint,
    validate_auditor_receipt,
    validate_auditor_report,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.router import ModelRouter
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    AdmissionState,
    CostTier,
    DataClass,
    LogicalModel,
    ModelCatalogEntry,
    ModelFamily,
    ProviderId,
    RetryPolicy,
    TaskClass,
    TaskRequest,
)
from runtime.candidate_materialization import CandidateMaterialization, verify_candidate_integrity
from runtime.court.completeness_firewall import (
    AuthoritativeCapabilityManifest,
    CompletenessFirewall,
    PreAuditVerdict,
    create_authoritative_manifest,
    load_authoritative_manifest,
)
from runtime.orchestrator import (
    L14AuditArtifacts,
    _derive_runtime_completeness_bundle,
    _evidence_to_json,
    _observation_digest,
    physical_slo_observations,
)
from ops.p1_l14_resume import ContinuationProof

_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[^\s,;`]+"),
    re.compile(
        r"(?i)(\b(?:api[_ -]?key|authorization|secret|token|password)\b\s*[:=]\s*)(?!Bearer\b)[^\s,;`]+"
    ),
    re.compile(r"(?i)\b(?:sk|key|token)-[A-Za-z0-9_-]{8,}\b"),
)

_L14_AUTHORIZATION_SHA256 = "0df79d6f36856a2dda66f0897515033b8dcdc14cb403b2e03b29e791d56ba3bf"
_L14_PREVIEW_AUTHORIZATION_SHA256 = (
    "041de138ad0707d2a0f5469e23ff74db77223fa675475866261325f4c97f489f"
)
_L14_DEFAULT_MODEL = "gemini-3.6-flash"
_L14_PREVIEW_MODEL = "gemini-3-flash-preview"
_L14_PREVIEW_RUN_ID = "r-34f8ddaf"
_L14_PREVIEW_CANDIDATE_ID = "cand-3d28c8598b8448fba9ab79f4d1f4cf86"
_L14_PREVIEW_CANDIDATE_SHA256 = (
    "0703bb9a2ca779264a23521ce6b6d1c5a124c262af872cb41e84491a302c4244"
)
_L14_PREVIEW_QUALIFICATION = ".state-p1-debt0248-preview-qualification-02"
_L14_PREVIEW_QUALIFICATION_HASHES = {
    "validated-public-receipt.json": "d1e5f0a06ba1967c8f1fbe088371a7ba482217d9e85e4e859bf7048302daf396",
    "observed-report.md": "be432d030fc9f0e3552be538d4704c550e8ba7918cb9a6359330ff9739805cbb",
    "physical-identity.json": "aef451ba82eb401281701d6a80a47583741820c0555a664c7a549ec8a60aeea4",
    "preflight.json": "ff09d727f6dff96a120afbf92ccc8cf53eed10f8c30b0a081fc03ebd29b95794",
    "local-adjudication.json": "498445432b43ba3863d2f6ac0c590af68d6b1adbcd840b8c1b59f351b6dc01d9",
}
_L14_PREVIEW_PUBLIC_CANDIDATE_SHA256 = "74e5f5e1e46fd49ff34c33d50af6a4dfb4ec0139b45d2c3f7a4f95d44a06e1c6"
_L14_PREVIEW_PUBLIC_EVIDENCE_SHA256 = "430b4519ac251da208da40c51309caa207f438da25c614ad14eb3efb1060a51d"
_L14_PREVIEW_PUBLIC_SCOPE_SHA256 = "1d7c055bfe090f81db68f0c15f43726d57cda9a2252124c246fe84db35e574a4"
_L14_SOURCE_PIN = "95fe1c7b4d81e9a71bf4c5ea945f97eb57f73f1aa631f2c408406f3ab0a30715"
_L14_FILESET_SHA256 = "c6447db66470073e26a3ea01418994e1b8b355387f0b055eab84672b79956e1d"
_L14_PROJECTION_AUTHORIZATION_SHA256 = (
    "5172956a414b0aafdaadee2a563625ca52e1aac60cf3d450a50a161a554c89c5"
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
_EXCLUDED_DOMAIN_CONTENT = re.compile(
    r"(?i)(?:"
    r"\b(?:sentium|legacy[ _-]+orca)\b[^\r\n]{0,100}"
    r"\b(?:trading|strategy|capital|execution|private|material)\b"
    r"|\b(?:trading|strategy|capital|execution|private|material)\b[^\r\n]{0,100}"
    r"\b(?:sentium|legacy[ _-]+orca)\b"
    r")"
)
_EXACT_NEGATIVE_SCOPE_SENTENCE = (
    "No P2\u2013P9, Phase 5, Sentium, trading/order state, credential, or legacy\n"
    "credential-bearing Orca work is included."
)
_VOCABULARY_SET = frozenset(
    {
        "auth.json",
        "api_keys.json",
        "credential",
        "credentials",
        "secret",
        "secrets",
        "token",
        "tokens",
        "sentium",
        "orca",
        ".env",
        "private",
        "keys",
    }
)
_BOUNDED_SET_LITERAL = re.compile(r"\{[^{}]{1,2048}\}", re.DOTALL)
_BOUNDED_PAREN_LITERAL = re.compile(r"\([^()]{1,2048}\)", re.DOTALL)
_PATH_TOKEN = re.compile(r"[^\s\"'`<>{}\[\](),;:=]+(?:[/\\][^\s\"'`<>{}\[\](),;:=]+)+")

_COMPLETENESS_FILES = tuple(
    f"reviews/audits/completeness/{name}"
    for name in (
        "01_ECOSYSTEM_COMPLETENESS_SCOPE.md",
        "02_INTENDED_CAPABILITY_CENSUS.md",
        "03_IMPLEMENTATION_AND_REACHABILITY_CENSUS.md",
        "04_MOCK_STUB_PLACEHOLDER_REGISTER.md",
        "05_USER_JOURNEY_AND_E2E_MATRIX.md",
        "06_CODE_AND_ARCHITECTURE_QUALITY_FINDINGS.md",
        "07_TEST_COVERAGE_CLASSIFICATION.md",
        "08_DOCUMENTATION_VS_RUNTIME_DRIFT.md",
        "09_SYSTEM_BY_SYSTEM_READINESS.md",
        "10_CROSS_ECOSYSTEM_COMPLETENESS_GAPS.md",
        "11_PAEOS_COMPLETENESS_FIREWALL_SPEC.md",
        "12_REMEDIATION_DEPENDENCY_DAG.md",
        "13_REVISED_ECOSYSTEM_READINESS_ASSESSMENT.md",
    )
)

_AUTHORITY_FILES = (
    "CURRENT_REMEDIATION_STATE.md",
    "reviews/audits/completeness/P1_REQUALIFICATION_FINAL_STATUS.md",
    "reviews/audits/completeness/P1_DEBT_0100_ROOT_CAUSE.md",
    "architecture/FOUNDER_ECOSYSTEM_TARGET_ARCHITECTURE_v0.2.md",
    "spec/PAEOS-9B-multi-model-runtime-architecture.md",
    "operations/ENGINEERING_LIFECYCLE.md",
    "operations/WORKFLOW_STATE_MACHINE.yaml",
    *_COMPLETENESS_FILES,
)

_CANDIDATE_FILES = (
    "runtime/candidate_materialization.py",
    "runtime/court/completeness_firewall.py",
    "runtime/orchestrator/__init__.py",
    "runtime/verification.py",
    "runtime/agents/__init__.py",
    "runtime/integrations/hybrid.py",
    "ops/autonomous_run.py",
    "ops/verify_completeness_firewall_court.py",
    "paeos/model_router/auditor_receipt.py",
    "kernel/evidence.py",
    "kernel/sandbox.py",
    "tests/runtime/test_completeness_firewall.py",
)


def _redact(value: str) -> str:
    redacted = value
    for index, pattern in enumerate(_SECRET_PATTERNS):
        replacement = (
            "Bearer <REDACTED>"
            if index == 0
            else (r"\1<REDACTED>" if index == 1 else "<REDACTED>")
        )
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _read_file(path: Path, label: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise AuditorReceiptError(f"required L14 evidence file is missing or unsafe: {label}")
    raw = path.read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise AuditorReceiptError(f"required L14 evidence file is too large: {label}")
    try:
        return _redact(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise AuditorReceiptError(f"required L14 evidence file is not UTF-8: {label}") from exc


def _evidence_json(evidence: tuple[Evidence, ...]) -> list[dict[str, object]]:
    return [
        {
            "hash": item.hash,
            "kind": item.kind.name,
            "claim_id": item.claim_id,
            "artifact_hash": item.artifact_hash,
            "environment_hash": item.environment_hash,
            "reproducible_command": item.reproducible_command,
            "producer_role": item.producer.role.name,
            "producer_session": item.producer.session,
            "determinism": item.determinism.name,
            "result": item.result,
            "attestation": item.attestation,
        }
        for item in evidence
    ]


def _build_evidence_content(
    *,
    repo_root: Path,
    candidate: CandidateMaterialization,
    pre_audit: PreAuditVerdict,
    evidence: tuple[Evidence, ...],
    manifest: AuthoritativeCapabilityManifest,
) -> str:
    sections: list[str] = [
        "## MACHINE-BINDING RECORDS",
        "```json",
        json.dumps(
            {
                "candidate": candidate.to_json(),
                "l13_pre_audit": {
                    "passed": pre_audit.passed,
                    "violations": list(pre_audit.violations),
                    "evidence_bundle_sha256": pre_audit.evidence_bundle_sha256,
                },
                "manifest": {
                    "manifest_id": manifest.manifest_id,
                    "milestone_id": manifest.milestone_id,
                    "manifest_sha256": manifest.manifest_sha256,
                    "expected_capabilities": list(manifest.expected_capabilities),
                    "verification_obligations": [
                        {"claim_id": item.claim_id, "argv": list(item.argv), "timeout_s": item.timeout_s}
                        for item in manifest.verification_obligations
                    ],
                },
                "physical_l13_evidence": _evidence_json(evidence),
            },
            sort_keys=True,
            indent=2,
        ),
        "```",
        "",
        "## AUTHORITATIVE SCOPE FILES",
    ]
    for relative in _AUTHORITY_FILES:
        content = _read_file(repo_root / relative, relative)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        sections.extend(
            [
                f"### {relative} | redacted_sha256={digest}",
                "```text",
                content,
                "```",
            ]
        )
    sections.append("## CANDIDATE IMPLEMENTATION FILES AT L12")
    for relative in _CANDIDATE_FILES:
        content = _read_file(candidate.candidate_workspace / relative, relative)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        sections.extend(
            [
                f"### {relative} | candidate_redacted_sha256={digest}",
                "```text",
                content,
                "```",
            ]
        )
    return "\n".join(sections)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


_PROJECTION_SCHEMA = "paeos.p1-l14-projection/1"
_PROJECTION_RULE_VERSION = "p1-l14-projection-v1"
_PROJECTION_MAX_FILE_BYTES = 4 * 1024 * 1024
_PROJECTION_DENIED_PATH_PARTS = frozenset(
    {".env", "private", "secrets", "secret", "credentials", "credential", "keys", "sentium"}
)


def _projection_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise AuditorReceiptError("L14 projection contains an invalid required path")
    path = Path(raw)
    normalized = path.as_posix()
    parts = path.parts
    folded_parts = tuple(part.casefold() for part in parts)
    if (
        path.is_absolute()
        or path == Path(".")
        or ".." in parts
        or normalized != raw.replace("\\", "/")
        or any(part in _PROJECTION_DENIED_PATH_PARTS for part in folded_parts)
        or any(part.startswith("sentium") for part in folded_parts)
        or any(part in {"auth.json", "api_keys.json"} for part in folded_parts)
        or any(
            part in {"legacyorca", "legacy_orca", "legacy-orca", "legacy orca"}
            for part in folded_parts
        )
        or any(
            left == "legacy" and right == "orca"
            for left, right in itertools.pairwise(folded_parts)
        )
    ):
        raise AuditorReceiptError("L14 projection contains an unsafe required path")
    return normalized


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {item.name: _json_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _project_p1_evidence(
    *,
    repo_root: Path,
    candidate: CandidateMaterialization,
    pre_audit: PreAuditVerdict,
    evidence: tuple[Evidence, ...],
    manifest: AuthoritativeCapabilityManifest,
) -> dict[str, object]:
    """Build the complete, deterministic, candidate-bound L14 disclosure projection."""
    try:
        authoritative_manifest_path = (
            Path(repo_root) / "ops" / "manifests" / "p1_authoritative_completeness_manifest.json"
        )
        _safe_physical_path(authoritative_manifest_path)
        authoritative_manifest_raw = authoritative_manifest_path.read_bytes()
        authoritative_manifest_file_sha256 = hashlib.sha256(authoritative_manifest_raw).hexdigest()
        if load_authoritative_manifest(authoritative_manifest_path) != manifest:
            raise AuditorReceiptError("L14 projection current authoritative manifest mismatch")

        manifest_args = {
            item.name: getattr(manifest, item.name)
            for item in fields(AuthoritativeCapabilityManifest)
            if item.name != "manifest_sha256"
        }
        rebuilt = create_authoritative_manifest(**manifest_args)
        if not manifest.manifest_sha256 or rebuilt.manifest_sha256 != manifest.manifest_sha256:
            raise AuditorReceiptError("L14 projection manifest identity mismatch")
        if (
            not candidate.candidate_id
            or not candidate.run_id
            or not candidate.l11_binding_sha256
            or not candidate.builder_identity
            or not candidate.base_revision
            or not candidate.cas_artifact_hash
            or not candidate.workspace_identity
            or not candidate.environment_identity
            or not candidate.created_at
            or not pre_audit.evidence_bundle_sha256
        ):
            raise AuditorReceiptError("L14 projection identity binding is incomplete")

        claims = tuple(manifest.expected_capabilities)
        obligation_claims = tuple(item.claim_id for item in manifest.verification_obligations)
        if (
            not claims
            or any(not isinstance(item, str) or not item for item in claims)
            or len(set(claims)) != len(claims)
            or not obligation_claims
            or any(not item for item in obligation_claims)
            or len(set(obligation_claims)) != len(obligation_claims)
            or set(obligation_claims) != set(claims)
        ):
            raise AuditorReceiptError("L14 projection manifest claims are incomplete")

        evidence_claims = tuple(item.claim_id for item in evidence)
        if (
            len(evidence_claims) != len(set(evidence_claims))
            or set(evidence_claims) != set(claims)
            or len({item.hash for item in evidence}) != len(evidence)
            or any(
                not item.hash
                or item.artifact_hash != candidate.cas_artifact_hash
                or not item.environment_hash
                for item in evidence
            )
        ):
            raise AuditorReceiptError("L14 projection evidence set is not exact and candidate-bound")

        metadata_path = candidate.metadata_path
        if not metadata_path.is_absolute() or len(metadata_path.parents) < 3:
            raise AuditorReceiptError("L14 projection candidate location is invalid")
        state_dir = metadata_path.parents[2]
        candidate_root = state_dir / "candidates" / candidate.candidate_id
        if (
            metadata_path != candidate_root / "candidate.json"
            or candidate.candidate_workspace != candidate_root / "workspace"
        ):
            raise AuditorReceiptError("L14 projection candidate location is invalid")
        verify_candidate_integrity(
            candidate,
            run_id=candidate.run_id,
            cas=CAS(FilesystemCasStore(state_dir / "cas")),
        )

        required = set(manifest.verification_source_paths) | set(manifest.verification_support_paths)
        for obligation in manifest.verification_obligations:
            for argument in obligation.argv:
                selected = argument.split("::", 1)[0]
                if selected.endswith(".py"):
                    required.add(selected)
        required.update(item.path for item in candidate.changed_files)
        required_paths = {_projection_path(item) for item in required}

        all_records = (
            tuple(candidate.changed_files)
            + tuple(candidate.verification_support_files)
            + tuple(candidate.verification_source_files)
        )
        by_path: dict[str, object] = {}
        for item in all_records:
            path = _projection_path(item.path)
            if path in by_path:
                raise AuditorReceiptError("L14 projection candidate metadata contains duplicate paths")
            by_path[path] = item
        if not required_paths or not required_paths.issubset(by_path):
            missing = sorted(required_paths - set(by_path))
            missing_label = ",".join(missing) if missing else "<none>"
            claim_label = ",".join(sorted(claims))
            raise AuditorReceiptError(
                "L14 projection required record is absent from candidate metadata: "
                f"path={missing_label}; claim_id={claim_label}"
            )
        if set(by_path) != required_paths:
            raise AuditorReceiptError("L14 projection candidate metadata contains unauthorized records")

        cas = CAS(FilesystemCasStore(state_dir / "cas"))
        projected_records: list[dict[str, str]] = []
        packet_files: list[tuple[str, str, str, str]] = []
        exclusion_verification = {
            "sentium_records": 0,
            "legacy_orca_records": 0,
            "credential_secret_hits": 0,
            "unrelated_repository_records": len(set(by_path) - required_paths),
        }
        for path in sorted(required_paths):
            item = by_path[path]
            target = candidate.candidate_workspace / path
            _safe_physical_path(target)
            raw = target.read_bytes()
            raw_sha256 = hashlib.sha256(raw).hexdigest()
            if len(raw) > _PROJECTION_MAX_FILE_BYTES or raw_sha256 != item.file_sha256 or len(raw) != item.size:
                raise AuditorReceiptError("L14 projection required record metadata mismatch")
            if cas.get(item.cas_hash) != raw:
                raise AuditorReceiptError("L14 projection required record CAS mismatch")
            try:
                decoded = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise AuditorReceiptError("L14 projection required record is not UTF-8") from exc
            content = _redact(decoded)
            credential_hit = _PRIVATE_KEY.search(content) is not None or _redact(content) != content
            domain_hit = _contains_excluded_domain_material(content)
            if credential_hit:
                exclusion_verification["credential_secret_hits"] += 1
            if domain_hit and re.search(r"(?i)\bsentium\b", content):
                exclusion_verification["sentium_records"] += 1
            if domain_hit and re.search(r"(?i)\blegacy[ _-]+orca\b", content):
                exclusion_verification["legacy_orca_records"] += 1
            if credential_hit or domain_hit:
                raise AuditorReceiptError(
                    "L14 projection required record cannot lawfully be included: "
                    f"path={path}; claim_id={','.join(sorted(claims))}"
                )
            content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
            projected_records.append(
                {"path": path, "raw_sha256": raw_sha256, "content_sha256": content_sha256}
            )
            packet_files.append((path, raw_sha256, content_sha256, content))

        excluded_records: list[dict[str, str]] = []
        repo_root = Path(repo_root)
        for raw_path in _AUTHORITY_FILES:
            path = _projection_path(raw_path)
            target = repo_root / path
            _safe_physical_path(target)
            raw = target.read_bytes()
            excluded_records.append(
                {
                    "path": path,
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "reason": "local-authority-provenance-not-transmitted",
                }
            )

        manifest_json = _json_value(manifest)
        physical_evidence = _evidence_json(evidence)
        coverage = {
            "claim_evidence": {item.claim_id: item.hash for item in sorted(evidence, key=lambda x: x.claim_id)},
            "claim_source_files": {claim: sorted(required_paths) for claim in sorted(claims)},
        }
        packet_object = {
            "schema": _PROJECTION_SCHEMA,
            "candidate": candidate.to_json(),
            "l13_pre_audit": _json_value(pre_audit),
            "manifest": manifest_json,
            "physical_l13_evidence": physical_evidence,
            "coverage": coverage,
        }
        packet_sections = [
            json.dumps(packet_object, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        ]
        for path, raw_sha256, content_sha256, content in packet_files:
            packet_sections.append(
                "\n".join(
                    (
                        "## PROJECTED FILE",
                        f"path: {path}",
                        f"raw_sha256: {raw_sha256}",
                        f"content_sha256: {content_sha256}",
                        "-- BEGIN LITERAL REDACTED SOURCE --",
                        content,
                        "-- END LITERAL REDACTED SOURCE --",
                    )
                )
            )
        packet = "\n\n".join(packet_sections)
        if _redact(packet) != packet:
            raise AuditorReceiptError("L14 projection packet redaction is not idempotent")
        if any(exclusion_verification.values()):
            raise AuditorReceiptError("L14 projection exclusion verification failed")
        source_set = {
            "projected_records": projected_records,
            "excluded_records": excluded_records,
            "authoritative_manifest_sha256": manifest.manifest_sha256,
            "authoritative_manifest_file_sha256": authoritative_manifest_file_sha256,
        }
        rule = {
            "version": _PROJECTION_RULE_VERSION,
            "required_selectors": [
                "manifest.verification_source_paths",
                "manifest.verification_support_paths",
                "manifest.verification_obligations.argv[*].py_without_node_selector",
                "candidate.changed_files",
            ],
            "redaction": [pattern.pattern for pattern in _SECRET_PATTERNS],
            "excluded_provenance": list(_AUTHORITY_FILES),
            "max_file_bytes": _PROJECTION_MAX_FILE_BYTES,
        }
        implementation_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        return {
            "schema": _PROJECTION_SCHEMA,
            "packet": packet,
            "packet_sha256": hashlib.sha256(packet.encode("utf-8")).hexdigest(),
            "projected_records": projected_records,
            "source_set_sha256": _canonical_sha256(projected_records),
            "source_set": source_set,
            "full_source_set_sha256": _canonical_sha256(source_set),
            "authoritative_manifest_file_sha256": authoritative_manifest_file_sha256,
            "rule_version": _PROJECTION_RULE_VERSION,
            "rule_sha256": _canonical_sha256(rule),
            "rule_implementation_sha256": implementation_sha256,
            "excluded_records": excluded_records,
            "coverage": coverage,
            "coverage_sha256": _canonical_sha256(coverage),
            "exclusion_verification": exclusion_verification,
        }
    except AuditorReceiptError:
        raise
    except Exception:
        raise AuditorReceiptError("L14 projection could not be established") from None


def _verify_p1_projection(
    projection: dict[str, object],
    *,
    repo_root: Path,
    candidate: CandidateMaterialization,
    pre_audit: PreAuditVerdict,
    evidence: tuple[Evidence, ...],
    manifest: AuthoritativeCapabilityManifest,
) -> None:
    """Recompute the authoritative projection; attacker-supplied internal hashes are irrelevant."""
    try:
        expected = _project_p1_evidence(
            repo_root=repo_root,
            candidate=candidate,
            pre_audit=pre_audit,
            evidence=evidence,
            manifest=manifest,
        )
        if not isinstance(projection, dict) or projection != expected:
            raise AuditorReceiptError("L14 projection verification mismatch")
    except AuditorReceiptError:
        raise
    except Exception:
        raise AuditorReceiptError("L14 projection verification failed") from None


def _project_p1_runtime_evidence(
    *,
    state_dir: Path,
    candidate: CandidateMaterialization,
    pre_audit: PreAuditVerdict,
    evidence: tuple[Evidence, ...],
    manifest: AuthoritativeCapabilityManifest,
    continuation_proof: ContinuationProof | None = None,
) -> dict[str, object]:
    """Reconstruct the exact L13 packet from immutable, current-run runtime proof."""

    def fail(obligation: str) -> None:
        raise AuditorReceiptError(f"L14 runtime projection missing proof: {obligation}")

    try:
        ledger_path = state_dir / "ledger.db"
        _safe_physical_path(ledger_path)
        with sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True) as connection:
            connection.execute("BEGIN")
            cursor = connection.execute(
                "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload "
                "FROM ledger_rows ORDER BY seq ASC"
            )
            rows = []
            expected_seq = 1
            previous_hash = GENESIS_HASH
            for row in cursor.fetchall():
                seq, timestamp, prev_hash, row_hash, schema_ver, kind, raw_payload = row
                try:
                    payload = json.loads(raw_payload)
                except Exception:
                    fail("ledger_payload_json")
                if (
                    not isinstance(seq, int) or isinstance(seq, bool) or seq != expected_seq
                    or not isinstance(timestamp, str) or not isinstance(prev_hash, str)
                    or prev_hash != previous_hash or not isinstance(row_hash, str)
                    or not isinstance(schema_ver, int) or isinstance(schema_ver, bool)
                    or not isinstance(kind, str) or not isinstance(payload, dict)
                    or compute_row_hash(
                        prev_hash, seq, timestamp,
                        Event(schema_ver=schema_ver, kind=kind, payload=payload),
                    ) != row_hash
                ):
                    fail("ledger_hash_chain")
                rows.append({"seq": seq, "row_hash": row_hash, "prev_hash": prev_hash,
                             "kind": kind, "payload": payload})
                previous_hash = row_hash
                expected_seq += 1
        if not rows:
            fail("L13_COMPLETENESS_CLEARED")
        if continuation_proof is not None:
            if (
                rows[-1]["seq"] != continuation_proof.current_head_seq
                or rows[-1]["row_hash"] != continuation_proof.current_head_sha256
            ):
                fail("continuation_proof.head_drift")
            c_matches = [r for r in rows if r["seq"] == continuation_proof.clearance_seq]
            if not c_matches:
                fail("L13_COMPLETENESS_CLEARED")
            clearance = c_matches[0]
            v_matches = [r for r in rows if r["seq"] == continuation_proof.verification_seq]
            if not v_matches:
                fail("L13_VERIFICATION")
            verification = v_matches[0]
        else:
            clearance = rows[-1]
            if len(rows) < 2:
                fail("L13_VERIFICATION")
            verification = rows[-2]
        clearance_payload = clearance["payload"]
        if (
            clearance["kind"] != "L13_COMPLETENESS_CLEARED"
            or not isinstance(clearance_payload, dict)
            or clearance_payload.get("run_id") != candidate.run_id
            or clearance_payload.get("candidate_id") != candidate.candidate_id
            or clearance_payload.get("candidate_sha256") != candidate.cas_artifact_hash
            or clearance_payload.get("evidence_bundle_sha256") != pre_audit.evidence_bundle_sha256
        ):
            fail("L13_COMPLETENESS_CLEARED")
        verification_payload = verification["payload"]
        if (
            verification["kind"] != "L13_VERIFICATION"
            or clearance["prev_hash"] != verification["row_hash"]
            or not isinstance(verification_payload, dict)
            or verification_payload.get("run_id") != candidate.run_id
            or verification_payload.get("candidate_id") != candidate.candidate_id
            or verification_payload.get("candidate_sha256") != candidate.cas_artifact_hash
            or verification_payload.get("verdict") != "PASS"
            or verification_payload.get("evidence_hashes") != [item.hash for item in evidence]
        ):
            fail("L13_VERIFICATION")
        goal_id = verification_payload.get("goal_id")
        if not isinstance(goal_id, str) or not goal_id or clearance_payload.get("goal_id") != goal_id:
            fail("L13_VERIFICATION.goal_id")

        l11_rows = [row for row in rows[:-2] if row["kind"] == "L11_FREEZE"
                    and isinstance(row["payload"], dict)
                    and row["payload"].get("run_id") == candidate.run_id]
        if not l11_rows:
            fail("L11_FREEZE")
        l11 = l11_rows[-1]
        l11_payload = l11["payload"]
        if (
            l11_payload.get("goal_id") != goal_id
            or l11_payload.get("plan_sha256") != candidate.l11_binding_sha256
            or l11_payload.get("manifest_id") != manifest.manifest_id
            or l11_payload.get("manifest_sha256") != manifest.manifest_sha256
            or l11_payload.get("expected_capabilities") != list(manifest.expected_capabilities)
        ):
            fail("L11_FREEZE.binding")
        cas = CAS(FilesystemCasStore(state_dir / "cas"))
        try:
            plan_raw = cas.get(candidate.l11_binding_sha256)
        except Exception:
            fail("L11_FREEZE.plan_cas")
        if hashlib.sha256(plan_raw).hexdigest() != candidate.l11_binding_sha256:
            fail("L11_FREEZE.plan_cas")
        plan = json.loads(plan_raw.decode("utf-8"))
        support = [_json_value(item) for item in candidate.verification_support_files]
        source = [_json_value(item) for item in candidate.verification_source_files]
        obligations = [
            {"claim_id": item.claim_id, "argv": list(item.argv), "timeout_s": item.timeout_s,
             "kind": item.kind.value}
            for item in manifest.verification_obligations
        ]
        if (
            not isinstance(plan, dict)
            or plan.get("candidate_task_identity") != {"goal_id": goal_id, "run_id": candidate.run_id}
            or plan.get("completeness_manifest_sha256") != manifest.manifest_sha256
            or plan.get("expected_capabilities") != list(manifest.expected_capabilities)
            or plan.get("verification_obligations") != obligations
            or plan.get("verification_support_files") != support
            or plan.get("verification_source_files") != source
            or l11_payload.get("verification_support_files")
            != [{"path": x["path"], "file_sha256": x["file_sha256"], "size": x["size"]} for x in support]
            or l11_payload.get("verification_source_files")
            != [{"path": x["path"], "file_sha256": x["file_sha256"], "size": x["size"]} for x in source]
        ):
            fail("L11_FREEZE.plan_identity")

        l10_safe: dict[str, object] | None = None
        l10_refs: tuple[str, ...] = ()
        if "l10_family_match_requires_independent_sealed_context" in manifest.slo_obligations:
            l10_rows = [row for row in rows[: int(verification["seq"]) - 1]
                        if row["kind"] == "L10_SEALED_CONTEXT_OBSERVED"
                        and isinstance(row["payload"], dict)
                        and row["payload"].get("run_id") == candidate.run_id]
            if len(l10_rows) != 1:
                fail("l10_family_match_requires_independent_sealed_context")
            l10 = l10_rows[0]
            lp = l10["payload"]
            ref = lp.get("ref")
            task_id = lp.get("task_id")
            if lp.get("goal_id") != goal_id or not isinstance(task_id, str) or not task_id or not isinstance(ref, str):
                fail("L10_SEALED_CONTEXT_OBSERVED.binding")
            try:
                envelope_raw = cas.get(ref)
            except Exception:
                fail("L10_SEALED_CONTEXT_OBSERVED.cas")
            if hashlib.sha256(envelope_raw).hexdigest() != ref:
                fail("L10_SEALED_CONTEXT_OBSERVED.cas")
            envelope = json.loads(envelope_raw.decode("utf-8"))
            if (
                not isinstance(envelope, dict)
                or envelope.get("schema") != "paeos.l10-sealed-context-execution/1"
                or envelope.get("run_id") != candidate.run_id
                or envelope.get("goal_id") != goal_id
                or envelope.get("task_id") != task_id
                or not isinstance(envelope.get("authorization"), dict)
                or not isinstance(envelope.get("context_refs"), list)
                or not envelope["context_refs"]
                or not isinstance(envelope.get("observation"), dict)
                or "transcript" in envelope["observation"]
            ):
                fail("L10_SEALED_CONTEXT_OBSERVED.envelope")
            l10_refs = (ref,)
            l10_safe = {
                "ledger": {"seq": l10["seq"], "row_hash": l10["row_hash"]},
                "ref": ref, "schema": envelope["schema"], "task_id": task_id,
                "goal_id": goal_id, "run_id": candidate.run_id,
                "authorization": envelope["authorization"],
                "context_refs": envelope["context_refs"],
                "observation": envelope["observation"],
                "trace_sha256": envelope.get("trace_sha256"),
                "request_sha256": envelope.get("request_sha256"),
                "response_sha256": envelope.get("response_sha256"),
            }

        evidence_refs = tuple(item.hash for item in evidence)
        pre_e2e = {
            "production_intake": (_observation_digest(
                "production-intake", {"goal_id": goal_id, "run_id": candidate.run_id,
                                      "ledger_head": verification["row_hash"]}),),
            "l11_manifest_freeze": (candidate.l11_binding_sha256,),
            "l12_implementation": (candidate.cas_artifact_hash,),
            "l13_physical_verification": (_observation_digest("l13-physical-verification", evidence_refs),),
        }
        pre_slo = {
            "no_expected_result_injection": (_observation_digest(
                "physical-verifier-observations", tuple(_evidence_to_json(item) for item in evidence)),),
            "sentium_quarantine_preserved": (_observation_digest(
                "candidate-quarantine-scope",
                tuple({"path": item.path, "file_sha256": item.file_sha256}
                      for item in candidate.changed_files)),),
        }
        pre_slo.update(physical_slo_observations(evidence))
        if l10_refs:
            pre_slo["l10_family_match_requires_independent_sealed_context"] = l10_refs
        bundle = _derive_runtime_completeness_bundle(
            manifest=manifest, candidate=candidate, evidence=evidence,
            transport_kinds=("SUBPROCESS_RUN", "SQLITE_WAL_LEDGER"),
            transport_observation_refs={"SUBPROCESS_RUN": evidence_refs,
                                        "SQLITE_WAL_LEDGER": (verification["row_hash"],)},
            e2e_observations=pre_e2e, slo_observations=pre_slo, cas=cas,
        )
        verdict = CompletenessFirewall().verify_pre_audit_completeness(bundle=bundle, manifest=manifest)
        if not verdict.passed or verdict.violations:
            fail("CompletenessFirewall:" + "|".join(verdict.violations))
        if not pre_audit.passed or pre_audit.violations:
            fail("pre_audit.PASS")
        if verdict.evidence_bundle_sha256 != pre_audit.evidence_bundle_sha256:
            fail("pre_audit.evidence_bundle_sha256")
        bundle_json = _json_value(bundle)
        return {
            "schema": "paeos.p1-l14-runtime-projection/1",
            "bundle": bundle_json,
            "bundle_sha256": _canonical_sha256(bundle_json),
            "ledger": {
                "l11_freeze": {"seq": l11["seq"], "row_hash": l11["row_hash"]},
                "l13_verification": {"seq": verification["seq"], "row_hash": verification["row_hash"]},
                "l13_clearance": {"seq": clearance["seq"], "row_hash": clearance["row_hash"]},
            },
            "l11": {"plan_sha256": candidate.l11_binding_sha256,
                    "manifest_sha256": manifest.manifest_sha256},
            "l10": l10_safe,
            "evidence_bundle_sha256": verdict.evidence_bundle_sha256,
        }
    except AuditorReceiptError:
        raise
    except Exception as exc:
        raise AuditorReceiptError(
            f"L14 runtime projection missing proof: {type(exc).__name__}"
        ) from None


def _safe_physical_path(path: Path, *, directory: bool = False) -> None:
    """Reject links anywhere in an existing absolute path without resolving through them."""
    if not path.is_absolute():
        raise AuditorReceiptError("L14 disclosure binding path is unsafe")
    cursor = Path(path.anchor)
    try:
        for part in path.parts[1:]:
            cursor /= part
            if cursor.is_symlink():
                raise AuditorReceiptError("L14 disclosure binding path is unsafe")
        valid = path.is_dir() if directory else path.is_file()
    except OSError as exc:
        raise AuditorReceiptError("L14 disclosure binding path is unavailable") from exc
    if not valid:
        raise AuditorReceiptError("L14 disclosure binding path is unavailable")


def _contains_excluded_domain_material(content: str) -> bool:
    """Identify actual excluded-domain material without rejecting policy vocabulary."""
    def remove_exact_negative_literal(match: re.Match[str]) -> str:
        try:
            value = ast.literal_eval(match.group(0))
        except (SyntaxError, ValueError):
            return match.group(0)
        return "" if value == _EXACT_NEGATIVE_SCOPE_SENTENCE else match.group(0)

    scanned = content.replace(_EXACT_NEGATIVE_SCOPE_SENTENCE, "")
    scanned = _BOUNDED_PAREN_LITERAL.sub(remove_exact_negative_literal, scanned)

    def remove_vocabulary_set(match: re.Match[str]) -> str:
        try:
            value = ast.literal_eval(match.group(0))
        except (SyntaxError, ValueError):
            return match.group(0)
        if (
            isinstance(value, set)
            and value
            and all(isinstance(item, str) for item in value)
            and {item.casefold() for item in value}.issubset(_VOCABULARY_SET)
        ):
            return ""
        return match.group(0)

    scanned = _BOUNDED_SET_LITERAL.sub(remove_vocabulary_set, scanned)
    lowered = scanned.lower()
    if _EXCLUDED_DOMAIN_CONTENT.search(scanned):
        return True
    if "founder ecosystem target architecture" in lowered and re.search(
        r"(?is)sentium.{0,160}\bpurpose\b|\bpurpose\b.{0,160}sentium", scanned
    ):
        return True
    for line in scanned.splitlines():
        path_like = line.lower()
        for match in _PATH_TOKEN.finditer(line):
            parts = {
                part.casefold()
                for part in re.split(r"[/\\]+", match.group(0).strip(".?!"))
                if part
            }
            if "sentium" in parts and parts.intersection(
                {"strategy", "capital", "execution", "trading", "order"}
            ):
                return True
        if "auth.json" in path_like and any(
            marker in path_like for marker in ("content", "private", "secret", "token", "key")
        ):
            return True
    return False


def build_l14_catalog(preview: bool = False) -> ModelCatalog:
    """Construct the fail-closed catalog; preview is admitted only by its witness validator."""
    if preview:
        raise AuditorReceiptError("preview admission requires the pinned qualification witness")
    return ModelCatalog()


def _preview_catalog() -> ModelCatalog:
    catalog = ModelCatalog()
    catalog.register(
        ModelCatalogEntry(
            model_id=_L14_PREVIEW_MODEL, provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI, cost_tier=CostTier.FREE,
            pricing_verified_free=True, live_verified=True, available=True,
            admission_state=AdmissionState.ADMITTED, context_window=1_048_576,
            supports_tools=True, supports_json=True,
            entitlement_notes="Saved public qualification; restricted to exact root06 L14 binding.",
        )
    )
    return catalog


def _validate_preview_qualification(repo_root: Path) -> ModelCatalog:
    """Validate the saved public capability witness without treating it as root06 evidence."""
    root = repo_root / _L14_PREVIEW_QUALIFICATION
    paths: dict[str, Path] = {}
    for name, expected in _L14_PREVIEW_QUALIFICATION_HASHES.items():
        path = root / name
        _safe_physical_path(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise AuditorReceiptError(f"L14 preview qualification artifact is not pinned: {name}")
        paths[name] = path

    identity = json.loads(paths["physical-identity.json"].read_text(encoding="utf-8"))
    preflight = json.loads(paths["preflight.json"].read_text(encoding="utf-8"))
    adjudication = json.loads(paths["local-adjudication.json"].read_text(encoding="utf-8"))
    if identity != {
        "actual_model": _L14_PREVIEW_MODEL, "attempts": 1,
        "configured_model": _L14_PREVIEW_MODEL,
        "fallback_chain": [f"google:{_L14_PREVIEW_MODEL}"],
        "family": "gemini", "provider": "google",
    }:
        raise AuditorReceiptError("L14 preview physical identity is invalid")
    if (
        preflight.get("schema") != "paeos.bounded-auditor-qualification/1"
        or preflight.get("authority_sha256") != _L14_PREVIEW_AUTHORIZATION_SHA256
        or preflight.get("data_class") != "PUBLIC"
        or preflight.get("recipient") != f"google:{_L14_PREVIEW_MODEL}"
        or preflight.get("request_sha256") != _L14_PREVIEW_PUBLIC_SCOPE_SHA256
        or preflight.get("fallback") is not False
        or preflight.get("paid_usage") is not False
        or preflight.get("probe_limit") != 1
        or preflight.get("production_admission") is not False
        or preflight.get("historical_root_mutation") is not False
        or preflight.get("repository_payload_records") != 0
        or preflight.get("purpose") != "public synthetic L14 role/output probe, not P1 audit"
    ):
        raise AuditorReceiptError("L14 preview preflight is invalid")
    if (
        adjudication.get("status") != "PUBLIC_ROLE_CONTRACT_PROVEN"
        or adjudication.get("actual_model") != _L14_PREVIEW_MODEL
        or adjudication.get("a08") != "PASS"
        or adjudication.get("report_status") != "BLOCKED_UNQUALIFIABLE"
        or adjudication.get("provider_calls_this_adjudication") != 0
        or adjudication.get("private_packet_sent") is not False
        or adjudication.get("production_eligible") is not False
    ):
        raise AuditorReceiptError("L14 preview local adjudication is invalid")

    catalog = _preview_catalog()
    contract = AuditorReceiptContract(
        audit_id="debt0248-preview-public-qualification-02",
        candidate_sha256=_L14_PREVIEW_PUBLIC_CANDIDATE_SHA256,
        evidence_bundle_sha256=_L14_PREVIEW_PUBLIC_EVIDENCE_SHA256,
        review_scope_sha256=_L14_PREVIEW_PUBLIC_SCOPE_SHA256,
        builder_provider="openai", builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT, expected_worker_counts=(0, 0, 0),
        expected_court_counts=(0, 0, 0),
    )
    receipt = load_auditor_receipt(paths["validated-public-receipt.json"])
    report = paths["observed-report.md"].read_text(encoding="utf-8")
    status = validate_auditor_report(report, contract)
    if status is AuditorReportStatus.PASS:
        raise AuditorReceiptError("L14 preview synthetic report must be non-PASS")
    if receipt.report_sha256 != hashlib.sha256(report.encode("utf-8")).hexdigest():
        raise AuditorReceiptError("L14 preview report binding mismatch")
    if (
        receipt.configured_provider_id is not ProviderId.GOOGLE
        or receipt.actual_provider_id is not ProviderId.GOOGLE
        or receipt.configured_model_id != _L14_PREVIEW_MODEL
        or receipt.actual_model_id != _L14_PREVIEW_MODEL
        or receipt.actual_family is not ModelFamily.GEMINI
    ):
        raise AuditorReceiptError("L14 preview receipt route is invalid")
    validate_auditor_receipt(receipt, contract, catalog, require_report_binding=True)
    return catalog


def _bind_l14_transmission(
    *,
    repo_root: Path,
    state_dir: Path,
    candidate: CandidateMaterialization,
    pre_audit: PreAuditVerdict,
    evidence: tuple[Evidence, ...],
    manifest: AuthoritativeCapabilityManifest,
    request: TaskRequest,
    contract: AuditorReceiptContract,
    projection: dict[str, object] | None = None,
    runtime_projection: dict[str, object] | None = None,
    continuation_proof: ContinuationProof | None = None,
    audit_dir: Path | None = None,
) -> ModelCatalog:
    """Bind the sole authorized L14 disclosure before credentials or transports exist."""
    try:
        _safe_physical_path(repo_root, directory=True)
        _safe_physical_path(state_dir, directory=True)
        if repo_root != repo_root.resolve() or state_dir != state_dir.resolve():
            raise AuditorReceiptError("L14 disclosure roots are not canonical")
        if not _SAFE_ID.fullmatch(candidate.run_id) or not _SAFE_ID.fullmatch(candidate.candidate_id):
            raise AuditorReceiptError("L14 disclosure identity is unsafe")

        selected_model = request.explicit_model
        if selected_model not in {_L14_DEFAULT_MODEL, _L14_PREVIEW_MODEL}:
            raise AuditorReceiptError("L14 auditor model is not authorized")
        preview = selected_model == _L14_PREVIEW_MODEL
        authorization_path = (
            repo_root / "reviews/governance/P1_DEBT0248_PARALLEL_RECOVERY_AUTHORIZATION_20260919.md"
            if preview
            else repo_root / ".state-p1-l14-disclosure-authorization-20260917" / "authorization.json"
        )
        _safe_physical_path(authorization_path)
        authorization_raw = authorization_path.read_bytes()
        authorization_sha256 = (
            _L14_PREVIEW_AUTHORIZATION_SHA256 if preview else _L14_AUTHORIZATION_SHA256
        )
        if hashlib.sha256(authorization_raw).hexdigest() != authorization_sha256:
            raise AuditorReceiptError("L14 disclosure authorization is not the pinned record")
        if preview:
            if (
                candidate.run_id != _L14_PREVIEW_RUN_ID
                or candidate.candidate_id != _L14_PREVIEW_CANDIDATE_ID
                or candidate.cas_artifact_hash != _L14_PREVIEW_CANDIDATE_SHA256
            ):
                raise AuditorReceiptError("L14 preview authorization is not for this root06 candidate")
            authorization_id = "founder-p1-l14-preview-root06-20260919"
        else:
            authorization = json.loads(authorization_raw.decode("utf-8"))
            if not isinstance(authorization, dict):
                raise AuditorReceiptError("L14 disclosure authorization is malformed")
            if (
                authorization.get("schema") != "paeos.p1-l14-founder-disclosure-authorization/1"
                or authorization.get("authorization_id")
                != "founder-p1-l14-gemini36-20260917-01"
                or authorization.get("revision") != 1
            ):
                raise AuditorReceiptError("L14 disclosure authorization identity is invalid")
            if authorization.get("route") != {
                "provider_id": "google", "model_id": _L14_DEFAULT_MODEL,
                "model_family": "gemini", "recipient": "Google AI Studio",
                "fallback_allowed": False, "additional_routes_allowed": False,
            } or authorization.get("task") != {
                "role": "AUDITOR", "purpose": "independent L14 P1 completeness audit",
                "disclosure_class": "REDACTED_INTERNAL_ENGINEERING_SOURCE",
                "sensitivity": "INTERNAL",
            }:
                raise AuditorReceiptError("L14 disclosure authorization dimensions are invalid")
            scope = authorization.get("scope")
            if (
                not isinstance(scope, dict)
                or scope.get("scope_kind") != "exact-current-P1-candidate-and-direct-L13-audit-evidence"
                or scope.get("fresh_attempt_identity_required") is not True
                or scope.get("composition_source") != "ops/p1_runtime_l14_audit.py"
                or scope.get("composition_symbols")
                != ["_AUTHORITY_FILES", "_CANDIDATE_FILES", "_build_evidence_content"]
                or scope.get("composition_source_sha256") != _L14_SOURCE_PIN
            ):
                raise AuditorReceiptError("L14 disclosure authorization dimensions are invalid")
            authorization_id = "founder-p1-l14-gemini36-20260917-01"

        fileset = {"authority": list(_AUTHORITY_FILES), "candidate": list(_CANDIDATE_FILES)}
        if _canonical_sha256(fileset) != _L14_FILESET_SHA256:
            raise AuditorReceiptError("L14 disclosure file set is not frozen")

        candidate_root = state_dir / "candidates" / candidate.candidate_id
        if candidate.metadata_path != candidate_root / "candidate.json" or candidate.candidate_workspace != candidate_root / "workspace":
            raise AuditorReceiptError("L14 candidate path binding is invalid")
        _safe_physical_path(candidate_root, directory=True)
        _safe_physical_path(candidate.metadata_path)
        _safe_physical_path(candidate.candidate_workspace, directory=True)
        verify_candidate_integrity(
            candidate,
            run_id=candidate.run_id,
            cas=CAS(FilesystemCasStore(state_dir / "cas")),
        )

        fingerprint = request_fingerprint(request)
        if (
            request.data_class is not DataClass.INTERNAL
            or request.task_class is not TaskClass.AUDIT
            or request.logical_model is not LogicalModel.PAEOS_AUDIT
            or request.builder_family is not ModelFamily.GPT
            or request.allow_fallback
            or request.retry_policy is not RetryPolicy.NONE
            or request.require_tools
            or request.tools is not None
            or request.tool_choice is not None
            or request.stream
            or request.metadata != {}
            or request.allow_paid_usage is not False
            or request.free_worker_pool is not False
        ):
            raise AuditorReceiptError("L14 transmission request is outside authorization")
        if (
            contract.builder_family is not ModelFamily.GPT
            or contract.builder_provider != "openai"
            or contract.builder_model_id != candidate.builder_identity
            or contract.expected_worker_counts != (1, 0, 0)
            or contract.expected_court_counts != (1, 0, 0)
        ):
            raise AuditorReceiptError("L14 builder contract is outside authorization")
        if (
            contract.audit_id != f"p1-l14-{candidate.run_id}"
            or contract.candidate_sha256 != candidate.cas_artifact_hash
            or contract.evidence_bundle_sha256 != pre_audit.evidence_bundle_sha256
            or contract.review_scope_sha256 != fingerprint
            or not pre_audit.passed
            or pre_audit.violations
        ):
            raise AuditorReceiptError("L14 receipt contract is not current")
        if not evidence or any(item.artifact_hash != candidate.cas_artifact_hash for item in evidence):
            raise AuditorReceiptError("L14 evidence is not candidate-bound")

        if (projection is None) != (runtime_projection is None):
            raise AuditorReceiptError("L14 projection binding is incomplete")
        if projection is not None and runtime_projection is not None:
            projection_authorization_path = (
                repo_root / "reviews/governance/P1_L14_PROJECTION_AUTHORIZATION_20260919.md"
            )
            _safe_physical_path(projection_authorization_path)
            projection_authorization_raw = projection_authorization_path.read_bytes()
            if hashlib.sha256(projection_authorization_raw).hexdigest() != _L14_PROJECTION_AUTHORIZATION_SHA256:
                raise AuditorReceiptError("L14 projection authorization is not the pinned record")
            _verify_p1_projection(
                projection, repo_root=repo_root, candidate=candidate, pre_audit=pre_audit,
                evidence=evidence, manifest=manifest,
            )
            expected_runtime = _project_p1_runtime_evidence(
                state_dir=state_dir, candidate=candidate, pre_audit=pre_audit,
                evidence=evidence, manifest=manifest, continuation_proof=continuation_proof,
            )
            if runtime_projection != expected_runtime:
                raise AuditorReceiptError("L14 runtime projection verification mismatch")
            evidence_content = projection["packet"] + "\n\n" + json.dumps(
                runtime_projection, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            )
            expected_prompt = build_substantive_audit_prompt(
                candidate.cas_artifact_hash, pre_audit.evidence_bundle_sha256, evidence_content,
                worker_counts=(1, 0, 0), court_counts=(1, 0, 0),
            )
            expected_system = (
                "You are the independent non-GPT PAEOS Layer 14 auditor. Review only the"
                " embedded packet, do not modify files, invoke tools, or claim authority."
            )
            if request.messages != [
                {"role": "system", "content": expected_system},
                {"role": "user", "content": expected_prompt},
            ]:
                raise AuditorReceiptError("L14 projected prompt binding mismatch")

        messages_bytes = json.dumps(
            request.messages, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        raw_contents = [message.get("content", "") for message in request.messages]
        if any(not isinstance(content, str) for content in raw_contents):
            raise AuditorReceiptError("L14 disclosure packet contains unauthorized material")
        packet = "\n".join(raw_contents)
        if (
            _redact(packet) != packet
            or _PRIVATE_KEY.search(packet)
            or _contains_excluded_domain_material(packet)
            or authorization_raw.decode("utf-8") in packet
            or (
                projection is not None
                and projection_authorization_raw.decode("utf-8") in packet
            )
        ):
            raise AuditorReceiptError("L14 disclosure packet contains unauthorized material")

        ledger_path = state_dir / "ledger.db"
        _safe_physical_path(ledger_path)
        with sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True) as connection:
            connection.execute("BEGIN")
            ledger_rows = connection.execute(
                "SELECT seq,timestamp,prev_hash,row_hash,schema_ver,kind,payload "
                "FROM ledger_rows ORDER BY seq"
            ).fetchall()
        previous_hash = GENESIS_HASH
        latest_verification: tuple[int, str, dict[str, object]] | None = None
        for expected_seq, row in enumerate(ledger_rows, start=1):
            seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload_raw = row
            payload = json.loads(payload_raw)
            if (
                not isinstance(seq, int)
                or isinstance(seq, bool)
                or seq != expected_seq
                or not isinstance(timestamp, str)
                or not isinstance(prev_hash, str)
                or prev_hash != previous_hash
                or not isinstance(row_hash, str)
                or not isinstance(schema_ver, int)
                or isinstance(schema_ver, bool)
                or not isinstance(kind, str)
                or not isinstance(payload, dict)
            ):
                raise AuditorReceiptError("L14 ledger chain is invalid")
            event = Event(schema_ver=schema_ver, kind=kind, payload=payload)
            if compute_row_hash(prev_hash, seq, timestamp, event) != row_hash:
                raise AuditorReceiptError("L14 ledger chain is invalid")
            previous_hash = row_hash
            if (
                kind == "L13_VERIFICATION"
                and payload.get("run_id") == candidate.run_id
                and payload.get("candidate_id") == candidate.candidate_id
            ):
                latest_verification = (seq, row_hash, payload)

        required_clearance = {
            "run_id": candidate.run_id,
            "candidate_id": candidate.candidate_id,
            "candidate_sha256": candidate.cas_artifact_hash,
            "evidence_bundle_sha256": pre_audit.evidence_bundle_sha256,
        }
        if not ledger_rows:
            raise AuditorReceiptError("L14 current L13 clearance is absent")
        if continuation_proof is not None:
            ledger_head_seq, _, _, ledger_head_hash, _, _, _ = ledger_rows[-1]
            if (
                ledger_head_seq != continuation_proof.current_head_seq
                or ledger_head_hash != continuation_proof.current_head_sha256
            ):
                raise AuditorReceiptError("L14 continuation proof ledger head drift")
            c_rows = [r for r in ledger_rows if r[0] == continuation_proof.clearance_seq]
            if not c_rows:
                raise AuditorReceiptError("L14 current L13 clearance is absent")
            _, _, _, _, _, clearance_kind, clearance_payload_raw = c_rows[0]
            clearance_payload = json.loads(clearance_payload_raw)
            if (
                clearance_kind != "L13_COMPLETENESS_CLEARED"
                or not isinstance(clearance_payload, dict)
                or any(clearance_payload.get(name) != value for name, value in required_clearance.items())
            ):
                raise AuditorReceiptError("L14 current L13 clearance is absent")
            v_rows = [r for r in ledger_rows if r[0] == continuation_proof.verification_seq]
            if not v_rows:
                raise AuditorReceiptError("L14 current L13 verification is absent")
            verification_seq, _, _, verification_hash, _, _, v_payload_raw = v_rows[0]
            verification_payload = json.loads(v_payload_raw)
        else:
            ledger_head_seq, _, _, ledger_head_hash, _, ledger_head_kind, head_payload_raw = ledger_rows[-1]
            head_payload = json.loads(head_payload_raw)
            if (
                ledger_head_kind != "L13_COMPLETENESS_CLEARED"
                or not isinstance(head_payload, dict)
                or any(head_payload.get(name) != value for name, value in required_clearance.items())
            ):
                raise AuditorReceiptError("L14 current L13 clearance is absent")
            if latest_verification is None:
                raise AuditorReceiptError("L14 current L13 verification is absent")
            verification_seq, verification_hash, verification_payload = latest_verification
        if (
            verification_payload.get("candidate_sha256") != candidate.cas_artifact_hash
            or verification_payload.get("verdict") != "PASS"
            or verification_payload.get("evidence_hashes") != [item.hash for item in evidence]
        ):
            raise AuditorReceiptError("L14 current L13 verification is invalid")

        catalog = _validate_preview_qualification(repo_root) if preview else build_l14_catalog()
        catalog_entry = catalog.get(selected_model)
        if (
            catalog_entry is None
            or catalog_entry.provider_id is not ProviderId.GOOGLE
            or catalog_entry.family is not ModelFamily.GEMINI
            or catalog_entry.context_window != 1_048_576
        ):
            raise AuditorReceiptError("L14 authorized catalog route is unavailable")

        evidence_hash = _canonical_sha256(_evidence_json(evidence))
        metadata_hash = hashlib.sha256(candidate.metadata_path.read_bytes()).hexdigest()
        binding = {
            "schema": "paeos.p1-l14-disclosure-binding/1",
            "repo_root": str(repo_root),
            "repo_root_sha256": hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest(),
            "state_root": str(state_dir),
            "state_root_sha256": hashlib.sha256(str(state_dir).encode("utf-8")).hexdigest(),
            "authority_source_sha256": _L14_SOURCE_PIN,
            "run_id": candidate.run_id,
            "candidate_id": candidate.candidate_id,
            "candidate_cas_sha256": candidate.cas_artifact_hash,
            "candidate_metadata_sha256": metadata_hash,
            "l13_evidence_bundle_sha256": pre_audit.evidence_bundle_sha256,
            "evidence_tuple_sha256": evidence_hash,
            "manifest_sha256": manifest.manifest_sha256,
            "request_fingerprint": fingerprint,
            "request_metadata": request.metadata,
            "request_allow_paid_usage": request.allow_paid_usage,
            "request_free_worker_pool": request.free_worker_pool,
            "ledger_head_seq": ledger_head_seq,
            "ledger_head_sha256": ledger_head_hash,
            "l13_verification_seq": verification_seq,
            "l13_verification_sha256": verification_hash,
            "prompt_sha256": hashlib.sha256(
                str(request.messages[-1].get("content", "")).encode("utf-8")
            ).hexdigest(),
            "messages_sha256": hashlib.sha256(messages_bytes).hexdigest(),
            "authorization": {
                "id": authorization_id,
                "revision": 1,
                "raw_sha256": authorization_sha256,
                "provider": "google",
                "model": selected_model,
                "family": "gemini",
                "recipient": "Google AI Studio",
                "role": "AUDITOR",
                "purpose": "independent L14 P1 completeness audit",
                "content_class": "REDACTED_INTERNAL_ENGINEERING_SOURCE",
                "data_class": "INTERNAL",
                "scope": "exact-current-P1-candidate-and-direct-L13-audit-evidence",
                "fallback": False,
            },
            "provider_attempts": 1,
        }
        if continuation_proof is not None:
            binding["continuation_proof_sha256"] = continuation_proof.proof_sha256

        if audit_dir is None:
            if continuation_proof is not None:
                audit_dir = state_dir / "l14-resume-attempts" / continuation_proof.proof_sha256
            else:
                audit_dir = state_dir / "l14-audits" / candidate.run_id
        audit_dir = audit_dir.resolve()
        try:
            audit_dir.relative_to(state_dir.resolve())
        except ValueError:
            raise AuditorReceiptError("L14 audit dir is not within state dir")
        if audit_dir.is_symlink():
            raise AuditorReceiptError("L14 disclosure binding parent is unsafe")
        audit_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        binding_path = audit_dir / "disclosure-binding.json"
        projection_path = audit_dir / "projection.json"
        if binding_path.exists() or projection_path.exists():
            raise AuditorReceiptError("L14 disclosure provenance already exists")
        if projection is not None and runtime_projection is not None:
            projection_record = {
                "schema": "paeos.p1-l14-bound-projection/1",
                "projection": projection,
                "runtime_projection": runtime_projection,
                "evidence_content_sha256": hashlib.sha256(evidence_content.encode("utf-8")).hexdigest(),
            }
            projection_bytes = (
                json.dumps(projection_record, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            projection_fd = os.open(
                projection_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            try:
                offset = 0
                while offset < len(projection_bytes):
                    count = os.write(projection_fd, projection_bytes[offset:])
                    if count <= 0:
                        raise OSError("short L14 projection write")
                    offset += count
                os.fsync(projection_fd)
            finally:
                os.close(projection_fd)
            if projection_path.read_bytes() != projection_bytes:
                raise AuditorReceiptError("L14 projection verification failed")
            binding.update({
                "projection_authorization_sha256": _L14_PROJECTION_AUTHORIZATION_SHA256,
                "projection_file_sha256": hashlib.sha256(projection_bytes).hexdigest(),
                "projection_packet_sha256": projection["packet_sha256"],
                "projection_source_set_sha256": projection["source_set_sha256"],
                "projection_full_source_set_sha256": projection["full_source_set_sha256"],
                "projection_rule_sha256": projection["rule_sha256"],
                "projection_rule_implementation_sha256": projection["rule_implementation_sha256"],
                "projection_coverage_sha256": projection["coverage_sha256"],
                "runtime_projection_sha256": _canonical_sha256(runtime_projection),
                "runtime_bundle_sha256": runtime_projection["bundle_sha256"],
                "outbound_evidence_content_sha256": projection_record["evidence_content_sha256"],
            })
        binding_bytes = (json.dumps(binding, sort_keys=True, separators=(",", ":")) + "\n").encode()
        fd = os.open(binding_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            written = 0
            while written < len(binding_bytes):
                count = os.write(fd, binding_bytes[written:])
                if count <= 0:
                    raise OSError("short L14 disclosure binding write")
                written += count
            os.fsync(fd)
        finally:
            os.close(fd)
        parent_fd = os.open(audit_dir, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        if binding_path.read_bytes() != binding_bytes:
            raise AuditorReceiptError("L14 disclosure binding verification failed")
        return catalog
    except AuditorReceiptError as exc:
        raise AuditorReceiptError(str(exc)) from None
    except (OSError, ValueError, TypeError, KeyError, AttributeError, sqlite3.Error):
        raise AuditorReceiptError("L14 disclosure binding could not be established") from None


def _audit_candidate_impl(
    *,
    repo_root: Path,
    state_dir: Path,
    candidate: CandidateMaterialization,
    pre_audit: PreAuditVerdict,
    evidence: tuple[Evidence, ...],
    manifest: AuthoritativeCapabilityManifest,
    auditor_model: str = _L14_DEFAULT_MODEL,
    continuation_proof: ContinuationProof | None = None,
    audit_dir: Path | None = None,
) -> L14AuditArtifacts:
    """Perform exactly one no-fallback Gemini audit and persist an immutable artifact pair."""
    projection = _project_p1_evidence(
        repo_root=repo_root,
        candidate=candidate,
        pre_audit=pre_audit,
        evidence=evidence,
        manifest=manifest,
    )
    _verify_p1_projection(
        projection, repo_root=repo_root, candidate=candidate, pre_audit=pre_audit,
        evidence=evidence, manifest=manifest,
    )
    runtime_projection = _project_p1_runtime_evidence(
        state_dir=state_dir,
        candidate=candidate,
        pre_audit=pre_audit,
        evidence=evidence,
        manifest=manifest,
        continuation_proof=continuation_proof,
    )
    evidence_content = projection["packet"] + "\n\n" + json.dumps(
        runtime_projection, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    prompt = build_substantive_audit_prompt(
        candidate.cas_artifact_hash,
        pre_audit.evidence_bundle_sha256,
        evidence_content,
        worker_counts=(1, 0, 0),
        court_counts=(1, 0, 0),
    )
    request = TaskRequest(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the independent non-GPT PAEOS Layer 14 auditor. Review only the"
                    " embedded packet, do not modify files, invoke tools, or claim authority."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        task_class=TaskClass.AUDIT,
        data_class=DataClass.INTERNAL,
        logical_model=LogicalModel.PAEOS_AUDIT,
        explicit_model=auditor_model,
        builder_family=ModelFamily.GPT,
        max_tokens=8000,
        temperature=0.0,
        retry_policy=RetryPolicy.NONE,
        allow_fallback=False,
    )
    audit_id = f"p1-l14-{candidate.run_id}"
    contract = AuditorReceiptContract(
        audit_id=audit_id,
        candidate_sha256=candidate.cas_artifact_hash,
        evidence_bundle_sha256=pre_audit.evidence_bundle_sha256,
        review_scope_sha256=request_fingerprint(request),
        builder_provider="openai",
        builder_model_id=candidate.builder_identity,
        builder_family=ModelFamily.GPT,
        expected_worker_counts=(1, 0, 0),
        expected_court_counts=(1, 0, 0),
    )
    if audit_dir is None:
        if continuation_proof is not None:
            audit_dir = state_dir / "l14-resume-attempts" / continuation_proof.proof_sha256
        else:
            audit_dir = state_dir / "l14-audits" / candidate.run_id
    audit_dir = audit_dir.resolve()
    catalog = _bind_l14_transmission(
        repo_root=repo_root,
        state_dir=state_dir,
        candidate=candidate,
        pre_audit=pre_audit,
        evidence=evidence,
        manifest=manifest,
        request=request,
        contract=contract,
        projection=projection,
        runtime_projection=runtime_projection,
        continuation_proof=continuation_proof,
        audit_dir=audit_dir,
    )
    router_db_path = (
        (audit_dir / "l14-router.sqlite3")
        if continuation_proof is not None
        else (state_dir / "l14-router.sqlite3")
    )
    router = ModelRouter(
        credentials=CredentialStore(),
        catalog=catalog,
        state_db=RouterStateDB(router_db_path),
    )
    interaction = capture_auditor_interaction(router, contract, request)
    if (
        interaction.receipt.actual_provider_id.value != "google"
        or interaction.receipt.actual_model_id != auditor_model
        or interaction.receipt.actual_family is not ModelFamily.GEMINI
    ):
        raise AuditorReceiptError("L14 physical route did not return the admitted Gemini auditor")
    validate_auditor_report(interaction.response_content, contract)
    bound = bind_auditor_report(interaction.receipt, interaction.response_content)
    validate_auditor_receipt(bound, contract, router.catalog, require_report_binding=True)
    report_path = audit_dir / "report.md"
    receipt_path = audit_dir / "receipt.json"
    persist_auditor_report(interaction.response_content, report_path)
    persist_auditor_receipt(bound, receipt_path)
    return L14AuditArtifacts(receipt_path=receipt_path, report_path=report_path, contract=contract)


def audit_candidate(
    *,
    repo_root: Path,
    state_dir: Path,
    candidate: CandidateMaterialization,
    pre_audit: PreAuditVerdict,
    evidence: tuple[Evidence, ...],
    manifest: AuthoritativeCapabilityManifest,
    auditor_model: str = _L14_DEFAULT_MODEL,
    continuation_proof: ContinuationProof | None = None,
    audit_dir: Path | None = None,
) -> L14AuditArtifacts:
    """Run the L14 guard while preserving a content-free, fail-closed error boundary."""
    try:
        return _audit_candidate_impl(
            repo_root=repo_root,
            state_dir=state_dir,
            candidate=candidate,
            pre_audit=pre_audit,
            evidence=evidence,
            manifest=manifest,
            auditor_model=auditor_model,
            continuation_proof=continuation_proof,
            audit_dir=audit_dir,
        )
    except Exception:
        raise AuditorReceiptError("L14 audit failed closed") from None
