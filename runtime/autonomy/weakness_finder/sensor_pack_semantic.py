"""Sensor Pack 2: Semantic Scope and Lineage Integrity Probes."""

from __future__ import annotations

from paeos.semantic.lineage import SemanticLineageDAG
from runtime.autonomy.mdg import MissionDependencyGraph
from runtime.autonomy.weakness_finder.types import (
    FindingSeverity,
    SensorFinding,
    WeaknessCategory,
)


class SemanticScopeSensorPack:
    """Sensor Pack 2: Probes for semantic scope collapse, unrepresented obligations, and dropped scope."""
    name: str = "SensorPack2_Semantic_Scope"
    category: WeaknessCategory = WeaknessCategory.SEMANTIC_SCOPE

    def scan(self, context: MissionDependencyGraph) -> list[SensorFinding]:
        findings: list[SensorFinding] = []
        lineage = context.semantic_lineage

        # Check each task in graph for unrepresented parent obligations
        for task in context.tasks.values():
            if not task.parent_task_id:
                continue

            parent_obs = lineage.get_task_obligations(task.parent_task_id)
            if not parent_obs:
                continue

            child_obs = lineage.get_task_obligations(task.task_id)
            child_ob_ids = {o.obligation_id for o in child_obs}
            child_disps = lineage.get_task_dispositions(task.task_id)

            for p_ob in parent_obs:
                if p_ob.obligation_id not in child_ob_ids and p_ob.obligation_id not in child_disps:
                    findings.append(
                        SensorFinding(
                            finding_id="WF-SEM-01",
                            sensor_name="SemanticScopeSensorPack",
                            category=WeaknessCategory.SEMANTIC_SCOPE,
                            severity=FindingSeverity.CRITICAL,
                            title="Unrepresented Parent Obligation",
                            description=(
                                f"Task '{task.task_id}' has parent '{task.parent_task_id}' with obligation "
                                f"'{p_ob.obligation_id}' ({p_ob.description}) that is neither inherited nor deferred."
                            ),
                            affected_nodes=(task.task_id, task.parent_task_id),
                            remediation_hint="Bind parent obligation in child task or record lawful AUTHORIZED_DEFERMENT.",
                        )
                    )

        return findings
