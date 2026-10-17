"""
PAEOS Model Router — Multi-Stage Constraint Pipeline & Economy of Reasoning Policy
"""
from __future__ import annotations

import os

from paeos.model_router.aimd import AIMDController
from paeos.model_router.audit import select_heterogeneous_auditor
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.intelligence_tier import (
    ADMITTED_FREE_WORKER_POOL,
    catalogued_free_worker_pool,
)
from paeos.model_router.privacy import evaluate_privacy_eligibility
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    AdmissionState,
    CostTier,
    FailureScope,
    LogicalModel,
    ModelCatalogEntry,
    ModelFamily,
    ProviderHealth,
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

    def resolve_candidate_chain(self, request: TaskRequest) -> list[ModelCatalogEntry]:
        """
        Executes the ordered multi-stage constraint pipeline:
        1. Privacy Eligibility (Data Class vs Provider Policy)
        2. Explicit Physical Model Selection (if specified)
        3. Operational Availability & Admission Gate (Strict Fail-Closed)
        3b. Paid-Provider Guardrail (Strict Fail-Closed)
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
            try:
                eligible = evaluate_privacy_eligibility(request.data_class, policy)
            except ValueError:
                eligible = False
            if not eligible:
                continue
            candidates.append(model)

        # Step 2: Explicit Physical Model Selection (Guaranteed strict selection)
        if request.explicit_model:
            candidates = [m for m in candidates if m.model_id == request.explicit_model]
            if not candidates:
                return []

        if request.free_worker_pool:
            catalogued_free_ids = set(catalogued_free_worker_pool(self.catalog.list_models()))
            governed_free_ids = catalogued_free_ids & set(ADMITTED_FREE_WORKER_POOL)
            candidates = [
                m for m in candidates
                if m.model_id in governed_free_ids and m.cost_tier is CostTier.FREE
            ]

        # Step 3: Operational Availability & Admission Gate (Strict Fail-Closed)
        candidates = [
            m for m in candidates
            if m.available
            and m.admission_state == AdmissionState.ADMITTED
            and (not request.free_worker_pool or m.live_verified)
        ]
        if not candidates:
            return []

        # Step 3b: Paid-Provider Guardrail (Strict Fail-Closed)
        # Default autonomous routing strictly prefers FREE and SUBSCRIPTION_INCLUDED capacity.
        # Any PAID / PAY_PER_TOKEN provider requires explicit configured paid-budget authorization.
        paid_authorized = bool(
            getattr(request, "allow_paid_usage", False)
            or (request.metadata and request.metadata.get("paid_budget_authorized", False))
            or os.getenv("PAEOS_ALLOW_PAID_ROUTING", "").lower() in ("true", "1", "yes")
        )
        if not paid_authorized:
            candidates = [
                m for m in candidates
                if m.cost_tier in (CostTier.FREE, CostTier.SUBSCRIPTION_INCLUDED)
            ]
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
            if h not in (
                ProviderHealth.HEALTHY.value,
                ProviderHealth.THROTTLED.value,
                ProviderHealth.COOLDOWN.value,
            ):
                continue
            scoped = self.state_db.get_scoped_health(m.provider_id, FailureScope.MODEL, m.model_id)
            if scoped["health_status"] in {
                ProviderHealth.EXHAUSTED.value,
                ProviderHealth.QUARANTINED.value,
                ProviderHealth.UNAVAILABLE.value,
            }:
                continue
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
        candidates: list[ModelCatalogEntry],
        request: TaskRequest,
    ) -> list[ModelCatalogEntry]:
        filtered = []
        for m in candidates:
            descriptor = self.catalog.provider_registry.resolve(m.provider_id)
            _, _, rpd, _ = self.state_db.get_window_usage(m.provider_id)
            max_rpd = descriptor.max_rpd
            if max_rpd is not None:
                threshold = 0.70 if request.task_class is TaskClass.ROUTINE else 0.90
                if request.task_class in {
                    TaskClass.ROUTINE,
                    TaskClass.IMPLEMENTATION,
                    TaskClass.CODE_REVIEW,
                } and rpd >= int(max_rpd * threshold):
                    continue
            filtered.append(m)
        return filtered

    def _order_strong_tier(self, candidates: list[ModelCatalogEntry]) -> list[ModelCatalogEntry]:
        return sorted(
            candidates,
            key=lambda m: (
                self.catalog.provider_registry.resolve(m.provider_id).preference_rank.get(
                    LogicalModel.PAEOS_STRONG, 99
                ),
                -m.base_quality_score,
            ),
        )

    def _order_code_tier(self, candidates: list[ModelCatalogEntry]) -> list[ModelCatalogEntry]:
        return sorted(
            candidates,
            key=lambda m: (
                self.catalog.provider_registry.resolve(m.provider_id).preference_rank.get(
                    LogicalModel.PAEOS_CODE, 99
                ),
                -m.base_quality_score,
            ),
        )

    def _order_cheap_tier(self, candidates: list[ModelCatalogEntry]) -> list[ModelCatalogEntry]:
        return sorted(
            candidates,
            key=lambda m: self.catalog.provider_registry.resolve(m.provider_id).preference_rank.get(
                LogicalModel.PAEOS_CHEAP, 99
            ),
        )

    def _score_and_rank(
        self,
        candidates: list[ModelCatalogEntry],
        request: TaskRequest,
    ) -> list[ModelCatalogEntry]:
        def calculate_score(m: ModelCatalogEntry) -> float:
            st = self.state_db.get_provider_state(m.provider_id)
            health_mult = 1.0 if st["health_status"] == ProviderHealth.HEALTHY.value else 0.4
            descriptor = self.catalog.provider_registry.resolve(m.provider_id)
            task_fit = descriptor.task_fit.get(request.task_class, 1.0)
            quality = m.base_quality_score + descriptor.quality_bias
            latency_cost = 1.0 + descriptor.latency_bias
            cost_mult = 1.0 if m.cost_tier in (CostTier.FREE, CostTier.SUBSCRIPTION_INCLUDED) else 0.5
            return (task_fit * quality * health_mult * cost_mult) / latency_cost

        return sorted(candidates, key=calculate_score, reverse=True)
