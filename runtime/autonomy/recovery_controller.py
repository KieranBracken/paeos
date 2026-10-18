"""Autonomous recovery from child failure and recursion depth/churn circuit breaker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.autonomy.authority import (
    AuthorityTier,
    FounderDecisionPacket,
    FounderStopPredicate,
    FounderStopRequiredError,
)
from runtime.autonomy.mdg import (
    CeremonyTrace,
    EdgeType,
    MissionDependencyGraph,
    TaskNode,
    TaskStatus,
)


class CircuitBreakerTrippedError(RuntimeError):
    """Recursion depth or churn exceeded operational limits."""

    def __init__(self, message: str, diagnostic: CircuitBreakerDiagnostic | None = None) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


@dataclass(frozen=True, slots=True)
class CircuitBreakerPolicy:
    max_nesting_depth: int = 5
    max_churn_retries: int = 3


@dataclass(frozen=True, slots=True)
class CircuitBreakerDiagnostic:
    """Root Cause Analysis (RCA) and replanning diagnostic produced when a circuit breaker trips."""
    tripped_task_id: str
    blocker_signature: str
    nesting_depth: int
    churn_count: int
    root_cause_summary: str
    recommended_action: str
    requires_founder: bool
    founder_packet: FounderDecisionPacket | None = None


class RecoveryController:
    """Governs autonomous recovery from child remediation failures and prevents runaway recursion.

    Per doctrine, exceeding depth or churn pauses the branch for RCA and consolidation under
    existing delegated authority (A1-A3). Founder escalation occurs ONLY IF the required remediation
    action actually crosses a Founder-reserved authority boundary (A4 Constitutional or A5 Sovereign).
    """

    def __init__(
        self,
        graph: MissionDependencyGraph,
        policy: CircuitBreakerPolicy | None = None,
    ) -> None:
        self.graph = graph
        self.policy = policy or CircuitBreakerPolicy()
        self._churn_counts: dict[str, int] = {}  # signature -> retry count

    def check_circuit_breaker(
        self,
        task_id: str,
        nesting_depth: int,
        blocker_signature: str,
    ) -> tuple[bool, str]:
        """Check if nesting depth or churn threshold is breached."""
        if nesting_depth > self.policy.max_nesting_depth:
            return (
                True,
                f"Nesting depth {nesting_depth} exceeds maximum limit {self.policy.max_nesting_depth}",
            )
        retries = self._churn_counts.get(blocker_signature, 0)
        if retries >= self.policy.max_churn_retries:
            return (
                True,
                f"Churn retries {retries} for signature {blocker_signature} exceeds maximum limit {self.policy.max_churn_retries}",
            )
        return False, "OK"

    def perform_rca_and_replanning(
        self,
        task_id: str,
        nesting_depth: int,
        blocker_signature: str,
        reason: str,
        checkpoint_ref: str = "",
    ) -> CircuitBreakerDiagnostic:
        """Perform Root Cause Analysis (RCA) and determine appropriate delegation level.

        Depth or churn alone is NEVER treated as A4 Constitutional. It pauses the branch,
        analyzes common-cause factors, and attempts consolidation under delegated authority.
        """
        # Common-cause analysis
        is_sentium_or_sovereign = "sentium" in blocker_signature.lower() or "trading" in blocker_signature.lower()
        is_constitutional = "constitution" in blocker_signature.lower() or "lifecycle" in blocker_signature.lower()

        if is_sentium_or_sovereign or is_constitutional:
            tier = AuthorityTier.A5_SOVEREIGN if is_sentium_or_sovereign else AuthorityTier.A4_CONSTITUTIONAL
            is_stop, packet = FounderStopPredicate.evaluate(
                tier=tier,
                description=f"Circuit breaker tripped on reserved boundary: {blocker_signature}",
                checkpoint_ref=checkpoint_ref,
            )
            return CircuitBreakerDiagnostic(
                tripped_task_id=task_id,
                blocker_signature=blocker_signature,
                nesting_depth=nesting_depth,
                churn_count=self._churn_counts.get(blocker_signature, 0),
                root_cause_summary=f"Reserved boundary encountered during recursive remediation: {reason}",
                recommended_action="Founder escalation required due to reserved authority tier",
                requires_founder=True,
                founder_packet=packet,
            )

        # Non-reserved boundary: consolidate under existing delegated authority (A1-A3)
        return CircuitBreakerDiagnostic(
            tripped_task_id=task_id,
            blocker_signature=blocker_signature,
            nesting_depth=nesting_depth,
            churn_count=self._churn_counts.get(blocker_signature, 0),
            root_cause_summary=f"Operational recursion threshold reached: {reason}",
            recommended_action="Consolidate nested remediation; re-plan under Council/Architect authority",
            requires_founder=False,
            founder_packet=None,
        )

    def derive_alternative_remediation(
        self,
        failed_child_task_id: str,
        blocker_id: str,
        alternative_strategy: str,
        ceremony_trace: CeremonyTrace = CeremonyTrace.TRACE_B,
    ) -> tuple[TaskNode, str]:
        """Autonomously recover from failed child by compiling an alternative remediation child with SUPERSEDES edge."""
        failed_task = self.graph.tasks[failed_child_task_id]
        blocker = self.graph.blockers[blocker_id]

        # Update churn count
        current_churn = self._churn_counts.get(blocker.signature, 0) + 1
        self._churn_counts[blocker.signature] = current_churn

        # Check circuit breaker
        tripped, reason = self.check_circuit_breaker(
            failed_task.task_id, failed_task.nesting_depth, blocker.signature
        )
        if tripped:
            # Pause branch via SUSPENDED_CIRCUIT_BREAKER
            self.graph.suspend_circuit_breaker(failed_task.task_id, reason=reason)
            diagnostic = self.perform_rca_and_replanning(
                task_id=failed_task.task_id,
                nesting_depth=failed_task.nesting_depth,
                blocker_signature=blocker.signature,
                reason=reason,
                checkpoint_ref=failed_task.checkpoint_ref or "",
            )
            if diagnostic.requires_founder and diagnostic.founder_packet is not None:
                raise FounderStopRequiredError(
                    f"Circuit breaker escalated to Founder: {diagnostic.root_cause_summary}"
                )
            raise CircuitBreakerTrippedError(
                f"Circuit breaker tripped (branch paused for RCA/replanning): {reason}",
                diagnostic=diagnostic,
            )

        # Mark failed task as TERMINAL_FAILURE
        self.graph.retire_task(failed_child_task_id, TaskStatus.TERMINAL_FAILURE)

        # Spawn replacement child
        new_task_id = f"{failed_task.task_id}-remedy-{current_churn}"
        new_child = self.graph.spawn_task(
            task_id=new_task_id,
            root_mission_id=failed_task.root_mission_id,
            parent_task_id=failed_task.parent_task_id,
            nesting_depth=failed_task.nesting_depth,
            ceremony_trace=ceremony_trace,
            metadata={
                "alternative_strategy": alternative_strategy,
                "supersedes_task_id": failed_child_task_id,
                "churn_iteration": current_churn,
            },
        )

        # Add SUPERSEDES edge from replacement child to failed child
        self.graph.add_edge(EdgeType.SUPERSEDES, new_task_id, failed_child_task_id)

        # Bind replacement child to the unresolved blocker
        self.graph.add_edge(EdgeType.REMEDIATES, new_task_id, blocker_id)

        return new_child, f"Derived alternative remediation {new_task_id} under SUPERSEDES"
