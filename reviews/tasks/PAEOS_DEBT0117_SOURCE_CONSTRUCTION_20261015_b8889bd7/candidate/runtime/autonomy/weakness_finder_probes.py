"""Weakness Finder 9 advisory MDG graph-health invariant probes (WF-MDG-01 through WF-MDG-09)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from runtime.autonomy.authority import FindingClass
from runtime.autonomy.cycle_detector import would_cause_cycle
from runtime.autonomy.mdg import BlockerStatus, EdgeType, MissionDependencyGraph, TaskStatus


class ProbeSeverity(StrEnum):
    ADVISORY = "ADVISORY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ProbeFinding:
    probe_id: str
    probe_name: str
    severity: ProbeSeverity
    description: str
    affected_nodes: tuple[str, ...]

    @property
    def detail(self) -> str:
        return self.description


class WeaknessFinderProbes:
    """Audits MDG graph health and invariants without direct mutation authority."""

    def __init__(self, graph: MissionDependencyGraph) -> None:
        self.graph = graph

    def run_all(self) -> list[ProbeFinding]:
        findings: list[ProbeFinding] = []
        findings.extend(self.probe_wf_mdg_01_orphan_detector())
        findings.extend(self.probe_wf_mdg_02_deadlock_abandoned_parent())
        findings.extend(self.probe_wf_mdg_03_zombie_completed_child())
        findings.extend(self.probe_wf_mdg_04_blocker_recurrence_flapping())
        findings.extend(self.probe_wf_mdg_05_excessive_nesting_depth())
        findings.extend(self.probe_wf_mdg_06_low_information_churn())
        findings.extend(self.probe_wf_mdg_07_cyclic_dependency_invariant())
        findings.extend(self.probe_wf_mdg_08_spurious_blocker_probe())
        findings.extend(self.probe_wf_mdg_09_unreachable_root_objective())
        return findings

    run_all_probes = run_all

    def probe_wf_mdg_01_orphan_detector(self) -> list[ProbeFinding]:
        """WF-MDG-01: Child tasks whose parent task is missing or terminated abnormally."""
        findings = []
        for task in self.graph.tasks.values():
            if task.parent_task_id is not None:
                parent = self.graph.tasks.get(task.parent_task_id)
                if parent is None:
                    findings.append(
                        ProbeFinding(
                            probe_id="WF-MDG-01",
                            probe_name="Orphan Detector",
                            severity=ProbeSeverity.CRITICAL,
                            description=f"Task {task.task_id} has missing parent {task.parent_task_id}",
                            affected_nodes=(task.task_id,),
                        )
                    )
        return findings

    def probe_wf_mdg_02_deadlock_abandoned_parent(self) -> list[ProbeFinding]:
        """WF-MDG-02: Suspended parents with no active blocker or active remediation child."""
        findings = []
        for task in self.graph.tasks.values():
            if task.status is TaskStatus.SUSPENDED:
                active_blockers = self.graph.get_active_blockers_for_task(task.task_id)
                # Check for any active child task spawned by this task
                active_children = [
                    t for t in self.graph.tasks.values()
                    if t.parent_task_id == task.task_id and t.status in {TaskStatus.ACTIVE, TaskStatus.SUSPENDED}
                ]
                if not active_blockers and not active_children:
                    findings.append(
                        ProbeFinding(
                            probe_id="WF-MDG-02",
                            probe_name="Deadlock / Abandoned Parent",
                            severity=ProbeSeverity.WARNING,
                            description=f"Suspended parent {task.task_id} has no active blockers and no active children",
                            affected_nodes=(task.task_id,),
                        )
                    )
        return findings

    def probe_wf_mdg_03_zombie_completed_child(self) -> list[ProbeFinding]:
        """WF-MDG-03: Child marked TERMINAL_SUCCESS whose parent was never resumed."""
        findings = []
        for task in self.graph.tasks.values():
            if task.status is TaskStatus.TERMINAL_SUCCESS and task.parent_task_id:
                parent = self.graph.tasks.get(task.parent_task_id)
                if parent and parent.status is TaskStatus.SUSPENDED:
                    # If all blockers for parent are extinguished, this child is a zombie completed child
                    if self.graph.can_resume_task(parent.task_id):
                        findings.append(
                            ProbeFinding(
                                probe_id="WF-MDG-03",
                                probe_name="Zombie Completed Child",
                                severity=ProbeSeverity.WARNING,
                                description=f"Child {task.task_id} completed successfully but parent {parent.task_id} remains suspended",
                                affected_nodes=(task.task_id, parent.task_id),
                            )
                        )
        return findings

    def probe_wf_mdg_04_blocker_recurrence_flapping(self) -> list[ProbeFinding]:
        """WF-MDG-04: Identical blocker signatures repeatedly spawned across multiple tasks."""
        findings = []
        signatures = [b.signature for b in self.graph.blockers.values()]
        counts = Counter(signatures)
        for sig, count in counts.items():
            if count >= 3:
                affected = tuple(
                    b.blocker_id for b in self.graph.blockers.values() if b.signature == sig
                )
                findings.append(
                    ProbeFinding(
                        probe_id="WF-MDG-04",
                        probe_name="Blocker Recurrence Flapping",
                        severity=ProbeSeverity.WARNING,
                        description=f"Blocker signature '{sig}' spawned {count} times across graph",
                        affected_nodes=affected,
                    )
                )
        return findings

    def probe_wf_mdg_05_excessive_nesting_depth(self) -> list[ProbeFinding]:
        """WF-MDG-05: Nesting depth approaching or exceeding circuit breaker."""
        findings = []
        for task in self.graph.tasks.values():
            if task.nesting_depth >= 4:
                findings.append(
                    ProbeFinding(
                        probe_id="WF-MDG-05",
                        probe_name="Excessive Nesting Depth & Churn",
                        severity=ProbeSeverity.WARNING,
                        description=f"Task {task.task_id} has high nesting depth {task.nesting_depth}",
                        affected_nodes=(task.task_id,),
                    )
                )
        return findings

    def probe_wf_mdg_06_low_information_churn(self) -> list[ProbeFinding]:
        """WF-MDG-06: Recursive remediation retries without distinct diagnostics."""
        findings = []
        supersedes_edges = [e for e in self.graph.edges if e.edge_type is EdgeType.SUPERSEDES]
        if len(supersedes_edges) >= 3:
            findings.append(
                ProbeFinding(
                    probe_id="WF-MDG-06",
                    probe_name="Low-Information Recursive Churn",
                    severity=ProbeSeverity.ADVISORY,
                    description=f"{len(supersedes_edges)} SUPERSEDES edges detected across graph",
                    affected_nodes=tuple(e.source_id for e in supersedes_edges),
                )
            )
        return findings

    def probe_wf_mdg_07_cyclic_dependency_invariant(self) -> list[ProbeFinding]:
        """WF-MDG-07: Verifies graph topology remains strictly acyclic."""
        findings = []
        dep_edges = [
            (e.source_id, e.target_id)
            for e in self.graph.edges
            if e.edge_type in {EdgeType.BLOCKS, EdgeType.DEPENDS_ON}
        ]
        nodes = set(self.graph.tasks.keys()) | set(self.graph.blockers.keys())
        # If any edge forms a cycle
        for src, dst in dep_edges:
            other_edges = [e for e in dep_edges if e != (src, dst)]
            if would_cause_cycle(nodes, other_edges, (src, dst)):
                findings.append(
                    ProbeFinding(
                        probe_id="WF-MDG-07",
                        probe_name="Cyclic Dependency Invariant",
                        severity=ProbeSeverity.CRITICAL,
                        description=f"Cycle detected involving edge {src} -> {dst}",
                        affected_nodes=(src, dst),
                    )
                )
        return findings

    def probe_wf_mdg_08_spurious_blocker_probe(self) -> list[ProbeFinding]:
        """WF-MDG-08: Tasks suspended on non-blocking findings or future improvements."""
        findings = []
        for edge in self.graph.edges:
            if edge.edge_type is EdgeType.BLOCKS:
                blocker = self.graph.blockers.get(edge.source_id)
                if blocker and blocker.finding_class != FindingClass.CURRENT_BLOCKER:
                    findings.append(
                        ProbeFinding(
                            probe_id="WF-MDG-08",
                            probe_name="Spurious Blocker Probe",
                            severity=ProbeSeverity.CRITICAL,
                            description=f"Task {edge.target_id} blocked by non-CURRENT_BLOCKER finding ({blocker.finding_class.value})",
                            affected_nodes=(edge.target_id, edge.source_id),
                        )
                    )
        return findings

    def probe_wf_mdg_09_unreachable_root_objective(self) -> list[ProbeFinding]:
        """WF-MDG-09: Remediation failure rendering root objective impossible."""
        findings = []
        for task in self.graph.tasks.values():
            if task.status is TaskStatus.TERMINAL_FAILURE and not task.parent_task_id:
                findings.append(
                    ProbeFinding(
                        probe_id="WF-MDG-09",
                        probe_name="Unreachable Root Objective",
                        severity=ProbeSeverity.CRITICAL,
                        description=f"Root mission {task.task_id} is in TERMINAL_FAILURE state",
                        affected_nodes=(task.task_id,),
                    )
                )
        return findings
