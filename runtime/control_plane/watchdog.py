"""Pure watchdog decisions derived from verified transaction events.

The watchdog is advisory.  It never edits a transaction, restarts a process, rotates a provider,
or retries an operation.  A coordinator must re-check the observed head, fence, and side-effect
certainty before committing any returned action.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from runtime.control_plane.events import side_effect_retry_eligible
from runtime.control_plane.liveness import (
    DeadlinePolicy,
    LivenessSnapshot,
    LivenessStatus,
    assess_liveness,
)


class RecoveryAction(StrEnum):
    NONE = "NONE"
    DIAGNOSE = "DIAGNOSE"
    EXPIRE_PRE_SIDE_EFFECT_LEASE = "EXPIRE_PRE_SIDE_EFFECT_LEASE"
    RESTART_STATELESS_ADAPTER = "RESTART_STATELESS_ADAPTER"
    ROTATE_PROVIDER = "ROTATE_PROVIDER"
    REQUIRE_RECONCILIATION = "REQUIRE_RECONCILIATION"
    HALT_SHARED_CONTROL_PLANE = "HALT_SHARED_CONTROL_PLANE"


@dataclass(frozen=True, slots=True)
class WatchdogDecision:
    transaction_key: str
    fencing_token: int
    action: RecoveryAction
    reason_code: str
    observed_ledger_head: str
    evidence_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.transaction_key, str) or not self.transaction_key.strip():
            raise ValueError("transaction_key must be non-empty")
        if isinstance(self.fencing_token, bool) or not isinstance(self.fencing_token, int):
            raise TypeError("fencing_token must be an integer")
        if self.fencing_token < 1:
            raise ValueError("fencing_token must be positive")
        if not isinstance(self.action, RecoveryAction):
            raise TypeError("action must be a RecoveryAction")
        if not isinstance(self.reason_code, str) or not self.reason_code.strip():
            raise ValueError("reason_code must be non-empty")
        if not isinstance(self.observed_ledger_head, str):
            raise TypeError("observed_ledger_head must be a string")
        if not isinstance(self.evidence_hashes, tuple) or any(
            not isinstance(value, str) or not value for value in self.evidence_hashes
        ):
            raise TypeError("evidence_hashes must be a tuple of non-empty strings")


def _decision(
    snapshot: LivenessSnapshot,
    *,
    action: RecoveryAction,
    reason: str,
) -> WatchdogDecision:
    return WatchdogDecision(
        transaction_key=snapshot.transaction_key,
        fencing_token=snapshot.fencing_token,
        action=action,
        reason_code=reason,
        observed_ledger_head=snapshot.observed_ledger_head,
        evidence_hashes=snapshot.evidence_hashes,
    )


def decide_recovery(
    snapshot: LivenessSnapshot,
    *,
    now_monotonic: float,
    projection_verified: bool,
    shared_integrity_healthy: bool,
    policy: DeadlinePolicy | None = None,
    trace_b: bool = False,
    last_checkpoint_monotonic: float | None = None,
) -> WatchdogDecision:
    """Return one typed, side-effect-free recovery proposal.

    Integrity failures take precedence over local liveness.  This prevents a poisoned projection
    or shared ledger fault from being mistaken for a recoverable worker timeout.  The returned
    action is not authorization; ``RecoveryController`` must compare the current ledger head and
    fence before appending a transition.
    """

    if not isinstance(snapshot, LivenessSnapshot):
        raise TypeError("snapshot must be a LivenessSnapshot")
    if not isinstance(projection_verified, bool):
        raise TypeError("projection_verified must be a boolean")
    if not isinstance(shared_integrity_healthy, bool):
        raise TypeError("shared_integrity_healthy must be a boolean")
    if not shared_integrity_healthy:
        return _decision(
            snapshot,
            action=RecoveryAction.HALT_SHARED_CONTROL_PLANE,
            reason="SHARED_INTEGRITY_FAILURE",
        )
    if not projection_verified:
        return _decision(
            snapshot,
            action=RecoveryAction.HALT_SHARED_CONTROL_PLANE,
            reason="PROJECTION_UNVERIFIED",
        )

    assessment = assess_liveness(
        snapshot,
        now_monotonic=now_monotonic,
        policy=policy,
        trace_b=trace_b,
        last_checkpoint_monotonic=last_checkpoint_monotonic,
    )
    status = assessment.status
    if status is LivenessStatus.TERMINAL:
        return _decision(snapshot, action=RecoveryAction.NONE, reason="TRANSACTION_TERMINAL")
    if status is LivenessStatus.HEALTHY:
        return _decision(snapshot, action=RecoveryAction.NONE, reason="MEANINGFUL_PROGRESS_FRESH")
    if status in {
        LivenessStatus.CLOCK_REGRESSION,
        LivenessStatus.MISSING_HEARTBEAT,
        LivenessStatus.MISSING_MEANINGFUL_EVENT,
        LivenessStatus.SOFT_STALL,
    }:
        return _decision(snapshot, action=RecoveryAction.DIAGNOSE, reason=assessment.reason_code)
    if status is LivenessStatus.PRE_SIDE_EFFECT_HARD_STALL:
        return _decision(
            snapshot,
            action=RecoveryAction.EXPIRE_PRE_SIDE_EFFECT_LEASE,
            reason="PRE_SIDE_EFFECT_HARD_STALL",
        )
    if status is LivenessStatus.TOOL_TIMEOUT:
        return _decision(
            snapshot,
            action=RecoveryAction.RESTART_STATELESS_ADAPTER,
            reason="TOOL_DEADLINE_EXCEEDED",
        )
    if status is LivenessStatus.TRANSACTION_TIMEOUT:
        if side_effect_retry_eligible(snapshot.side_effect_certainty):
            return _decision(
                snapshot,
                action=RecoveryAction.EXPIRE_PRE_SIDE_EFFECT_LEASE,
                reason="TRANSACTION_DEADLINE_EXCEEDED",
            )
        return _decision(
            snapshot,
            action=RecoveryAction.REQUIRE_RECONCILIATION,
            reason="TRANSACTION_TIMEOUT_AFTER_POSSIBLE_SIDE_EFFECT",
        )
    if status is LivenessStatus.TRACE_B_CHECKPOINT_MISSED:
        return _decision(
            snapshot,
            action=RecoveryAction.REQUIRE_RECONCILIATION,
            reason="TRACE_B_CHECKPOINT_DEADLINE_EXCEEDED",
        )
    if status is LivenessStatus.SIDE_EFFECT_UNCERTAIN:
        return _decision(
            snapshot,
            action=RecoveryAction.REQUIRE_RECONCILIATION,
            reason=assessment.reason_code,
        )
    return _decision(snapshot, action=RecoveryAction.DIAGNOSE, reason=assessment.reason_code)


__all__ = ["RecoveryAction", "WatchdogDecision", "decide_recovery"]
