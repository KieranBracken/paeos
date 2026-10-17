"""Tests for promotion policy and intent encoding (Gate F Task 5)."""

from __future__ import annotations

from kernel.promotion import PromotionIntent


def test_promotion_operation_encoding() -> None:
    from kernel.promotion import PromotionIntent, promotion_operation

    intent = PromotionIntent(
        repository_id="repo-001",
        target_ref="refs/heads/main",
        expected_target_head="0" * 40,
        reviewed_commit="1" * 40,
        disposition_hash="d" * 64,
        rollback_commit="0" * 40,
        health_command_id="pytest-focused",
        expires_seq=100,
    )
    op = promotion_operation(intent)
    assert op.startswith("promote:")
    for value in (
        intent.repository_id,
        intent.target_ref,
        intent.expected_target_head,
        intent.reviewed_commit,
        intent.disposition_hash,
        intent.rollback_commit,
        intent.health_command_id,
        str(intent.expires_seq),
    ):
        assert value in op


def test_evaluate_promotion_is_fail_closed_without_bootstrap() -> None:
    from kernel.promotion import PromotionEvidence, evaluate_promotion

    intent = PromotionIntent(
        repository_id="repo-001",
        target_ref="refs/heads/feature",
        expected_target_head="0" * 40,
        reviewed_commit="1" * 40,
        disposition_hash="d" * 64,
        rollback_commit="2" * 40,
        health_command_id="pytest-focused",
        expires_seq=100,
    )

    reasons = evaluate_promotion(intent, PromotionEvidence())

    assert reasons == ("FOUNDER_BOOTSTRAP_REQUIRED",)


def test_evaluate_promotion_rejects_correlated_risks() -> None:
    from kernel.promotion import PromotionEvidence, evaluate_promotion

    intent = PromotionIntent(
        repository_id="repo-002",
        target_ref="refs/heads/main",
        expected_target_head="0" * 40,
        reviewed_commit="1" * 40,
        disposition_hash="d" * 64,
        rollback_commit="2" * 40,
        health_command_id="pytest-focused",
        expires_seq=100,
    )
    evidence = PromotionEvidence(
        bootstrap_verified=True,
        trace="TRACE_B",
        protected_paths=True,
        builder_family="glm",
        auditor_family="glm",
        blocking_debt=True,
        incident_open=True,
        reconciliation_required=True,
        l11_contract_hash="x" * 64,
        l13_evidence_hash="y" * 64,
        l14_receipt_hash="z" * 64,
        l15_document_hash="w" * 64,
    )

    reasons = evaluate_promotion(intent, evidence)

    assert "TRACE_B_NOT_ELIGIBLE" in reasons
    assert "PROTECTED_PATH" in reasons
    assert "AUDITOR_DECORRELATION_UNPROVEN" in reasons
    assert "BLOCKING_DEBT_PRESENT" in reasons
    assert "INCIDENT_OPEN" in reasons
    assert "RECONCILIATION_REQUIRED" in reasons


def test_evaluate_promotion_accepts_complete_reversible_trace_a_evidence(tmp_path: Path) -> None:
    import json
    import hashlib
    from kernel.cas import CAS, InMemoryCasStore
    from kernel.promotion import PromotionEvidence, evaluate_promotion

    cand_file = tmp_path / "mod.py"
    cand_file.write_text("print('hello')\n", encoding="utf-8")
    tree = {cand_file.name: hashlib.sha256(cand_file.read_bytes()).hexdigest()}
    computed_root = hashlib.sha256(json.dumps(tree, sort_keys=True).encode("utf-8")).hexdigest()

    cas = CAS(InMemoryCasStore())
    l11_hash = cas.put(json.dumps({"candidate_root": computed_root}).encode("utf-8"))
    l13_hash = cas.put(json.dumps({"candidate_root": computed_root}).encode("utf-8"))
    report_hash = cas.put(b"AUDIT_COMPLETE: true\nL14_STATUS: PASS\n")
    l14_receipt_hash = cas.put(json.dumps({
        "builder_family": "glm",
        "auditor_family": "gemini",
        "a08_verdict": "PASS",
        "candidate_sha256": computed_root,
        "evidence_bundle_sha256": l13_hash,
        "report_sha256": report_hash,
        "external_generation_id": "gen-test-12345678",
        "host_turn_uuid": "d3b07384-d113-4e2a-9f5e-26f53ef58941",
        "transport_request_sha256": "1" * 64,
        "transport_response_sha256": "2" * 64,
    }).encode("utf-8"))
    l15_hash = cas.put(json.dumps({"candidate_root": computed_root}).encode("utf-8"))

    intent = PromotionIntent(
        repository_id="repo-003",
        target_ref="refs/heads/feature/canary",
        expected_target_head="0" * 40,
        reviewed_commit="1" * 40,
        disposition_hash="d" * 64,
        rollback_commit="2" * 40,
        health_command_id="pytest-focused",
        expires_seq=100,
        candidate_root_hash=computed_root,
    )
    evidence = PromotionEvidence(
        bootstrap_verified=True,
        l11_contract_hash=l11_hash,
        l13_evidence_hash=l13_hash,
        l14_receipt_hash=l14_receipt_hash,
        l15_document_hash=l15_hash,
        builder_family="glm",
        auditor_family="gemini",
        rollback_verified=True,
        health_passed=True,
        candidate_root_hash=computed_root,
    )

    assert evaluate_promotion(intent, evidence, cas=cas, candidate_files=[cand_file], candidate_base_dir=tmp_path) == ()
