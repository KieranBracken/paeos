"""Hidden mutation and canary fault-injection harness (Gate F Task 2)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kernel.ledger import Event


@dataclass(frozen=True, slots=True)
class CanaryManifest:
    canary_id: str
    version: str
    target_hash: str
    mutation_hash: str
    expected_failure_code: str
    installer_hash: str


@dataclass(frozen=True, slots=True)
class CanaryResult:
    canary_id: str
    installed: bool
    reached: bool
    killed: bool
    observed_failure_code: str | None
    evidence_refs: tuple[str, ...]


def adjudicate_canary(
    manifest: CanaryManifest, observations: Sequence[Event]
) -> CanaryResult:
    installed = False
    reached = False
    killed = False
    observed_failure_code = None
    evidence_refs: list[str] = []

    for event in observations:
        payload = event.payload or {}
        if payload.get("canary_id") == manifest.canary_id:
            if event.kind == "CANARY_INSTALLED":
                installed = True
            elif event.kind == "CANARY_REACHED":
                reached = True
            elif event.kind == "CANARY_KILLED":
                observed_code = str(payload.get("observed_failure_code", ""))
                if observed_code == manifest.expected_failure_code:
                    killed = True
                    observed_failure_code = observed_code
                evidence_refs.append(str(payload.get("evidence_ref", "")))

    return CanaryResult(
        canary_id=manifest.canary_id,
        installed=installed,
        reached=reached,
        killed=killed,
        observed_failure_code=observed_failure_code,
        evidence_refs=tuple(evidence_refs),
    )
