"""Unit tests for PAEOS Intelligence Tier Policy and Dynamic Allocation.

Tests:
1. Routine/Mechanical tier routes to Luna xhigh / admitted free worker pool.
2. Substantive Engineering tier dynamically evaluates Luna xhigh vs Sol High.
3. Architectural / High-Consequence tier prefers GPT-5.6 Sol High.
4. Critical / Irreversible / Ambiguous tier permits GPT-5.6 Sol XHigh at bounded checkpoints.
5. Blanket wave Sol XHigh usage is strictly rejected.
6. Unbounded Sol XHigh escalation is strictly rejected.
7. Codex execution-overseer prefers GPT-5.6 Sol High for supervisory decisions.
8. Status/watchdog/heartbeat cycles are verified non-LLM zero-token operations.
9. A-08 heterogeneous model decorrelation (Builder != Auditor) is strictly enforced for GPT family.
10. Preserves all admitted free/low-cost worker pool models.
"""

from __future__ import annotations

import pytest
from paeos.model_router import (
    ADMITTED_FREE_WORKER_POOL,
    HETEROGENEOUS_AUDITOR_FAMILIES_FOR_GPT,
    QUALIFIED_FREE_WORKER_POOL,
    IntelligencePolicyRouter,
    IntelligenceTier,
    ModelFamily,
    ReasoningEffort,
    TaskClass,
    TaskContext,
    is_deterministic_status_operation,
)
from paeos.model_router.a08_enforcer import AUDITOR_MAPPING, A08Enforcer, A08Verdict
from paeos.model_router.catalog import ModelCatalog


@pytest.fixture
def router() -> IntelligencePolicyRouter:
    return IntelligencePolicyRouter()


# Test 1: Routine / Mechanical Tier
def test_routine_mechanical_routes_to_luna_xhigh_or_free_pool(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="create_contract_fixtures",
        description="Create deterministic contract fixtures and adapters",
        task_class=TaskClass.ROUTINE,
        consequence_level=0.1,
        complexity_score=0.2,
    )
    assert router.evaluate_tier(ctx) == IntelligenceTier.ROUTINE_MECHANICAL
    assignment = router.assign_model(ctx)
    assert assignment.model_id == "gpt-5.6-luna"
    assert assignment.reasoning_effort == ReasoningEffort.XHIGH
    assert assignment.tier == IntelligenceTier.ROUTINE_MECHANICAL
    assert not assignment.is_zero_token_noop
    for m in ADMITTED_FREE_WORKER_POOL:
        assert m in assignment.fallback_models


# Test 2: Substantive Engineering Tier (Moderate vs High Complexity)
def test_substantive_engineering_moderate_complexity(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="implement_adapter_logic",
        description="Standard non-trivial adapter implementation",
        task_class=TaskClass.IMPLEMENTATION,
        complexity_score=0.55,
        uncertainty_score=0.4,
    )
    assert router.evaluate_tier(ctx) == IntelligenceTier.SUBSTANTIVE_ENGINEERING
    assignment = router.assign_model(ctx)
    # Moderate complexity should select cost-efficient Luna xhigh
    assert assignment.model_id == "gpt-5.6-luna"
    assert assignment.reasoning_effort == ReasoningEffort.XHIGH


def test_substantive_engineering_high_complexity_escalates_to_sol_high(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="debug_complex_integration_concurrency",
        description="Difficult integration debugging with high uncertainty",
        task_class=TaskClass.IMPLEMENTATION,
        complexity_score=0.8,
        uncertainty_score=0.75,
    )
    assert router.evaluate_tier(ctx) == IntelligenceTier.SUBSTANTIVE_ENGINEERING
    assignment = router.assign_model(ctx)
    # High complexity/uncertainty should escalate to Sol High
    assert assignment.model_id == "gpt-5.6-sol"
    assert assignment.reasoning_effort == ReasoningEffort.HIGH


def test_substantive_engineering_cross_system_boundary_escalates_to_sol_high(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="integrate_kae_evidence_bridge",
        description="Cross-system boundary integration between KAE and LOF",
        task_class=TaskClass.IMPLEMENTATION,
        is_cross_system_boundary=True,
    )
    assignment = router.assign_model(ctx)
    assert assignment.model_id == "gpt-5.6-sol"
    assert assignment.reasoning_effort == ReasoningEffort.HIGH


# Test 3: Architectural / High-Consequence Tier
def test_architectural_tier_prefers_sol_high(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="ecosystem_target_topology_design",
        description="System boundary and architecture design",
        task_class=TaskClass.ARCHITECTURE,
        consequence_level=0.75,
    )
    assert router.evaluate_tier(ctx) == IntelligenceTier.ARCHITECTURAL_HIGH_CONSEQUENCE
    assignment = router.assign_model(ctx)
    assert assignment.model_id == "gpt-5.6-sol"
    assert assignment.reasoning_effort == ReasoningEffort.HIGH
    assert assignment.tier == IntelligenceTier.ARCHITECTURAL_HIGH_CONSEQUENCE


def test_difficult_remand_routes_to_sol_high(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="remand_root_cause_resolution",
        description="Diagnose and remediate complex non-vacuity Court remand",
        is_difficult_remand=True,
    )
    assert router.evaluate_tier(ctx) == IntelligenceTier.ARCHITECTURAL_HIGH_CONSEQUENCE
    assignment = router.assign_model(ctx)
    assert assignment.model_id == "gpt-5.6-sol"
    assert assignment.reasoning_effort == ReasoningEffort.HIGH


# Test 4: Critical / Irreversible / Ambiguous Tier & Sol XHigh Bounded Checkpoints
def test_critical_tier_permits_sol_xhigh_at_bounded_checkpoint(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="w9_authority_cutover_disposition",
        description="Decide final production external database cutover",
        is_authority_cutover=True,
        bounded_checkpoint=True,
        checkpoint_id="W9_FINAL_CUTOVER_DISPOSITION",
    )
    assert router.evaluate_tier(ctx) == IntelligenceTier.CRITICAL_IRREVERSIBLE_AMBIGUOUS
    assignment = router.assign_model(ctx)
    assert assignment.model_id == "gpt-5.6-sol"
    assert assignment.reasoning_effort == ReasoningEffort.XHIGH
    assert assignment.tier == IntelligenceTier.CRITICAL_IRREVERSIBLE_AMBIGUOUS


def test_founder_adjudication_permits_sol_xhigh_at_bounded_checkpoint(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="founder_contradiction_adjudication",
        description="Resolve contradictory architectural claims for Founder review",
        is_founder_adjudication=True,
        bounded_checkpoint=True,
        checkpoint_id="FOUNDER_CONTRADICTION_GATE_01",
    )
    assert router.evaluate_tier(ctx) == IntelligenceTier.CRITICAL_IRREVERSIBLE_AMBIGUOUS
    assignment = router.assign_model(ctx)
    assert assignment.model_id == "gpt-5.6-sol"
    assert assignment.reasoning_effort == ReasoningEffort.XHIGH


# Test 5 & 6: Sol XHigh Violations (Blanket Wave and Unbounded Escalation)
def test_sol_xhigh_blanket_wave_is_rejected(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="wave_6_execution",
        description="Execute entire Wave 6 under Sol XHigh",
        is_authority_cutover=True,
        is_blanket_wave=True,
        bounded_checkpoint=True,
    )
    with pytest.raises(ValueError, match="Sol XHigh Policy Violation: Sol XHigh is prohibited as a blanket default"):
        router.assign_model(ctx)


def test_sol_xhigh_unbounded_escalation_is_rejected(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="unbounded_authority_cutover",
        description="Authority cutover without explicit checkpoint demarcation",
        is_authority_cutover=True,
        bounded_checkpoint=False,
    )
    with pytest.raises(ValueError, match="Sol XHigh Escalation Violation: Escalation to Sol XHigh requires explicit bounded checkpoint"):
        router.assign_model(ctx)


# Test 7: Codex Execution Overseer Profile
def test_codex_overseer_prefers_sol_high_for_supervisory_decisions(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="supervise_wave_intake",
        description="Supervise PAEOS autonomous lifecycle progress and diagnose stalls",
        role="overseer",
        consequence_level=0.5,
    )
    assignment = router.assign_model(ctx)
    assert assignment.role == "overseer"
    assert assignment.model_id == "gpt-5.6-sol"
    assert assignment.reasoning_effort == ReasoningEffort.HIGH
    assert not assignment.is_zero_token_noop


def test_codex_overseer_bounded_sol_xhigh_escalation(router: IntelligencePolicyRouter) -> None:
    ctx = TaskContext(
        task_name="supervise_critical_cutover",
        description="Supervise critical cutover checkpoint",
        role="overseer",
        is_authority_cutover=True,
        bounded_checkpoint=True,
        checkpoint_id="OVERSEER_CUTOVER_GATE",
    )
    assignment = router.assign_model(ctx)
    assert assignment.role == "overseer"
    assert assignment.model_id == "gpt-5.6-sol"
    assert assignment.reasoning_effort == ReasoningEffort.XHIGH


# Test 8: Deterministic Status/Watchdog Cycles (Zero LLM Tokens)
@pytest.mark.parametrize(
    "action",
    ["heartbeat", "status", "watchdog", "health_check", "ping", "supervisory_cycle", "audit_poll"],
)
def test_deterministic_status_actions_are_zero_token_operations(
    router: IntelligencePolicyRouter, action: str
) -> None:
    assert is_deterministic_status_operation(action)
    ctx = TaskContext(task_name=action, is_deterministic_status_op=True)
    assignment = router.assign_model(ctx)
    assert assignment.is_zero_token_noop
    assert assignment.model_id == "none"
    assert assignment.reasoning_effort is None


# Test 9: A-08 Heterogeneous Decorrelation (Builder != Auditor)
def test_a08_heterogeneous_auditor_selection_for_gpt_builder(router: IntelligencePolicyRouter) -> None:
    builder_ctx = TaskContext(
        task_name="implement_wave6_fixtures",
        role="builder",
        complexity_score=0.8,
    )
    builder_assignment = router.assign_model(builder_ctx)
    assert builder_assignment.family == ModelFamily.GPT

    auditor_ctx = TaskContext(
        task_name="court_verify_wave6",
        role="auditor",
        consequence_level=0.75,
    )
    auditor_assignment = router.assign_model(auditor_ctx)
    assert auditor_assignment.family != ModelFamily.GPT
    assert auditor_assignment.family in HETEROGENEOUS_AUDITOR_FAMILIES_FOR_GPT
    assert router.validate_a08_independence(builder_assignment, auditor_assignment)


def test_a08_enforcer_gpt_mapping_enforcement() -> None:
    catalog = ModelCatalog()
    enforcer = A08Enforcer(catalog)
    # Check that AUDITOR_MAPPING includes GPT
    assert ModelFamily.GPT in AUDITOR_MAPPING
    assert ModelFamily.GEMINI in AUDITOR_MAPPING[ModelFamily.GPT]

    # Enforce Builder = GPT, Auditor = GEMINI -> PASS
    result_pass = enforcer.enforce(
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
        auditor_provider="google",
        auditor_model_id="gemini-3.6-flash",
        auditor_family=ModelFamily.GEMINI,
    )
    assert result_pass.verdict == A08Verdict.PASS

    # Enforce Builder = GPT, Auditor = GPT -> FAIL_SAME_FAMILY
    result_fail = enforcer.enforce(
        builder_provider="codex",
        builder_model_id="gpt-5.6-sol",
        builder_family=ModelFamily.GPT,
        auditor_provider="openai",
        auditor_model_id="gpt-5.6-luna",
        auditor_family=ModelFamily.GPT,
    )
    assert result_fail.verdict == A08Verdict.FAIL_SAME_FAMILY


# Test 10: Preserved Admitted & Qualified Free Worker Pool
def test_admitted_free_worker_pool_members() -> None:
    expected_admitted_models = {
        "gemini-3.6-flash",
        "minimax/minimax-m2.5",
        "poolside/laguna-s-2.1:free",
        "z-ai/glm-5.3-flash",
        "cline-free/longcat-2.0",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "kilo-auto/free",
        "openrouter/free",
    }
    assert set(ADMITTED_FREE_WORKER_POOL) == expected_admitted_models

    expected_qualified_models = {
        "gemini-3.6-flash",
        "minimax/minimax-m2.5",
        "poolside/laguna-s-2.1:free",
        "z-ai/glm-5.3-flash",
        "cline-free/longcat-2.0",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "kilo-auto/free",
        "openrouter/free",
    }
    assert set(QUALIFIED_FREE_WORKER_POOL) == expected_qualified_models
