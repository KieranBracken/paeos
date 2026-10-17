from __future__ import annotations

import pytest
from runtime.control_plane.storage_policy import (
    StorageDisposition,
    StorageObservation,
    StoragePolicy,
    decide_storage,
)


def observation(**changes: int) -> StorageObservation:
    values = {
        "cas_bytes": 100,
        "trace_bytes": 100,
        "projection_bytes": 100,
        "quarantine_bytes": 100,
        "free_bytes": 1_000_000_000,
    }
    values.update(changes)
    return StorageObservation(**values)


def test_accepts_below_soft_limits() -> None:
    assert decide_storage(observation(), StoragePolicy()) is StorageDisposition.ACCEPT


def test_soft_pressure_applies_backpressure_without_deleting_evidence() -> None:
    policy = StoragePolicy(soft_total_bytes=1_000, hard_total_bytes=2_000)
    result = decide_storage(observation(cas_bytes=800), policy)
    assert result is StorageDisposition.BACKPRESSURE


def test_hard_pressure_halts_new_dispatch() -> None:
    policy = StoragePolicy(soft_total_bytes=1_000, hard_total_bytes=2_000)
    assert (
        decide_storage(observation(cas_bytes=1_700, free_bytes=100), policy)
        is StorageDisposition.HALT_NEW_DISPATCH
    )
    assert (
        decide_storage(observation(free_bytes=499), StoragePolicy(minimum_free_bytes=500))
        is StorageDisposition.HALT_NEW_DISPATCH
    )


def test_quarantine_growth_has_its_own_soft_and_hard_boundaries() -> None:
    policy = StoragePolicy(
        soft_total_bytes=10_000,
        hard_total_bytes=20_000,
        quarantine_soft_limit_bytes=500,
        quarantine_hard_limit_bytes=800,
    )
    assert (
        decide_storage(observation(quarantine_bytes=500), policy)
        is StorageDisposition.BACKPRESSURE
    )
    assert (
        decide_storage(observation(quarantine_bytes=800), policy)
        is StorageDisposition.HALT_NEW_DISPATCH
    )


@pytest.mark.parametrize(
    "field",
    ["cas_bytes", "trace_bytes", "projection_bytes", "quarantine_bytes", "free_bytes"],
)
def test_observation_rejects_negative_and_boolean_values(field: str) -> None:
    values = {
        "cas_bytes": 1,
        "trace_bytes": 1,
        "projection_bytes": 1,
        "quarantine_bytes": 1,
        "free_bytes": 1,
    }
    values[field] = -1
    with pytest.raises(ValueError):
        StorageObservation(**values)
    values[field] = True
    with pytest.raises(TypeError):
        StorageObservation(**values)  # type: ignore[arg-type]


def test_policy_limits_are_ordered_and_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        StoragePolicy(soft_total_bytes=0)
    with pytest.raises(ValueError, match="hard"):
        StoragePolicy(soft_total_bytes=2_000, hard_total_bytes=1_000)
    with pytest.raises(ValueError, match="quarantine"):
        StoragePolicy(quarantine_soft_limit_bytes=900, quarantine_hard_limit_bytes=800)
