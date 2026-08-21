"""
PAEOS Model Router — First-Class Data Privacy Eligibility Gating
"""
from __future__ import annotations

from paeos.model_router.types import DataClass, ProviderDataPolicy, ProviderId


def evaluate_privacy_eligibility(
    data_class: DataClass,
    provider_policy: ProviderDataPolicy,
) -> bool:
    """
    Evaluates whether a task's data classification permits routing to a provider.
    Privacy is a strict boolean eligibility constraint, not a soft score.
    """
    # SECRET material is NEVER dispatched to any remote model
    if data_class == DataClass.SECRET:
        raise ValueError(
            "CRITICAL PRIVACY INVARIANT VIOLATION: Task marked 'SECRET' must never be dispatched to a remote LLM."
        )

    # CONFIDENTIAL requires strict non-training and non-retention guarantee
    if data_class == DataClass.CONFIDENTIAL:
        if not provider_policy.allows_confidential:
            return False
        if provider_policy.trains_on_inputs:
            return False
        return True

    # INTERNAL allows standard project code on zero-retention / non-training routes
    if data_class == DataClass.INTERNAL:
        if not provider_policy.allows_internal:
            return False
        if provider_policy.trains_on_inputs:
            # Block training routes (e.g. Kilo Auto Free) from ingesting internal codebase
            return False
        return True

    # PUBLIC allows all active routes
    if data_class == DataClass.PUBLIC:
        return True

    return False
