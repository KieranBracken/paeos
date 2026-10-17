"""Multi-sensor Continuous Weakness Finder package.

Exposes sensor packs, coordinator, and finding data models.
Preserves existing 9 MDG probes as Sensor Pack 1.
"""

from runtime.autonomy.weakness_finder.coordinator import ContinuousWeaknessFinder
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

__all__ = [
    "ArchitectureDriftSensorPack",
    "ContinuousWeaknessFinder",
    "FindingSeverity",
    "MDGStructuralSensorPack",
    "SemanticScopeSensorPack",
    "SensorFinding",
    "SensorPack",
    "StructuralQuestionSensorPack",
    "WeaknessCategory",
]
