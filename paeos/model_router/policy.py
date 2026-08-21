"""
PAEOS Model Router — Multi-Stage Constraint Pipeline & Economy of Reasoning Policy
"""
from __future__ import annotations

from typing import List, Optional

from paeos.model_router.aimd import AIMDController
from paeos.model_router.audit import select_heterogeneous_auditor
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.privacy import evaluate_privacy_eligibility
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    DataClass,
    LogicalModel,
    ModelCatalogEntry,
    ModelFamily,
    ProviderHealth,
    ProviderId,
    TaskClass,
    TaskRequest,
)


class RoutingPolicyEngine:
    def __init__(
        self,
        catalog: ModelCatalog,
        state_db: RouterStateDB,
        credentials: CredentialStore,
        aimd: AIMDController,
    ):
        self.catalog = catalog
        self.state_db = state_db
        self.credentials = credentials
        self.aimd = aimd

    def resolve_candidate_chain(self, request: TaskRequest) -> List[ModelCatalogEntry]:
        """
        Executes the ordered multi-stage constraint pipeline:
        1. Privacy Eligibility (Data Class vs Provider Policy)
        2. Explicit Physical Model Selection (if specified)
        3. Operational Availability Gate (Fails closed)
        4. Required Capabilities (Tools, JSON)
        5. Context Size Compatibility
        6. Credential Availability
        7. Provider Operational Health & Cooldowns
        8. Quota Reservations
        9. Economy of Reasoning Scoring
        """
        # Step 1: Filter by Privacy Gating
        candidates = []
        for model in self.catalog.list_models():
            policy = self.catalog.get_data_policy(model.provider_id)
            if not evaluate_privacy_eligibility(request.data_class, policy):
                continue
            candidates.append(model)

        # Step 2: Explicit Physical Model Selection (Guaranteed strict selection)
        if request.explicit_model:
            candidates = [m for m in candidates if m.model_id == request.explicit_model]
            if not candidates:
                return []

        # Step 3: Operational Availability Gate (Strict Fail-Closed)
        candidates = [m for m in candidates if m.available]
        if not candidates:
            return []

        # Step 4: Filter by Required Capabilities
        if request.require_tools:
            candidates = [m for m in candidates if m.supports_tools]
        if request.require_json:
            candidates = [m for m in candidates if m.supports_json]

        # Step 5: Filter by Context Size Compatibility
        est_tokens = self._estimate_request_tokens(request)
        candidates = [m for m in candidates if m.context_window >= est_tokens]

        # Step 6: Filter by Credential Availability
        candidates = [m for m in candidates if self.credentials.has_key(m.provider_id)]

        # Step 7: Filter by Health (Remove QUARANTINED / EXHAUSTED / UNAVAILABLE)
        healthy_candidates = []
        for m in candidates:
            st = self.state_db.get_provider_state(m.provider_id)
            h = st["health_status"]
            if h in (ProviderHealth.HEALTHY.value, ProviderHealth.THROTTLED.value, ProviderHealth.COOLDOWN.value):
                healthy_candidates.append(m)
        candidates = healthy_candidates

        # Step 8: Apply Quota Reservation Gates
        candidates = self._filter_quota_reservations(candidates, request)

        # If explicit model requested, return immediately after eligibility verification
        if request.explicit_model and candidates:
            return candidates

        # Step 9: Handle Special Logical Model Classes
        if request.logical_model == LogicalModel.PAEOS_AUDIT:
            builder_fam = request.builder_family or ModelFamily.DEEPSEEK
            auditor = select_heterogeneous_auditor(
                builder_family=builder_fam,
                catalog=self.catalog,
                available_providers=[m.provider_id for m in candidates],
            )
            if auditor:
                return [auditor] + [m for m in candidates if m.family != builder_fam]
            return [m for m in candidates if m.family != builder_fam]

        # Step 10: Order by Logical Tier or Economy of Reasoning Score
        if request.logical_model == LogicalModel.PAEOS_STRONG:
            return self._order_strong_tier(candidates)
        elif request.logical_model == LogicalModel.PAEOS_CODE:
            return self._order_code_tier(candidates)
        elif request.logical_model == LogicalModel.PAEOS_CHEAP:
            return self._order_cheap_tier(candidates)

        return self._score_and_rank(candidates, request)

    def _estimate_request_tokens(self, request: TaskRequest) -> int:
        char_count = sum(len(str(m.get("content", ""))) for m in request.messages)
        return (char_count // 4) + (request.max_tokens or 1000)

    def _filter_quota_reservations(
        self,
        candidates: List[ModelCatalogEntry],
        request: TaskRequest,
    ) -> List[ModelCatalogEntry]:
        filtered = []
        for m in candidates:
            if m.provider_id == ProviderId.GOOGLE:
                rpm, _, rpd, _ = self.state_db.get_window_usage(ProviderId.GOOGLE)
                limits = self.aimd.limits.get(ProviderId.GOOGLE, {})
                max_rpd = limits.get("max_rpd", 1200)

                if request.task_class == TaskClass.ROUTINE and rpd >= int(max_rpd * 0.70):
                    continue
                if request.task_class in (TaskClass.IMPLEMENTATION, TaskClass.CODE_REVIEW) and rpd >= int(max_rpd * 0.90):
                    continue
            filtered.append(m)
        return filtered

    def _order_strong_tier(self, candidates: List[ModelCatalogEntry]) -> List[ModelCatalogEntry]:
        pref_order = [ProviderId.GOOGLE, ProviderId.NVIDIA, ProviderId.CLINE, ProviderId.KILO, ProviderId.OPENROUTER]
        return sorted(candidates, key=lambda m: (pref_order.index(m.provider_id) if m.provider_id in pref_order else 99, -m.base_quality_score))

    def _order_code_tier(self, candidates: List[ModelCatalogEntry]) -> List[ModelCatalogEntry]:
        pref_order = [ProviderId.CLINE, ProviderId.OPENROUTER, ProviderId.KILO, ProviderId.GOOGLE, ProviderId.NVIDIA]
        return sorted(candidates, key=lambda m: (pref_order.index(m.provider_id) if m.provider_id in pref_order else 99, -m.base_quality_score))

    def _order_cheap_tier(self, candidates: List[ModelCatalogEntry]) -> List[ModelCatalogEntry]:
        pref_order = [ProviderId.KILO, ProviderId.OPENROUTER, ProviderId.CLINE, ProviderId.NVIDIA, ProviderId.GOOGLE]
        return sorted(candidates, key=lambda m: (pref_order.index(m.provider_id) if m.provider_id in pref_order else 99))

    def _score_and_rank(
        self,
        candidates: List[ModelCatalogEntry],
        request: TaskRequest,
    ) -> List[ModelCatalogEntry]:
        def calculate_score(m: ModelCatalogEntry) -> float:
            st = self.state_db.get_provider_state(m.provider_id)
            health_mult = 1.0 if st["health_status"] == ProviderHealth.HEALTHY.value else 0.4

            task_fit = 1.0
            if request.task_class == TaskClass.ARCHITECTURE and m.family in (ModelFamily.GEMINI, ModelFamily.GLM):
                task_fit = 1.5
            elif request.task_class == TaskClass.IMPLEMENTATION and m.family in (ModelFamily.DEEPSEEK, ModelFamily.MINIMAX, ModelFamily.LAGUNA, ModelFamily.LLAMA):
                task_fit = 1.4
            elif request.task_class == TaskClass.ROUTINE:
                task_fit = 1.2 if m.provider_id in (ProviderId.KILO, ProviderId.OPENROUTER) else 0.8

            opp_cost = 1.0
            if m.provider_id == ProviderId.GOOGLE:
                opp_cost = 2.5
            elif m.provider_id == ProviderId.NVIDIA:
                opp_cost = 1.5
            elif m.provider_id in (ProviderId.KILO, ProviderId.OPENROUTER):
                opp_cost = 0.5

            return (task_fit * m.base_quality_score * health_mult) / opp_cost

        return sorted(candidates, key=calculate_score, reverse=True)
