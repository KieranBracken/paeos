from __future__ import annotations

from typing import Any

import pytest
from runtime.control_plane.events import SideEffectCertainty
from runtime.control_plane.liveness import LivenessSnapshot
from runtime.control_plane.storage_policy import StorageObservation, StoragePolicy
from runtime.control_plane.watchdog import RecoveryAction, decide_recovery
from runtime.integrations.bridge_protocol import TransactionState


def snapshot(**changes: object) -> LivenessSnapshot:
    values: dict[str, Any] = {
        "request_id": "req-001",
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
    return LivenessSnapshot(**values)


@pytest.mark.parametrize(
    ("name", "changes", "expected"),
    [
        (
            "hung reasoning",
            {"last_meaningful_monotonic": 400.0},
            RecoveryAction.EXPIRE_PRE_SIDE_EFFECT_LEASE,
        ),
        (
            "hung tool",
            {"active_tool_deadline_monotonic": 700.0},
            RecoveryAction.RESTART_STATELESS_ADAPTER,
        ),
        (
            "token-only stream",
            {"last_meaningful_monotonic": 580.0},
            RecoveryAction.DIAGNOSE,
        ),
        (
            "quota loss before acceptance",
            {"last_meaningful_monotonic": 400.0},
            RecoveryAction.EXPIRE_PRE_SIDE_EFFECT_LEASE,
        ),
        (
            "process death",
            {"last_heartbeat_monotonic": 680.0},
            RecoveryAction.DIAGNOSE,
        ),
        (
            "pre-side-effect crash",
            {"last_meaningful_monotonic": 400.0},
            RecoveryAction.EXPIRE_PRE_SIDE_EFFECT_LEASE,
        ),
        (
            "post-side-effect crash",
            {
                "last_meaningful_monotonic": 400.0,
                "side_effect_certainty": SideEffectCertainty.ACCEPTED,
            },
            RecoveryAction.REQUIRE_RECONCILIATION,
        ),
    ],
)
def test_liveness_fault_matrix(
    name: str,
    changes: dict[str, object],
    expected: RecoveryAction,
) -> None:
    del name
    result = decide_recovery(
        snapshot(**changes),
        now_monotonic=700.0,
        projection_verified=True,
        shared_integrity_healthy=True,
    )
    assert result.action is expected


def test_projection_poison_halts_shared_plane() -> None:
    result = decide_recovery(
        snapshot(),
        now_monotonic=700.0,
        projection_verified=False,
        shared_integrity_healthy=True,
    )
    assert result.action is RecoveryAction.HALT_SHARED_CONTROL_PLANE


def test_disk_exhaustion_halts_new_dispatch() -> None:
    result = decide_recovery(
        snapshot(),
        now_monotonic=700.0,
        projection_verified=True,
        shared_integrity_healthy=True,
        storage_observation=StorageObservation(2_000, 0, 0, 0, 1_000_000_000),
        storage_policy=StoragePolicy(soft_total_bytes=1_000, hard_total_bytes=2_000),
    )
    assert result.action is RecoveryAction.HALT_SHARED_CONTROL_PLANE


def test_unrelated_healthy_transaction_is_not_blocked() -> None:
    result = decide_recovery(
        snapshot(transaction_key="d" * 64, request_id="req-002"),
        now_monotonic=700.0,
        projection_verified=True,
        shared_integrity_healthy=True,
    )
    assert result.action is RecoveryAction.NONE


def test_same_failed_observation_is_deterministic_and_not_replayed() -> None:
    value = snapshot(last_heartbeat_monotonic=680.0)
    first = decide_recovery(
        value,
        now_monotonic=700.0,
        projection_verified=True,
        shared_integrity_healthy=True,
    )
    second = decide_recovery(
        value,
        now_monotonic=700.0,
        projection_verified=True,
        shared_integrity_healthy=True,
    )
    assert first == second
    assert first.action is RecoveryAction.DIAGNOSE
