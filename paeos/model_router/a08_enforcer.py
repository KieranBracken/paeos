"""
PAEOS A-08 Heterogeneous Model Decorrelation Enforcement

Fail-closed enforcement of constitutional requirement A-08: the auditor must be from
a different model family than the builder. This module provides runtime enforcement
of heterogeneous independence, not merely router preference scoring.

Required Semantics:
- BuilderFamily != AuditorFamily
- Same family = FAIL/REMAND
- Unknown family = FAIL CLOSED
- No eligible heterogeneous auditor = HALT/REMAND
- Fallback must re-evaluate family eligibility
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.types import ModelCatalogEntry, ModelFamily, ProviderId


class A08Verdict(Enum):
    """A-08 enforcement verdicts."""
    PASS = "PASS"                    # Heterogeneous families confirmed
    FAIL_SAME_FAMILY = "FAIL_SAME_FAMILY"
    FAIL_UNKNOWN_BUILDER = "FAIL_UNKNOWN_BUILDER"
    FAIL_UNKNOWN_AUDITOR = "FAIL_UNKNOWN_AUDITOR"
    FAIL_NO_ELIGIBLE_AUDITOR = "FAIL_NO_ELIGIBLE_AUDITOR"


@dataclass(frozen=True)
class Provenance:
    """Model provenance for A-08 verification."""
    provider: str
    model_id: str
    family: ModelFamily
    
    def __str__(self) -> str:
        return f"{self.provider}:{self.model_id} ({self.family.value})"


@dataclass(frozen=True)
class A08EnforcementResult:
    """Result of A-08 heterogeneous independence verification."""
    verdict: A08Verdict
    builder_provenance: Optional[Provenance]
    auditor_provenance: Optional[Provenance]
    reason: str
    
    @property
    def passed(self) -> bool:
        return self.verdict == A08Verdict.PASS
    
    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "builder_provenance": str(self.builder_provenance) if self.builder_provenance else None,
            "auditor_provenance": str(self.auditor_provenance) if self.auditor_provenance else None,
            "reason": self.reason,
        }


# A-08 Heterogeneous Auditor Mapping
# Strict Invariant: Auditor Family MUST NEVER equal Builder Family
AUDITOR_MAPPING = {
    ModelFamily.DEEPSEEK: [ModelFamily.GEMINI, ModelFamily.GLM, ModelFamily.LAGUNA],
    ModelFamily.MINIMAX: [ModelFamily.GEMINI, ModelFamily.GLM],
    ModelFamily.GEMINI: [ModelFamily.GLM, ModelFamily.DEEPSEEK, ModelFamily.LAGUNA],
    ModelFamily.GLM: [ModelFamily.GEMINI, ModelFamily.DEEPSEEK],
    ModelFamily.LAGUNA: [ModelFamily.GEMINI, ModelFamily.GLM],
    ModelFamily.HY3: [ModelFamily.GEMINI, ModelFamily.GLM],
    ModelFamily.NEMOTRON: [ModelFamily.GEMINI, ModelFamily.GLM],
    ModelFamily.LLAMA: [ModelFamily.GEMINI, ModelFamily.GLM, ModelFamily.DEEPSEEK],
    ModelFamily.UNKNOWN: [],  # Unknown builder family = FAIL CLOSED
}


class A08Enforcer:
    """
    A-08 Heterogeneous Model Decorrelation Enforcer.
    
    Provides fail-closed enforcement of constitutional A-08:
    - Verifies builder/auditor are from different model families
    - Captures and persists provenance for Court/seal evidence
    - Fails closed when heterogeneous auditor unavailable
    - Re-evaluates family eligibility on every fallback candidate
    """
    
    def __init__(self, catalog: ModelCatalog):
        self._catalog = catalog
    
    def enforce(
        self,
        builder_provider: str,
        builder_model_id: str,
        builder_family: ModelFamily,
        auditor_provider: str,
        auditor_model_id: str,
        auditor_family: ModelFamily,
    ) -> A08EnforcementResult:
        """
        Enforce A-08: verify heterogeneous independence between builder and auditor.
        
        Returns PASS only if families are confirmed different.
        Fails closed on: same family, unknown family, or heterogeneous auditor unavailable.
        """
        # Build provenance records
        builder_prov = Provenance(
            provider=builder_provider,
            model_id=builder_model_id,
            family=builder_family,
        )
        auditor_prov = Provenance(
            provider=auditor_provider,
            model_id=auditor_model_id,
            family=auditor_family,
        )
        
        # Check for unknown builder family - FAIL CLOSED
        if builder_family == ModelFamily.UNKNOWN:
            return A08EnforcementResult(
                verdict=A08Verdict.FAIL_UNKNOWN_BUILDER,
                builder_provenance=builder_prov,
                auditor_provenance=auditor_prov,
                reason="Builder family unknown - cannot verify heterogeneous independence. FAIL CLOSED.",
            )
        
        # Check for unknown auditor family - FAIL CLOSED
        if auditor_family == ModelFamily.UNKNOWN:
            return A08EnforcementResult(
                verdict=A08Verdict.FAIL_UNKNOWN_AUDITOR,
                builder_provenance=builder_prov,
                auditor_provenance=auditor_prov,
                reason="Auditor family unknown - heterogeneous independence unverified. FAIL CLOSED.",
            )
        
        # Check for same family - FAIL/REMAND
        if builder_family == auditor_family:
            return A08EnforcementResult(
                verdict=A08Verdict.FAIL_SAME_FAMILY,
                builder_provenance=builder_prov,
                auditor_provenance=auditor_prov,
                reason=f"Same model family detected: builder={builder_family.value}, auditor={auditor_family.value}. A-08 violation.",
            )
        
        # Different families confirmed - PASS
        return A08EnforcementResult(
            verdict=A08Verdict.PASS,
            builder_provenance=builder_prov,
            auditor_provenance=auditor_prov,
            reason=f"Heterogeneous independence verified: builder={builder_family.value}, auditor={auditor_family.value}",
        )
    
    def select_auditor(
        self,
        builder_family: ModelFamily,
        available_providers: Optional[List[ProviderId]] = None,
    ) -> Optional[Tuple[ModelCatalogEntry, ModelFamily]]:
        """
        Select a heterogeneous auditor for a given builder family.
        
        Returns (auditor_model, auditor_family) if available, None if no eligible auditor.
        Re-evaluates family eligibility on every candidate.
        """
        if builder_family == ModelFamily.UNKNOWN:
            # Unknown builder family - no eligible auditor
            return None
        
        # Get preferred auditor families for this builder
        preferred_families = AUDITOR_MAPPING.get(builder_family, [])
        
        # First pass: try preferred families
        for target_family in preferred_families:
            if target_family == builder_family:
                continue
            if target_family == ModelFamily.UNKNOWN:
                continue
                
            for model in self._catalog.list_models():
                if model.family != target_family:
                    continue
                if not model.available:
                    continue
                if available_providers and model.provider_id not in available_providers:
                    continue
                return (model, target_family)
        
        # Fallback: any available model whose family != builder_family and != UNKNOWN
        for model in self._catalog.list_models():
            if model.family == builder_family:
                continue
            if model.family == ModelFamily.UNKNOWN:
                continue
            if not model.available:
                continue
            if available_providers and model.provider_id not in available_providers:
                continue
            return (model, model.family)
        
        # No eligible heterogeneous auditor found
        return None
    
    def verify_fallback_chain(
        self,
        builder_family: ModelFamily,
        fallback_chain: List[Tuple[str, str, ModelFamily]],
    ) -> A08EnforcementResult:
        """
        Verify that the FINAL fallback candidate maintains heterogeneous independence.
        
        Post-failover: Only the candidate that actually EXECUTED matters for A-08.
        Earlier failed/unavailable candidates are skipped and don't affect the verdict.
        
        The fallback_chain represents candidates in order of execution:
        - Earlier candidates may fail/unavailable
        - The LAST candidate is the one that executed and determines A-08 outcome
        """
        builder_prov = Provenance(
            provider="builder",
            model_id="builder_model",
            family=builder_family,
        )
        
        if builder_family == ModelFamily.UNKNOWN:
            return A08EnforcementResult(
                verdict=A08Verdict.FAIL_UNKNOWN_BUILDER,
                builder_provenance=builder_prov,
                auditor_provenance=None,
                reason="Builder family unknown - cannot verify fallback chain. FAIL CLOSED.",
            )
        
        if not fallback_chain:
            return A08EnforcementResult(
                verdict=A08Verdict.FAIL_NO_ELIGIBLE_AUDITOR,
                builder_provenance=builder_prov,
                auditor_provenance=None,
                reason="No fallback candidates to verify - no eligible auditor.",
            )
        
        # Only verify the FINAL candidate that executed
        provider, model_id, family = fallback_chain[-1]
        
        auditor_prov = Provenance(
            provider=provider,
            model_id=model_id,
            family=family,
        )
        
        if family == ModelFamily.UNKNOWN:
            return A08EnforcementResult(
                verdict=A08Verdict.FAIL_UNKNOWN_AUDITOR,
                builder_provenance=builder_prov,
                auditor_provenance=auditor_prov,
                reason=f"Final fallback has unknown family - heterogeneous independence unverified. FAIL CLOSED.",
            )
        
        if family == builder_family:
            return A08EnforcementResult(
                verdict=A08Verdict.FAIL_SAME_FAMILY,
                builder_provenance=builder_prov,
                auditor_provenance=auditor_prov,
                reason=f"Final fallback resolves to same family as builder ({builder_family.value}). Fallback chain rejected.",
            )
        
        # Final candidate maintains heterogeneity
        return A08EnforcementResult(
            verdict=A08Verdict.PASS,
            builder_provenance=builder_prov,
            auditor_provenance=auditor_prov,
            reason=f"Final fallback candidate ({model_id}) maintains heterogeneous independence.",
        )


def resolve_logical_model_family(
    logical_model: str,
    catalog: ModelCatalog,
    resolved_physical_model: Optional[ModelCatalogEntry] = None,
) -> ModelFamily:
    """
    Resolve a logical model alias to its physical model family.
    
    For dynamic routes (paeos-auto, kilo-auto, openrouter/free), if the actual
    physical model is known, return its family. Otherwise return UNKNOWN.
    """
    # Logical aliases that dynamically select models
    dynamic_aliases = {
        "paeos-auto",
        "paeos-code", 
        "paeos-audit",
        "kilo-auto",
        "openrouter/free",
    }
    
    if logical_model.lower() in dynamic_aliases:
        # If we have a resolved physical model, use its family
        if resolved_physical_model is not None:
            return resolved_physical_model.family
        # Otherwise, family is unknown
        return ModelFamily.UNKNOWN
    
    # For explicit physical models, look up in catalog
    if resolved_physical_model is not None:
        return resolved_physical_model.family
    
    return ModelFamily.UNKNOWN


def derive_family_from_actual_model(
    actual_model: str,
    catalog: ModelCatalog,
) -> ModelFamily:
    """
    Derive the model family from the actual upstream model identity.
    
    This is critical for A-08 enforcement with dynamic routes like:
    - openrouter/free
    - kilo-auto/free
    - paeos-code
    - paeos-audit
    
    The actual_model is the real model selected by the upstream provider,
    not the logical alias. A-08 enforcement must use this actual family.
    
    Returns:
        ModelFamily - The actual physical model family
        ModelFamily.UNKNOWN - If family cannot be determined
    """
    if not actual_model:
        return ModelFamily.UNKNOWN
    
    # First, check if it's a known catalog entry
    catalog_entry = catalog.get(actual_model)
    if catalog_entry is not None:
        return catalog_entry.family
    
    # Pattern-match to infer family from model ID strings
    model_lower = actual_model.lower()
    
    # DeepSeek patterns
    if "deepseek" in model_lower:
        return ModelFamily.DEEPSEEK
    
    # Gemini patterns
    if "gemini" in model_lower:
        return ModelFamily.GEMINI
    
    # GLM patterns
    if "glm-" in model_lower or "glm4" in model_lower or "glm5" in model_lower:
        return ModelFamily.GLM
    
    # Llama patterns
    if "llama" in model_lower or "llama" in model_lower:
        return ModelFamily.LLAMA
    
    # Minimax patterns
    if "minimax" in model_lower:
        return ModelFamily.MINIMAX
    
    # Laguna patterns
    if "laguna" in model_lower:
        return ModelFamily.LAGUNA
    
    # Hy3 patterns
    if "hy3" in model_lower:
        return ModelFamily.HY3
    
    # Nemotron patterns
    if "nemotron" in model_lower:
        return ModelFamily.NEMOTRON
    
    # Qwen patterns
    if "qwen" in model_lower:
        return ModelFamily.QWEN

    # GPT patterns
    if "gpt-" in model_lower or model_lower.startswith("gpt"):
        return ModelFamily.GPT

    # Cannot determine family from model string
    return ModelFamily.UNKNOWN
