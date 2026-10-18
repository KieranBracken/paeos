"""PAEOS Minimum Completeness Firewall (v2.0).

Canonical Lifecycle Placement:
  - L11: Freeze completeness obligations & derived SLOs
  - L13: PRE_AUDIT_COMPLETENESS (Verification Court pre-audit checks)
  - L14: Independent Heterogeneous Audit (Correctness AND Estate Coverage)
  - L16: PROMOTION_COMPLETENESS (Validates genuine L14 receipt & untainted pre-audit evidence)

Strict Invariant:
  Preserves canonical PAEOS lifecycle L01-L19. No pseudo-layers (e.g. L13-CF).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import uuid

from paeos.model_router.auditor_receipt import (
    AuditorReceiptContract,
    AuditorReceiptError,
    AuditorReportStatus,
    adjudicate_auditor_artifact_pair,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.semantic.freeze_guard import L11FreezeDeniedError, L11SemanticFreezeGuard
from paeos.semantic.types import SemanticObligation, SemanticObligationDisposition


class CompletenessFirewallError(ValueError):
    """Raised when an artifact or milestone violates completeness invariants."""


class SystemProfileTag(StrEnum):
    """Profile tags defining mandatory verification obligations (CF-04)."""
    PROFILE_USER_FACING = "PROFILE_USER_FACING"
    PROFILE_CONCURRENT_STREAMING = "PROFILE_CONCURRENT_STREAMING"
    PROFILE_CROSS_BOUNDARY = "PROFILE_CROSS_BOUNDARY"
    PROFILE_CRITICAL_EXECUTION = "PROFILE_CRITICAL_EXECUTION"
    PROFILE_PERFORMANCE_SENSITIVE = "PROFILE_PERFORMANCE_SENSITIVE"


class VerificationObligationKind(StrEnum):
    """Whether an L11 verifier invocation discriminates a candidate or controls the Court."""

    CANDIDATE_DISCRIMINATION = "CANDIDATE_DISCRIMINATION"
    NEGATIVE_COURT_CONTROL = "NEGATIVE_COURT_CONTROL"


@dataclass(frozen=True, slots=True)
class AuthoritativeCapabilityManifest:
    """Authoritative capability manifest frozen at L11.

    Eliminates the omission tautology: Every capability listed in expected_capabilities
    MUST be explicitly represented in PreAuditCompletenessBundle.capabilities.
    Silently dropping a capability from the bundle fails closed.
    """
    manifest_id: str
    milestone_id: str
    expected_capabilities: tuple[str, ...]
    required_profiles: tuple[SystemProfileTag, ...] = ()
    verification_obligations: tuple[VerificationObligation, ...] = ()
    verification_support_paths: tuple[str, ...] = ()
    verification_source_paths: tuple[str, ...] = ()
    required_transport_kinds: tuple[str, ...] = ()
    pre_audit_transport_kinds: tuple[str, ...] = ()
    post_audit_transport_kinds: tuple[str, ...] = ()
    required_e2e_classes: tuple[str, ...] = ()
    pre_audit_e2e_classes: tuple[str, ...] = ()
    post_audit_e2e_classes: tuple[str, ...] = ()
    slo_obligations: tuple[str, ...] = ()
    pre_audit_slo_obligations: tuple[str, ...] = ()
    post_audit_slo_obligations: tuple[str, ...] = ()
    explicit_exclusions: tuple[str, ...] = ()
    deferred_debt: tuple[str, ...] = ()
    derivation_refs: tuple[str, ...] = ()
    manifest_sha256: str = ""


@dataclass(frozen=True, slots=True)
class VerificationObligation:
    """One L11-frozen physical verifier invocation, expressed without host-specific Python path."""

    claim_id: str
    argv: tuple[str, ...]
    timeout_s: int = 30
    kind: VerificationObligationKind = VerificationObligationKind.CANDIDATE_DISCRIMINATION


def create_authoritative_manifest(
    manifest_id: str,
    milestone_id: str,
    expected_capabilities: tuple[str, ...],
    required_profiles: tuple[SystemProfileTag, ...] = (),
    verification_obligations: tuple[VerificationObligation, ...] = (),
    verification_support_paths: tuple[str, ...] = (),
    verification_source_paths: tuple[str, ...] = (),
    required_transport_kinds: tuple[str, ...] = (),
    pre_audit_transport_kinds: tuple[str, ...] = (),
    post_audit_transport_kinds: tuple[str, ...] = (),
    required_e2e_classes: tuple[str, ...] = (),
    pre_audit_e2e_classes: tuple[str, ...] = (),
    post_audit_e2e_classes: tuple[str, ...] = (),
    slo_obligations: tuple[str, ...] = (),
    pre_audit_slo_obligations: tuple[str, ...] = (),
    post_audit_slo_obligations: tuple[str, ...] = (),
    explicit_exclusions: tuple[str, ...] = (),
    deferred_debt: tuple[str, ...] = (),
    derivation_refs: tuple[str, ...] = (),
) -> AuthoritativeCapabilityManifest:
    payload = {
        "expected_capabilities": sorted(expected_capabilities),
        "manifest_id": manifest_id,
        "milestone_id": milestone_id,
        "required_profiles": sorted(p.value for p in required_profiles),
        "verification_obligations": [
            {
                "claim_id": o.claim_id,
                "argv": list(o.argv),
                "timeout_s": o.timeout_s,
                "kind": o.kind.value,
            }
            for o in sorted(verification_obligations, key=lambda item: item.claim_id)
        ],
        "verification_support_paths": sorted(verification_support_paths),
        "verification_source_paths": sorted(verification_source_paths),
        "required_transport_kinds": sorted(required_transport_kinds),
        "pre_audit_transport_kinds": sorted(pre_audit_transport_kinds),
        "post_audit_transport_kinds": sorted(post_audit_transport_kinds),
        "required_e2e_classes": sorted(required_e2e_classes),
        "pre_audit_e2e_classes": sorted(pre_audit_e2e_classes),
        "post_audit_e2e_classes": sorted(post_audit_e2e_classes),
        "slo_obligations": sorted(slo_obligations),
        "pre_audit_slo_obligations": sorted(pre_audit_slo_obligations),
        "post_audit_slo_obligations": sorted(post_audit_slo_obligations),
        "explicit_exclusions": sorted(explicit_exclusions),
        "deferred_debt": sorted(deferred_debt),
        "derivation_refs": sorted(derivation_refs),
    }
    sha256 = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return AuthoritativeCapabilityManifest(
        manifest_id=manifest_id,
        milestone_id=milestone_id,
        expected_capabilities=expected_capabilities,
        required_profiles=required_profiles,
        verification_obligations=verification_obligations,
        verification_support_paths=verification_support_paths,
        verification_source_paths=verification_source_paths,
        required_transport_kinds=required_transport_kinds,
        pre_audit_transport_kinds=pre_audit_transport_kinds,
        post_audit_transport_kinds=post_audit_transport_kinds,
        required_e2e_classes=required_e2e_classes,
        pre_audit_e2e_classes=pre_audit_e2e_classes,
        post_audit_e2e_classes=post_audit_e2e_classes,
        slo_obligations=slo_obligations,
        pre_audit_slo_obligations=pre_audit_slo_obligations,
        post_audit_slo_obligations=post_audit_slo_obligations,
        explicit_exclusions=explicit_exclusions,
        deferred_debt=deferred_debt,
        derivation_refs=derivation_refs,
        manifest_sha256=sha256,
    )


def load_authoritative_manifest(path: Path) -> AuthoritativeCapabilityManifest:
    """Load and hash-check the Founder-derived manifest; malformed state fails closed."""
    if path.is_symlink() or not path.is_file():
        raise CompletenessFirewallError(f"authoritative manifest is missing or unsafe: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CompletenessFirewallError("authoritative manifest is not valid UTF-8 JSON") from exc
    if not isinstance(raw, dict) or raw.get("schema") != "paeos.authoritative-completeness-manifest/1":
        raise CompletenessFirewallError("authoritative manifest schema is invalid")
    expected = raw.get("expected_capability_ids")
    profiles = raw.get("required_profiles")
    obligations = raw.get("verification_obligations")
    support_paths = raw.get("verification_support_paths", [])
    source_paths = raw.get("verification_source_paths", [])
    if (
        not isinstance(expected, list)
        or not expected
        or any(not isinstance(item, str) or not item for item in expected)
        or len(set(expected)) != len(expected)
        or not isinstance(profiles, list)
        or any(not isinstance(item, str) or not item for item in profiles)
        or len(set(profiles)) != len(profiles)
        or not isinstance(obligations, list)
        or len(obligations) != len(expected)
        or not isinstance(support_paths, list)
        or any(not isinstance(item, str) or not item for item in support_paths)
        or len(set(support_paths)) != len(support_paths)
        or not isinstance(source_paths, list)
        or any(not isinstance(item, str) or not item for item in source_paths)
        or len(set(source_paths)) != len(source_paths)
    ):
        raise CompletenessFirewallError("authoritative manifest obligation set is malformed")
    parsed_obligations: list[VerificationObligation] = []
    for item in obligations:
        if not isinstance(item, dict) or not isinstance(item.get("claim_id"), str):
            raise CompletenessFirewallError("authoritative verifier obligation is malformed")
        try:
            kind = VerificationObligationKind(item.get("kind"))
        except (TypeError, ValueError) as exc:
            raise CompletenessFirewallError(
                "authoritative verifier obligation kind is missing or invalid"
            ) from exc
        argv = item.get("argv")
        timeout = item.get("timeout_s", 30)
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(arg, str) or not arg for arg in argv)
            or "-c" in argv
            or any(any(character in arg for character in ";&|$<>\n\r") for arg in argv)
            or not isinstance(timeout, int)
            or timeout <= 0
        ):
            raise CompletenessFirewallError("authoritative verifier argv or timeout is malformed")
        parsed_obligations.append(
            VerificationObligation(item["claim_id"], tuple(argv), timeout, kind)
        )
    if len({item.claim_id for item in parsed_obligations}) != len(parsed_obligations):
        raise CompletenessFirewallError("verifier obligations contain duplicate claim IDs")
    if {item.claim_id for item in parsed_obligations} != set(expected):
        raise CompletenessFirewallError("verifier obligations do not exactly cover expected capabilities")
    for source_path in source_paths:
        source = Path(source_path)
        if source.is_absolute() or source == Path(".") or ".." in source.parts:
            raise CompletenessFirewallError("authoritative verification source path is unsafe")
    list_fields = (
        "required_transport_kinds",
        "pre_audit_transport_kinds",
        "post_audit_transport_kinds",
        "required_e2e_classes",
        "pre_audit_e2e_classes",
        "post_audit_e2e_classes",
        "slo_obligations",
        "pre_audit_slo_obligations",
        "post_audit_slo_obligations",
        "explicit_exclusions",
        "deferred_debt",
        "derivation_refs",
    )
    parsed_lists: dict[str, tuple[str, ...]] = {}
    for field_name in list_fields:
        value = raw.get(field_name, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise CompletenessFirewallError(f"authoritative manifest field is malformed: {field_name}")
        if len(set(value)) != len(value):
            raise CompletenessFirewallError(f"authoritative manifest field contains duplicates: {field_name}")
        parsed_lists[field_name] = tuple(value)
    manifest_id = raw.get("manifest_id")
    milestone_id = raw.get("milestone_id")
    if not isinstance(manifest_id, str) or not isinstance(milestone_id, str):
        raise CompletenessFirewallError("authoritative manifest identity is malformed")
    try:
        parsed_profiles = tuple(SystemProfileTag(item) for item in profiles)
    except (TypeError, ValueError) as exc:
        raise CompletenessFirewallError("authoritative manifest profile is invalid") from exc
    manifest = create_authoritative_manifest(
        manifest_id=manifest_id,
        milestone_id=milestone_id,
        expected_capabilities=tuple(expected),
        required_profiles=parsed_profiles,
        verification_obligations=tuple(parsed_obligations),
        verification_support_paths=tuple(support_paths),
        verification_source_paths=tuple(source_paths),
        required_transport_kinds=parsed_lists["required_transport_kinds"],
        pre_audit_transport_kinds=parsed_lists["pre_audit_transport_kinds"],
        post_audit_transport_kinds=parsed_lists["post_audit_transport_kinds"],
        required_e2e_classes=parsed_lists["required_e2e_classes"],
        pre_audit_e2e_classes=parsed_lists["pre_audit_e2e_classes"],
        post_audit_e2e_classes=parsed_lists["post_audit_e2e_classes"],
        slo_obligations=parsed_lists["slo_obligations"],
        pre_audit_slo_obligations=parsed_lists["pre_audit_slo_obligations"],
        post_audit_slo_obligations=parsed_lists["post_audit_slo_obligations"],
        explicit_exclusions=parsed_lists["explicit_exclusions"],
        deferred_debt=parsed_lists["deferred_debt"],
        derivation_refs=parsed_lists["derivation_refs"],
    )
    if "candidate_sha256" in raw:
        raise CompletenessFirewallError(
            "candidate identity must be bound at L13 to the materialized candidate, not frozen as stale L11 metadata"
        )
    for all_name, pre_name, post_name in (
        ("required_transport_kinds", "pre_audit_transport_kinds", "post_audit_transport_kinds"),
        ("required_e2e_classes", "pre_audit_e2e_classes", "post_audit_e2e_classes"),
        ("slo_obligations", "pre_audit_slo_obligations", "post_audit_slo_obligations"),
    ):
        all_items = set(parsed_lists[all_name])
        pre_items = set(parsed_lists[pre_name])
        post_items = set(parsed_lists[post_name])
        if (pre_items | post_items) != all_items or pre_items & post_items:
            raise CompletenessFirewallError(
                f"authoritative manifest {pre_name}/{post_name} partition is invalid"
            )
    if not manifest.manifest_id or not manifest.milestone_id or raw.get("manifest_sha256") != manifest.manifest_sha256:
        raise CompletenessFirewallError("authoritative manifest hash or identity is invalid")
    return manifest


@dataclass(frozen=True, slots=True)
class CapabilityDisposition:
    """Explicit disposition for an intended capability (CF-01)."""
    capability_id: str
    system_id: str
    status: str  # e.g., "IMPLEMENTED", "PRESERVED_AS_IS", "DEFERRED", "DEBT_RECORDED"
    debt_id: str | None = None
    notes: str = ""
    observation_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OperationalTransportProof:
    """Proof of physical runtime reachability (CF-02)."""
    adapter_name: str
    transport_kind: str  # "IPC", "SHARED_MEMORY", "SQLITE_WAL", "IN_PROCESS", "OUTBOX", "HTTP"
    caller_entrypoint: str
    is_test_only: bool = False
    verified: bool = True
    observation_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PathInspectionResult:
    """Inspection of authoritative paths for undisclosed stubs or hardcoded metrics (CF-03)."""
    path: str
    has_undisclosed_synthetic_fallback: bool = False
    has_hardcoded_authoritative_metric: bool = False
    details: str = ""
    content_sha256: str = ""
    observation_sha256: str = ""


@dataclass(frozen=True, slots=True)
class PreAuditCompletenessBundle:
    """Evidence bundle evaluated at L13 prior to external audit dispatch."""
    milestone_id: str
    candidate_sha: str
    profiles: tuple[SystemProfileTag, ...]
    capabilities: tuple[CapabilityDisposition, ...]
    transports: tuple[OperationalTransportProof, ...]
    path_inspections: tuple[PathInspectionResult, ...]
    e2e_evidence_hashes: tuple[str, ...] = ()
    fixtures_only: bool = False
    unresolved_omissions: tuple[str, ...] = ()
    manifest_candidate_binding_sha256: str = ""
    e2e_observations: tuple[tuple[str, tuple[str, ...]], ...] = ()
    slo_observations: tuple[tuple[str, tuple[str, ...]], ...] = ()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def manifest_candidate_binding_sha256(
    manifest: AuthoritativeCapabilityManifest, candidate_sha: str
) -> str:
    """Bind an L11-frozen obligation manifest to one materialized L12 candidate.

    The candidate does not exist when L11 freezes the obligation set, so this digest is created
    at L12 and verified at L13/L16.  It prevents a valid obligation manifest from being replayed
    against a different candidate without changing the authoritative evidence identity.
    """
    if not (
        isinstance(candidate_sha, str)
        and len(candidate_sha) in (40, 64)
        and all(character in "0123456789abcdef" for character in candidate_sha)
    ):
        raise CompletenessFirewallError("candidate identity must be a SHA digest")
    return hashlib.sha256(
        f"paeos.manifest-candidate-binding/1\0{manifest.manifest_sha256}\0{candidate_sha}".encode(
            "ascii"
        )
    ).hexdigest()


def _coverage_map(
    observations: tuple[tuple[str, tuple[str, ...]], ...], label: str, violations: list[str]
) -> dict[str, tuple[str, ...]]:
    coverage: dict[str, tuple[str, ...]] = {}
    for key, refs in observations:
        if key in coverage:
            violations.append(f"{label}: duplicate observation for {key}")
            continue
        if not refs or any(not _is_sha256(ref) for ref in refs):
            violations.append(f"{label}: observation for {key} lacks valid physical evidence refs")
        coverage[key] = refs
    return coverage


def _required_or_all(preferred: tuple[str, ...], all_items: tuple[str, ...]) -> tuple[str, ...]:
    """Return explicit stage coverage, retaining compatibility with older manifests."""
    return preferred or all_items


def _verify_manifest_coverage(
    *,
    bundle: PreAuditCompletenessBundle,
    manifest: AuthoritativeCapabilityManifest,
    phase: str,
    violations: list[str],
) -> None:
    if bundle.manifest_candidate_binding_sha256 != manifest_candidate_binding_sha256(
        manifest, bundle.candidate_sha
    ):
        violations.append(
            f"CF-01: Candidate is not bound to the frozen manifest for {phase} coverage"
        )

    for capability in bundle.capabilities:
        if not capability.observation_refs or any(
            not _is_sha256(ref) for ref in capability.observation_refs
        ):
            violations.append(
                f"CF-01: Capability {capability.capability_id} lacks valid physical observation refs"
            )

    transport_observations: dict[str, tuple[str, ...]] = {}
    for transport in bundle.transports:
        if transport.transport_kind in transport_observations:
            violations.append(
                f"CF-02: Duplicate physical transport observation: {transport.transport_kind}"
            )
        if not transport.observation_refs or any(
            not _is_sha256(ref) for ref in transport.observation_refs
        ):
            violations.append(
                f"CF-02: Transport {transport.transport_kind} has no valid physical observation"
            )
        transport_observations[transport.transport_kind] = transport.observation_refs

    required_transports = _required_or_all(
        getattr(manifest, f"{phase}_audit_transport_kinds"), manifest.required_transport_kinds
    )
    for required in required_transports:
        if required not in transport_observations:
            violations.append(f"CF-02: Required physical transport missing: {required}")

    e2e = _coverage_map(bundle.e2e_observations, "CF-05 E2E", violations)
    required_e2e = _required_or_all(
        getattr(manifest, f"{phase}_audit_e2e_classes"), manifest.required_e2e_classes
    )
    for required in required_e2e:
        if required not in e2e:
            violations.append(f"CF-05: Required E2E class missing physical evidence: {required}")

    slo = _coverage_map(bundle.slo_observations, "CF-05 SLO", violations)
    required_slos = _required_or_all(
        getattr(manifest, f"{phase}_audit_slo_obligations"), manifest.slo_obligations
    )
    for required in required_slos:
        if required not in slo:
            violations.append(f"CF-05: Required SLO observation missing: {required}")

    for inspection in bundle.path_inspections:
        if not _is_sha256(inspection.content_sha256) or not _is_sha256(
            inspection.observation_sha256
        ):
            violations.append(
                f"CF-03: Path inspection for {inspection.path} lacks physical content observation"
            )


@dataclass(frozen=True, slots=True)
class PreAuditVerdict:
    """L13 Pre-Audit Completeness Verdict."""
    passed: bool
    violations: tuple[str, ...] = ()
    evidence_bundle_sha256: str = ""


@dataclass(frozen=True, slots=True)
class PromotionCompletenessVerdict:
    """L16 Promotion Completeness Verdict."""
    passed: bool
    l13_cleared: bool
    l14_qualified: bool
    violations: tuple[str, ...] = ()


class CompletenessFirewall:
    """Enforces profile-based completeness invariants across L11, L13, L14, and L16."""

    def __init__(self, catalog: ModelCatalog | None = None) -> None:
        self.catalog = catalog or ModelCatalog()

    def verify_l11_semantic_freeze(
        self,
        manifest: AuthoritativeCapabilityManifest,
        obligations: tuple[SemanticObligation, ...] = (),
        dispositions: tuple[SemanticObligationDisposition, ...] = (),
    ) -> None:
        """Checkpoint L11: Enforce semantic completeness before freezing manifest.

        Fails closed with L11FreezeDeniedError ('L11_FREEZE_DENIED: ...') if any
        capability obligation is omitted, unrepresented, or unlawfully disposed.
        """
        L11SemanticFreezeGuard.validate_freeze(
            manifest_id=manifest.manifest_id,
            expected_capabilities=manifest.expected_capabilities,
            deferred_debt=manifest.deferred_debt,
            obligations=obligations,
            dispositions=dispositions,
        )

    def verify_pre_audit_completeness(
        self,
        bundle: PreAuditCompletenessBundle,
        manifest: AuthoritativeCapabilityManifest | None = None,
    ) -> PreAuditVerdict:
        """Checkpoint A (L13): Validate pre-audit completeness before dispatching L14.

        Enforces:
        - CF-01: Explicit capability disposition against authoritative manifest (no silently omitted capabilities).
        - CF-02: Operational transport proof (rejects phantom adapters imported only by tests).
        - CF-03: No undisclosed synthetic fallbacks or hardcoded authoritative metrics.
        - CF-04: Profile-triggered obligations (rejects claimed integrations with only fixtures).
        - CF-05: Mandatory E2E evidence for completion claims.
        """
        violations: list[str] = []

        # 0. Point 3: Authoritative Capability Manifest Enforcement (eliminates omission tautology)
        if manifest is not None:
            if bundle.milestone_id != manifest.milestone_id:
                violations.append(
                    f"CF-01: Milestone ID mismatch: bundle '{bundle.milestone_id}' != manifest '{manifest.milestone_id}'"
                )
            bundle_cap_ids = {cap.capability_id for cap in bundle.capabilities}
            if len(bundle_cap_ids) != len(bundle.capabilities):
                violations.append("CF-01: Duplicate capability disposition in bundle")
            unexpected = sorted(bundle_cap_ids - set(manifest.expected_capabilities))
            for capability_id in unexpected:
                violations.append(
                    f"CF-01: Capability is not present in authoritative manifest: {capability_id}"
                )
            for expected_cap in manifest.expected_capabilities:
                if expected_cap not in bundle_cap_ids:
                    violations.append(
                        f"CF-01: Authoritative capability missing from bundle: {expected_cap} (omission not represented)"
                    )
            for req_profile in manifest.required_profiles:
                if req_profile not in bundle.profiles:
                    violations.append(
                        f"CF-04: Required profile {req_profile.value} from manifest missing in bundle profiles"
                    )
            try:
                _verify_manifest_coverage(
                    bundle=bundle,
                    manifest=manifest,
                    phase="pre",
                    violations=violations,
                )
            except CompletenessFirewallError as exc:
                violations.append(f"CF-01: {exc}")

        # 1. CF-01: Capability omissions without disposition
        if bundle.unresolved_omissions:
            for omission in bundle.unresolved_omissions:
                violations.append(
                    f"CF-01: Capability omission lacking explicit disposition or debt entry: {omission}"
                )
        for cap in bundle.capabilities:
            if cap.status not in ("IMPLEMENTED", "PRESERVED_AS_IS", "PRESERVED_AND_REINTERPRET") and not cap.debt_id:
                violations.append(
                    f"CF-01: Unmet capability {cap.capability_id} has no associated signed DEBT-xxxx entry"
                )

        # 2. CF-02: Unreachable phantom adapters
        for tr in bundle.transports:
            if tr.is_test_only or not tr.verified:
                violations.append(
                    f"CF-02: Unreachable phantom adapter detected: {tr.adapter_name} imported only in tests or unverified"
                )

        # 3. CF-03: Undisclosed synthetic fallback or hardcoded authoritative metrics
        for insp in bundle.path_inspections:
            if insp.has_undisclosed_synthetic_fallback:
                violations.append(
                    f"CF-03: Undisclosed synthetic fallback in authoritative path: {insp.path} ({insp.details})"
                )
            if insp.has_hardcoded_authoritative_metric:
                violations.append(
                    f"CF-03: Hardcoded authoritative metric in UI/reporting path: {insp.path} ({insp.details})"
                )

        # 4. CF-04: Claimed cross-system integration implemented only with fixtures
        if SystemProfileTag.PROFILE_CROSS_BOUNDARY in bundle.profiles and bundle.fixtures_only:
            violations.append(
                "CF-04: Cross-boundary system claims integration but relies exclusively on synthetic fixtures"
            )

        # 5. CF-05: Missing E2E evidence for user-facing or cross-boundary profile
        if (
            SystemProfileTag.PROFILE_USER_FACING in bundle.profiles
            or SystemProfileTag.PROFILE_CROSS_BOUNDARY in bundle.profiles
        ) and not bundle.e2e_evidence_hashes:
            violations.append(
                "CF-05: Mandatory end-to-end evidence missing for declared system profile"
            )

        # Compute deterministic bundle hash
        bundle_dict = {
            "milestone_id": bundle.milestone_id,
            "candidate_sha": bundle.candidate_sha,
            "manifest_sha256": manifest.manifest_sha256 if manifest is not None else "",
            "profiles": [p.value for p in bundle.profiles],
            "capabilities": [
                {
                    "id": c.capability_id,
                    "status": c.status,
                    "debt": c.debt_id,
                    "observation_refs": list(c.observation_refs),
                }
                for c in bundle.capabilities
            ],
            "transports": [
                {
                    "name": t.adapter_name,
                    "transport": t.transport_kind,
                    "test_only": t.is_test_only,
                    "observation_refs": list(t.observation_refs),
                }
                for t in bundle.transports
            ],
            "manifest_candidate_binding_sha256": bundle.manifest_candidate_binding_sha256,
            "e2e_observations": [
                {"class": key, "evidence_refs": list(refs)}
                for key, refs in bundle.e2e_observations
            ],
            "slo_observations": [
                {"obligation": key, "evidence_refs": list(refs)}
                for key, refs in bundle.slo_observations
            ],
            "violations_count": len(violations),
        }
        bundle_bytes = json.dumps(bundle_dict, sort_keys=True).encode("utf-8")
        evidence_hash = hashlib.sha256(bundle_bytes).hexdigest()

        return PreAuditVerdict(
            passed=(len(violations) == 0),
            violations=tuple(violations),
            evidence_bundle_sha256=evidence_hash,
        )

    def verify_promotion_completeness(
        self,
        pre_audit_verdict: PreAuditVerdict,
        receipt_path: Path,
        report_path: Path,
        contract: AuditorReceiptContract,
        *,
        post_audit_bundle: PreAuditCompletenessBundle | None = None,
        manifest: AuthoritativeCapabilityManifest | None = None,
    ) -> PromotionCompletenessVerdict:
        """Checkpoint B (L16): Validate promotion completeness after L14 completes.

        Blocks promotion unless:
        1. Pre-audit completeness was cleared and remains untainted.
        2. A genuine, qualified L14 Heterogeneous Audit receipt is verified.
        3. Receipt binds the exact report, candidate SHA, and evidence bundle SHA.
        4. Rejects invalid, synthetic, or same-family provenance.
        """
        violations: list[str] = []

        if not pre_audit_verdict.passed:
            violations.append("L16-BLOCK: L13 Pre-Audit Completeness was not cleared or has open violations")

        if post_audit_bundle is not None:
            if manifest is None:
                violations.append("L16-BLOCK: post-audit completeness has no authoritative manifest")
            else:
                try:
                    _verify_manifest_coverage(
                        bundle=post_audit_bundle,
                        manifest=manifest,
                        phase="post",
                        violations=violations,
                    )
                except CompletenessFirewallError as exc:
                    violations.append(f"L16-BLOCK: {exc}")

        l14_qualified, l14_violations = self.verify_l14_heterogeneous_audit(
            receipt_path=receipt_path,
            report_path=report_path,
            contract=contract,
        )
        violations.extend(l14_violations)

        return PromotionCompletenessVerdict(
            passed=(len(violations) == 0 and l14_qualified),
            l13_cleared=pre_audit_verdict.passed,
            l14_qualified=l14_qualified,
            violations=tuple(violations),
        )

    def verify_l14_heterogeneous_audit(
        self,
        receipt_path: Path,
        report_path: Path,
        contract: AuditorReceiptContract,
        *,
        require_external_provenance: bool = True,
        expected_host_turn_uuid: str | None = None,
        expected_transport_request_sha256: str | None = None,
        expected_transport_response_sha256: str | None = None,
        raw_request_bytes: bytes | None = None,
        raw_response_bytes: bytes | None = None,
    ) -> tuple[bool, list[str]]:
        """Verify Layer 14 Heterogeneous Audit physical receipt and external provenance (ELH-01, ELH-03)."""
        violations: list[str] = []
        l14_qualified = False

        if not receipt_path.exists():
            violations.append(f"L16-BLOCK: Missing L14 receipt: {receipt_path}")
            return False, violations
        if not report_path.exists():
            violations.append(f"L16-BLOCK: Missing L14 report: {report_path}")
            return False, violations

        try:
            adjudication = adjudicate_auditor_artifact_pair(
                receipt_path=receipt_path,
                report_path=report_path,
                contract=contract,
                catalog=self.catalog,
            )
            if adjudication.report_status is not AuditorReportStatus.PASS:
                violations.append(
                    "L16-BLOCK: L14 substantive report did not qualify: "
                    f"{adjudication.report_status.value}"
                )
            if adjudication.a08_verdict != "PASS":
                violations.append(
                    f"L16-BLOCK: L14 A-08 decorrelation failed: {adjudication.a08_verdict}"
                )
            if adjudication.qualified:
                l14_qualified = True

            # Check external provenance (ELH-01) if required
            if require_external_provenance:
                if not receipt_path.exists():
                    violations.append("L16-BLOCK: Missing L14 receipt for external provenance verification")
                else:
                    raw_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    gen_id = raw_receipt.get("external_generation_id")
                    if (
                        not gen_id
                        or not str(gen_id).startswith("gen-")
                        or any(kw in str(gen_id).lower() for kw in ("unknown", "none", "mock", "synthetic"))
                    ):
                        violations.append(
                            "L16-BLOCK: Missing or synthetic external generation ID in L14 receipt"
                        )
                    host_turn = raw_receipt.get("host_turn_uuid")
                    if expected_host_turn_uuid is not None:
                        if host_turn != expected_host_turn_uuid:
                            violations.append(
                                f"L16-BLOCK: Mismatched host turn UUID in L14 receipt (expected {expected_host_turn_uuid}, got {host_turn})"
                            )
                    else:
                        is_valid_uuid = False
                        if host_turn and isinstance(host_turn, str):
                            try:
                                u = uuid.UUID(host_turn)
                                is_valid_uuid = (str(u).lower() == host_turn.lower())
                            except ValueError:
                                is_valid_uuid = False
                        if (
                            not host_turn
                            or not is_valid_uuid
                            or host_turn.strip() == "00000000-0000-0000-0000-000000000000"
                            or any(kw in str(host_turn).lower() for kw in ("unknown", "none", "mock", "synthetic", "nil"))
                        ):
                            violations.append(
                                "L16-BLOCK: Missing or synthetic host turn UUID in L14 receipt"
                            )
                    req_sha = raw_receipt.get("transport_request_sha256")
                    res_sha = raw_receipt.get("transport_response_sha256")
                    if not req_sha or not _is_sha256(req_sha):
                        violations.append("L16-BLOCK: Invalid or missing transport request SHA-256")
                    else:
                        exp_req = expected_transport_request_sha256 or getattr(contract, "review_scope_sha256", None)
                        if exp_req and req_sha != exp_req:
                            violations.append(
                                f"L16-BLOCK: Mismatched transport request SHA-256 (expected {exp_req}, got {req_sha})"
                            )
                        if raw_request_bytes is not None:
                            recomputed_req = hashlib.sha256(raw_request_bytes).hexdigest()
                            if req_sha != recomputed_req:
                                violations.append(
                                    f"L16-BLOCK: Transport request SHA-256 does not match raw request bytes (expected {recomputed_req}, got {req_sha})"
                                )
                    if not res_sha or not _is_sha256(res_sha):
                        violations.append("L16-BLOCK: Invalid or missing transport response SHA-256")
                    else:
                        if expected_transport_response_sha256 is not None and res_sha != expected_transport_response_sha256:
                            violations.append(
                                f"L16-BLOCK: Mismatched transport response SHA-256 (expected {expected_transport_response_sha256}, got {res_sha})"
                            )
                        if raw_response_bytes is not None:
                            recomputed_res = hashlib.sha256(raw_response_bytes).hexdigest()
                            if res_sha != recomputed_res:
                                violations.append(
                                    f"L16-BLOCK: Transport response SHA-256 does not match raw response bytes (expected {recomputed_res}, got {res_sha})"
                                )
                    if req_sha and res_sha and _is_sha256(req_sha) and _is_sha256(res_sha):
                        expected_transcript = hashlib.sha256(
                            json.dumps({"request": req_sha, "response": res_sha}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
                        ).hexdigest()
                        transcript_sha = raw_receipt.get("transcript_sha256")
                        if not transcript_sha or transcript_sha != expected_transcript:
                            violations.append(
                                f"L16-BLOCK: Mismatched or invalid transcript SHA-256 in L14 receipt (expected {expected_transcript}, got {transcript_sha})"
                            )
                    if report_path.exists():
                        try:
                            actual_report_sha = hashlib.sha256(report_path.read_bytes()).hexdigest()
                            receipt_rep_sha = raw_receipt.get("report_sha256")
                            if receipt_rep_sha and receipt_rep_sha != actual_report_sha:
                                violations.append(
                                    f"L16-BLOCK: L14 receipt report_sha256 does not match physical report (expected {actual_report_sha}, got {receipt_rep_sha})"
                                )
                        except OSError as exc:
                            violations.append(f"L16-BLOCK: Failed to read L14 report file for hash verification: {exc}")
        except (AuditorReceiptError, ValueError, OSError) as exc:
            violations.append(f"L16-BLOCK: Invalid or synthetic L14 auditor receipt/report: {exc}")

        return l14_qualified and len(violations) == 0, violations
