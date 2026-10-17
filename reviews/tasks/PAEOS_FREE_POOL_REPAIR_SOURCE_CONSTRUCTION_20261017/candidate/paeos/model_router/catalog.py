"""
PAEOS Model Router — Validated Model Catalog & Free-Only Registry
"""
from __future__ import annotations

from paeos.model_router.providers import ProviderRegistry, build_builtin_provider_registry
from paeos.model_router.types import (
    AdmissionState,
    CostTier,
    ModelCatalogEntry,
    ModelFamily,
    ProviderDataPolicy,
    ProviderId,
)

PROVIDER_DATA_POLICIES: dict[ProviderId, ProviderDataPolicy] = {
    ProviderId.GOOGLE: ProviderDataPolicy(
        provider_id=ProviderId.GOOGLE,
        trains_on_inputs=False,
        retains_prompts=False,
        allows_internal=True,
        allows_confidential=True,
    ),
    ProviderId.CLINE: ProviderDataPolicy(
        provider_id=ProviderId.CLINE,
        trains_on_inputs=False,
        retains_prompts=False,
        allows_internal=True,
        allows_confidential=True,
    ),
    ProviderId.NVIDIA: ProviderDataPolicy(
        provider_id=ProviderId.NVIDIA,
        trains_on_inputs=False,
        retains_prompts=False,
        allows_internal=True,
        allows_confidential=True,
    ),
    ProviderId.KILO: ProviderDataPolicy(
        provider_id=ProviderId.KILO,
        trains_on_inputs=True,   # Kilo Auto Free routes may train or log prompts
        retains_prompts=True,
        allows_internal=False,  # Excluded from INTERNAL / CONFIDENTIAL
        allows_confidential=False,
    ),
    ProviderId.OPENROUTER: ProviderDataPolicy(
        provider_id=ProviderId.OPENROUTER,
        trains_on_inputs=False,
        retains_prompts=False,
        allows_internal=True,
        allows_confidential=True,
    ),
}


INITIAL_MODEL_CATALOG: list[ModelCatalogEntry] = [
    # Google AI Studio (Live verified zero-cost Free Tier)
    ModelCatalogEntry(
        model_id="gemini-3.6-flash",
        provider_id=ProviderId.GOOGLE,
        family=ModelFamily.GEMINI,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=True,          # Empirically verified live 200 OK
        available=True,
        admission_state=AdmissionState.ADMITTED,
        context_window=1_048_576,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.95,
        entitlement_notes="Google AI Studio Free Tier (Zero-cost API key); live 200 OK verified.",
    ),
    # NVIDIA meta/llama-3.1-8b-instruct is retired (upstream HTTP 410) and
    # intentionally has no live catalog entry or replacement until eligibility is proven.
    # NVIDIA NIM (Deprecated EOL model)
    ModelCatalogEntry(
        model_id="z-ai/glm-5.2",
        provider_id=ProviderId.NVIDIA,
        family=ModelFamily.GLM,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=False,
        available=False,
        admission_state=AdmissionState.DISCOVERED,
        context_window=1_000_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.90,
        entitlement_notes="Retired by NVIDIA NIM backend on 2026-08-21T09:00:00Z (410 Gone).",
    ),
    # Cline API (Probed zero-cost route: Minimax M2.5)
    ModelCatalogEntry(
        model_id="minimax/minimax-m2.5",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.MINIMAX,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=False,         # Live probe returned HTTP 401 Unauthorized (expired WorkOS OAuth session)
        available=False,
        admission_state=AdmissionState.SDK_QUALIFIED,
        context_window=128_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.85,
        entitlement_notes="Zero-cost model on Cline API; live probe returned HTTP 401 (expired session). Awaiting re-authentication.",
    ),
    # Cline API (Live verified zero-cost route: Laguna S 2.1 Free)
    ModelCatalogEntry(
        model_id="poolside/laguna-s-2.1:free",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.LAGUNA,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=True,          # Empirically verified slug; subject to daily free inference quota
        available=False,             # Daily cap exhausted; disabled to prevent router failover stalls
        admission_state=AdmissionState.LIVE_PROBED,
        context_window=64_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.82,
        entitlement_notes="Daily free model on Cline; returns 429 INFERENCE_CAP_ERROR upon daily quota exhaustion.",
    ),
    # ClinePass Subscription Route (Surface restricted)
    ModelCatalogEntry(
        model_id="deepseek/deepseek-v4-flash",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.DEEPSEEK,
        cost_tier=CostTier.SUBSCRIPTION_INCLUDED,
        pricing_verified_free=True,
        live_verified=False,         # Live probe returned HTTP 401
        available=False,
        admission_state=AdmissionState.SDK_QUALIFIED,
        context_window=64_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.88,
        entitlement_notes="Restricted to Cline product surfaces / ClinePass subscription key; live probe returned HTTP 401.",
    ),
    # Cline Pass Qualified Models (Verified from installed @cline/llms package closure)
    ModelCatalogEntry(
        model_id="z-ai/glm-5.3-flash",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.GLM,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=False,         # Live probe returned HTTP 401
        available=False,
        admission_state=AdmissionState.SDK_QUALIFIED,
        context_window=1_310_720,
        supports_tools=True,
        supports_json=True,
        verified_at=1772755200.0,
        base_quality_score=0.92,
        entitlement_notes="Zero-cost model on Cline Pass; live probe returned HTTP 401 (expired session).",
    ),
    ModelCatalogEntry(
        model_id="cline-pass/glm-5.3",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.GLM,
        cost_tier=CostTier.SUBSCRIPTION_INCLUDED,
        pricing_verified_free=True,
        live_verified=False,         # Live probe returned HTTP 401
        available=False,
        admission_state=AdmissionState.SDK_QUALIFIED,
        context_window=1_310_720,
        supports_tools=True,
        supports_json=True,
        verified_at=1772755200.0,
        base_quality_score=0.94,
        entitlement_notes="Cline Pass subscription model (Z-AI top open weights model, 1.31M context); live probe returned HTTP 401.",
    ),
    ModelCatalogEntry(
        model_id="cline-pass/kimi-k3",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.KIMI,
        cost_tier=CostTier.SUBSCRIPTION_INCLUDED,
        pricing_verified_free=True,
        live_verified=True,          # Empirically verified live 200 OK via api.cline.bot
        available=True,
        admission_state=AdmissionState.ADMITTED,
        context_window=1_048_576,
        supports_tools=True,
        supports_json=True,
        verified_at=1772755200.0,
        base_quality_score=0.93,
        entitlement_notes="Cline Pass subscription model (Moonshot Kimi K3 1M context); zero marginal cost under pass; live 200 OK verified.",
    ),
    ModelCatalogEntry(
        model_id="cline-free/longcat-2.0",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.LONGCAT,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=False,         # Live probe returned HTTP 403 (restricted surface)
        available=False,
        admission_state=AdmissionState.SDK_QUALIFIED,
        context_window=1_048_756,
        supports_tools=True,
        supports_json=True,
        verified_at=1772755200.0,
        base_quality_score=0.85,
        entitlement_notes="Zero-cost model on Cline Free (1M context agentic coding model); live probe returned HTTP 403.",
    ),
    ModelCatalogEntry(
        model_id="cline-pass/qwen3.8-max",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.QWEN,
        cost_tier=CostTier.SUBSCRIPTION_INCLUDED,
        pricing_verified_free=True,
        live_verified=True,          # Empirically verified live 200 OK via api.cline.bot
        available=True,
        admission_state=AdmissionState.ADMITTED,
        context_window=1_000_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1772755200.0,
        base_quality_score=0.93,
        entitlement_notes="Cline Pass subscription model (Qwen 3.8 Max SOTA coding model); zero marginal cost under pass; live 200 OK verified.",
    ),
    # Kilo Gateway (Live verified free endpoints)
    ModelCatalogEntry(
        model_id="kilo-auto/free",
        provider_id=ProviderId.KILO,
        family=ModelFamily.UNKNOWN,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=True,
        available=True,
        admission_state=AdmissionState.ADMITTED,
        context_window=64_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.75,
        entitlement_notes="Kilo Auto Free Gateway; live 200 OK verified.",
    ),
    ModelCatalogEntry(
        model_id="nvidia/nemotron-3-ultra-550b-a55b:free",
        provider_id=ProviderId.KILO,
        family=ModelFamily.NEMOTRON,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=True,
        available=True,
        admission_state=AdmissionState.ADMITTED,
        context_window=128_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.84,
        entitlement_notes="Kilo Nemotron-3 free endpoint; live 200 OK verified.",
    ),
    # OpenRouter Free Router (Strict FREE_ONLY)
    ModelCatalogEntry(
        model_id="openrouter/free",
        provider_id=ProviderId.OPENROUTER,
        family=ModelFamily.UNKNOWN,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=True,
        available=True,
        admission_state=AdmissionState.ADMITTED,
        context_window=32_000,
        supports_tools=False,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.70,
        entitlement_notes="OpenRouter Free Router; live 200 OK verified.",
    ),
    ModelCatalogEntry(
        model_id="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        provider_id=ProviderId.OPENROUTER,
        family=ModelFamily.NEMOTRON,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=True,
        available=True,
        admission_state=AdmissionState.ADMITTED,
        context_window=32_000,
        supports_tools=False,
        supports_json=True,
        base_quality_score=0.70,
        entitlement_notes="Observed FREE OpenRouter model used by the DEBT-0124 fixed supervisor binding.",
    ),
]


class ModelCatalog:
    def __init__(
        self,
        entries: list[ModelCatalogEntry] | None = None,
        provider_registry: ProviderRegistry | None = None,
    ):
        self._catalog: dict[str, ModelCatalogEntry] = {}
        self.provider_registry = provider_registry or build_builtin_provider_registry()
        entries = entries if entries is not None else INITIAL_MODEL_CATALOG
        for e in entries:
            self.register(e)

    def register(self, entry: ModelCatalogEntry) -> None:
        """Register a model entry with strict FREE_ONLY / SUBSCRIPTION_INCLUDED invariants."""
        if entry.provider_id == ProviderId.OPENROUTER:
            is_valid_free = entry.model_id == "openrouter/free" or entry.model_id.endswith(":free")
            if not is_valid_free:
                raise ValueError(
                    f"FREE_ONLY Invariant Violation: Non-free OpenRouter model rejected '{entry.model_id}'."
                )

        if not entry.pricing_verified_free:
            raise ValueError(
                f"FREE_ONLY Invariant Violation: Model without verified free/subscription pricing rejected '{entry.model_id}'."
            )

        self._catalog[entry.model_id] = entry

    def get(self, model_id: str) -> ModelCatalogEntry | None:
        return self._catalog.get(model_id)

    def list_models(
        self,
        provider_id: ProviderId | None = None,
        available_only: bool = False,
    ) -> list[ModelCatalogEntry]:
        models = list(self._catalog.values())
        if provider_id:
            models = [m for m in models if m.provider_id == provider_id]
        if available_only:
            models = [m for m in models if m.available]
        return models

    def get_data_policy(self, provider_id: ProviderId) -> ProviderDataPolicy:
        try:
            descriptor = self.provider_registry.resolve(provider_id)
        except KeyError:
            return ProviderDataPolicy(
                provider_id=provider_id,
                trains_on_inputs=True,
                retains_prompts=True,
                allows_internal=False,
                allows_confidential=False,
            )
        return ProviderDataPolicy(
            provider_id=provider_id,
            trains_on_inputs=descriptor.trains_on_inputs,
            retains_prompts=descriptor.retains_prompts,
            allows_internal=descriptor.allows_internal,
            allows_confidential=descriptor.allows_confidential,
        )
