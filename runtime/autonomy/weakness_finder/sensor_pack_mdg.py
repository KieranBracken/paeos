"""Sensor Pack 1: MDG Structural Health Probes (preserves existing 9 probes)."""

from __future__ import annotations

from runtime.autonomy.mdg import MissionDependencyGraph
from runtime.autonomy.weakness_finder.types import (
    FindingSeverity,
    SensorFinding,
    WeaknessCategory,
)
from runtime.autonomy.weakness_finder_probes import WeaknessFinderProbes


class MDGStructuralSensorPack:
    """Sensor Pack 1: Audits MDG graph invariants using the 9 canonical graph probes."""
    name: str = "SensorPack1_MDG_Structural"
    category: WeaknessCategory = WeaknessCategory.MDG_STRUCTURAL

    def scan(self, context: MissionDependencyGraph) -> list[SensorFinding]:
        probes = WeaknessFinderProbes(context)
        raw_findings = probes.run_all()
        findings = []
        for rf in raw_findings:
            severity = FindingSeverity(rf.severity.value)
            findings.append(
                SensorFinding(
                    finding_id=rf.probe_id,
                    sensor_name="MDGStructuralSensorPack",
                    category=WeaknessCategory.MDG_STRUCTURAL,
                    severity=severity,
                    title=rf.probe_name,
                    description=rf.description,
                    affected_nodes=rf.affected_nodes,
                    remediation_hint=f"Check MDG task graph lifecycle invariants for {rf.affected_nodes}",
                )
            )
        return findings
