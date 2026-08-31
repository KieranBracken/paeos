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
    invalid_sequence = False
    observed_failure_code = None
    evidence_refs: list[str] = []

    for event in observations:
        payload = event.payload or {}
        if payload.get("canary_id") == manifest.canary_id:
            if event.kind == "CANARY_INSTALLED":
                if installed or reached or killed:
                    invalid_sequence = True
                else:
                    installed = True
            elif event.kind == "CANARY_REACHED":
                if not installed or reached or killed:
                    invalid_sequence = True
                else:
                    reached = True
            elif event.kind == "CANARY_KILLED":
                observed_code = str(payload.get("observed_failure_code", ""))
                evidence_ref = payload.get("evidence_ref")
                if (
                    not installed
                    or not reached
                    or killed
                    or observed_code != manifest.expected_failure_code
                    or not isinstance(evidence_ref, str)
                    or not evidence_ref.strip()
                ):
                    invalid_sequence = True
                else:
                    killed = True
                    observed_failure_code = observed_code
                    evidence_refs.append(evidence_ref)

    return CanaryResult(
        canary_id=manifest.canary_id,
        installed=installed,
        reached=reached,
        killed=killed and not invalid_sequence,
        observed_failure_code=observed_failure_code,
        evidence_refs=tuple(evidence_refs),
    )
