"""Deterministic, event-based liveness facts for control-plane transactions.

This module deliberately contains no sleeps, I/O, process inspection, or recovery side
effects.  It turns monotonic observations into a small, typed assessment that a watchdog or
coordinator may later verify and commit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from runtime.control_plane.events import SideEffectCertainty, side_effect_retry_eligible
from runtime.integrations.bridge_protocol import TransactionState


class ProgressKind(StrEnum):
    HEARTBEAT = "HEARTBEAT"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_PROGRESS = "TOOL_PROGRESS"
    TOOL_FINISHED = "TOOL_FINISHED"
    ARTIFACT_COMMITTED = "ARTIFACT_COMMITTED"
    RESPONSE_PERSISTED = "RESPONSE_PERSISTED"
    RESPONSE_VERIFIED = "RESPONSE_VERIFIED"


@dataclass(frozen=True, slots=True)
class DeadlinePolicy:
    """Positive monotonic deadlines; wall-clock timestamps are not accepted here."""

    heartbeat_seconds: int = 15
    soft_stall_seconds: int = 120
    pre_side_effect_hard_stall_seconds: int = 300
    default_tool_seconds: int = 300
    trace_a_seconds: int = 1800
    trace_b_checkpoint_seconds: int = 300

    def __post_init__(self) -> None:
        for name in (
            "heartbeat_seconds",
            "soft_stall_seconds",
            "pre_side_effect_hard_stall_seconds",
            "default_tool_seconds",
            "trace_a_seconds",
            "trace_b_checkpoint_seconds",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.soft_stall_seconds > self.pre_side_effect_hard_stall_seconds:
            raise ValueError("soft stall must not exceed pre-side-effect hard stall")


def _validate_time(value: float | None, name: str, *, allow_none: bool = True) -> None:
    if value is None:
        if allow_none:
            return
        raise TypeError(f"{name} must be a finite monotonic value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite monotonic value")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"{name} must be a finite non-negative monotonic value")


@dataclass(frozen=True, slots=True)
class LivenessSnapshot:
    transaction_key: str
    state: TransactionState
    fencing_token: int
    last_heartbeat_monotonic: float | None
    last_meaningful_monotonic: float | None
    active_tool_deadline_monotonic: float | None
    transaction_deadline_monotonic: float
    side_effect_certainty: SideEffectCertainty
    observed_ledger_head: str = ""
    evidence_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.transaction_key, str) or not self.transaction_key.strip():
            raise ValueError("transaction_key must be non-empty")
        if not isinstance(self.state, TransactionState):
            raise TypeError("state must be a TransactionState")
        if isinstance(self.fencing_token, bool) or not isinstance(self.fencing_token, int):
            raise TypeError("fencing_token must be an integer")
        if self.fencing_token < 1:
            raise ValueError("fencing_token must be positive")
        _validate_time(self.last_heartbeat_monotonic, "last_heartbeat_monotonic")
        _validate_time(self.last_meaningful_monotonic, "last_meaningful_monotonic")
        _validate_time(self.active_tool_deadline_monotonic, "active_tool_deadline_monotonic")
        _validate_time(
            self.transaction_deadline_monotonic,
            "transaction_deadline_monotonic",
            allow_none=False,
        )
        if not isinstance(self.side_effect_certainty, SideEffectCertainty):
            raise TypeError("side_effect_certainty must be a SideEffectCertainty")
        if not isinstance(self.observed_ledger_head, str):
            raise TypeError("observed_ledger_head must be a string")
        if not isinstance(self.evidence_hashes, tuple) or any(
            not isinstance(value, str) or not value for value in self.evidence_hashes
        ):
            raise TypeError("evidence_hashes must be a tuple of non-empty strings")


class LivenessStatus(StrEnum):
    HEALTHY = "HEALTHY"
    MISSING_HEARTBEAT = "MISSING_HEARTBEAT"
    MISSING_MEANINGFUL_EVENT = "MISSING_MEANINGFUL_EVENT"
    SOFT_STALL = "SOFT_STALL"
    PRE_SIDE_EFFECT_HARD_STALL = "PRE_SIDE_EFFECT_HARD_STALL"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TRANSACTION_TIMEOUT = "TRANSACTION_TIMEOUT"
    TRACE_B_CHECKPOINT_MISSED = "TRACE_B_CHECKPOINT_MISSED"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
    TERMINAL = "TERMINAL"
    CLOCK_REGRESSION = "CLOCK_REGRESSION"


@dataclass(frozen=True, slots=True)
class LivenessAssessment:
    transaction_key: str
    fencing_token: int
    status: LivenessStatus
    reason_code: str
    now_monotonic: float
    heartbeat_age_seconds: float | None
    meaningful_age_seconds: float | None
    side_effect_certainty: SideEffectCertainty
    safe_lease_expiry: bool

    @property
    def is_healthy(self) -> bool:
        return self.status is LivenessStatus.HEALTHY


_TERMINAL_STATES = frozenset(
    {
        TransactionState.CONSUMED,
        TransactionState.RECONCILIATION_REQUIRED,
        TransactionState.QUARANTINED,
    }
)


def _assessment(
    snapshot: LivenessSnapshot,
    *,
    now: float,
    status: LivenessStatus,
    reason: str,
    heartbeat_age: float | None,
    meaningful_age: float | None,
    safe_lease_expiry: bool = False,
) -> LivenessAssessment:
    return LivenessAssessment(
        transaction_key=snapshot.transaction_key,
        fencing_token=snapshot.fencing_token,
        status=status,
        reason_code=reason,
        now_monotonic=now,
        heartbeat_age_seconds=heartbeat_age,
        meaningful_age_seconds=meaningful_age,
        side_effect_certainty=snapshot.side_effect_certainty,
        safe_lease_expiry=safe_lease_expiry,
    )


def assess_liveness(
    snapshot: LivenessSnapshot,
    *,
    now_monotonic: float,
    policy: DeadlinePolicy | None = None,
    trace_b: bool = False,
    last_checkpoint_monotonic: float | None = None,
) -> LivenessAssessment:
    """Assess one immutable snapshot at a monotonic instant.

    ``HEARTBEAT`` observations only affect heartbeat freshness.  Meaningful progress must be
    supplied explicitly by the execution layer, so a token stream cannot mask a stalled tool or
    transaction.  At or beyond every threshold the assessment is already due (``>=``).
    """

    if not isinstance(snapshot, LivenessSnapshot):
        raise TypeError("snapshot must be a LivenessSnapshot")
    selected_policy = DeadlinePolicy() if policy is None else policy
    if not isinstance(selected_policy, DeadlinePolicy):
        raise TypeError("policy must be a DeadlinePolicy")
    _validate_time(now_monotonic, "now_monotonic", allow_none=False)
    now = float(now_monotonic)
    heartbeat = snapshot.last_heartbeat_monotonic
    meaningful = snapshot.last_meaningful_monotonic
    heartbeat_age = None if heartbeat is None else now - float(heartbeat)
    meaningful_age = None if meaningful is None else now - float(meaningful)

    if (heartbeat_age is not None and heartbeat_age < 0) or (
        meaningful_age is not None and meaningful_age < 0
    ):
        return _assessment(
            snapshot,
            now=now,
            status=LivenessStatus.CLOCK_REGRESSION,
            reason="MONOTONIC_CLOCK_REGRESSION",
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
        )
    if snapshot.state in _TERMINAL_STATES:
        return _assessment(
            snapshot,
            now=now,
            status=LivenessStatus.TERMINAL,
            reason="TRANSACTION_TERMINAL",
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
        )
    if heartbeat is None or (
        heartbeat_age is not None
        and heartbeat_age >= selected_policy.heartbeat_seconds
    ):
        return _assessment(
            snapshot,
            now=now,
            status=LivenessStatus.MISSING_HEARTBEAT,
            reason="HEARTBEAT_DEADLINE_EXCEEDED",
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
        )
    if meaningful is None:
        return _assessment(
            snapshot,
            now=now,
            status=LivenessStatus.MISSING_MEANINGFUL_EVENT,
            reason="NO_MEANINGFUL_PROGRESS_OBSERVED",
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
        )

    checkpoint = (
        snapshot.last_meaningful_monotonic
        if last_checkpoint_monotonic is None
        else last_checkpoint_monotonic
    )
    _validate_time(checkpoint, "last_checkpoint_monotonic")
    checkpoint_age = now - float(checkpoint) if checkpoint is not None else None
    if checkpoint_age is not None and checkpoint_age < 0:
        return _assessment(
            snapshot,
            now=now,
            status=LivenessStatus.CLOCK_REGRESSION,
            reason="MONOTONIC_CLOCK_REGRESSION",
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
        )
    if (
        trace_b
        and checkpoint_age is not None
        and checkpoint_age >= selected_policy.trace_b_checkpoint_seconds
    ):
        return _assessment(
            snapshot,
            now=now,
            status=LivenessStatus.TRACE_B_CHECKPOINT_MISSED,
            reason="TRACE_B_CHECKPOINT_DEADLINE_EXCEEDED",
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
        )
    if now >= snapshot.transaction_deadline_monotonic:
        status = (
            LivenessStatus.SIDE_EFFECT_UNCERTAIN
            if not side_effect_retry_eligible(snapshot.side_effect_certainty)
            else LivenessStatus.TRANSACTION_TIMEOUT
        )
        return _assessment(
            snapshot,
            now=now,
            status=status,
            reason="TRANSACTION_DEADLINE_EXCEEDED",
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
        )
    if (
        snapshot.active_tool_deadline_monotonic is not None
        and now >= snapshot.active_tool_deadline_monotonic
    ):
        status = (
            LivenessStatus.SIDE_EFFECT_UNCERTAIN
            if not side_effect_retry_eligible(snapshot.side_effect_certainty)
            else LivenessStatus.TOOL_TIMEOUT
        )
        return _assessment(
            snapshot,
            now=now,
            status=status,
            reason="TOOL_DEADLINE_EXCEEDED",
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
        )
    assert meaningful_age is not None
    if meaningful_age >= selected_policy.pre_side_effect_hard_stall_seconds:
        safe = side_effect_retry_eligible(snapshot.side_effect_certainty)
        return _assessment(
            snapshot,
            now=now,
            status=(
                LivenessStatus.PRE_SIDE_EFFECT_HARD_STALL
                if safe
                else LivenessStatus.SIDE_EFFECT_UNCERTAIN
            ),
            reason=(
                "PRE_SIDE_EFFECT_HARD_STALL"
                if safe
                else "HARD_STALL_AFTER_POSSIBLE_SIDE_EFFECT"
            ),
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
            safe_lease_expiry=safe,
        )
    if meaningful_age >= selected_policy.soft_stall_seconds:
        return _assessment(
            snapshot,
            now=now,
            status=LivenessStatus.SOFT_STALL,
            reason="MEANINGFUL_PROGRESS_STALE",
            heartbeat_age=heartbeat_age,
            meaningful_age=meaningful_age,
        )
    return _assessment(
        snapshot,
        now=now,
        status=LivenessStatus.HEALTHY,
        reason="MEANINGFUL_PROGRESS_FRESH",
        heartbeat_age=heartbeat_age,
        meaningful_age=meaningful_age,
    )


def evaluate_liveness(
    snapshot: LivenessSnapshot,
    *,
    now_monotonic: float,
    policy: DeadlinePolicy | None = None,
    trace_b: bool = False,
    last_checkpoint_monotonic: float | None = None,
) -> LivenessAssessment:
    """Compatibility spelling for callers that use ``evaluate_liveness``."""

    return assess_liveness(
        snapshot,
        now_monotonic=now_monotonic,
        policy=policy,
        trace_b=trace_b,
        last_checkpoint_monotonic=last_checkpoint_monotonic,
    )


__all__ = [
    "DeadlinePolicy",
    "LivenessAssessment",
    "LivenessSnapshot",
    "LivenessStatus",
    "ProgressKind",
    "assess_liveness",
    "evaluate_liveness",
]
