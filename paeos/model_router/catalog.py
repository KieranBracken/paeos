"""
PAEOS Model Router — Validated Model Catalog & Free-Only Registry
"""
from __future__ import annotations

from typing import Dict, List, Optional

from paeos.model_router.types import (
    CostTier,
    ModelCatalogEntry,
    ModelFamily,
    ProviderDataPolicy,
    ProviderId,
)


PROVIDER_DATA_POLICIES: Dict[ProviderId, ProviderDataPolicy] = {
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


INITIAL_MODEL_CATALOG: List[ModelCatalogEntry] = [
    # Google AI Studio (Live verified zero-cost Free Tier)
    ModelCatalogEntry(
        model_id="gemini-3.6-flash",
        provider_id=ProviderId.GOOGLE,
        family=ModelFamily.GEMINI,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=True,          # Empirically verified live 200 OK
        available=True,
        context_window=1_048_576,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.95,
        entitlement_notes="Google AI Studio Free Tier (Zero-cost API key); live 200 OK verified.",
    ),
    # NVIDIA NIM (Live verified active model)
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
        verified_at=1771680000.0,
        base_quality_score=0.86,
        entitlement_notes="NVIDIA free developer tier; live 200 OK verified.",
    ),
    # NVIDIA NIM (Deprecated EOL model)
    ModelCatalogEntry(
        model_id="z-ai/glm-5.2",
        provider_id=ProviderId.NVIDIA,
        family=ModelFamily.GLM,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=False,
        available=False,
        context_window=1_000_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.90,
        entitlement_notes="Retired by NVIDIA NIM backend on 2026-08-21T09:00:00Z (410 Gone).",
    ),
    # Cline API (Live verified zero-cost route: Minimax M2.5)
    ModelCatalogEntry(
        model_id="minimax/minimax-m2.5",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.MINIMAX,
        cost_tier=CostTier.FREE,
        pricing_verified_free=True,
        live_verified=True,          # Live verified 200 OK with cost: 0
        available=True,
        context_window=128_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.85,
        entitlement_notes="Zero-cost model on Cline API; verified cost: $0.00. Requires non-negative account balance.",
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
        live_verified=False,         # 403 on standalone usage-billing key; available via ClinePass surface
        available=False,
        context_window=64_000,
        supports_tools=True,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.88,
        entitlement_notes="Restricted to Cline product surfaces / ClinePass subscription key.",
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
        context_window=32_000,
        supports_tools=False,
        supports_json=True,
        verified_at=1771680000.0,
        base_quality_score=0.70,
        entitlement_notes="OpenRouter Free Router; live 200 OK verified.",
    ),
]


class ModelCatalog:
    def __init__(self, entries: Optional[List[ModelCatalogEntry]] = None):
        self._catalog: Dict[str, ModelCatalogEntry] = {}
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

    def get(self, model_id: str) -> Optional[ModelCatalogEntry]:
        return self._catalog.get(model_id)

    def list_models(
        self,
        provider_id: Optional[ProviderId] = None,
        available_only: bool = False,
    ) -> List[ModelCatalogEntry]:
        models = list(self._catalog.values())
        if provider_id:
            models = [m for m in models if m.provider_id == provider_id]
        if available_only:
            models = [m for m in models if m.available]
        return models

    def get_data_policy(self, provider_id: ProviderId) -> ProviderDataPolicy:
        return PROVIDER_DATA_POLICIES.get(
            provider_id,
            ProviderDataPolicy(
                provider_id=provider_id,
                trains_on_inputs=True,
                retains_prompts=True,
                allows_internal=False,
                allows_confidential=False,
            ),
        )
