"""PAEOS Model Router — Intelligence Tier Policy & Dynamic Allocation.

Implements the dynamic intelligence tier allocation governing Codex, PAEOS,
and worker pool dispatch across the Sentium Ecosystem Migration.

Controlling Principle:
PAEOS Policy Router dynamically selects intelligence according to task consequence,
complexity, uncertainty, role, available quota, and required independence.

Policy Tiers:
1. ROUTINE / MECHANICAL:
   tests, fixtures, adapters, simple implementation, deterministic remediation
   -> Luna xhigh / admitted free worker pool
2. SUBSTANTIVE ENGINEERING:
   non-trivial implementation, difficult debugging, integration reasoning
   -> Luna xhigh or Sol High according to router evaluation
3. ARCHITECTURAL / HIGH-CONSEQUENCE:
   system design, cross-system boundary decisions, difficult remands, capability loss, migration decisions
   -> prefer GPT-5.6 Sol High
4. CRITICAL / IRREVERSIBLE / AMBIGUOUS:
   authority cutovers, major architectural conflicts, W9 cutover reasoning, Founder adjudication
   -> permit GPT-5.6 Sol XHigh at bounded high-value reasoning checkpoints;
      NEVER use Sol XHigh as a blanket default for entire waves.

Operational Invariants:
- Codex execution-overseer prefers GPT-5.6 Sol High for actual supervisory LLM decisions.
- Heartbeat/watchdog status cycles MUST remain deterministic non-LLM no-ops (0 token consumption).
- A-08 Heterogeneous Decorrelation: Builder using OpenAI (GPT family) forces Auditor to be heterogeneous (non-OpenAI, e.g. Gemini, GLM, DeepSeek, Llama).
- Preserves all admitted free/low-cost providers in the execution mesh.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from paeos.model_router.types import CostTier, ModelCatalogEntry, ModelFamily, TaskClass


class IntelligenceTier(StrEnum):
    ROUTINE_MECHANICAL = "ROUTINE_MECHANICAL"
    SUBSTANTIVE_ENGINEERING = "SUBSTANTIVE_ENGINEERING"
    ARCHITECTURAL_HIGH_CONSEQUENCE = "ARCHITECTURAL_HIGH_CONSEQUENCE"
    CRITICAL_IRREVERSIBLE_AMBIGUOUS = "CRITICAL_IRREVERSIBLE_AMBIGUOUS"


class ReasoningEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


DETERMINISTIC_STATUS_ACTIONS: frozenset[str] = frozenset(
    {
        "heartbeat",
        "status",
        "watchdog",
        "health_check",
        "ping",
        "supervisory_cycle",
        "audit_poll",
        "liveness_probe",
    }
)

ADMITTED_FREE_WORKER_POOL: tuple[str, ...] = (
    "gemini-3.6-flash",
    "meta/llama-3.1-8b-instruct",
    "minimax/minimax-m2.5",
    "poolside/laguna-s-2.1:free",
    "z-ai/glm-5.3-flash",
    "cline-free/longcat-2.0",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "kilo-auto/free",
    "openrouter/free",
)

QUALIFIED_FREE_WORKER_POOL: tuple[str, ...] = (
    "gemini-3.6-flash",
    "meta/llama-3.1-8b-instruct",
    "minimax/minimax-m2.5",
    "poolside/laguna-s-2.1:free",
    "z-ai/glm-5.3-flash",
    "cline-free/longcat-2.0",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "kilo-auto/free",
    "openrouter/free",
)


def catalogued_free_worker_pool(entries: Iterable[ModelCatalogEntry]) -> tuple[str, ...]:
    """Return catalogued FREE ids; eligibility is still enforced by routing gates."""

    return tuple(entry.model_id for entry in entries if entry.cost_tier is CostTier.FREE)

HETEROGENEOUS_AUDITOR_FAMILIES_FOR_GPT: tuple[ModelFamily, ...] = (
    ModelFamily.GEMINI,
    ModelFamily.GLM,
    ModelFamily.DEEPSEEK,
    ModelFamily.LLAMA,
    ModelFamily.KIMI,
    ModelFamily.QWEN,
)


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    reasoning_effort: ReasoningEffort | str | None
    family: ModelFamily
    cost_tier: CostTier
    provider: str
    is_zero_token_noop: bool = False
    notes: str = ""


OVERSEER_PREFERRED_PROFILE = ModelProfile(
    model_id="gpt-5.6-sol",
    reasoning_effort=ReasoningEffort.HIGH,
    family=ModelFamily.GPT,
    cost_tier=CostTier.SUBSCRIPTION_INCLUDED,
    provider="codex",
    notes="Preferred profile for supervisory LLM decisions",
)

LUNA_ROUTINE_PROFILE = ModelProfile(
    model_id="gpt-5.6-luna",
    reasoning_effort=ReasoningEffort.XHIGH,
    family=ModelFamily.GPT,
    cost_tier=CostTier.SUBSCRIPTION_INCLUDED,
    provider="codex",
    notes="Cost-efficient routine/mechanical worker",
)

SOL_HIGH_PROFILE = ModelProfile(
    model_id="gpt-5.6-sol",
    reasoning_effort=ReasoningEffort.HIGH,
    family=ModelFamily.GPT,
    cost_tier=CostTier.SUBSCRIPTION_INCLUDED,
    provider="codex",
    notes="Substantive/architectural engineering profile",
)

SOL_XHIGH_BOUNDED_PROFILE = ModelProfile(
    model_id="gpt-5.6-sol",
    reasoning_effort=ReasoningEffort.XHIGH,
    family=ModelFamily.GPT,
    cost_tier=CostTier.SUBSCRIPTION_INCLUDED,
    provider="codex",
    notes="Permitted bounded critical checkpoint profile",
)


@dataclass
class TaskContext:
    task_name: str = ""
    description: str = ""
    tier: IntelligenceTier | None = None
    task_class: TaskClass = TaskClass.ROUTINE
    consequence_level: float = 0.0  # 0.0 (trivial) to 1.0 (fatal / irreversible)
    complexity_score: float = 0.0   # 0.0 (simple) to 1.0 (extreme reasoning depth)
    uncertainty_score: float = 0.0  # 0.0 (deterministic) to 1.0 (highly ambiguous)
    is_cross_system_boundary: bool = False
    is_difficult_remand: bool = False
    is_authority_cutover: bool = False
    is_architectural_conflict: bool = False
    is_founder_adjudication: bool = False
    is_deterministic_status_op: bool = False
    is_blanket_wave: bool = False
    bounded_checkpoint: bool = False
    checkpoint_id: str | None = None
    role: str = "builder"  # "builder", "overseer", "auditor"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelAssignment:
    model_id: str
    reasoning_effort: ReasoningEffort | str | None
    tier: IntelligenceTier
    role: str
    family: ModelFamily
    is_zero_token_noop: bool
    fallback_models: list[str]
    rationale: str
    a08_heterogeneous_required: bool = True


def is_deterministic_status_operation(action: str) -> bool:
    """Check if an action is a zero-LLM-token deterministic status/watchdog check."""
    return action.strip().lower() in DETERMINISTIC_STATUS_ACTIONS


class IntelligencePolicyRouter:
    """Dynamic Intelligence Router implementing the 4-tier migration intelligence policy."""

    def evaluate_tier(self, ctx: TaskContext) -> IntelligenceTier:
        """Determine intelligence tier according to consequence, complexity, and consequence."""
        if ctx.tier is not None:
            return ctx.tier

        # Tier 4: CRITICAL / IRREVERSIBLE / AMBIGUOUS
        if (
            ctx.is_authority_cutover
            or ctx.is_architectural_conflict
            or ctx.is_founder_adjudication
            or ctx.consequence_level >= 0.90
        ):
            return IntelligenceTier.CRITICAL_IRREVERSIBLE_AMBIGUOUS

        # Tier 3: ARCHITECTURAL / HIGH-CONSEQUENCE
        if (
            ctx.is_cross_system_boundary
            or ctx.is_difficult_remand
            or ctx.consequence_level >= 0.70
            or ctx.task_class == TaskClass.ARCHITECTURE
        ):
            return IntelligenceTier.ARCHITECTURAL_HIGH_CONSEQUENCE

        # Tier 2: SUBSTANTIVE ENGINEERING
        if (
            ctx.complexity_score >= 0.50
            or ctx.uncertainty_score >= 0.50
            or ctx.task_class in {TaskClass.IMPLEMENTATION, TaskClass.CODE_REVIEW}
        ):
            return IntelligenceTier.SUBSTANTIVE_ENGINEERING

        # Tier 1: ROUTINE / MECHANICAL
        return IntelligenceTier.ROUTINE_MECHANICAL

    def assign_model(self, ctx: TaskContext) -> ModelAssignment:
        """Assign model, reasoning effort, and fallbacks based on policy evaluation."""
        # Check 1: Deterministic non-LLM no-op check
        if ctx.is_deterministic_status_op or is_deterministic_status_operation(ctx.task_name):
            return ModelAssignment(
                model_id="none",
                reasoning_effort=None,
                tier=IntelligenceTier.ROUTINE_MECHANICAL,
                role=ctx.role,
                family=ModelFamily.UNKNOWN,
                is_zero_token_noop=True,
                fallback_models=[],
                rationale="Deterministic non-LLM status/watchdog cycle: zero LLM tokens consumed.",
                a08_heterogeneous_required=False,
            )

        tier = self.evaluate_tier(ctx)

        # Overseer Role (Codex Execution Overseer)
        if ctx.role.lower() in {"overseer", "execution_overseer"}:
            if tier == IntelligenceTier.CRITICAL_IRREVERSIBLE_AMBIGUOUS:
                self._validate_sol_xhigh_eligibility(ctx)
                return ModelAssignment(
                    model_id="gpt-5.6-sol",
                    reasoning_effort=ReasoningEffort.XHIGH,
                    tier=tier,
                    role=ctx.role,
                    family=ModelFamily.GPT,
                    is_zero_token_noop=False,
                    fallback_models=["gpt-5.6-sol", "gpt-5.6-luna"],
                    rationale="Permitted GPT-5.6 Sol XHigh for overseer at bounded high-value reasoning checkpoint.",
                )
            # Default supervisory profile: GPT-5.6 Sol High
            return ModelAssignment(
                model_id="gpt-5.6-sol",
                reasoning_effort=ReasoningEffort.HIGH,
                tier=tier,
                role=ctx.role,
                family=ModelFamily.GPT,
                is_zero_token_noop=False,
                fallback_models=["gpt-5.6-luna"],
                rationale="Codex execution-overseer prefers GPT-5.6 Sol High for actual supervisory LLM decisions.",
            )

        # Auditor Role: Enforce heterogeneous family separation
        if ctx.role.lower() in {"auditor", "critic", "verifier"}:
            return self._assign_heterogeneous_auditor(tier, ctx)

        # Builder Role
        if tier == IntelligenceTier.CRITICAL_IRREVERSIBLE_AMBIGUOUS:
            self._validate_sol_xhigh_eligibility(ctx)
            return ModelAssignment(
                model_id="gpt-5.6-sol",
                reasoning_effort=ReasoningEffort.XHIGH,
                tier=tier,
                role="builder",
                family=ModelFamily.GPT,
                is_zero_token_noop=False,
                fallback_models=["gpt-5.6-sol", "gpt-5.6-luna"],
                rationale="Permitted GPT-5.6 Sol XHigh at bounded high-value reasoning checkpoint.",
            )

        if tier == IntelligenceTier.ARCHITECTURAL_HIGH_CONSEQUENCE:
            return ModelAssignment(
                model_id="gpt-5.6-sol",
                reasoning_effort=ReasoningEffort.HIGH,
                tier=tier,
                role="builder",
                family=ModelFamily.GPT,
                is_zero_token_noop=False,
                fallback_models=["gpt-5.6-luna", "gemini-3.6-flash"],
                rationale="Architectural / High-Consequence: prefer GPT-5.6 Sol High.",
            )

        if tier == IntelligenceTier.SUBSTANTIVE_ENGINEERING:
            # Dynamic evaluation between Luna xhigh and Sol High
            # Escalate to Sol High if complexity or uncertainty is high, or cross-system boundary involved
            if (
                ctx.complexity_score >= 0.70
                or ctx.uncertainty_score >= 0.70
                or ctx.is_cross_system_boundary
            ):
                return ModelAssignment(
                    model_id="gpt-5.6-sol",
                    reasoning_effort=ReasoningEffort.HIGH,
                    tier=tier,
                    role="builder",
                    family=ModelFamily.GPT,
                    is_zero_token_noop=False,
                    fallback_models=["gpt-5.6-luna", "minimax/minimax-m2.5"],
                    rationale="Substantive engineering (high complexity/uncertainty): routed to GPT-5.6 Sol High.",
                )
            return ModelAssignment(
                model_id="gpt-5.6-luna",
                reasoning_effort=ReasoningEffort.XHIGH,
                tier=tier,
                role="builder",
                family=ModelFamily.GPT,
                is_zero_token_noop=False,
                fallback_models=["gpt-5.6-sol", "minimax/minimax-m2.5"],
                rationale="Substantive engineering (standard): routed to cost-efficient Luna xhigh.",
            )

        # ROUTINE_MECHANICAL
        return ModelAssignment(
            model_id="gpt-5.6-luna",
            reasoning_effort=ReasoningEffort.XHIGH,
            tier=tier,
            role="builder",
            family=ModelFamily.GPT,
            is_zero_token_noop=False,
            fallback_models=list(ADMITTED_FREE_WORKER_POOL),
            rationale="Routine / Mechanical: routed to Luna xhigh with admitted free worker pool fallback.",
        )

    def _validate_sol_xhigh_eligibility(self, ctx: TaskContext) -> None:
        """Enforces that Sol XHigh is never used as a blanket default for entire waves."""
        if ctx.is_blanket_wave:
            raise ValueError(
                "Sol XHigh Policy Violation: Sol XHigh is prohibited as a blanket default for "
                "entire migration waves. It is permitted only at bounded high-value reasoning checkpoints."
            )
        if not ctx.bounded_checkpoint:
            raise ValueError(
                "Sol XHigh Escalation Violation: Escalation to Sol XHigh requires explicit "
                "bounded checkpoint demarcation (e.g. W9 cutover disposition, authority conflict resolution)."
            )

    def _assign_heterogeneous_auditor(self, tier: IntelligenceTier, ctx: TaskContext) -> ModelAssignment:
        """Assigns an auditor strictly satisfying A-08 heterogeneous independence."""
        # Builder is OpenAI/GPT, so Auditor MUST NOT be OpenAI/GPT
        if tier in {
            IntelligenceTier.ARCHITECTURAL_HIGH_CONSEQUENCE,
            IntelligenceTier.CRITICAL_IRREVERSIBLE_AMBIGUOUS,
        }:
            model_id = "gemini-3.7-flash"
            family = ModelFamily.GEMINI
            fallbacks = ["gemini-3.6-flash", "cline-pass/glm-5.3", "meta/llama-3.1-8b-instruct", "cline-pass/kimi-k3"]
        else:
            model_id = "gemini-3.6-flash"
            family = ModelFamily.GEMINI
            fallbacks = ["z-ai/glm-5.3-flash", "meta/llama-3.1-8b-instruct", "minimax/minimax-m2.5"]

        return ModelAssignment(
            model_id=model_id,
            reasoning_effort=ReasoningEffort.HIGH if tier != IntelligenceTier.ROUTINE_MECHANICAL else None,
            tier=tier,
            role="auditor",
            family=family,
            is_zero_token_noop=False,
            fallback_models=fallbacks,
            rationale=f"A-08 Heterogeneous Auditor: Non-OpenAI ({family.value}) assigned to audit GPT builder.",
        )

    def validate_a08_independence(
        self,
        builder_assignment: ModelAssignment,
        auditor_assignment: ModelAssignment,
    ) -> bool:
        """Validates that Builder and Auditor maintain heterogeneous independence."""
        if builder_assignment.family == ModelFamily.UNKNOWN:
            return False
        if auditor_assignment.family == ModelFamily.UNKNOWN:
            return False
        return builder_assignment.family != auditor_assignment.family
