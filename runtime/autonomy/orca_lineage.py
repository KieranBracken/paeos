"""Orca Mission Control read-only lineage projection adapter."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from kernel.ledger import Ledger
from runtime.autonomy.mdg import EdgeType, MissionDependencyGraph, TaskStatus


class OrcaLineageProjection:
    """Provides read-only MDG lineage projections without acquiring locks or mutating state."""

    def __init__(self, graph: MissionDependencyGraph) -> None:
        self.graph = graph

    @classmethod
    def from_durable_ledger(cls, ledger: Ledger) -> OrcaLineageProjection:
        """Construct read-only projection directly from the authoritative append-only ledger."""
        graph = MissionDependencyGraph.from_ledger(ledger)
        return cls(graph)

    def query_lineage(self, root_mission_id: str) -> dict[str, Any]:
        """GET /api/v1/missions/{root_mission_id}/lineage read-only query projection."""
        # Filter tasks belonging to this root mission
        mission_tasks = {
            t_id: t
            for t_id, t in self.graph.tasks.items()
            if t.root_mission_id == root_mission_id or t.task_id == root_mission_id
        }

        # Find active leaf tasks (tasks with no children in mission_tasks)
        parents_with_children = {
            t.parent_task_id for t in mission_tasks.values() if t.parent_task_id
        }
        leaf_tasks = [
            t_id for t_id, t in mission_tasks.items()
            if t_id not in parents_with_children and t.status in {TaskStatus.ACTIVE, TaskStatus.SUSPENDED}
        ]

        # Calculate blocking chains from root to each leaf
        blocking_chains = []
        for leaf_id in leaf_tasks:
            chain = self.graph.get_lineage(leaf_id)
            blocking_chains.append(chain)

        # Projected resume targets: suspended tasks in this mission
        suspended_targets = []
        for t_id, t in mission_tasks.items():
            if t.status is TaskStatus.SUSPENDED:
                active_blockers = self.graph.get_active_blockers_for_task(t_id)
                suspended_targets.append({
                    "task_id": t_id,
                    "checkpoint_ref": t.checkpoint_ref,
                    "fencing_token": t.fencing_token,
                    "active_blockers_count": len(active_blockers),
                    "active_blocker_ids": [b.blocker_id for b in active_blockers],
                    "can_resume_now": len(active_blockers) == 0,
                })

        # Edges involving these tasks
        relevant_edges = [
            asdict(e)
            for e in self.graph.edges
            if e.source_id in mission_tasks or e.target_id in mission_tasks
        ]

        return {
            "root_mission_id": root_mission_id,
            "total_tasks_count": len(mission_tasks),
            "tasks": {t_id: asdict(t) for t_id, t in mission_tasks.items()},
            "active_leaf_tasks": leaf_tasks,
            "blocking_chains": blocking_chains,
            "projected_resume_targets": suspended_targets,
            "edges": relevant_edges,
            "is_read_only": True,
            "classification": "OPERATIONAL_READ_PROJECTION_ENDPOINT",
        }


def handle_orca_lineage_request(
    root_mission_id: str,
    ledger: Ledger,
) -> tuple[int, dict[str, Any]]:
    """Operational HTTP/API endpoint router for GET /api/v1/missions/{root_mission_id}/lineage."""
    projection = OrcaLineageProjection.from_durable_ledger(ledger)
    result = projection.query_lineage(root_mission_id)
    if not result["tasks"]:
        return 404, {"error": f"Mission {root_mission_id} not found", "is_read_only": True}
    return 200, result
