"""Canary calibration harness (scaffold) — PAEOS-8 §10 B0.14 / PAEOS-7 §5.3.

A **canary** is a deliberately-planted *known-bad* artifact. If a detector (the Court, the
Adversary, a gate) fails to catch a canary, the detector is miscalibrated — a **miss** — which is
an alarm (the FR-2/FR-3 tripwire, §5.3). Canaries live in `constitution/canaries/` (Z0, immutable)
and are versioned like the rest of the constitution.

This module is the Phase-0 **scaffold**: the canary format (`Canary`), a loader, and a harness
that submits a canary to a *detector* and records catch/miss (`CanaryResult`). The detector is
injected — real catching (running the artifact through the Court) arrives in Phase 1; here the
harness just records the result, which is all B0.14 requires.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from kernel.ledger import JsonValue

__all__ = [
    "CANARY_GLOB",
    "EXPECTED_CAUGHT",
    "Canary",
    "CanaryResult",
    "Detector",
    "load_canaries",
    "load_canary",
    "run_calibration",
    "run_canary",
]

CANARY_GLOB = "CANARY-*.json"
EXPECTED_CAUGHT = "CAUGHT"


@dataclass(frozen=True, slots=True)
class Canary:
    """A known-bad artifact + how a correct detector should recognise it."""

    id: str
    category: str  # the defect class, e.g. "forged-evidence"
    description: str
    expected: str  # "CAUGHT" — a correct detector must catch it
    detection_signature: str  # how it should be recognised
    artifact: Mapping[str, JsonValue]  # the known-bad artifact


@dataclass(frozen=True, slots=True)
class CanaryResult:
    """The outcome of submitting a canary to a detector."""

    canary_id: str
    expected: str
    caught: bool
    passed: bool  # caught == (expected is CAUGHT): the detector behaved correctly
    detail: str


# A detector returns True iff it caught the canary's bad artifact.
Detector = Callable[[Canary], bool]


def load_canary(path: str | Path) -> Canary:
    """Parse one canary JSON file."""
    data: JsonValue = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"canary {path} is not a JSON object")
    artifact = data["artifact"]
    if not isinstance(artifact, dict):
        raise ValueError(f"canary {path} has a non-object artifact")
    return Canary(
        id=_s(data, "id"),
        category=_s(data, "category"),
        description=_s(data, "description"),
        expected=_s(data, "expected"),
        detection_signature=_s(data, "detection_signature"),
        artifact=artifact,
    )


def load_canaries(directory: str | Path) -> list[Canary]:
    """Load every `CANARY-*.json` in `directory`, sorted by id."""
    root = Path(directory)
    return sorted((load_canary(p) for p in root.glob(CANARY_GLOB)), key=lambda c: c.id)


def run_canary(canary: Canary, detector: Detector) -> CanaryResult:
    """Submit `canary` to `detector`; record catch/miss. A `CAUGHT`-expected canary the detector
    does not catch is a MISS (`passed=False`) — a calibration alarm."""
    caught = detector(canary)
    should_catch = canary.expected == EXPECTED_CAUGHT
    passed = caught == should_catch
    if caught:
        detail = "caught as expected" if should_catch else "caught (unexpected)"
    else:
        detail = "MISS: not caught" if should_catch else "not caught (expected)"
    return CanaryResult(
        canary_id=canary.id,
        expected=canary.expected,
        caught=caught,
        passed=passed,
        detail=detail,
    )


def run_calibration(canaries: Iterable[Canary], detector: Detector) -> list[CanaryResult]:
    """Run a detector over a set of canaries, recording one result each."""
    return [run_canary(canary, detector) for canary in canaries]


def _s(data: Mapping[str, JsonValue], key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"canary field {key!r} must be a string, got {type(value).__name__}")
    return value
