"""Investigation Loop - Minimum capability proof for multi-branch reasoning.

This module implements a purpose-built orchestrator that dispatches a native, multi-branch
reasoning mission. It runs Branch A and Branch B independently, critiques them, and synthesizes
them into a final verdict.
"""

from __future__ import annotations

import uuid

from kernel.capability import CapabilityBroker
from kernel.cas import CAS
from kernel.ledger import Event, Ledger
from kernel.types import ArtifactRef, StageId
from nacl.signing import SigningKey
from runtime.agents import StagePlaybook
from runtime.claude_code import AgentDispatcher, AgentRuntime
from runtime.task_package import Cost
from runtime.triage import GoalBudget

GOAL_CREATED = "goal_created"


class InvestigationLoop:
    """Orchestrates a multi-branch reasoning investigation."""

    def __init__(
        self,
        *,
        ledger: Ledger,
        signing_key: SigningKey,
        cas: CAS,
        agent_runtime: AgentRuntime,
    ) -> None:
        self._ledger = ledger
        self._cas = cas
        self._broker = CapabilityBroker(signing_key)
        self._dispatcher = AgentDispatcher(self._broker, cas, agent_runtime, clock=self._now)
        self._playbook = StagePlaybook(self._dispatcher)

    def _now(self) -> int:
        head = self._ledger.head()
        return head.seq if head is not None else 0

    def run_investigation(
        self,
        *,
        mission: str,
        budget_tokens: int = 2_000_000,
    ) -> dict[str, str | int]:
        """Run the proof-of-capability DAG."""
        goal_id = "g-" + uuid.uuid4().hex[:12]
        run_id = "r-" + uuid.uuid4().hex[:12]

        self._ledger.append(
            Event(
                1,
                GOAL_CREATED,
                {"goal_id": goal_id, "weight_class": "SUBSTANTIAL"},
            )
        )

        from runtime.task_package import Budget

        base_budget = Budget(tokens=budget_tokens, wallclock_s=7200, retries=5)
        goal_budget = GoalBudget(base_budget)
        total_cost = Cost(0, 0.0, "unknown")

        def _run_stage(
            stage: StageId,
            session: str,
            detail: str,
            context: tuple[ArtifactRef, ...] = (),
            scope: str = "",
        ) -> list[ArtifactRef]:
            nonlocal total_cost
            result = self._playbook.run_stage(
                goal_id=goal_id,
                run_id=run_id,
                stage=stage,
                session=session,
                budget=base_budget,
                detail=detail,
                context_refs=context,
                write_scopes=(scope,) if scope else (),
            )
            goal_budget.charge(result.cost)
            return list(result.artifacts)

        # 1. Branch A
        branch_a_artifacts = _run_stage(
            StageId.RESEARCH,
            "branch_a",
            f"MISSION: {mission}\nApproach: Optimize for determinism and strict isolation. Propose a solution.",
            scope="research/branch_a/",
        )

        # 2. Branch B
        branch_b_artifacts = _run_stage(
            StageId.RESEARCH,
            "branch_b",
            f"MISSION: {mission}\nApproach: Optimize for flexibility and speed. Propose a solution.",
            scope="research/branch_b/",
        )

        # 3. Critique
        critic_context = tuple(branch_a_artifacts + branch_b_artifacts)
        critique_artifacts = _run_stage(
            StageId.CRITIQUE,
            "critic",
            "Review the independent proposals (Branch A and Branch B). Identify flaws, verify consistency, and attempt to falsify their claims.",
            context=critic_context,
            scope="research/critique/",
        )

        # 4. Synthesis
        synthesis_context = tuple(branch_a_artifacts + branch_b_artifacts + critique_artifacts)
        synthesis_artifacts = _run_stage(
            StageId.TRADEOFF,
            "synthesizer",
            "Read the original proposals and the adversarial critique. Produce a final synthesis and verdict selecting the best path.",
            context=synthesis_context,
            scope="research/synthesis/",
        )

        return {
            "goal_id": goal_id,
            "run_id": run_id,
            "status": "COMPLETED",
            "artifacts_a": len(branch_a_artifacts),
            "artifacts_b": len(branch_b_artifacts),
            "critiques": len(critique_artifacts),
            "synthesis": len(synthesis_artifacts),
            "spent_tokens": goal_budget.spent_tokens,
        }
