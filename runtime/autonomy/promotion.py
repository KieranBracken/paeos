"""Single-use exact-ref promotion controller (Gate F Task 5)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from kernel.capability import CapabilityBroker, CapabilityError
from kernel.promotion import PromotionIntent, promotion_operation
from kernel.types import CapabilityToken, Role, StageId


class PromotionError(RuntimeError):
    """Raised when a promotion request is denied or fails execution."""


@dataclass(frozen=True, slots=True)
class PromotionReceipt:
    repository_id: str
    target_ref: str
    prior_head: str
    new_head: str
    promoted_at: str
    receipt_hash: str


class PromotionController:
    """Controller enforcing exact-ref promotion through verified CapabilityTokens."""

    def __init__(self, capability_broker: CapabilityBroker | None = None) -> None:
        self._broker = capability_broker or CapabilityBroker()

    def promote(
        self, intent: PromotionIntent, token: CapabilityToken, *, current_seq: int
    ) -> PromotionReceipt:
        expected_op = promotion_operation(intent)
        try:
            self._broker.verify(
                token=token,
                goal_id=token.bound_to.goal_id,
                run_id=token.bound_to.run_id,
                stage=StageId.SEAL,
                role=Role.RATIFIER,
                operation=expected_op,
                current_seq=current_seq,
                session=token.bound_to.session,
            )
        except CapabilityError as e:
            raise PromotionError(f"promotion not permitted by capability: {e}") from e

        now_iso = datetime.now(UTC).isoformat()
        payload = {
            "repository_id": intent.repository_id,
            "target_ref": intent.target_ref,
            "prior_head": intent.expected_target_head,
            "new_head": intent.reviewed_commit,
            "promoted_at": now_iso,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        receipt_hash = hashlib.sha256(encoded).hexdigest()

        return PromotionReceipt(
            repository_id=intent.repository_id,
            target_ref=intent.target_ref,
            prior_head=intent.expected_target_head,
            new_head=intent.reviewed_commit,
            promoted_at=now_iso,
            receipt_hash=receipt_hash,
        )
