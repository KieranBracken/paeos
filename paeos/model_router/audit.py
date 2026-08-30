"""
PAEOS Model Router — Heterogeneous Adversarial Audit Routing

This module provides A-08 heterogeneous model decorrelation enforcement.
It is integrated with paeos.model_router.a08_enforcer for fail-closed verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from paeos.model_router.a08_enforcer import (
    A08Enforcer,
    A08EnforcementResult,
    A08Verdict,
    resolve_logical_model_family,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.types import ModelCatalogEntry, ModelFamily, ProviderId


@dataclass
class AuditRouteResult:
    """Result of heterogeneous auditor routing with A-08 enforcement."""
    builder_family: ModelFamily
    auditor_family: ModelFamily
    auditor_model: Optional[ModelCatalogEntry]
    eligible: bool
    a08_result: Optional[A08EnforcementResult] = None
    rejection_reason: Optional[str] = None


# Preferred Heterogeneous Auditor Mapping
# Strict Invariant: Auditor Family MUST NEVER equal Builder Family
AUDITOR_MAPPING = {
    ModelFamily.DEEPSEEK: [ModelFamily.GEMINI, ModelFamily.GLM, ModelFamily.LAGUNA],
    ModelFamily.MINIMAX: [ModelFamily.GEMINI, ModelFamily.GLM],
    ModelFamily.GEMINI: [ModelFamily.GLM, ModelFamily.DEEPSEEK, ModelFamily.LAGUNA],
    ModelFamily.GLM: [ModelFamily.GEMINI, ModelFamily.DEEPSEEK],
    ModelFamily.LAGUNA: [ModelFamily.GEMINI, ModelFamily.GLM],
    ModelFamily.HY3: [ModelFamily.GEMINI, ModelFamily.GLM],
    ModelFamily.NEMOTRON: [ModelFamily.GEMINI, ModelFamily.GLM],
    ModelFamily.UNKNOWN: [],  # Unknown builder family = FAIL CLOSED
}


def select_heterogeneous_auditor(
    builder_family: ModelFamily,
    catalog: ModelCatalog,
    available_providers: List[ProviderId],
) -> Optional[ModelCatalogEntry]:
    """
    Selects an auditor from a strictly distinct model family from the builder.
    Uses A-08 enforcer for fail-closed semantics.
    """
    enforcer = A08Enforcer(catalog)
    result = enforcer.select_auditor(builder_family, available_providers)
    
    if result is None:
        return None
    
    model, _ = result
    return model


def select_heterogeneous_auditor_with_enforcement(
    builder_family: ModelFamily,
    builder_provider: str,
    builder_model_id: str,
    catalog: ModelCatalog,
    available_providers: List[ProviderId],
) -> AuditRouteResult:
    """
    Select a heterogeneous auditor with full A-08 enforcement.
    
    This is the primary entry point for A-08 compliant audit routing.
    Returns AuditRouteResult with full provenance and enforcement result.
    """
    enforcer = A08Enforcer(catalog)
    
    # Attempt to select a heterogeneous auditor
    selection_result = enforcer.select_auditor(builder_family, available_providers)
    
    if selection_result is None:
        # No eligible heterogeneous auditor found
        return AuditRouteResult(
            builder_family=builder_family,
            auditor_family=ModelFamily.UNKNOWN,
            auditor_model=None,
            eligible=False,
            rejection_reason=f"No eligible heterogeneous auditor found for builder family: {builder_family.value}",
        )
    
    auditor_model, auditor_family = selection_result
    
    # Enforce A-08 verification
    a08_result = enforcer.enforce(
        builder_provider=builder_provider,
        builder_model_id=builder_model_id,
        builder_family=builder_family,
        auditor_provider=auditor_model.provider_id.value,
        auditor_model_id=auditor_model.model_id,
        auditor_family=auditor_family,
    )
    
    return AuditRouteResult(
        builder_family=builder_family,
        auditor_family=auditor_family,
        auditor_model=auditor_model,
        eligible=a08_result.passed,
        a08_result=a08_result,
        rejection_reason=None if a08_result.passed else a08_result.reason,
    )


def verify_audit_route(
    builder_provider: str,
    builder_model_id: str,
    builder_family: ModelFamily,
    auditor_provider: str,
    auditor_model_id: str,
    auditor_family: ModelFamily,
    catalog: ModelCatalog,
) -> A08EnforcementResult:
    """
    Verify an audit route for A-08 compliance.
    
    Use this to verify a completed builder->auditor routing decision.
    Returns the A-08 enforcement result with full provenance.
    """
    enforcer = A08Enforcer(catalog)
    return enforcer.enforce(
        builder_provider=builder_provider,
        builder_model_id=builder_model_id,
        builder_family=builder_family,
        auditor_provider=auditor_provider,
        auditor_model_id=auditor_model_id,
        auditor_family=auditor_family,
    )


def verify_fallback_chain(
    builder_family: ModelFamily,
    fallback_chain: List[tuple],
    catalog: ModelCatalog,
) -> A08EnforcementResult:
    """
    Verify that a fallback chain maintains heterogeneous independence.
    
    Each fallback candidate is re-evaluated for family eligibility.
    """
    enforcer = A08Enforcer(catalog)
    
    # Convert to the format expected by verify_fallback_chain
    chain = [
        (provider, model_id, family)
        for provider, model_id, family in fallback_chain
    ]
    
    return enforcer.verify_fallback_chain(builder_family, chain)
