"""Tests for promotion policy and intent encoding (Gate F Task 5)."""

from __future__ import annotations


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
    assert op.startswith("promote:repo-001:refs/heads/main:")
    assert "1" * 40 in op
