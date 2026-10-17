"""Mission Dependency Graph (MDG) core data model and lineage ledger projection."""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from runtime.autonomy.authority import FindingClass
from runtime.autonomy.cycle_detector import CycleDetectedError, would_cause_cycle
from paeos.semantic.lineage import SemanticLineageDAG
from paeos.semantic.types import SemanticObligation, SemanticObligationDisposition


class EdgeType(StrEnum):
    BLOCKS = "BLOCKS"
    SPAWNED_BY = "SPAWNED_BY"
    REMEDIATES = "REMEDIATES"
    DEPENDS_ON = "DEPENDS_ON"
    RESUMES = "RESUMES"
    SUPERSEDES = "SUPERSEDES"


class TaskStatus(StrEnum):
    INIT = "INIT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    SUSPENDED_CIRCUIT_BREAKER = "SUSPENDED_CIRCUIT_BREAKER"
    RESUMING = "RESUMING"
    TERMINAL_SUCCESS = "TERMINAL_SUCCESS"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"


class BlockerStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXTINGUISHED = "EXTINGUISHED"


class CeremonyTrace(StrEnum):
    TRACE_A = "TRACE_A"
    TRACE_B = "TRACE_B"


@dataclass(frozen=True, slots=True)
class TaskNode:
    task_id: str
    root_mission_id: str
    parent_task_id: str | None
    nesting_depth: int
    status: TaskStatus
    checkpoint_ref: str | None = None
    fencing_token: int = 0
    ceremony_trace: CeremonyTrace = CeremonyTrace.TRACE_B
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BlockerNode:
    blocker_id: str
    finding_class: FindingClass
    signature: str
    status: BlockerStatus
    created_at_utc: str


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    edge_type: EdgeType
    source_id: str
    target_id: str
    created_at_utc: str


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, (set, frozenset)):
        return sorted(list(obj))
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if hasattr(obj, "value"):
        return obj.value
    return obj


class MissionDependencyGraph:
    """Canonical directed acyclic graph tracking mission, tasks, blockers, and dependencies."""

    def __init__(self, ledger: Any | None = None) -> None:
        self._ledger = ledger
        self._tasks: dict[str, TaskNode] = {}
        self._blockers: dict[str, BlockerNode] = {}
        self._edges: list[DependencyEdge] = []
        self._semantic_lineage: SemanticLineageDAG = SemanticLineageDAG()

    def attach_ledger(self, ledger: Any) -> None:
        self._ledger = ledger

    @property
    def semantic_lineage(self) -> SemanticLineageDAG:
        return self._semantic_lineage

    def _commit_event(self, kind: str, payload: dict[str, Any]) -> int:
        if self._ledger is not None:
            from kernel.ledger import Event
            return self._ledger.append(Event(1, kind, _json_safe(payload)))
        return 0

    @property
    def tasks(self) -> dict[str, TaskNode]:
        return dict(self._tasks)

    @property
    def blockers(self) -> dict[str, BlockerNode]:
        return dict(self._blockers)

    @property
    def edges(self) -> list[DependencyEdge]:
        return list(self._edges)

    def spawn_task(
        self,
        task_id: str,
        root_mission_id: str,
        parent_task_id: str | None = None,
        nesting_depth: int = 0,
        ceremony_trace: CeremonyTrace = CeremonyTrace.TRACE_B,
        metadata: dict[str, Any] | None = None,
        semantic_obligations: tuple[SemanticObligation, ...] = (),
        semantic_dispositions: tuple[SemanticObligationDisposition, ...] = (),
    ) -> TaskNode:
        if task_id in self._tasks:
            raise ValueError(f"Task {task_id} already exists in MDG")

        # Validate semantic obligation inheritance
        if parent_task_id:
            self._semantic_lineage.validate_child_spawn(
                parent_task_id=parent_task_id,
                child_task_id=task_id,
                child_obligations=semantic_obligations,
                child_dispositions=semantic_dispositions,
            )

        if semantic_obligations or semantic_dispositions:
            self._semantic_lineage.register_task_obligations(
                task_id=task_id,
                obligations=semantic_obligations,
                dispositions=semantic_dispositions,
                parent_task_id=parent_task_id,
            )

        node = TaskNode(
            task_id=task_id,
            root_mission_id=root_mission_id,
            parent_task_id=parent_task_id,
            nesting_depth=nesting_depth,
            status=TaskStatus.ACTIVE,
            ceremony_trace=ceremony_trace,
            metadata=metadata or {},
        )
        self._tasks[task_id] = node
        self._commit_event("MDG_TASK_SPAWNED", asdict(node))
        if parent_task_id:
            self.add_edge(EdgeType.SPAWNED_BY, task_id, parent_task_id)
        return node

    def register_blocker(
        self,
        blocker_id: str,
        finding_class: FindingClass,
        signature: str,
        blocked_task_id: str | None = None,
    ) -> BlockerNode:
        if blocker_id in self._blockers:
            raise ValueError(f"Blocker {blocker_id} already exists in MDG")
        blocker = BlockerNode(
            blocker_id=blocker_id,
            finding_class=finding_class,
            signature=signature,
            status=BlockerStatus.ACTIVE,
            created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        self._blockers[blocker_id] = blocker
        self._commit_event("MDG_BLOCKER_REGISTERED", asdict(blocker))
        if blocked_task_id:
            self.add_edge(EdgeType.BLOCKS, blocker_id, blocked_task_id)
        return blocker

    def add_edge(self, edge_type: EdgeType, source_id: str, target_id: str) -> DependencyEdge:
        """Add a typed dependency edge, validating cycle invariants for BLOCKS/DEPENDS_ON."""
        if edge_type in {EdgeType.BLOCKS, EdgeType.DEPENDS_ON}:
            existing_blocks = [
                (e.source_id, e.target_id)
                for e in self._edges
                if e.edge_type in {EdgeType.BLOCKS, EdgeType.DEPENDS_ON}
            ]
            all_blocks = existing_blocks + [(source_id, target_id)]
            nodes = set()
            for u, v in all_blocks:
                nodes.add(u)
                nodes.add(v)
            if would_cause_cycle(list(nodes), existing_blocks, (source_id, target_id)):
                raise CycleDetectedError(
                    f"Adding edge {edge_type} from {source_id} to {target_id} would create a cycle"
                )

        edge = DependencyEdge(
            edge_type=edge_type,
            source_id=source_id,
            target_id=target_id,
            created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        self._edges.append(edge)
        self._commit_event("MDG_EDGE_COMMITTED", asdict(edge))
        return edge

    def suspend_task(self, task_id: str, checkpoint_ref: str) -> TaskNode:
        task = self._tasks[task_id]
        updated = TaskNode(
            task_id=task.task_id,
            root_mission_id=task.root_mission_id,
            parent_task_id=task.parent_task_id,
            nesting_depth=task.nesting_depth,
            status=TaskStatus.SUSPENDED,
            checkpoint_ref=checkpoint_ref,
            fencing_token=task.fencing_token,
            ceremony_trace=task.ceremony_trace,
            metadata=task.metadata,
        )
        self._tasks[task_id] = updated
        self._commit_event("MDG_TASK_SUSPENDED", asdict(updated))
        return updated

    def suspend_circuit_breaker(self, task_id: str, reason: str = "") -> TaskNode:
        task = self._tasks[task_id]
        meta = dict(task.metadata)
        meta["circuit_breaker_reason"] = reason
        updated = TaskNode(
            task_id=task.task_id,
            root_mission_id=task.root_mission_id,
            parent_task_id=task.parent_task_id,
            nesting_depth=task.nesting_depth,
            status=TaskStatus.SUSPENDED_CIRCUIT_BREAKER,
            checkpoint_ref=task.checkpoint_ref,
            fencing_token=task.fencing_token,
            ceremony_trace=task.ceremony_trace,
            metadata=meta,
        )
        self._tasks[task_id] = updated
        self._commit_event("MDG_TASK_CIRCUIT_BREAKER", asdict(updated))
        return updated

    def extinguish_blocker(self, blocker_id: str) -> BlockerNode:
        blocker = self._blockers[blocker_id]
        updated = BlockerNode(
            blocker_id=blocker.blocker_id,
            finding_class=blocker.finding_class,
            signature=blocker.signature,
            status=BlockerStatus.EXTINGUISHED,
            created_at_utc=blocker.created_at_utc,
        )
        self._blockers[blocker_id] = updated
        self._commit_event("MDG_BLOCKER_EXTINGUISHED", asdict(updated))
        return updated

    def get_active_blockers_for_task(self, task_id: str) -> list[BlockerNode]:
        blocker_ids = [
            e.source_id
            for e in self._edges
            if e.edge_type is EdgeType.BLOCKS and e.target_id == task_id
        ]
        return [
            self._blockers[bid]
            for bid in blocker_ids
            if bid in self._blockers and self._blockers[bid].status is BlockerStatus.ACTIVE
        ]

    def can_resume_task(self, task_id: str) -> bool:
        """True iff task is SUSPENDED and has zero active blockers in precondition set."""
        task = self._tasks.get(task_id)
        if task is None or task.status is not TaskStatus.SUSPENDED:
            return False
        active_blockers = self.get_active_blockers_for_task(task_id)
        return len(active_blockers) == 0

    def resume_task(self, task_id: str, new_fencing_token: int) -> TaskNode:
        if not self.can_resume_task(task_id):
            raise ValueError(f"Task {task_id} cannot be resumed: active blockers remain or not suspended")
        task = self._tasks[task_id]
        updated = TaskNode(
            task_id=task.task_id,
            root_mission_id=task.root_mission_id,
            parent_task_id=task.parent_task_id,
            nesting_depth=task.nesting_depth,
            status=TaskStatus.ACTIVE,
            checkpoint_ref=task.checkpoint_ref,
            fencing_token=new_fencing_token,
            ceremony_trace=task.ceremony_trace,
            metadata=task.metadata,
        )
        self._tasks[task_id] = updated
        self._commit_event("MDG_TASK_RESUMED", asdict(updated))
        return updated

    def qualify_task(self, task_id: str) -> TaskNode:
        task = self._tasks[task_id]
        updated = TaskNode(
            task_id=task.task_id,
            root_mission_id=task.root_mission_id,
            parent_task_id=task.parent_task_id,
            nesting_depth=task.nesting_depth,
            status=TaskStatus.TERMINAL_SUCCESS,
            checkpoint_ref=task.checkpoint_ref,
            fencing_token=task.fencing_token,
            ceremony_trace=task.ceremony_trace,
            metadata=task.metadata,
        )
        self._tasks[task_id] = updated
        self._commit_event("MDG_TASK_QUALIFIED", asdict(updated))
        return updated

    def retire_task(
        self,
        task_id: str,
        terminal_status: TaskStatus = TaskStatus.TERMINAL_FAILURE,
    ) -> TaskNode:
        task = self._tasks[task_id]
        updated = TaskNode(
            task_id=task.task_id,
            root_mission_id=task.root_mission_id,
            parent_task_id=task.parent_task_id,
            nesting_depth=task.nesting_depth,
            status=terminal_status,
            checkpoint_ref=task.checkpoint_ref,
            fencing_token=task.fencing_token,
            ceremony_trace=task.ceremony_trace,
            metadata=task.metadata,
        )
        self._tasks[task_id] = updated
        self._commit_event("MDG_TASK_RETIRED", asdict(updated))
        return updated

    def get_lineage(self, task_id: str) -> list[str]:
        """Compute root-to-leaf path of task IDs."""
        path = [task_id]
        curr = self._tasks.get(task_id)
        while curr and curr.parent_task_id:
            path.append(curr.parent_task_id)
            curr = self._tasks.get(curr.parent_task_id)
        return list(reversed(path))

    def to_ledger_events(self) -> list[dict[str, Any]]:
        """Serialize graph state into ledger event records."""
        events = []
        for task in self._tasks.values():
            events.append({
                "kind": "MDG_TASK_RECORD",
                "payload": asdict(task),
            })
        for blocker in self._blockers.values():
            events.append({
                "kind": "MDG_BLOCKER_RECORD",
                "payload": asdict(blocker),
            })
        for edge in self._edges:
            events.append({
                "kind": "MDG_EDGE_RECORD",
                "payload": asdict(edge),
            })
        return events

    @classmethod
    def from_ledger_events(cls, events: list[dict[str, Any]]) -> MissionDependencyGraph:
        """Deterministic reconstruction from ledger event dictionaries."""
        graph = cls()
        for ev in events:
            kind = ev.get("kind")
            payload = ev.get("payload", {})
            if kind in {
                "MDG_TASK_SPAWNED",
                "MDG_TASK_SUSPENDED",
                "MDG_TASK_RESUMED",
                "MDG_TASK_QUALIFIED",
                "MDG_TASK_RETIRED",
                "MDG_TASK_CIRCUIT_BREAKER",
                "MDG_TASK_RECORD",
            }:
                graph._tasks[payload["task_id"]] = TaskNode(
                    task_id=payload["task_id"],
                    root_mission_id=payload["root_mission_id"],
                    parent_task_id=payload.get("parent_task_id"),
                    nesting_depth=payload["nesting_depth"],
                    status=TaskStatus(payload["status"]),
                    checkpoint_ref=payload.get("checkpoint_ref"),
                    fencing_token=payload.get("fencing_token", 0),
                    ceremony_trace=CeremonyTrace(payload.get("ceremony_trace", "TRACE_B")),
                    metadata=payload.get("metadata", {}),
                )
            elif kind in {
                "MDG_BLOCKER_REGISTERED",
                "MDG_BLOCKER_EXTINGUISHED",
                "MDG_BLOCKER_RECORD",
            }:
                graph._blockers[payload["blocker_id"]] = BlockerNode(
                    blocker_id=payload["blocker_id"],
                    finding_class=FindingClass(payload["finding_class"]),
                    signature=payload["signature"],
                    status=BlockerStatus(payload["status"]),
                    created_at_utc=payload["created_at_utc"],
                )
            elif kind in {"MDG_EDGE_COMMITTED", "MDG_EDGE_RECORD"}:
                graph._edges.append(
                    DependencyEdge(
                        edge_type=EdgeType(payload["edge_type"]),
                        source_id=payload["source_id"],
                        target_id=payload["target_id"],
                        created_at_utc=payload["created_at_utc"],
                    )
                )
        return graph

    @classmethod
    def from_ledger(cls, ledger: Any) -> MissionDependencyGraph:
        """Deterministic reconstruction of graph state directly from an append-only PAEOS Ledger."""
        graph = cls(ledger=ledger)
        head = ledger.head()
        if head is None:
            return graph
        rows = ledger.read(1, head.seq + 1)
        events = [{"kind": r.event.kind, "payload": dict(r.event.payload)} for r in rows]
        rebuilt = cls.from_ledger_events(events)
        rebuilt.attach_ledger(ledger)
        return rebuilt
