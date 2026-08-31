"""Tests for dormant single-use exact-ref promotion controller (Gate F Task 5)."""

from __future__ import annotations

from pathlib import Path

from kernel.capability import CapabilityBroker
from kernel.promotion import PromotionIntent
from kernel.types import Role, StageId


def test_promotion_controller_executes_with_verified_token(tmp_path: Path) -> None:
    from runtime.autonomy.promotion import PromotionController, PromotionReceipt

    broker = CapabilityBroker()
    controller = PromotionController(capability_broker=broker)

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
    op = f"promote:repo-001:refs/heads/main:{intent.reviewed_commit}"
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

    receipt = controller.promote(
        intent,
        token,
        current_seq=15,
        current_target_head=intent.expected_target_head,
    )
    assert isinstance(receipt, PromotionReceipt)
    assert receipt.repository_id == "repo-001"
    assert receipt.target_ref == "refs/heads/main"


def test_promotion_controller_rejects_reuse_of_single_use_token() -> None:
    from runtime.autonomy.promotion import PromotionController, PromotionError

    broker = CapabilityBroker()
    controller = PromotionController(capability_broker=broker)
    intent = PromotionIntent(
        repository_id="repo-once",
        target_ref="refs/heads/main",
        expected_target_head="0" * 40,
        reviewed_commit="1" * 40,
        disposition_hash="d" * 64,
        rollback_commit="0" * 40,
        health_command_id="pytest-focused",
        expires_seq=100,
    )
    op = f"promote:repo-once:refs/heads/main:{intent.reviewed_commit}"
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

    controller.promote(
        intent,
        token,
        current_seq=15,
        current_target_head=intent.expected_target_head,
    )
    try:
        controller.promote(
            intent,
            token,
            current_seq=15,
            current_target_head=intent.expected_target_head,
        )
    except PromotionError as exc:
        assert "single-use" in str(exc)
    else:
        raise AssertionError("promotion token was reused")
