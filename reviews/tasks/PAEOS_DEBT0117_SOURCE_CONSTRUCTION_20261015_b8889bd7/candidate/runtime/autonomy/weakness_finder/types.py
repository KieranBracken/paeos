"""Types and data models for the multi-sensor Continuous Weakness Finder.

Strictly Advisory Invariant:
Weakness Finder provides continuous estate-wide diagnostic visibility,
generates finding records, and suggests remediation handoffs.
It CANNOT self-authorize remediation missions, self-issue capability tokens,
or bypass Court/promotion firewalls.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class WeaknessCategory(StrEnum):
    """The 12 canonical estate-wide weakness classes."""
    MDG_STRUCTURAL = "MDG_STRUCTURAL"
    SEMANTIC_SCOPE = "SEMANTIC_SCOPE"
    ARCHITECTURE_DRIFT = "ARCHITECTURE_DRIFT"
    EVIDENCE_PROVENANCE = "EVIDENCE_PROVENANCE"
    AUTHORITY_ENVELOPE = "AUTHORITY_ENVELOPE"
    PRODUCTION_PATH = "PRODUCTION_PATH"
    VERIFICATION_ORACLE = "VERIFICATION_ORACLE"
    STATE_RECOVERY = "STATE_RECOVERY"
    REASONING_RESOURCE = "REASONING_RESOURCE"
    COMPLETENESS = "COMPLETENESS"
    ADVERSARIAL_EXPLORATORY = "ADVERSARIAL_EXPLORATORY"
    SAKG_SCAR_RECURRENCE = "SAKG_SCAR_RECURRENCE"


class FindingSeverity(StrEnum):
    ADVISORY = "ADVISORY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class SensorFinding:
    """A structured finding emitted by a weakness sensor."""
    finding_id: str
    sensor_name: str
    category: WeaknessCategory
    severity: FindingSeverity
    title: str
    description: str
    affected_nodes: tuple[str, ...] = ()
    remediation_hint: str = ""
    dedup_signature: str = ""

    def __post_init__(self) -> None:
        if not self.dedup_signature:
            sig = hashlib.sha256(
                f"{self.category.value}:{self.title}:{sorted(self.affected_nodes)}".encode("utf-8")
            ).hexdigest()[:16]
            object.__setattr__(self, "dedup_signature", sig)


class SensorPack(Protocol):
    """Protocol implemented by all weakness sensor packs."""
    name: str
    category: WeaknessCategory

    def scan(self, context: Any) -> list[SensorFinding]:
        ...
