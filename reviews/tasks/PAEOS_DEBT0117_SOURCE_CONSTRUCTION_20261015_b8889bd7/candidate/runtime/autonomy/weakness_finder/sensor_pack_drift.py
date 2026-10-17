"""Sensor Pack 3: Architecture Drift & Invariant Probes."""

from __future__ import annotations

from typing import Any

from runtime.autonomy.weakness_finder.types import (
    FindingSeverity,
    SensorFinding,
    WeaknessCategory,
)


class ArchitectureDriftSensorPack:
    """Sensor Pack 3: Detects architectural invariant violations and unauthorized pattern drifts."""
    name: str = "SensorPack3_Architecture_Drift"
    category: WeaknessCategory = WeaknessCategory.ARCHITECTURE_DRIFT

    def scan(self, context: Any) -> list[SensorFinding]:
        findings: list[SensorFinding] = []
        # Checks if context provides changed files or paths
        paths = getattr(context, "changed_paths", ())
        for p in paths:
            if "constitution/" in p and not getattr(context, "founder_authorized", False):
                findings.append(
                    SensorFinding(
                        finding_id="WF-DFT-01",
                        sensor_name="ArchitectureDriftSensorPack",
                        category=WeaknessCategory.ARCHITECTURE_DRIFT,
                        severity=FindingSeverity.CRITICAL,
                        title="Unauthorized Constitution Modification Attempt",
                        description=f"Path '{p}' mutates constitution without Founder authorization token.",
                        affected_nodes=(p,),
                        remediation_hint="Route constitutional changes through Founder Ratification.",
                    )
                )
        return findings
