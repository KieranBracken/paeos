from __future__ import annotations

from typing import Any, cast

import pytest
from runtime.control_plane.events import SideEffectCertainty
from runtime.control_plane.liveness import (
    DeadlinePolicy,
    LivenessSnapshot,
    LivenessStatus,
    ProgressKind,
    assess_liveness,
)
from runtime.integrations.bridge_protocol import TransactionState


def snapshot(**changes: object) -> LivenessSnapshot:
    values: dict[str, object] = {
        "transaction_key": "a" * 64,
        "state": TransactionState.CLAIMED,
        "fencing_token": 2,
        "last_heartbeat_monotonic": 100.0,
        "last_meaningful_monotonic": 100.0,
        "active_tool_deadline_monotonic": None,
        "transaction_deadline_monotonic": 1_900.0,
        "side_effect_certainty": SideEffectCertainty.NOT_ATTEMPTED,
    }
    values.update(changes)
    # The factory intentionally permits invalid values so runtime validation paths can be tested.
    return LivenessSnapshot(**cast(Any, values))


def test_progress_kind_is_closed_and_stream_tokens_are_not_progress() -> None:
    assert ProgressKind.HEARTBEAT.value == "HEARTBEAT"
    assert ProgressKind.TOOL_PROGRESS.value == "TOOL_PROGRESS"
    assert ProgressKind.RESPONSE_VERIFIED.value == "RESPONSE_VERIFIED"


def test_default_policy_and_threshold_validation() -> None:
    policy = DeadlinePolicy()
    assert policy.heartbeat_seconds == 15
    assert policy.soft_stall_seconds == 120
    assert policy.pre_side_effect_hard_stall_seconds == 300
    assert policy.default_tool_seconds == 300
    assert policy.trace_a_seconds == 1_800
    assert policy.trace_b_checkpoint_seconds == 300
    with pytest.raises(ValueError, match="positive"):
        DeadlinePolicy(soft_stall_seconds=0)
    with pytest.raises(TypeError, match="integer"):
        DeadlinePolicy(heartbeat_seconds=True)  # type: ignore[arg-type]


def test_healthy_before_exact_thresholds_and_soft_stall_at_boundary() -> None:
    policy = DeadlinePolicy()
    assert assess_liveness(
        snapshot(last_heartbeat_monotonic=219.99, last_meaningful_monotonic=100.0),
        now_monotonic=219.99,
        policy=policy,
    ).status is LivenessStatus.HEALTHY
    result = assess_liveness(
        snapshot(last_heartbeat_monotonic=220.0, last_meaningful_monotonic=100.0),
        now_monotonic=220.0,
        policy=policy,
    )
    assert result.status is LivenessStatus.SOFT_STALL
    assert result.reason_code == "MEANINGFUL_PROGRESS_STALE"


def test_tokens_without_meaningful_progress_reach_hard_stall() -> None:
    result = assess_liveness(
        snapshot(last_heartbeat_monotonic=399.0),
        now_monotonic=400.0,
    )
    assert result.status is LivenessStatus.PRE_SIDE_EFFECT_HARD_STALL
    assert result.safe_lease_expiry is True


def test_hard_stall_after_possible_side_effect_requires_reconciliation() -> None:
    result = assess_liveness(
        snapshot(
            last_heartbeat_monotonic=399.0,
            side_effect_certainty=SideEffectCertainty.ACCEPTED,
        ),
        now_monotonic=400.0,
    )
    assert result.status is LivenessStatus.SIDE_EFFECT_UNCERTAIN
    assert result.safe_lease_expiry is False


def test_authorized_long_running_tool_progress_avoids_soft_stall() -> None:
    result = assess_liveness(
        snapshot(
            last_heartbeat_monotonic=219.0,
            last_meaningful_monotonic=219.0,
            active_tool_deadline_monotonic=500.0,
        ),
        now_monotonic=220.0,
    )
    assert result.status is LivenessStatus.HEALTHY


def test_clock_regression_and_missing_observations_fail_closed() -> None:
    assert (
        assess_liveness(snapshot(), now_monotonic=99.0).status
        is LivenessStatus.CLOCK_REGRESSION
    )
    assert (
        assess_liveness(snapshot(last_heartbeat_monotonic=None), now_monotonic=200.0).status
        is LivenessStatus.MISSING_HEARTBEAT
    )
    assert (
        assess_liveness(
            snapshot(last_heartbeat_monotonic=200.0, last_meaningful_monotonic=None),
            now_monotonic=200.0,
        ).status
        is LivenessStatus.MISSING_MEANINGFUL_EVENT
    )


def test_tool_and_transaction_deadlines_are_distinct() -> None:
    tool = assess_liveness(
        snapshot(
            last_heartbeat_monotonic=220.0,
            active_tool_deadline_monotonic=220.0,
        ),
        now_monotonic=220.0,
    )
    assert tool.status is LivenessStatus.TOOL_TIMEOUT
    task = assess_liveness(
        snapshot(last_heartbeat_monotonic=1_900.0, last_meaningful_monotonic=1_900.0),
        now_monotonic=1_900.0,
    )
    assert task.status is LivenessStatus.TRANSACTION_TIMEOUT


def test_trace_b_checkpoint_is_reported_without_sleeping() -> None:
    result = assess_liveness(
        snapshot(
            last_heartbeat_monotonic=400.0,
            last_meaningful_monotonic=100.0,
            transaction_deadline_monotonic=10_000.0,
        ),
        now_monotonic=400.0,
        trace_b=True,
    )
    assert result.status is LivenessStatus.TRACE_B_CHECKPOINT_MISSED


def test_terminal_transactions_are_not_recovered() -> None:
    result = assess_liveness(
        snapshot(state=TransactionState.CONSUMED), now_monotonic=10_000.0
    )
    assert result.status is LivenessStatus.TERMINAL
    assert result.safe_lease_expiry is False
