"""Tests for dormant single-use exact-ref promotion controller (Gate F Task 5)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from kernel.capability import CapabilityBroker
from kernel.promotion import PromotionEvidence, PromotionIntent, promotion_operation
from kernel.types import Role, StageId


def test_promotion_controller_is_dormant_without_bootstrap(tmp_path: Path) -> None:
    from runtime.autonomy.promotion import PromotionController, PromotionError

    broker = CapabilityBroker()
    controller = PromotionController(capability_broker=broker)

    intent = PromotionIntent(
        repository_id="repo-001",
        target_ref="refs/heads/feature",
        expected_target_head="0" * 40,
        reviewed_commit="1" * 40,
        disposition_hash="d" * 64,
        rollback_commit="0" * 40,
        health_command_id="pytest-focused",
        expires_seq=100,
    )
    op = promotion_operation(intent)
    token = broker.mint(
        goal_id="G-PROM-001",
        run_id="R-PROM-001",
        stage=StageId.SEAL,
        role=Role.RATIFIER,
        session="session-ratifier",
        operations=(op,),
        issued_seq=10,
        expires_seq=100,
    )

    try:
        controller.promote(
            intent,
            token,
            current_seq=15,
            current_target_head=intent.expected_target_head,
            repository_path=tmp_path,
        )
    except PromotionError as exc:
        assert "bootstrap" in str(exc).lower()
    else:
        raise AssertionError("dormant controller created a promotion receipt")


def test_controller_rejects_unhashable_bootstrap_manifest() -> None:
    from runtime.autonomy.promotion import PromotionController

    try:
        PromotionController(bootstrap_manifest_hash="not-a-hash")
    except ValueError as exc:
        assert "sha-256" in str(exc).lower()
    else:
        raise AssertionError("controller accepted an unbound bootstrap manifest")


def test_promotion_controller_remains_dormant_on_repeated_attempts() -> None:
    from runtime.autonomy.promotion import PromotionController, PromotionError

    broker = CapabilityBroker()
    controller = PromotionController(capability_broker=broker)
    intent = PromotionIntent(
        repository_id="repo-once",
        target_ref="refs/heads/feature",
        expected_target_head="0" * 40,
        reviewed_commit="1" * 40,
        disposition_hash="d" * 64,
        rollback_commit="0" * 40,
        health_command_id="pytest-focused",
        expires_seq=100,
    )
    op = promotion_operation(intent)
    token = broker.mint(
        goal_id="G-PROM-ONCE",
        run_id="R-PROM-ONCE",
        stage=StageId.SEAL,
        role=Role.RATIFIER,
        session="session-once",
        operations=(op,),
        issued_seq=10,
        expires_seq=100,
    )

    try:
        controller.promote(
            intent,
            token,
            current_seq=15,
            current_target_head=intent.expected_target_head,
        )
    except PromotionError as exc:
        assert "bootstrap" in str(exc).lower()
    else:
        raise AssertionError("dormant controller accepted a promotion")


def test_enabled_controller_updates_only_expected_feature_ref(tmp_path: Path) -> None:
    from runtime.autonomy.promotion import (
        PromotionController,
        PromotionError,
        PromotionReceipt,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args: str, input: str | None = None) -> str:
        result = subprocess.run(
            ["/usr/bin/git", "-C", str(repo), *args],
            input=input,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()

    git("init", "--quiet")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "PAEOS test")
    (repo / "state.txt").write_text("base\n", encoding="utf-8")
    git("add", "state.txt")
    git("commit", "--quiet", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("branch", "feature", base)
    (repo / "state.txt").write_text("reviewed\n", encoding="utf-8")
    git("commit", "--quiet", "-am", "reviewed")
    reviewed = git("rev-parse", "HEAD")
    base_tree = git("rev-parse", f"{base}^{{tree}}")
    rollback = git("commit-tree", base_tree, "-p", reviewed, input="rollback\n")

    import hashlib
    import json
    from kernel.cas import CAS, InMemoryCasStore

    cand_file = repo / "state.txt"
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
        "external_generation_id": "gen-test-promotion-ctrl",
        "host_turn_uuid": "d3b07384-d113-4e2a-9f5e-26f53ef58941",
        "transport_request_sha256": "1" * 64,
        "transport_response_sha256": "2" * 64,
    }).encode("utf-8"))
    l15_hash = cas.put(json.dumps({"candidate_root": computed_root}).encode("utf-8"))

    intent = PromotionIntent(
        repository_id="repo-enabled",
        target_ref="refs/heads/feature",
        expected_target_head=base,
        reviewed_commit=reviewed,
        disposition_hash="d" * 64,
        rollback_commit=rollback,
        health_command_id="pytest-focused",
        expires_seq=100,
        candidate_root_hash=computed_root,
    )
    broker = CapabilityBroker()
    token = broker.mint(
        goal_id="G-PROM-ENABLED",
        run_id="R-PROM-ENABLED",
        stage=StageId.SEAL,
        role=Role.RATIFIER,
        session="session-enabled",
        operations=(promotion_operation(intent),),
        issued_seq=10,
        expires_seq=100,
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
    controller = PromotionController(
        capability_broker=broker,
        bootstrap_manifest_hash="b" * 64,
        state_root=tmp_path / "state",
        cas=cas,
    )

    receipt = controller.promote(
        intent,
        token,
        current_seq=15,
        current_target_head=base,
        evidence=evidence,
        repository_path=repo,
        candidate_files=[cand_file],
        candidate_base_dir=repo,
    )

    assert isinstance(receipt, PromotionReceipt)
    assert git("rev-parse", "refs/heads/feature") == reviewed
    assert list((tmp_path / "state").glob("*.receipt.json"))
    try:
        controller.promote(
            intent,
            token,
            current_seq=15,
            current_target_head=base,
            evidence=evidence,
            repository_path=repo,
            candidate_files=[cand_file],
            candidate_base_dir=repo,
        )
    except PromotionError as exc:
        assert "single-use" in str(exc)
    else:
        raise AssertionError("promotion token was reused")
