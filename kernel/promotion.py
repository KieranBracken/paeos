"""Single-use exact-ref promotion intent and operation encoding (Gate F Task 5)."""

from __future__ import annotations

from dataclasses import dataclass


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


def promotion_operation(intent: PromotionIntent) -> str:
    return f"promote:{intent.repository_id}:{intent.target_ref}:{intent.reviewed_commit}"
