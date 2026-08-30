"""Fail-closed storage pressure policy for forensic control-plane state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class StorageObservation:
    cas_bytes: int
    trace_bytes: int
    projection_bytes: int
    quarantine_bytes: int
    free_bytes: int

    def __post_init__(self) -> None:
        for name in (
            "cas_bytes",
            "trace_bytes",
            "projection_bytes",
            "quarantine_bytes",
            "free_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")

    @property
    def total_bytes(self) -> int:
        return (
            self.cas_bytes
            + self.trace_bytes
            + self.projection_bytes
            + self.quarantine_bytes
        )


@dataclass(frozen=True, slots=True)
class StoragePolicy:
    """Limits for append-only forensic state.

    The defaults are intentionally conservative.  This policy never removes evidence; it only
    refuses new dispatch when pressure is unsafe.
    """

    soft_total_bytes: int = 1_073_741_824
    hard_total_bytes: int = 2_147_483_648
    minimum_free_bytes: int = 536_870_912
    quarantine_soft_limit_bytes: int = 268_435_456
    quarantine_hard_limit_bytes: int = 536_870_912

    def __post_init__(self) -> None:
        for name in (
            "soft_total_bytes",
            "hard_total_bytes",
            "minimum_free_bytes",
            "quarantine_soft_limit_bytes",
            "quarantine_hard_limit_bytes",
        ):
            _positive_int(getattr(self, name), name)
        if self.soft_total_bytes > self.hard_total_bytes:
            raise ValueError("hard_total_bytes must be at least soft_total_bytes")
        if self.quarantine_soft_limit_bytes > self.quarantine_hard_limit_bytes:
            raise ValueError(
                "quarantine_hard_limit_bytes must be at least quarantine_soft_limit_bytes"
            )


class StorageDisposition(StrEnum):
    ACCEPT = "ACCEPT"
    BACKPRESSURE = "BACKPRESSURE"
    HALT_NEW_DISPATCH = "HALT_NEW_DISPATCH"


def decide_storage(
    observation: StorageObservation,
    policy: StoragePolicy,
) -> StorageDisposition:
    """Return the most restrictive disposition implied by one storage observation."""

    if not isinstance(observation, StorageObservation):
        raise TypeError("observation must be a StorageObservation")
    if not isinstance(policy, StoragePolicy):
        raise TypeError("policy must be a StoragePolicy")
    if (
        observation.total_bytes >= policy.hard_total_bytes
        or observation.free_bytes < policy.minimum_free_bytes
        or observation.quarantine_bytes >= policy.quarantine_hard_limit_bytes
    ):
        return StorageDisposition.HALT_NEW_DISPATCH
    if (
        observation.total_bytes >= policy.soft_total_bytes
        or observation.quarantine_bytes >= policy.quarantine_soft_limit_bytes
    ):
        return StorageDisposition.BACKPRESSURE
    return StorageDisposition.ACCEPT


__all__ = [
    "StorageDisposition",
    "StorageObservation",
    "StoragePolicy",
    "decide_storage",
]
