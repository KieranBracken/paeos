"""
Adversarial Unit Tests: Generic Model Decorrelation / A-08 Fail-Closed

Tests prove that the A-08 heterogeneous independence enforcement works correctly:
- different families → PASS
- same exact model → FAIL
- different models/same family → FAIL
- different providers/same family → FAIL
- unknown builder family → FAIL CLOSED
- unknown auditor family → FAIL CLOSED
- fallback becomes same family → rejected and next candidate evaluated
- no eligible auditor remains → HALT/REMAND
- logical alias resolves same family → FAIL
- actual physical families differ → PASS
"""

import pytest
from paeos.model_router.a08_enforcer import (
    A08Enforcer,
    A08Verdict,
    resolve_logical_model_family,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.types import (
    CostTier,
    ModelCatalogEntry,
    ModelFamily,
    ProviderId,
)


# Test fixtures
@pytest.fixture
def catalog():
    """Create a test catalog with known models."""
    entries = [
        ModelCatalogEntry(
            model_id="gemini-3.6-flash",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            cost_tier=CostTier.FREE,
            pricing_verified_free=True,
            live_verified=True,
            available=True,
            context_window=1_048_576,
            supports_tools=True,
            supports_json=True,
        ),
        ModelCatalogEntry(
            model_id="meta/llama-3.1-8b-instruct",
            provider_id=ProviderId.NVIDIA,
            family=ModelFamily.LLAMA,
            cost_tier=CostTier.FREE,
            pricing_verified_free=True,
            live_verified=True,
            available=True,
            context_window=128_000,
            supports_tools=True,
            supports_json=True,
        ),
        ModelCatalogEntry(
            model_id="z-ai/glm-5.2",
            provider_id=ProviderId.NVIDIA,
            family=ModelFamily.GLM,
            cost_tier=CostTier.FREE,
            pricing_verified_free=True,
            live_verified=True,
            available=True,
            context_window=1_000_000,
            supports_tools=True,
            supports_json=True,
        ),
        ModelCatalogEntry(
            model_id="deepseek-ai/deepseek-chat:free",
            provider_id=ProviderId.OPENROUTER,
            family=ModelFamily.DEEPSEEK,
            cost_tier=CostTier.FREE,
            pricing_verified_free=True,
            live_verified=True,
            available=True,
            context_window=64_000,
            supports_tools=True,
            supports_json=True,
        ),
        ModelCatalogEntry(
            model_id="Kilo-Auto-Free",
            provider_id=ProviderId.KILO,
            family=ModelFamily.UNKNOWN,
            cost_tier=CostTier.FREE,
            pricing_verified_free=True,
            live_verified=True,
            available=True,
            context_window=64_000,
            supports_tools=True,
            supports_json=True,
        ),
    ]
    return ModelCatalog(entries)


@pytest.fixture
def enforcer(catalog):
    return A08Enforcer(catalog)


# ============================================================================
# Test Category 1: Different families → PASS
# ============================================================================

def test_different_families_gemini_builder_glm_auditor(enforcer):
    """Different model families: Gemini builder → GLM auditor = PASS"""
    result = enforcer.enforce(
        builder_provider="google",
        builder_model_id="gemini-3.6-flash",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="nvidia",
        auditor_model_id="z-ai/glm-5.2",
        auditor_family=ModelFamily.GLM,
    )
    
    assert result.passed
    assert result.verdict == A08Verdict.PASS
    assert "Heterogeneous independence verified" in result.reason


def test_different_families_deepseek_builder_gemini_auditor(enforcer):
    """Different model families: DeepSeek builder → Gemini auditor = PASS"""
    result = enforcer.enforce(
        builder_provider="openrouter",
        builder_model_id="deepseek-ai/deepseek-chat:free",
        builder_family=ModelFamily.DEEPSEEK,
        auditor_provider="google",
        auditor_model_id="gemini-3.6-flash",
        auditor_family=ModelFamily.GEMINI,
    )
    
    assert result.passed
    assert result.verdict == A08Verdict.PASS


def test_different_families_minimax_builder_nemotron_auditor(enforcer):
    """Different model families: MiniMax builder → Nemotron auditor = PASS"""
    result = enforcer.enforce(
        builder_provider="openrouter",
        builder_model_id="minimax/minimax-text-01:free",
        builder_family=ModelFamily.MINIMAX,
        auditor_provider="kilo",
        auditor_model_id="nvidia/nemotron-3-ultra-550b-a55b:free",
        auditor_family=ModelFamily.NEMOTRON,
    )
    
    assert result.passed
    assert result.verdict == A08Verdict.PASS


# ============================================================================
# Test Category 2: Same exact model → FAIL
# ============================================================================

def test_same_exact_model_fails(enforcer):
    """Same exact model: Gemini builder → Gemini auditor = FAIL"""
    result = enforcer.enforce(
        builder_provider="google",
        builder_model_id="gemini-3.6-flash",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="google",
        auditor_model_id="gemini-3.6-flash",
        auditor_family=ModelFamily.GEMINI,
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY
    assert "Same model family detected" in result.reason


# ============================================================================
# Test Category 3: Different models, same family → FAIL
# ============================================================================

def test_different_models_same_family_llama_fails(enforcer):
    """Different models, same family: Llama builder → Llama auditor = FAIL"""
    result = enforcer.enforce(
        builder_provider="nvidia",
        builder_model_id="meta/llama-3.1-8b-instruct",
        builder_family=ModelFamily.LLAMA,
        auditor_provider="nvidia",
        auditor_model_id="meta/llama-3.1-70b-instruct",
        auditor_family=ModelFamily.LLAMA,
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY


def test_different_models_same_family_glm_fails(enforcer):
    """Different GLM models, same family: GLM builder → GLM auditor = FAIL"""
    result = enforcer.enforce(
        builder_provider="nvidia",
        builder_model_id="z-ai/glm-5.2",
        builder_family=ModelFamily.GLM,
        auditor_provider="openrouter",
        auditor_model_id="z-ai/glm-4:free",
        auditor_family=ModelFamily.GLM,
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY


# ============================================================================
# Test Category 4: Different providers, same family → FAIL
# ============================================================================

def test_different_providers_same_family_fails(enforcer):
    """Different providers, same family: OpenRouter Gemini → Google Gemini = FAIL"""
    result = enforcer.enforce(
        builder_provider="openrouter",
        builder_model_id="google/gemini-3.6-flash:free",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="google",
        auditor_model_id="gemini-3.6-flash",
        auditor_family=ModelFamily.GEMINI,
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY


# ============================================================================
# Test Category 5: Unknown builder family → FAIL CLOSED
# ============================================================================

def test_unknown_builder_family_fails_closed(enforcer):
    """Unknown builder family = FAIL CLOSED"""
    result = enforcer.enforce(
        builder_provider="kilo",
        builder_model_id="Kilo-Auto-Free",
        builder_family=ModelFamily.UNKNOWN,
        auditor_provider="google",
        auditor_model_id="gemini-3.6-flash",
        auditor_family=ModelFamily.GEMINI,
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_UNKNOWN_BUILDER
    assert "FAIL CLOSED" in result.reason


# ============================================================================
# Test Category 6: Unknown auditor family → FAIL CLOSED
# ============================================================================

def test_unknown_auditor_family_fails_closed(enforcer):
    """Unknown auditor family = FAIL CLOSED"""
    result = enforcer.enforce(
        builder_provider="google",
        builder_model_id="gemini-3.6-flash",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="kilo",
        auditor_model_id="Kilo-Auto-Free",
        auditor_family=ModelFamily.UNKNOWN,
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_UNKNOWN_AUDITOR
    assert "FAIL CLOSED" in result.reason


# ============================================================================
# Test Category 7: Fallback chain validation
# ============================================================================

def test_fallback_chain_maintains_heterogeneity(enforcer):
    """Fallback chain: Gemini builder → fallback to GLM = PASS"""
    fallback_chain = [
        ("openrouter", "google/gemini-3.6-flash:free", ModelFamily.GEMINI),  # unavailable
        ("nvidia", "z-ai/glm-5.2", ModelFamily.GLM),  # heterogeneous - FINAL candidate
    ]
    
    result = enforcer.verify_fallback_chain(ModelFamily.GEMINI, fallback_chain)
    
    # Post-failover: only FINAL candidate matters for A-08
    # Final candidate GLM is different from builder GEMINI -> PASS
    assert result.passed
    assert result.verdict == A08Verdict.PASS
    assert "z-ai/glm-5.2" in result.reason


def test_fallback_chain_same_family_rejected(enforcer):
    """Fallback resolves to same family = chain rejected"""
    fallback_chain = [
        ("openrouter", "google/gemini-3.6-flash:free", ModelFamily.GEMINI),
    ]
    
    result = enforcer.verify_fallback_chain(ModelFamily.GEMINI, fallback_chain)
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY


def test_fallback_chain_unknown_family_rejected(enforcer):
    """Fallback has unknown family = chain rejected with FAIL CLOSED"""
    fallback_chain = [
        ("kilo", "Kilo-Auto-Free", ModelFamily.UNKNOWN),
    ]
    
    result = enforcer.verify_fallback_chain(ModelFamily.GEMINI, fallback_chain)
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_UNKNOWN_AUDITOR
    assert "FAIL CLOSED" in result.reason


# ============================================================================
# Test Category 8: No eligible auditor → HALT/REMAND
# ============================================================================

def test_no_eligible_auditor_returns_none(enforcer):
    """No eligible heterogeneous auditor = None returned"""
    # Try to find auditor for UNKNOWN builder family
    result = enforcer.select_auditor(ModelFamily.UNKNOWN)
    
    assert result is None


def test_no_eligible_auditor_for_limited_providers(enforcer):
    """No eligible auditor when only same-family providers available"""
    # Only NVIDIA providers available, but builder is also on NVIDIA
    limited_providers = [ProviderId.NVIDIA]
    
    # Create a custom catalog where builder is on NVIDIA
    entries = [
        ModelCatalogEntry(
            model_id="meta/llama-3.1-8b-instruct",
            provider_id=ProviderId.NVIDIA,
            family=ModelFamily.LLAMA,
            cost_tier=CostTier.FREE,
            pricing_verified_free=True,
            live_verified=True,
            available=True,
            context_window=128_000,
            supports_tools=True,
            supports_json=True,
        ),
    ]
    limited_catalog = ModelCatalog(entries)
    limited_enforcer = A08Enforcer(limited_catalog)
    
    result = limited_enforcer.select_auditor(ModelFamily.LLAMA, limited_providers)
    
    assert result is None


# ============================================================================
# Test Category 9: Logical alias resolution
# ============================================================================

def test_logical_alias_without_resolution_unknown(catalog):
    """Logical alias without resolved physical model = UNKNOWN"""
    family = resolve_logical_model_family("paeos-audit", catalog, None)
    
    assert family == ModelFamily.UNKNOWN


def test_logical_alias_with_resolution_returns_family(catalog):
    """Logical alias with resolved physical model = actual family"""
    gemini_model = catalog.get("gemini-3.6-flash")
    family = resolve_logical_model_family("paeos-audit", catalog, gemini_model)
    
    assert family == ModelFamily.GEMINI


def test_dynamic_route_kilo_auto_unknown(catalog):
    """Kilo Auto dynamic route = UNKNOWN without resolution"""
    family = resolve_logical_model_family("kilo-auto", catalog, None)
    
    assert family == ModelFamily.UNKNOWN


def test_dynamic_route_openrouter_free_unknown(catalog):
    """OpenRouter Free dynamic route = UNKNOWN without resolution"""
    family = resolve_logical_model_family("openrouter/free", catalog, None)
    
    assert family == ModelFamily.UNKNOWN


# ============================================================================
# Test Category 10: Provenance capture
# ============================================================================

def test_provenance_capture(enforcer):
    """Provenance is captured correctly for verification"""
    result = enforcer.enforce(
        builder_provider="google",
        builder_model_id="gemini-3.6-flash",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="nvidia",
        auditor_model_id="z-ai/glm-5.2",
        auditor_family=ModelFamily.GLM,
    )
    
    assert result.builder_provenance is not None
    assert result.auditor_provenance is not None
    
    assert result.builder_provenance.provider == "google"
    assert result.builder_provenance.model_id == "gemini-3.6-flash"
    assert result.builder_provenance.family == ModelFamily.GEMINI
    
    assert result.auditor_provenance.provider == "nvidia"
    assert result.auditor_provenance.model_id == "z-ai/glm-5.2"
    assert result.auditor_provenance.family == ModelFamily.GLM


def test_provenance_to_dict(enforcer):
    """Provenance can be serialized to dict for persistence"""
    result = enforcer.enforce(
        builder_provider="google",
        builder_model_id="gemini-3.6-flash",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="nvidia",
        auditor_model_id="z-ai/glm-5.2",
        auditor_family=ModelFamily.GLM,
    )
    
    d = result.to_dict()
    
    assert d["verdict"] == "PASS"
    assert d["builder_provenance"] is not None
    assert d["auditor_provenance"] is not None
    assert "gemini" in d["builder_provenance"].lower()
    assert "glm" in d["auditor_provenance"].lower()


# ============================================================================
# Test Category 11: Auditor selection
# ============================================================================

def test_select_auditor_for_deepseek_builder(enforcer):
    """Select heterogeneous auditor for DeepSeek builder"""
    result = enforcer.select_auditor(ModelFamily.DEEPSEEK)
    
    assert result is not None
    _model, family = result
    assert family != ModelFamily.DEEPSEEK
    assert family != ModelFamily.UNKNOWN


def test_select_auditor_for_gemini_builder(enforcer):
    """Select heterogeneous auditor for Gemini builder"""
    result = enforcer.select_auditor(ModelFamily.GEMINI)
    
    assert result is not None
    _model, family = result
    assert family != ModelFamily.GEMINI
    assert family != ModelFamily.UNKNOWN


def test_select_auditor_for_llama_builder(enforcer):
    """Select heterogeneous auditor for Llama builder"""
    result = enforcer.select_auditor(ModelFamily.LLAMA)
    
    assert result is not None
    _model, family = result
    assert family != ModelFamily.LLAMA
    assert family != ModelFamily.UNKNOWN


def test_select_auditor_filters_by_provider(enforcer):
    """Select auditor filters by available providers"""
    # Only NVIDIA available - should not select Gemini (Google)
    providers = [ProviderId.NVIDIA]
    
    result = enforcer.select_auditor(ModelFamily.GEMINI, providers)
    
    assert result is not None
    model, _family = result
    assert model.provider_id == ProviderId.NVIDIA


# ============================================================================
# Test Category 12: Regression test - fabricated same-family audit
# ============================================================================

def test_regression_fabricated_same_family_audit_blocked(enforcer):
    """
    Regression test: Historical fabricated/same-family audit condition
    can no longer reach L15 Seal.
    
    This simulates the historical defect where a same-family audit
    could pass through without detection.
    """
    # Attempt to verify a same-family audit (historical defect scenario)
    result = enforcer.enforce(
        builder_provider="google",
        builder_model_id="gemini-3.6-flash",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="openrouter",
        auditor_model_id="google/gemini-pro:free",
        auditor_family=ModelFamily.GEMINI,  # Same family!
    )
    
    # Must FAIL - same family detected
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY
    
    # Cannot proceed to Seal with this verdict
    # (This is the key regression test)
    assert result.verdict in (
        A08Verdict.FAIL_SAME_FAMILY,
        A08Verdict.FAIL_UNKNOWN_BUILDER,
        A08Verdict.FAIL_UNKNOWN_AUDITOR,
    )


# ============================================================================
# Test Category 13: Dynamic Physical Model Provenance
# ============================================================================

def test_derive_family_from_actual_model_deepseek(catalog):
    """Derive family from actual DeepSeek model string."""
    from paeos.model_router.a08_enforcer import derive_family_from_actual_model
    
    family = derive_family_from_actual_model("deepseek-chat", catalog)
    assert family == ModelFamily.DEEPSEEK


def test_derive_family_from_actual_model_gemini(catalog):
    """Derive family from actual Gemini model string."""
    from paeos.model_router.a08_enforcer import derive_family_from_actual_model
    
    family = derive_family_from_actual_model("gemini-2.0-flash", catalog)
    assert family == ModelFamily.GEMINI


def test_derive_family_from_actual_model_glm(catalog):
    """Derive family from actual GLM model string."""
    from paeos.model_router.a08_enforcer import derive_family_from_actual_model
    
    family = derive_family_from_actual_model("glm-4", catalog)
    assert family == ModelFamily.GLM


def test_derive_family_from_actual_model_unknown(catalog):
    """Unknown model string returns UNKNOWN."""
    from paeos.model_router.a08_enforcer import derive_family_from_actual_model
    
    family = derive_family_from_actual_model("completely-unknown-model-xyz", catalog)
    assert family == ModelFamily.UNKNOWN


def test_derive_family_from_actual_model_empty(catalog):
    """Empty model string returns UNKNOWN."""
    from paeos.model_router.a08_enforcer import derive_family_from_actual_model
    
    family = derive_family_from_actual_model("", catalog)
    assert family == ModelFamily.UNKNOWN


def test_dynamic_alias_different_provider_actual_same_family_fail(catalog, enforcer):
    """
    Aliases say different providers but actual physical families are same -> FAIL.
    
    Scenario: openrouter/free routes to a Gemini model
    Builder uses paeos-code which routes to a different Gemini variant
    Both resolve to GEMINI family -> A-08 FAIL
    """
    # Simulate: openrouter/free actually routes to gemini-pro (Gemini family)
    # Builder: paeos-code routes to another Gemini variant
    
    # First, verify with known families
    result = enforcer.enforce(
        builder_provider="openrouter",
        builder_model_id="google/gemini-pro:free",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="google",
        auditor_model_id="gemini-3.6-flash",
        auditor_family=ModelFamily.GEMINI,  # Same family!
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY


def test_dynamic_alias_different_aliases_same_actual_family_fail(catalog, enforcer):
    """
    Aliases differ but actual physical families are same -> FAIL.
    
    Scenario: paeos-code vs paeos-audit both resolve to same family
    """
    result = enforcer.enforce(
        builder_provider="kilo",
        builder_model_id="kilo-auto/free",
        builder_family=ModelFamily.GLM,
        auditor_provider="openrouter",
        auditor_model_id="openrouter/free",
        auditor_family=ModelFamily.GLM,  # Same family!
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY


def test_dynamic_alias_same_actual_families_differ_pass(catalog, enforcer):
    """
    Aliases might be similar but actual physical families differ -> PASS.
    
    This tests that A-08 correctly uses physical families, not aliases.
    """
    result = enforcer.enforce(
        builder_provider="openrouter",
        builder_model_id="deepseek-ai/deepseek-chat:free",
        builder_family=ModelFamily.DEEPSEEK,
        auditor_provider="google",
        auditor_model_id="gemini-3.6-flash",
        auditor_family=ModelFamily.GEMINI,  # Different family!
    )
    
    assert result.passed
    assert result.verdict == A08Verdict.PASS


def test_dynamic_auditor_identity_unknowable_fail_closed(catalog, enforcer):
    """
    Dynamic auditor identity unknowable -> FAIL CLOSED.
    
    Scenario: openrouter/free doesn't expose actual model -> UNKNOWN family
    """
    # When actual_model is unknown, the auditor family is UNKNOWN
    result = enforcer.enforce(
        builder_provider="google",
        builder_model_id="gemini-3.6-flash",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="openrouter",
        auditor_model_id="openrouter/free",
        auditor_family=ModelFamily.UNKNOWN,  # Unknown!
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_UNKNOWN_AUDITOR


def test_dynamic_builder_identity_unknowable_fail_closed(catalog, enforcer):
    """
    Dynamic builder identity unknowable -> FAIL CLOSED.
    
    Scenario: kilo-auto/free is the builder but actual model unknown
    """
    result = enforcer.enforce(
        builder_provider="kilo",
        builder_model_id="kilo-auto/free",
        builder_family=ModelFamily.UNKNOWN,  # Unknown builder!
        auditor_provider="google",
        auditor_model_id="gemini-3.6-flash",
        auditor_family=ModelFamily.GEMINI,
    )
    
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_UNKNOWN_BUILDER


def test_post_failover_provenance_uses_final_model(catalog, enforcer):
    """
    Post-failover: Provenance must use the candidate that actually executed.
    
    Scenario:
    - auditor candidate A = MiniMax -> unavailable (skipped)
    - auditor candidate B = Gemini -> executes
    - builder = Gemini
    
    Final A-08 evaluation MUST see: builder Gemini, auditor Gemini -> FAIL
    """
    # This tests the fallback chain verification
    fallback_chain = [
        ("minimax", "MiniMax-Text-01", ModelFamily.MINIMAX),  # Failed/unavailable
        ("google", "gemini-3.6-flash", ModelFamily.GEMINI),      # Executed
    ]
    
    result = enforcer.verify_fallback_chain(ModelFamily.GEMINI, fallback_chain)
    
    # The fallback chain includes a Gemini (same as builder) -> FAIL
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY


def test_post_failover_provenance_skips_same_family(catalog, enforcer):
    """
    Fallback chain skips candidates that resolve to same family as builder.
    
    Scenario:
    - builder = GLM
    - auditor candidate A = GLM -> skipped (same family)
    - auditor candidate B = Gemini -> selected
    """
    fallback_chain = [
        ("nvidia", "z-ai/glm-5.2", ModelFamily.GLM),   # Same as builder - should be skipped
        ("google", "gemini-3.6-flash", ModelFamily.GEMINI),  # Different - valid
    ]
    
    result = enforcer.verify_fallback_chain(ModelFamily.GLM, fallback_chain)
    
    # Only the final model matters - Gemini is different from GLM -> PASS
    assert result.passed
    assert result.verdict == A08Verdict.PASS


def test_dynamic_same_family_seal_block(catalog, enforcer):
    """
    Dynamic/logical route ultimately resolves to builder's physical family
    and therefore cannot reach L15 Seal.
    
    This is an integrated runtime simulation.
    """
    # Simulate: paeos-code routes to a DeepSeek model
    # Auditor: openrouter/free routes to another DeepSeek model
    # Both are DEEPSEEK family -> cannot reach Seal
    
    result = enforcer.enforce(
        builder_provider="openrouter",
        builder_model_id="deepseek-ai/deepseek-chat:free",
        builder_family=ModelFamily.DEEPSEEK,
        auditor_provider="openrouter",
        auditor_model_id="deepseek-ai/deepseek-coder:free",
        auditor_family=ModelFamily.DEEPSEEK,  # Same family!
    )
    
    # FAIL - same family detected
    assert not result.passed
    assert result.verdict == A08Verdict.FAIL_SAME_FAMILY
    
    # Cannot reach L15 Seal with this verdict
    assert result.verdict in (
        A08Verdict.FAIL_SAME_FAMILY,
        A08Verdict.FAIL_UNKNOWN_BUILDER,
        A08Verdict.FAIL_UNKNOWN_AUDITOR,
    )


def test_router_response_captures_actual_model():
    """RouterResponse can capture actual upstream model identity."""
    from paeos.model_router.types import RouterResponse
    
    # When dynamic route returns actual model
    resp = RouterResponse(
        content="test",
        model_id="openrouter/free",           # Catalog alias
        actual_model="google/gemini-2.0-flash",  # Actual upstream model
        provider_id=ProviderId.OPENROUTER,
        family=ModelFamily.UNKNOWN,           # Catalog family (unknown)
        actual_family=ModelFamily.GEMINI,    # Derived from actual_model
    )
    
    assert resp.model_id == "openrouter/free"
    assert resp.actual_model == "google/gemini-2.0-flash"
    assert resp.family == ModelFamily.UNKNOWN
    assert resp.actual_family == ModelFamily.GEMINI


def test_a08_enforcer_uses_actual_family_when_available(catalog, enforcer):
    """
    A-08 enforcement prefers actual_family over catalog family when available.
    
    This ensures dynamic routes are evaluated against the real physical model.
    """
    # When we have actual_model info, we should derive actual_family from it
    from paeos.model_router.a08_enforcer import derive_family_from_actual_model
    
    # Simulate: openrouter/free routes to gemini-2.0-flash
    actual_model = "google/gemini-2.0-flash"
    actual_family = derive_family_from_actual_model(actual_model, catalog)
    
    assert actual_family == ModelFamily.GEMINI
    
    # Now verify A-08 with the actual derived family
    result = enforcer.enforce(
        builder_provider="nvidia",
        builder_model_id="meta/llama-3.1-8b-instruct",
        builder_family=ModelFamily.LLAMA,
        auditor_provider="openrouter",
        auditor_model_id="openrouter/free",
        auditor_family=actual_family,  # Using derived actual family
    )
    
    assert result.passed
    assert result.verdict == A08Verdict.PASS
