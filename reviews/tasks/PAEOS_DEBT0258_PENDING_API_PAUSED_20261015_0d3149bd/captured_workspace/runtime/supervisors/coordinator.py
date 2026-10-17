"""Deterministic failure disposition for supervisor transactions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum


class RecoveryAction(StrEnum):
    RETRY_NEW_ATTEMPT = "RETRY_NEW_ATTEMPT"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    QUARANTINE = "QUARANTINE"
    HALT = "HALT"


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    transaction_key: str
    action: RecoveryAction
    reason_code: str
    raw_failure_hash: str


class SupervisorRecoveryCoordinator:
    """Policy-only recovery coordinator; it never invokes an adapter or sleeps."""

    def __init__(self, *, max_preacceptance_retries: int = 1) -> None:
        if max_preacceptance_retries < 0:
            raise ValueError("max_preacceptance_retries must be non-negative")
        self._max_preacceptance_retries = max_preacceptance_retries
        self._attempts: dict[str, int] = {}

    def decide(
        self,
        transaction_key: str,
        *,
        phase: str,
        failure: str,
        side_effect_accepted: bool = False,
        side_effect_ambiguous: bool = False,
        response_valid: bool = True,
        stale_checkpoint: bool = False,
        policy_expired: bool = False,
        receipt_conflict: bool = False,
        prompt_injection: bool = False,
    ) -> RecoveryDecision:
        if not transaction_key:
            raise ValueError("transaction_key must be non-empty")
        raw_hash = hashlib.sha256(failure.encode("utf-8")).hexdigest()

        if stale_checkpoint:
            return self._decision(
                transaction_key, RecoveryAction.HALT, "STALE_CHECKPOINT", raw_hash
            )
        if prompt_injection or receipt_conflict or policy_expired or not response_valid:
            reason = (
                "PROMPT_INJECTION"
                if prompt_injection
                else "RECEIPT_CONFLICT"
                if receipt_conflict
                else "POLICY_EXPIRED"
                if policy_expired
                else "INVALID_RESPONSE"
            )
            return self._decision(transaction_key, RecoveryAction.QUARANTINE, reason, raw_hash)
        if side_effect_accepted or side_effect_ambiguous:
            return self._decision(
                transaction_key,
                RecoveryAction.RECONCILIATION_REQUIRED,
                "SIDE_EFFECT_ACCEPTED_OR_AMBIGUOUS",
                raw_hash,
            )

        attempts = self._attempts.get(transaction_key, 0)
        if phase in {"NEW", "PREPARED", "CLAIMED"} and attempts < self._max_preacceptance_retries:
            self._attempts[transaction_key] = attempts + 1
            return self._decision(
                transaction_key,
                RecoveryAction.RETRY_NEW_ATTEMPT,
                "PRE_ACCEPTANCE_QUOTA_LOSS",
                raw_hash,
            )
        return self._decision(transaction_key, RecoveryAction.HALT, "NO_SAFE_RETRY", raw_hash)

    @staticmethod
    def _decision(
        transaction_key: str,
        action: RecoveryAction,
        reason_code: str,
        raw_hash: str,
    ) -> RecoveryDecision:
        return RecoveryDecision(
            transaction_key=transaction_key,
            action=action,
            reason_code=reason_code,
            raw_failure_hash=raw_hash,
        )
