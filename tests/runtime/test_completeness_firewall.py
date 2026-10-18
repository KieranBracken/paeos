"""CANARY negative & positive acceptance tests for PAEOS Completeness Firewall.

Proves fail-closed discrimination across all 7 mandatory completeness invariants:
1. Blocks unreachable phantom adapters (imported only by tests/unverified).
2. Blocks undisclosed production stub fallbacks.
3. Blocks hardcoded authoritative UI metrics.
4. Blocks claimed cross-system integrations implemented only with fixtures.
5. Blocks omitted capabilities lacking explicit disposition or debt entry.
6. Blocks completion claims lacking required E2E evidence.
7. Blocks promotion when L14 provenance is invalid, synthetic, or same-family.
8. Allows positive fully-qualified pre-audit and promotion runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import Role, StageId, WeightClass
from nacl.signing import SigningKey
from paeos.model_router.auditor_receipt import (
    AuditorReceiptContract,
    AuditorReceiptError,
    bind_auditor_report,
    persist_auditor_receipt,
    persist_auditor_report,
    sign_auditor_receipt,
    validate_auditor_receipt,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.types import ModelFamily, ProviderId
from runtime.claude_code import AgentWrite, RunOutput
from runtime.court.completeness_firewall import (
    CapabilityDisposition,
    CompletenessFirewall,
    OperationalTransportProof,
    PathInspectionResult,
    PreAuditCompletenessBundle,
    SystemProfileTag,
    create_authoritative_manifest,
    manifest_candidate_binding_sha256,
)
from runtime.orchestrator import RunStatus, SoftLoop
from runtime.sidecar_scorer import SidecarStageScorer
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus


@pytest.fixture
def firewall() -> CompletenessFirewall:
    return CompletenessFirewall(ModelCatalog())


def test_positive_pre_audit_and_promotion_clears(firewall: CompletenessFirewall, tmp_path: Path) -> None:
    """Positive test: fully compliant bundle and genuine L14 receipt clears both gates."""
    candidate_sha = "a" * 40
    evidence_sha = "b" * 64

    bundle = PreAuditCompletenessBundle(
        milestone_id="M-POSITIVE-01",
        candidate_sha=candidate_sha,
        profiles=(SystemProfileTag.PROFILE_USER_FACING,),
        capabilities=(
            CapabilityDisposition(
                capability_id="CAP-01",
                system_id="PAEOS",
                status="IMPLEMENTED",
            ),
        ),
        transports=(
            OperationalTransportProof(
                adapter_name="orca_mission_adapter",
                transport_kind="SQLITE_WAL",
                caller_entrypoint="app.orchestrator",
                is_test_only=False,
                verified=True,
            ),
        ),
        path_inspections=(
            PathInspectionResult(
                path="frontend/src/Dashboard.tsx",
                has_undisclosed_synthetic_fallback=False,
                has_hardcoded_authoritative_metric=False,
            ),
        ),
        e2e_evidence_hashes=("e2e-" + "c" * 60,),
    )

    pre_verdict = firewall.verify_pre_audit_completeness(bundle)
    assert pre_verdict.passed is True
    assert len(pre_verdict.violations) == 0

    # Build genuine auditor pair
    report_content = f"""Candidate SHA: {candidate_sha}
Evidence Bundle SHA-256: {evidence_sha}
L14_STATUS: PASS
Worker: Admitted: 1 | Rejected: 0 | Remediated: 0
Court: Sealed: 1 | Remanded: 0 | Remediated: 0

### Audit Findings
Substantive verification confirmed that all requirements are satisfied.

AUDIT_COMPLETE: true"""

    contract = AuditorReceiptContract(
        audit_id="audit-positive-01",
        candidate_sha256=candidate_sha,
        evidence_bundle_sha256=evidence_sha,
        review_scope_sha256="d" * 64,
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
    )

    from paeos.model_router.auditor_receipt import PhysicalAuditorReceipt
    raw_receipt = PhysicalAuditorReceipt(
        schema="paeos.auditor-physical-receipt/1",
        audit_id="audit-positive-01",
        invocation_id="audit-positive-01:inv01",
        session_id="audit-positive-01-sess01",
        candidate_sha256=candidate_sha,
        evidence_bundle_sha256=evidence_sha,
        review_scope_sha256="d" * 64,
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
        configured_provider_id=ProviderId.GOOGLE,
        configured_model_id="gemini-3.6-flash",
        actual_provider_id=ProviderId.GOOGLE,
        actual_model_id="gemini-3.6-flash",
        actual_family=ModelFamily.GEMINI,
        transport_id="paeos-model-router:google:gemini-3.6-flash:t01",
        provider_attempt_count=1,
        fallback_chain=("google:gemini-3.6-flash",),
        transport_request_sha256="d" * 64,
        transport_response_sha256="e" * 64,
        transcript_sha256="3507e0c0af18d8d54c9c27c100e7e54dad433e1c9c1515627a633800975e7a57",
        host_turn_uuid="12345678-1234-5678-1234-567812345678",
        external_generation_id="gen-positive-control-01",
        captured_at_unix=1788730000.0,
        a08_verdict="PASS",
    )
    signed_receipt = sign_auditor_receipt(raw_receipt)
    bound_receipt = bind_auditor_report(signed_receipt, report_content)

    report_path = tmp_path / "report.md"
    receipt_path = tmp_path / "receipt.json"
    persist_auditor_report(report_content, report_path)
    persist_auditor_receipt(bound_receipt, receipt_path)

    promo_verdict = firewall.verify_promotion_completeness(
        pre_verdict, receipt_path, report_path, contract
    )
    assert promo_verdict.passed is True
    assert promo_verdict.l13_cleared is True
    assert promo_verdict.l14_qualified is True


def test_canary_blocks_unreachable_phantom_adapter(firewall: CompletenessFirewall) -> None:
    """CANARY 1: Blocks when adapter is test-only or unverified in production call-graph."""
    bundle = PreAuditCompletenessBundle(
        milestone_id="M-CANARY-01",
        candidate_sha="a" * 40,
        profiles=(),
        capabilities=(),
        transports=(
            OperationalTransportProof(
                adapter_name="contracts/phantom_adapter.py",
                transport_kind="NONE",
                caller_entrypoint="tests/test_phantom.py",
                is_test_only=True,
                verified=False,
            ),
        ),
        path_inspections=(),
    )
    verdict = firewall.verify_pre_audit_completeness(bundle)
    assert verdict.passed is False
    assert any("CF-02: Unreachable phantom adapter detected" in v for v in verdict.violations)


def test_canary_blocks_undisclosed_production_stub_fallback(firewall: CompletenessFirewall) -> None:
    """CANARY 2: Blocks when undisclosed stub fallback is detected in authoritative paths."""
    bundle = PreAuditCompletenessBundle(
        milestone_id="M-CANARY-02",
        candidate_sha="a" * 40,
        profiles=(),
        capabilities=(),
        transports=(),
        path_inspections=(
            PathInspectionResult(
                path="backend/app/agents/stub_adapter.py",
                has_undisclosed_synthetic_fallback=True,
                details="Silently returns canned success response on missing agent CLI",
            ),
        ),
    )
    verdict = firewall.verify_pre_audit_completeness(bundle)
    assert verdict.passed is False
    assert any("CF-03: Undisclosed synthetic fallback in authoritative path" in v for v in verdict.violations)


def test_canary_blocks_hardcoded_authoritative_ui_metric(firewall: CompletenessFirewall) -> None:
    """CANARY 3: Blocks when hardcoded mock metrics exist in authoritative UI paths."""
    bundle = PreAuditCompletenessBundle(
        milestone_id="M-CANARY-03",
        candidate_sha="a" * 40,
        profiles=(),
        capabilities=(),
        transports=(),
        path_inspections=(
            PathInspectionResult(
                path="frontend/src/IdeaOsDashboard.tsx",
                has_hardcoded_authoritative_metric=True,
                details="Hardcoded £679 EOM spend in production view",
            ),
        ),
    )
    verdict = firewall.verify_pre_audit_completeness(bundle)
    assert verdict.passed is False
    assert any("CF-03: Hardcoded authoritative metric in UI/reporting path" in v for v in verdict.violations)


def test_canary_blocks_cross_system_integration_with_fixtures_only(firewall: CompletenessFirewall) -> None:
    """CANARY 4: Blocks when cross-boundary integration relies purely on test fixtures."""
    bundle = PreAuditCompletenessBundle(
        milestone_id="M-CANARY-04",
        candidate_sha="a" * 40,
        profiles=(SystemProfileTag.PROFILE_CROSS_BOUNDARY,),
        capabilities=(),
        transports=(
            OperationalTransportProof(
                adapter_name="cross_adapter",
                transport_kind="FIXTURE_REPLAY",
                caller_entrypoint="tests",
                is_test_only=False,
                verified=True,
            ),
        ),
        path_inspections=(),
        fixtures_only=True,
        e2e_evidence_hashes=("e2e-hash",),
    )
    verdict = firewall.verify_pre_audit_completeness(bundle)
    assert verdict.passed is False
    assert any("CF-04: Cross-boundary system claims integration but relies exclusively on synthetic fixtures" in v for v in verdict.violations)


def test_canary_blocks_omitted_capabilities_without_disposition(firewall: CompletenessFirewall) -> None:
    """CANARY 5: Blocks when intended capabilities are omitted without explicit disposition or debt."""
    bundle = PreAuditCompletenessBundle(
        milestone_id="M-CANARY-05",
        candidate_sha="a" * 40,
        profiles=(),
        capabilities=(
            CapabilityDisposition(
                capability_id="CAP-LINEAGE-MUTATION",
                system_id="IDEA_GRAPH",
                status="OMITTED",
                debt_id=None,
            ),
        ),
        transports=(),
        path_inspections=(),
        unresolved_omissions=("CAP-LINEAGE-MUTATION",),
    )
    verdict = firewall.verify_pre_audit_completeness(bundle)
    assert verdict.passed is False
    assert any("CF-01: Capability omission lacking explicit disposition" in v for v in verdict.violations)


def test_canary_blocks_completion_claims_lacking_e2e_evidence(firewall: CompletenessFirewall) -> None:
    """CANARY 6: Blocks completion claim for user-facing system lacking E2E evidence."""
    bundle = PreAuditCompletenessBundle(
        milestone_id="M-CANARY-06",
        candidate_sha="a" * 40,
        profiles=(SystemProfileTag.PROFILE_USER_FACING,),
        capabilities=(),
        transports=(),
        path_inspections=(),
        e2e_evidence_hashes=(),  # Missing E2E evidence!
    )
    verdict = firewall.verify_pre_audit_completeness(bundle)
    assert verdict.passed is False
    assert any("CF-05: Mandatory end-to-end evidence missing for declared system profile" in v for v in verdict.violations)


def test_canary_blocks_invalid_synthetic_l14_provenance(firewall: CompletenessFirewall, tmp_path: Path) -> None:
    """CANARY 7: Blocks promotion if L14 auditor receipt is same-family (e.g. GPT checking GPT)."""
    candidate_sha = "a" * 40
    evidence_sha = "b" * 64

    # Valid pre-audit bundle
    bundle = PreAuditCompletenessBundle(
        milestone_id="M-CANARY-07",
        candidate_sha=candidate_sha,
        profiles=(),
        capabilities=(),
        transports=(),
        path_inspections=(),
    )
    pre_verdict = firewall.verify_pre_audit_completeness(bundle)
    assert pre_verdict.passed is True

    # Same-family receipt (Builder = GPT, Auditor = GPT)
    contract = AuditorReceiptContract(
        audit_id="audit-canary-07",
        candidate_sha256=candidate_sha,
        evidence_bundle_sha256=evidence_sha,
        review_scope_sha256="d" * 64,
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
    )

    report_content = f"""Candidate SHA: {candidate_sha}
Evidence Bundle SHA-256: {evidence_sha}
L14_STATUS: PASS
Worker: Admitted: 1 | Rejected: 0 | Remediated: 0
Court: Sealed: 1 | Remanded: 0 | Remediated: 0

### Audit Findings
Synthetic audit findings.

AUDIT_COMPLETE: true"""

    from paeos.model_router.auditor_receipt import PhysicalAuditorReceipt
    raw_receipt = PhysicalAuditorReceipt(
        schema="paeos.auditor-physical-receipt/1",
        audit_id="audit-canary-07",
        invocation_id="audit-canary-07:inv01",
        session_id="audit-canary-07-sess01",
        candidate_sha256=candidate_sha,
        evidence_bundle_sha256=evidence_sha,
        review_scope_sha256="d" * 64,
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
        configured_provider_id=ProviderId.OPENROUTER,
        configured_model_id="openai/gpt-4o",
        actual_provider_id=ProviderId.OPENROUTER,
        actual_model_id="openai/gpt-4o",
        actual_family=ModelFamily.GPT,  # SAME FAMILY!
        transport_id="paeos-model-router:openrouter:gpt-4o:t01",
        provider_attempt_count=1,
        fallback_chain=("openrouter:openai/gpt-4o",),
        transport_request_sha256="d" * 64,
        transport_response_sha256="e" * 64,
        transcript_sha256="f" * 64,
        captured_at_unix=1788730000.0,
        a08_verdict="PASS",
    )
    signed_receipt = sign_auditor_receipt(raw_receipt)
    bound_receipt = bind_auditor_report(signed_receipt, report_content)

    report_path = tmp_path / "report.md"
    receipt_path = tmp_path / "receipt.json"
    persist_auditor_report(report_content, report_path)
    persist_auditor_receipt(bound_receipt, receipt_path)

    promo_verdict = firewall.verify_promotion_completeness(
        pre_verdict, receipt_path, report_path, contract
    )
    assert promo_verdict.passed is False
    assert promo_verdict.l14_qualified is False
    assert any("L16-BLOCK: Invalid or synthetic L14 auditor receipt/report" in v for v in promo_verdict.violations)


def test_canary_blocks_omitted_capabilities_from_authoritative_manifest(
    firewall: CompletenessFirewall,
) -> None:
    """CANARY 8 (Point 3): Blocks when capability in authoritative manifest is omitted from bundle,
    even if the caller did not disclose it in unresolved_omissions (eliminates the omission tautology).
    """
    manifest = create_authoritative_manifest(
        manifest_id="MANIFEST-M1",
        milestone_id="M-AUTH-01",
        expected_capabilities=("CAP-ORCA-01", "CAP-ORCA-02", "CAP-ORCA-03"),
        required_profiles=(SystemProfileTag.PROFILE_USER_FACING,),
    )

    # Caller only supplies CAP-ORCA-01, silently omitting CAP-ORCA-02 and CAP-ORCA-03
    # and leaving unresolved_omissions empty.
    bundle = PreAuditCompletenessBundle(
        milestone_id="M-AUTH-01",
        candidate_sha="a" * 40,
        profiles=(SystemProfileTag.PROFILE_USER_FACING,),
        capabilities=(
            CapabilityDisposition(
                capability_id="CAP-ORCA-01",
                system_id="ORCA",
                status="IMPLEMENTED",
                observation_refs=("c" * 64,),
            ),
        ),
        transports=(
            OperationalTransportProof(
                adapter_name="orca_adapter",
                transport_kind="SQLITE_WAL",
                caller_entrypoint="app.main",
                is_test_only=False,
                verified=True,
            ),
        ),
        path_inspections=(),
        e2e_evidence_hashes=("e2e-hash",),
        unresolved_omissions=(),  # Caller tried to hide the omissions!
    )

    verdict = firewall.verify_pre_audit_completeness(bundle, manifest=manifest)
    assert verdict.passed is False
    assert any(
        "CF-01: Authoritative capability missing from bundle: CAP-ORCA-02 (omission not represented)"
        in v
        for v in verdict.violations
    )
    assert any(
        "CF-01: Authoritative capability missing from bundle: CAP-ORCA-03 (omission not represented)"
        in v
        for v in verdict.violations
    )


def test_manifest_candidate_binding_is_required_and_exact(firewall: CompletenessFirewall) -> None:
    """A manifest cannot be replayed against a different candidate or an empty binding."""
    manifest = create_authoritative_manifest(
        manifest_id="MANIFEST-BINDING-01",
        milestone_id="M-BINDING-01",
        expected_capabilities=("CAP-01",),
    )
    bundle = PreAuditCompletenessBundle(
        milestone_id=manifest.milestone_id,
        candidate_sha="a" * 64,
        profiles=(),
        capabilities=(CapabilityDisposition("CAP-01", "SYS", "IMPLEMENTED", observation_refs=("c" * 64,)),),
        transports=(),
        path_inspections=(),
    )

    missing = firewall.verify_pre_audit_completeness(bundle, manifest=manifest)
    assert missing.passed is False
    assert any("Candidate is not bound to the frozen manifest" in item for item in missing.violations)

    from dataclasses import replace

    bound = replace(
        bundle,
        manifest_candidate_binding_sha256=manifest_candidate_binding_sha256(
            manifest, bundle.candidate_sha
        ),
    )
    accepted = firewall.verify_pre_audit_completeness(bound, manifest=manifest)
    assert accepted.passed is True

    replayed = replace(bound, candidate_sha="b" * 64)
    rejected = firewall.verify_pre_audit_completeness(replayed, manifest=manifest)
    assert rejected.passed is False
    assert any("Candidate is not bound to the frozen manifest" in item for item in rejected.violations)


def test_manifest_coverage_requires_physical_observations_not_flags(
    firewall: CompletenessFirewall,
) -> None:
    """Required transport/E2E/SLO sets cannot be satisfied by caller-controlled booleans."""
    manifest = create_authoritative_manifest(
        manifest_id="MANIFEST-COVERAGE-01",
        milestone_id="M-COVERAGE-01",
        expected_capabilities=("CAP-01",),
        required_transport_kinds=("SUBPROCESS_RUN", "PAEOS_MODEL_ROUTER"),
        required_e2e_classes=("l12_implementation",),
        slo_obligations=("failing_command_remands",),
    )
    bundle = PreAuditCompletenessBundle(
        milestone_id=manifest.milestone_id,
        candidate_sha="a" * 64,
        profiles=(),
        capabilities=(CapabilityDisposition("CAP-01", "SYS", "IMPLEMENTED", observation_refs=("c" * 64,)),),
        transports=(
            OperationalTransportProof(
                "builder",
                "SUBPROCESS_RUN",
                "runtime",
                is_test_only=False,
                verified=True,
            ),
            OperationalTransportProof(
                "router",
                "PAEOS_MODEL_ROUTER",
                "runtime",
                is_test_only=False,
                verified=True,
            ),
        ),
        path_inspections=(),
        manifest_candidate_binding_sha256=manifest_candidate_binding_sha256(
            manifest, "a" * 64
        ),
    )

    verdict = firewall.verify_pre_audit_completeness(bundle, manifest=manifest)
    assert verdict.passed is False
    assert any("no valid physical observation" in item for item in verdict.violations)
    assert any("Required E2E class missing physical evidence" in item for item in verdict.violations)
    assert any("Required SLO observation missing" in item for item in verdict.violations)


def test_manifest_capability_status_cannot_replace_physical_observation(
    firewall: CompletenessFirewall,
) -> None:
    """A favorable status without a verifier-produced observation is still a remand."""
    manifest = create_authoritative_manifest(
        manifest_id="MANIFEST-CAPABILITY-OBSERVATION-01",
        milestone_id="M-CAPABILITY-OBSERVATION-01",
        expected_capabilities=("CAP-01",),
    )
    bundle = PreAuditCompletenessBundle(
        milestone_id=manifest.milestone_id,
        candidate_sha="a" * 64,
        profiles=(),
        capabilities=(CapabilityDisposition("CAP-01", "SYS", "IMPLEMENTED"),),
        transports=(),
        path_inspections=(),
        manifest_candidate_binding_sha256=manifest_candidate_binding_sha256(
            manifest, "a" * 64
        ),
    )

    verdict = firewall.verify_pre_audit_completeness(bundle, manifest=manifest)
    assert verdict.passed is False
    assert any("lacks valid physical observation refs" in item for item in verdict.violations)


def test_path_truth_requires_content_and_observation_hashes(
    firewall: CompletenessFirewall,
) -> None:
    manifest = create_authoritative_manifest(
        manifest_id="MANIFEST-PATH-01",
        milestone_id="M-PATH-01",
        expected_capabilities=("CAP-01",),
    )
    bundle = PreAuditCompletenessBundle(
        milestone_id=manifest.milestone_id,
        candidate_sha="a" * 64,
        profiles=(),
        capabilities=(CapabilityDisposition("CAP-01", "SYS", "IMPLEMENTED", observation_refs=("c" * 64,)),),
        transports=(),
        path_inspections=(PathInspectionResult("runtime/feature.py"),),
        manifest_candidate_binding_sha256=manifest_candidate_binding_sha256(
            manifest, "a" * 64
        ),
    )

    verdict = firewall.verify_pre_audit_completeness(bundle, manifest=manifest)
    assert verdict.passed is False
    assert any("lacks physical content observation" in item for item in verdict.violations)


def test_canary_blocks_unattested_or_forged_auditor_receipt(
    firewall: CompletenessFirewall, tmp_path: Path
) -> None:
    """CANARY 9 (Point 4): Blocks when an auditor receipt lacks genuine kernel/router transport attestation."""
    from paeos.model_router.auditor_receipt import PhysicalAuditorReceipt

    candidate_sha = "a" * 40
    evidence_sha = "b" * 64
    contract = AuditorReceiptContract(
        audit_id="audit-canary-attest",
        candidate_sha256=candidate_sha,
        evidence_bundle_sha256=evidence_sha,
        review_scope_sha256="d" * 64,
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
    )
    raw_receipt = PhysicalAuditorReceipt(
        schema="paeos.auditor-physical-receipt/1",
        audit_id="audit-canary-attest",
        invocation_id="audit-canary-attest:inv01",
        session_id="audit-canary-attest-sess01",
        candidate_sha256=candidate_sha,
        evidence_bundle_sha256=evidence_sha,
        review_scope_sha256="d" * 64,
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
        configured_provider_id=ProviderId.GOOGLE,
        configured_model_id="gemini-3.6-flash",
        actual_provider_id=ProviderId.GOOGLE,
        actual_model_id="gemini-3.6-flash",
        actual_family=ModelFamily.GEMINI,
        transport_id="paeos-model-router:google:gemini-3.6-flash:t01",
        provider_attempt_count=1,
        fallback_chain=("google:gemini-3.6-flash",),
        transport_request_sha256="d" * 64,
        transport_response_sha256="e" * 64,
        transcript_sha256="f" * 64,
        captured_at_unix=1788730000.0,
        a08_verdict="PASS",
    )

    # 1. Unsigned in-memory receipt fails closed
    with pytest.raises(AuditorReceiptError, match="transport attestation missing"):
        validate_auditor_receipt(raw_receipt, contract, firewall.catalog)

    # 2. Receipt signed by an untrusted rogue key fails closed
    rogue_key = SigningKey.generate()
    rogue_signed_receipt = sign_auditor_receipt(raw_receipt, signing_key=rogue_key)
    with pytest.raises(AuditorReceiptError, match="transport attestation verification failed"):
        validate_auditor_receipt(rogue_signed_receipt, contract, firewall.catalog)

    # 3. Validly signed receipt tampered after signature fails closed
    from kernel.keystore import load_or_create_signing_key
    valid_key = load_or_create_signing_key()
    valid_signed_receipt = sign_auditor_receipt(raw_receipt, signing_key=valid_key)
    from dataclasses import replace
    tampered_receipt = replace(valid_signed_receipt, actual_model_id="gemini-3.6-pro")
    with pytest.raises(AuditorReceiptError):
        validate_auditor_receipt(tampered_receipt, contract, firewall.catalog)


# ---- SoftLoop Runtime Integration Helpers & Tests (Point 2) -----------------


class ScriptedRuntime:
    """Scripted AgentRuntime stand-in for SoftLoop tests."""

    def __init__(self, writes_by_stage: dict[StageId, tuple[AgentWrite, ...]]) -> None:
        self._writes = writes_by_stage

    def run(self, package: TaskPackage) -> RunOutput:
        return RunOutput(
            status=TaskStatus.COMPLETE,
            writes=self._writes.get(package.stage, ()),
            evidence=(),
            trace=b"trace-" + package.stage.name.encode(),
            cost=Cost(tokens=1000, wallclock_s=1.0, model_ver="model-x"),
        )


_CODE = b"def feature() -> int:\n    return 42\n"
_ARTIFACT = content_hash(_CODE)


def _evidence(claim_id: str, command: str, stdout: str) -> Evidence:
    return Evidence(
        hash=content_hash(f"{claim_id}:{command}".encode()),
        kind=EvidenceKind.TEST,
        claim_id=claim_id,
        artifact_hash=_ARTIFACT,
        environment_hash="e" * 64,
        reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session="builder"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": stdout},
        attestation="sig",
    )


def _loop_writes() -> dict[StageId, tuple[AgentWrite, ...]]:
    return {
        StageId.RE_DERIVE: (AgentWrite("derive/derive.md", b"derivation"),),
        StageId.IDEATE: (AgentWrite("ideate/ideate.md", b"ideation"),),
        StageId.RESEARCH: (AgentWrite("research/research.md", b"research"),),
        StageId.TRADEOFF: (AgentWrite("tradeoff/tradeoff.md", b"tradeoff"),),
        StageId.MITIGATION: (AgentWrite("mitigation/mitigation.md", b"mitigation"),),
        StageId.DESIGN: (AgentWrite("design/design.md", b"design"),),
        StageId.CRITIQUE: (AgentWrite("critique/critique.md", b"critique"),),
        StageId.PLAN: (AgentWrite("plan/plan.md", b"plan"),),
        StageId.IMPLEMENT: (AgentWrite("runtime/feature.py", _CODE),),
        StageId.ADVERSARIAL_REVIEW: (
            AgentWrite("review/adversary_report.md", b"no dissent\nVERDICT: PASS\n"),
        ),
        StageId.RETROSPECT: (AgentWrite("retrospective/retro.md", b"retrospect"),),
        StageId.MEMORY_UPDATE: (AgentWrite("memory/scar.md", b"scar"),),
    }


def _make_softloop(signing_key: SigningKey) -> tuple[SoftLoop, Ledger]:
    ledger = Ledger(InMemoryLedgerStore())
    loop = SoftLoop(
        ledger=ledger,
        signing_key=signing_key,
        cas=CAS(InMemoryCasStore()),
        agent_runtime=ScriptedRuntime(_loop_writes()),
        budget_by_class={
            WeightClass.ROUTINE: Budget(100_000, 3600, 5),
            WeightClass.SUBSTANTIAL: Budget(300_000, 7200, 5),
            WeightClass.KERNEL_TOUCHING: Budget(600_000, 10800, 5),
        },
        sidecar_scorer=SidecarStageScorer(None),
    )
    return loop, ledger


def test_softloop_pre_audit_completeness_remands_on_omission() -> None:
    """Point 2 (L13): SoftLoop enforces pre-audit completeness and remands on omitted capability."""
    from kernel.keystore import load_or_create_signing_key

    signing_key = load_or_create_signing_key()
    loop, ledger = _make_softloop(signing_key)

    manifest = create_authoritative_manifest(
        manifest_id="MANIFEST-LOOP-01",
        milestone_id="M-LOOP-01",
        expected_capabilities=("CAP-A", "CAP-B"),
    )
    incomplete_bundle = PreAuditCompletenessBundle(
        milestone_id="M-LOOP-01",
        candidate_sha="a" * 40,
        profiles=(),
        capabilities=(
                CapabilityDisposition(
                    capability_id="CAP-A",
                    system_id="SYS",
                    status="IMPLEMENTED",
                    observation_refs=("c" * 64,),
                ),
        ),  # Missing CAP-B!
        transports=(),
        path_inspections=(),
    )

    good_evidence = (_evidence("builds", "echo built", "built\n"),)
    outcome = loop.run(
        objective="test manifest enforcement",
        changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/",),
        builder_evidence=good_evidence,
        capability_manifest=manifest,
        completeness_bundle=incomplete_bundle,
    )

    assert outcome.status is RunStatus.REMANDED
    assert outcome.detail == "completeness firewall L13 pre-audit check failed"
    assert outcome.ephemeral_context is not None
    assert any("CF-01: Authoritative capability missing from bundle: CAP-B" in d for d in outcome.ephemeral_context.diagnostics)

    # Prove L11 frozen event exists in ledger
    events = [row.event for row in ledger.read() if row.event.kind == "COMPLETENESS_MANIFEST_FROZEN"]
    assert len(events) == 1
    assert events[0].payload["manifest_id"] == "MANIFEST-LOOP-01"


def test_softloop_promotion_completeness_remands_on_missing_or_invalid_l14_receipt(
    tmp_path: Path,
) -> None:
    """Point 2 (L16): SoftLoop blocks promotion when L14 receipt is missing or invalid."""
    from kernel.keystore import load_or_create_signing_key

    signing_key = load_or_create_signing_key()
    loop, _ledger = _make_softloop(signing_key)

    manifest = create_authoritative_manifest(
        manifest_id="MANIFEST-LOOP-02",
        milestone_id="M-LOOP-02",
        expected_capabilities=("CAP-A",),
    )
    compliant_bundle = PreAuditCompletenessBundle(
        milestone_id="M-LOOP-02",
        candidate_sha="a" * 40,
        profiles=(),
        capabilities=(
                CapabilityDisposition(
                    capability_id="CAP-A",
                    system_id="SYS",
                    status="IMPLEMENTED",
                    observation_refs=("c" * 64,),
                ),
        ),
        transports=(),
        path_inspections=(),
        manifest_candidate_binding_sha256=manifest_candidate_binding_sha256(
            manifest, "a" * 40
        ),
    )

    good_evidence = (_evidence("builds", "echo built", "built\n"),)

    # 1. Missing L14 receipt artifacts altogether
    outcome = loop.run(
        objective="test l16 promotion gate",
        changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/",),
        builder_evidence=good_evidence,
        capability_manifest=manifest,
        completeness_bundle=compliant_bundle,
    )
    assert outcome.status is RunStatus.REMANDED
    assert "completeness firewall L16 promotion check failed" in outcome.detail


def test_softloop_completeness_passes_and_seals(tmp_path: Path) -> None:
    """Point 2: SoftLoop successfully seals when completeness bundle and attested L14 receipt pass."""
    from kernel.keystore import load_or_create_signing_key
    from paeos.model_router.auditor_receipt import PhysicalAuditorReceipt

    signing_key = load_or_create_signing_key()
    loop, _ledger = _make_softloop(signing_key)

    candidate_sha = "a" * 40
    manifest = create_authoritative_manifest(
        manifest_id="MANIFEST-LOOP-03",
        milestone_id="M-LOOP-03",
        expected_capabilities=("CAP-A",),
    )
    bundle = PreAuditCompletenessBundle(
        milestone_id="M-LOOP-03",
        candidate_sha=candidate_sha,
        profiles=(),
        capabilities=(
            CapabilityDisposition(
                capability_id="CAP-A",
                system_id="SYS",
                status="IMPLEMENTED",
                observation_refs=("c" * 64,),
            ),
        ),
        transports=(),
        path_inspections=(),
        manifest_candidate_binding_sha256=manifest_candidate_binding_sha256(
            manifest, candidate_sha
        ),
    )

    firewall = CompletenessFirewall(ModelCatalog())
    pre_verdict = firewall.verify_pre_audit_completeness(bundle, manifest=manifest)
    assert pre_verdict.passed is True

    contract = AuditorReceiptContract(
        audit_id="audit-loop-03",
        candidate_sha256=candidate_sha,
        evidence_bundle_sha256=pre_verdict.evidence_bundle_sha256,
        review_scope_sha256="d" * 64,
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
    )

    report_content = f"""Candidate SHA: {candidate_sha}
Evidence Bundle SHA-256: {pre_verdict.evidence_bundle_sha256}
L14_STATUS: PASS
Worker: Admitted: 1 | Rejected: 0 | Remediated: 0
Court: Sealed: 1 | Remanded: 0 | Remediated: 0

### Audit Findings
All requirements verified and satisfied.

AUDIT_COMPLETE: true"""

    raw_receipt = PhysicalAuditorReceipt(
        schema="paeos.auditor-physical-receipt/1",
        audit_id="audit-loop-03",
        invocation_id="audit-loop-03:inv01",
        session_id="audit-loop-03-sess01",
        candidate_sha256=candidate_sha,
        evidence_bundle_sha256=pre_verdict.evidence_bundle_sha256,
        review_scope_sha256="d" * 64,
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
        configured_provider_id=ProviderId.GOOGLE,
        configured_model_id="gemini-3.6-flash",
        actual_provider_id=ProviderId.GOOGLE,
        actual_model_id="gemini-3.6-flash",
        actual_family=ModelFamily.GEMINI,
        transport_id="paeos-model-router:google:gemini-3.6-flash:t01",
        provider_attempt_count=1,
        fallback_chain=("google:gemini-3.6-flash",),
        transport_request_sha256="d" * 64,
        transport_response_sha256="e" * 64,
        transcript_sha256="3507e0c0af18d8d54c9c27c100e7e54dad433e1c9c1515627a633800975e7a57",
        host_turn_uuid="12345678-1234-5678-1234-567812345678",
        external_generation_id="gen-positive-control-01",
        captured_at_unix=1788730000.0,
        a08_verdict="PASS",
    )
    signed_receipt = sign_auditor_receipt(raw_receipt, signing_key=signing_key)
    bound_receipt = bind_auditor_report(signed_receipt, report_content, signing_key=signing_key)

    report_path = tmp_path / "report.md"
    receipt_path = tmp_path / "receipt.json"
    persist_auditor_report(report_content, report_path)
    persist_auditor_receipt(bound_receipt, receipt_path)

    good_evidence = (_evidence("builds", "echo built", "built\n"),)
    outcome = loop.run(
        objective="test complete positive run",
        changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/",),
        builder_evidence=good_evidence,
        capability_manifest=manifest,
        completeness_bundle=bundle,
        auditor_receipt_path=receipt_path,
        auditor_report_path=report_path,
        auditor_contract=contract,
    )

    assert outcome.status is RunStatus.SEALED
    assert outcome.seal is not None
