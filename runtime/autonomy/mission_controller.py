"""Persistent Mission Controller — native PAEOS mission autonomy and crash recovery."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from kernel.cas import CAS
from kernel.ledger import Event, Ledger
from runtime.autonomy.authority import (
    AuthorityEnvelope,
    AuthorityTier,
    FindingClass,
    RootEnvelopeAuthorityResolver,
)
from runtime.autonomy.weakness_finder import ContinuousWeaknessFinder
from runtime.autonomy.weakness_finder.types import SensorFinding
from runtime.autonomy.mdg import (
    BlockerNode,
    CeremonyTrace,
    EdgeType,
    MissionDependencyGraph,
    TaskNode,
    TaskStatus,
)
from runtime.autonomy.recovery_controller import (
    CircuitBreakerPolicy,
    RecoveryController,
)
from runtime.autonomy.cycle_detector import CycleDetector
from runtime.autonomy.resume_engine import ResumeEngine, TaskCheckpoint


class PersistentMissionController:
    """Native PAEOS mission controller orchestrating durable MDG adaptation and restart recovery."""

    def __init__(
        self,
        ledger: Ledger,
        cas: CAS,
        root_envelope: AuthorityEnvelope,
        circuit_policy: CircuitBreakerPolicy | None = None,
    ) -> None:
        self.ledger = ledger
        self.cas = cas
        self.root_envelope = root_envelope
        # Reconstruct or attach graph from ledger
        self.graph = MissionDependencyGraph.from_ledger(ledger)
        self.resume_engine = ResumeEngine(self.graph, cas=cas, ledger=ledger)
        self.recovery = RecoveryController(self.graph, policy=circuit_policy)
        self.weakness_finder = ContinuousWeaknessFinder()
        self.cycle_detector = CycleDetector(max_iterations=50)
        self.last_blocker_findings: list[SensorFinding] = []

    def run_weakness_audit(self) -> list[SensorFinding]:
        """Advisorily audit MDG, semantic lineage, and drift health across active mission state."""
        return self.weakness_finder.scan_all(self.graph)

    @classmethod
    def recover_from_durable_state(
        cls,
        ledger: Ledger,
        cas: CAS,
        root_envelope: AuthorityEnvelope,
        circuit_policy: CircuitBreakerPolicy | None = None,
    ) -> PersistentMissionController:
        """Crash recovery factory: reconstructs complete controller state from durable storage."""
        # Enforce cryptographic chain integrity before reconstructing autonomy graph
        ledger.verify_chain()
        return cls(
            ledger=ledger,
            cas=cas,
            root_envelope=root_envelope,
            circuit_policy=circuit_policy,
        )

    def start_root_task(
        self,
        task_id: str,
        ceremony_trace: CeremonyTrace = CeremonyTrace.TRACE_B,
        metadata: dict[str, Any] | None = None,
    ) -> TaskNode:
        return self.graph.spawn_task(
            task_id=task_id,
            root_mission_id=self.root_envelope.root_mission_id,
            parent_task_id=None,
            nesting_depth=0,
            ceremony_trace=ceremony_trace,
            metadata=metadata or {},
        )

    def handle_blocker_and_spawn_remediation(
        self,
        parent_task_id: str,
        blocker_id: str,
        signature: str,
        finding_class: FindingClass,
        checkpoint_payload: dict[str, Any],
        child_task_id: str,
        requested_paths: tuple[str, ...],
        requested_tier: AuthorityTier,
        ceremony_trace: CeremonyTrace = CeremonyTrace.TRACE_B,
    ) -> tuple[TaskNode, str]:
        """Classify gap, suspend parent at CAS checkpoint, and spawn confined remediation child."""
        parent_task = self.graph.tasks[parent_task_id]

        if finding_class is not FindingClass.CURRENT_BLOCKER:
            self.graph.register_blocker(blocker_id, finding_class, signature)
            return parent_task, "NONBLOCKING_JOURNALED"

        # 1. Suspend parent task at durable CAS checkpoint
        cp_ref = self.resume_engine.suspend_parent_task(
            task_id=parent_task_id,
            stage_id="L12_BLOCKED",
            state_payload=checkpoint_payload,
        )
        self.graph.suspend_task(parent_task_id, cp_ref)

        # Continuous advisory weakness scan on blocker encounter
        audit_findings = self.run_weakness_audit()
        if audit_findings:
            self.ledger.append(
                Event(
                    1,
                    "MISSION_WEAKNESS_FINDINGS_JOURNALED",
                    {
                        "parent_task_id": parent_task_id,
                        "findings_count": len(audit_findings),
                        "findings": [
                            {"id": f.finding_id, "title": f.title, "severity": f.severity.value}
                            for f in audit_findings
                        ],
                    },
                )
            )

        # 2. Register blocker on parent
        self.graph.register_blocker(
            blocker_id=blocker_id,
            finding_class=finding_class,
            signature=signature,
            blocked_task_id=parent_task_id,
        )

        # 2b. Check cycle detection / hard execution bound (ELH-11)
        self.cycle_detector.record_state(f"blocker:{signature}:{parent_task_id}")
        if self.cycle_detector.is_cycling():
            raise RuntimeError(
                f"EXECUTION_CYCLE_EXCEEDED: Remediation loop cycle or bound exceeded at task {parent_task_id}"
            )

        # 3. Resolve child authority envelope (fails closed if outside root envelope)
        child_env = RootEnvelopeAuthorityResolver.resolve_child_envelope(
            root_envelope=self.root_envelope,
            parent_envelope=self.root_envelope,
            requested_paths=requested_paths,
            requested_tier=requested_tier,
        )

        # 4. Spawn child remediation task
        child_task = self.graph.spawn_task(
            task_id=child_task_id,
            root_mission_id=self.root_envelope.root_mission_id,
            parent_task_id=parent_task_id,
            nesting_depth=parent_task.nesting_depth + 1,
            ceremony_trace=ceremony_trace,
            metadata={"envelope": asdict(child_env)},
        )

        # 5. Commit REMEDIATES edge
        self.graph.add_edge(EdgeType.REMEDIATES, child_task_id, blocker_id)

        # 6. Automatic advisory weakness scan on blocker handling
        self.last_blocker_findings = self.run_weakness_audit()

        return child_task, cp_ref

    def qualify_child_and_unwind(
        self,
        child_task_id: str,
        blocker_id: str,
    ) -> tuple[bool, str, TaskNode | None]:
        """Qualify remediation child, extinguish blocker, and auto-resume parent if preconditions satisfied."""
        self.graph.qualify_task(child_task_id)
        self.graph.extinguish_blocker(blocker_id)

        child = self.graph.tasks[child_task_id]
        parent_id = child.parent_task_id
        if not parent_id:
            return True, f"Root task {child_task_id} qualified", child

        self.graph.add_edge(EdgeType.RESUMES, child_task_id, parent_id)

        if self.graph.can_resume_task(parent_id):
            success, msg, resumed_parent = self.resume_engine.attempt_resume(parent_id)
            return success, msg, resumed_parent

        return False, f"Parent {parent_id} remains suspended; sibling blockers active", None

    def execute_autonomous_unwind_to_root(
        self,
        leaf_task_id: str,
        leaf_blocker_id: str,
    ) -> list[str]:
        """Autonomously unwind complete nested blocker hierarchy back to root mission without human intervention."""
        unwound_sequence: list[str] = []

        curr_task_id = leaf_task_id
        curr_blocker_id = leaf_blocker_id

        while True:
            self.cycle_detector.record_state(f"unwind:{curr_task_id}:{curr_blocker_id}")
            if self.cycle_detector.is_cycling():
                raise RuntimeError(
                    f"EXECUTION_CYCLE_EXCEEDED: Unwind cycle limit reached at task {curr_task_id}"
                )
            success, msg, resumed_parent = self.qualify_child_and_unwind(curr_task_id, curr_blocker_id)
            unwound_sequence.append(curr_task_id)

            if not success or resumed_parent is None:
                break

            parent_id = resumed_parent.task_id
            # If resumed parent is root (no parent_task_id), qualify root and finish
            if resumed_parent.parent_task_id is None:
                self.graph.qualify_task(parent_id)
                unwound_sequence.append(parent_id)
                break

            # Resumed parent has its own blocker to extinguish on its parent
            # Find the blocker that parent_id was remediating
            parent_remediates = [
                e.target_id for e in self.graph.edges
                if e.edge_type is EdgeType.REMEDIATES and e.source_id == parent_id
            ]
            if not parent_remediates:
                # Parent has no blocker it remediates; qualify parent
                self.graph.qualify_task(parent_id)
                unwound_sequence.append(parent_id)
                break

            curr_blocker_id = parent_remediates[0]
            curr_task_id = parent_id

        return unwound_sequence

    def acquire_task_lease(self, task_id: str, lease_seconds: float = 30.0) -> tuple[int, float]:
        """Acquire monotonic fencing lease on active task (ELH-08, ELH-11)."""
        tok = self.resume_engine.fencing.next_token(task_id)
        expire_at = time.time() + lease_seconds
        self.resume_engine._task_leases[task_id] = (tok, expire_at)
        self.resume_engine._commit_event("MDG_LEASE_RECORD", {
            "task_id": task_id,
            "fencing_token": tok,
            "expire_at_unix": expire_at,
        })
        return tok, expire_at

    def renew_task_lease(self, task_id: str, fencing_token: int, lease_seconds: float = 30.0) -> bool:
        """Renew active lease if monotonic token matches."""
        curr = self.resume_engine.fencing.current_token(task_id)
        if fencing_token != curr:
            return False
        expire_at = time.time() + lease_seconds
        self.resume_engine._task_leases[task_id] = (fencing_token, expire_at)
        self.resume_engine._commit_event("MDG_LEASE_RECORD", {
            "task_id": task_id,
            "fencing_token": fencing_token,
            "expire_at_unix": expire_at,
        })
        return True

    def reclaim_expired_leases(self, now: float | None = None) -> list[str]:
        """Watchdog: detect and reclaim tasks whose lease expired, fencing out abandoned workers (ELH-11)."""
        reclaimed: list[str] = []
        current_time = now if now is not None else time.time()
        for task_id, (tok, expire_at) in list(self.resume_engine._task_leases.items()):
            if current_time >= expire_at:
                success, _msg, _node = self.resume_engine.recover_interrupted_resume(
                    task_id=task_id,
                    lease_seconds=30.0,
                )
                if success:
                    reclaimed.append(task_id)
        return reclaimed
