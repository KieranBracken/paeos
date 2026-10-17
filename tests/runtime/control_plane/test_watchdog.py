from __future__ import annotations

from typing import Any, cast

import pytest
from runtime.control_plane.events import SideEffectCertainty
from runtime.control_plane.liveness import (
    LivenessSnapshot,
    LivenessStatus,
    assess_liveness,
)
from runtime.control_plane.storage_policy import StorageObservation, StoragePolicy
from runtime.control_plane.watchdog import RecoveryAction, decide_recovery
from runtime.integrations.bridge_protocol import TransactionState


def snapshot(**changes: object) -> LivenessSnapshot:
    values: dict[str, object] = {
        "transaction_key": "a" * 64,
        "state": TransactionState.CLAIMED,
        "fencing_token": 2,
        "last_heartbeat_monotonic": 700.0,
        "last_meaningful_monotonic": 700.0,
        "active_tool_deadline_monotonic": None,
        "transaction_deadline_monotonic": 1_000.0,
        "side_effect_certainty": SideEffectCertainty.NOT_ATTEMPTED,
        "observed_ledger_head": "b" * 64,
        "evidence_hashes": ("c" * 64,),
    }
    values.update(changes)
    # The factory intentionally permits invalid values so runtime validation paths can be tested.
    return LivenessSnapshot(**cast(Any, values))


def decision(snapshot_value: LivenessSnapshot, *, projection_verified: bool = True):
    assessment = assess_liveness(snapshot_value, now_monotonic=700.0)
    return decide_recovery(
        snapshot_value,
        now_monotonic=700.0,
        projection_verified=projection_verified,
        shared_integrity_healthy=True,
    ), assessment


def test_healthy_and_terminal_transactions_are_noops() -> None:
    healthy, assessment = decision(snapshot())
    assert assessment.status is LivenessStatus.HEALTHY
    assert healthy.action is RecoveryAction.NONE
    terminal, _ = decision(snapshot(state=TransactionState.CONSUMED))
    assert terminal.action is RecoveryAction.NONE
    assert terminal.reason_code == "TRANSACTION_TERMINAL"


def test_soft_stall_is_diagnostic_only() -> None:
    result, assessment = decision(snapshot(last_meaningful_monotonic=580.0))
    assert assessment.status is LivenessStatus.SOFT_STALL
    assert result.action is RecoveryAction.DIAGNOSE


def test_safe_hard_stall_expires_lease() -> None:
    result, assessment = decision(
        snapshot(last_heartbeat_monotonic=700.0, last_meaningful_monotonic=400.0)
    )
    assert assessment.status is LivenessStatus.PRE_SIDE_EFFECT_HARD_STALL
    assert result.action is RecoveryAction.EXPIRE_PRE_SIDE_EFFECT_LEASE
    assert result.fencing_token == 2


def test_tool_timeout_restarts_only_stateless_route() -> None:
    result, assessment = decision(
        snapshot(
            last_heartbeat_monotonic=700.0,
            active_tool_deadline_monotonic=700.0,
        )
    )
    assert assessment.status is LivenessStatus.TOOL_TIMEOUT
    assert result.action is RecoveryAction.RESTART_STATELESS_ADAPTER


def test_possible_side_effect_requires_reconciliation() -> None:
    result, assessment = decision(
        snapshot(
            last_heartbeat_monotonic=700.0,
            last_meaningful_monotonic=400.0,
            side_effect_certainty=SideEffectCertainty.ACCEPTED,
        )
    )
    assert assessment.status is LivenessStatus.SIDE_EFFECT_UNCERTAIN
    assert result.action is RecoveryAction.REQUIRE_RECONCILIATION


@pytest.mark.parametrize(
    "kwargs",
    [
        {"projection_verified": False},
    ],
)
def test_unverified_projection_halts_shared_control_plane(kwargs: dict[str, bool]) -> None:
    result, _ = decision(snapshot(), **kwargs)
    assert result.action is RecoveryAction.HALT_SHARED_CONTROL_PLANE
    assert result.reason_code == "PROJECTION_UNVERIFIED"


def test_shared_integrity_failure_halts_even_for_unrelated_transaction() -> None:
    result = decide_recovery(
        snapshot(last_meaningful_monotonic=699.0),
        now_monotonic=700.0,
        projection_verified=True,
        shared_integrity_healthy=False,
    )
    assert result.action is RecoveryAction.HALT_SHARED_CONTROL_PLANE
    assert result.reason_code == "SHARED_INTEGRITY_FAILURE"


def test_storage_hard_pressure_halts_new_dispatch() -> None:
    result = decide_recovery(
        snapshot(),
        now_monotonic=700.0,
        projection_verified=True,
        shared_integrity_healthy=True,
        storage_observation=StorageObservation(1_700, 100, 100, 100, 1_000_000),
        storage_policy=StoragePolicy(soft_total_bytes=1_000, hard_total_bytes=2_000),
    )
    assert result.action is RecoveryAction.HALT_SHARED_CONTROL_PLANE
    assert result.reason_code == "STORAGE_HARD_PRESSURE"


def test_storage_soft_pressure_is_diagnostic_when_liveness_is_healthy() -> None:
    result = decide_recovery(
        snapshot(),
        now_monotonic=700.0,
        projection_verified=True,
        shared_integrity_healthy=True,
        storage_observation=StorageObservation(800, 100, 100, 100, 1_000_000_000),
        storage_policy=StoragePolicy(soft_total_bytes=1_000, hard_total_bytes=2_000),
    )
    assert result.action is RecoveryAction.DIAGNOSE
    assert result.reason_code == "STORAGE_BACKPRESSURE"


def test_decision_binds_snapshot_identity_and_evidence() -> None:
    result, _ = decision(snapshot())
    assert result.transaction_key == "a" * 64
    assert result.observed_ledger_head == "b" * 64
    assert result.evidence_hashes == ("c" * 64,)


def test_decision_rejects_clock_regression_without_recovery() -> None:
    value = snapshot(last_heartbeat_monotonic=701.0, last_meaningful_monotonic=701.0)
    result = decide_recovery(
        value,
        now_monotonic=700.0,
        projection_verified=True,
        shared_integrity_healthy=True,
    )
    assert result.action is RecoveryAction.DIAGNOSE
    assert result.reason_code == "MONOTONIC_CLOCK_REGRESSION"
