"""Coordinator for the multi-sensor Continuous Weakness Finder.

Strictly Advisory Invariant:
Weakness Finder provides diagnostic audit findings and remediation recommendations.
It CANNOT self-authorize remediation missions or self-promote candidates.
"""

from __future__ import annotations

from typing import Any, Sequence

from runtime.autonomy.weakness_finder.sensor_pack_drift import ArchitectureDriftSensorPack
from runtime.autonomy.weakness_finder.sensor_pack_mdg import MDGStructuralSensorPack
from runtime.autonomy.weakness_finder.sensor_pack_semantic import SemanticScopeSensorPack
from runtime.autonomy.weakness_finder.sensor_pack_structural import StructuralQuestionSensorPack
from runtime.autonomy.weakness_finder.types import (
    FindingSeverity,
    SensorFinding,
    SensorPack,
    WeaknessCategory,
)


class ContinuousWeaknessFinder:
    """Multi-sensor diagnostic scanner auditing PAEOS estate health."""

    def __init__(self, sensor_packs: Sequence[SensorPack] | None = None) -> None:
        if sensor_packs is not None:
            self._packs = list(sensor_packs)
        else:
            self._packs = [
                MDGStructuralSensorPack(),
                SemanticScopeSensorPack(),
                ArchitectureDriftSensorPack(),
                StructuralQuestionSensorPack(),
            ]

    @property
    def is_advisory_only(self) -> bool:
        """Constitutional invariant: Weakness Finder is strictly advisory."""
        return True

    def register_sensor_pack(self, pack: SensorPack) -> None:
        """Register an additional sensor pack."""
        self._packs.append(pack)

    def scan_all(self, context: Any) -> list[SensorFinding]:
        """Execute all registered sensor packs and return deduplicated findings."""
        raw_findings: list[SensorFinding] = []
        for pack in self._packs:
            try:
                findings = pack.scan(context)
                raw_findings.extend(findings)
            except Exception:
                # Sensor failures are captured safely without crashing the hypervisor
                continue

        # Deduplicate by dedup_signature
        seen_signatures: set[str] = set()
        deduped: list[SensorFinding] = []
        for f in raw_findings:
            if f.dedup_signature not in seen_signatures:
                seen_signatures.add(f.dedup_signature)
                deduped.append(f)

        return deduped

    def generate_remediation_proposals(self, findings: Sequence[SensorFinding]) -> list[dict[str, Any]]:
        """Generate advisory remediation proposals for detected weaknesses.

        NOTE: These are strictly advisory recommendations for the MissionController
        or human engineer. The Weakness Finder itself has NO authority to dispatch tasks.
        """
        proposals = []
        for f in findings:
            if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.WARNING):
                proposals.append({
                    "advisory_remediation_id": f"REM-PROP-{f.dedup_signature}",
                    "finding_id": f.finding_id,
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "target_nodes": list(f.affected_nodes),
                    "action_summary": f.remediation_hint or f"Remediate {f.title}",
                    "requires_governed_authorization": True,
                })
        return proposals
