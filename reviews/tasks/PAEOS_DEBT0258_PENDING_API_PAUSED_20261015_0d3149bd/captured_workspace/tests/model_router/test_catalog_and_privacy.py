"""
Adversarial Unit Tests: Catalog, Free-Only Invariant, and Privacy Gating
"""
import pytest
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import mask_secret
from paeos.model_router.privacy import evaluate_privacy_eligibility
from paeos.model_router.types import (
    DataClass,
    ModelCatalogEntry,
    ModelFamily,
    ProviderDataPolicy,
    ProviderId,
)


def test_free_only_openrouter_rejection():
    """Invariant III: Reject any OpenRouter model that is not openrouter/free or ending in :free."""
    catalog = ModelCatalog()

    catalog.register(ModelCatalogEntry(
        model_id="openrouter/free",
        provider_id=ProviderId.OPENROUTER,
        family=ModelFamily.UNKNOWN,
        pricing_verified_free=True,
        live_verified=True,
        available=True,
        context_window=32000,
        supports_tools=False,
        supports_json=True,
        verified_at=100.0,
    ))
    catalog.register(ModelCatalogEntry(
        model_id="meta-llama/llama-3-8b-instruct:free",
        provider_id=ProviderId.OPENROUTER,
        family=ModelFamily.UNKNOWN,
        pricing_verified_free=True,
        live_verified=True,
        available=True,
        context_window=32000,
        supports_tools=False,
        supports_json=True,
        verified_at=100.0,
    ))

    with pytest.raises(ValueError, match="FREE_ONLY Invariant Violation"):
        catalog.register(ModelCatalogEntry(
            model_id="openrouter/auto",
            provider_id=ProviderId.OPENROUTER,
            family=ModelFamily.UNKNOWN,
            pricing_verified_free=True,
            live_verified=False,
            available=False,
            context_window=32000,
            supports_tools=False,
            supports_json=True,
            verified_at=100.0,
        ))

    with pytest.raises(ValueError, match="FREE_ONLY Invariant Violation"):
        catalog.register(ModelCatalogEntry(
            model_id="anthropic/claude-3.5-sonnet",
            provider_id=ProviderId.OPENROUTER,
            family=ModelFamily.UNKNOWN,
            pricing_verified_free=True,
            live_verified=False,
            available=False,
            context_window=200000,
            supports_tools=True,
            supports_json=True,
            verified_at=100.0,
        ))


def test_unverified_pricing_rejection():
    """Models with pricing_verified_free=False must be rejected from the free catalog."""
    catalog = ModelCatalog()
    with pytest.raises(ValueError, match="Model without verified free/subscription pricing rejected"):
        catalog.register(ModelCatalogEntry(
            model_id="paid/commercial-model",
            provider_id=ProviderId.CLINE,
            family=ModelFamily.DEEPSEEK,
            pricing_verified_free=False,
            live_verified=False,
            available=False,
            context_window=64000,
            supports_tools=True,
            supports_json=True,
            verified_at=100.0,
        ))


def test_privacy_gating_secret_never_remote():
    """Invariant IV: Task marked SECRET must raise an immediate exception and never reach any model."""
    policy = ProviderDataPolicy(provider_id=ProviderId.GOOGLE, allows_confidential=True, trains_on_inputs=False)
    with pytest.raises(ValueError, match="CRITICAL PRIVACY INVARIANT VIOLATION"):
        evaluate_privacy_eligibility(DataClass.SECRET, policy)


def test_privacy_gating_confidential_and_internal_training_filter():
    """INTERNAL and CONFIDENTIAL tasks must reject training routes (e.g. Kilo Auto Free)."""
    # Non-training private provider
    private_policy = ProviderDataPolicy(
        provider_id=ProviderId.GOOGLE,
        allows_internal=True,
        allows_confidential=True,
        trains_on_inputs=False,
    )
    assert evaluate_privacy_eligibility(DataClass.INTERNAL, private_policy) is True
    assert evaluate_privacy_eligibility(DataClass.CONFIDENTIAL, private_policy) is True

    # Training / Public route (Kilo Auto Free)
    training_policy = ProviderDataPolicy(
        provider_id=ProviderId.KILO,
        allows_internal=False,
        allows_confidential=False,
        trains_on_inputs=True,
    )
    assert evaluate_privacy_eligibility(DataClass.INTERNAL, training_policy) is False
    assert evaluate_privacy_eligibility(DataClass.CONFIDENTIAL, training_policy) is False
    assert evaluate_privacy_eligibility(DataClass.PUBLIC, training_policy) is True


def test_secret_masking_absolute_zero_leakage():
    """Secret values must be 100% masked without leaking any characters."""
    assert mask_secret(None) == "<UNSET>"
    assert mask_secret("") == "<UNSET>"
    assert mask_secret("sk-proj-1234567890abcdef") == "<CONFIGURED>"
    assert mask_secret("any-secret-token") == "<CONFIGURED>"
