"""
PAEOS Model Router — Deterministic AIMD Rate & Admission Controller
"""
from __future__ import annotations

import math
import time

from paeos.model_router.providers import ProviderRegistry, build_builtin_provider_registry
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    FailureScope,
    NormalizedError,
    NormalizedErrorType,
    ProviderHealth,
    ProviderId,
)

# Configurable safety ceilings (fallback defaults, not immutable provider limits)
DEFAULT_PUBLISHED_LIMITS: dict[ProviderId, dict[str, int]] = {
    ProviderId.GOOGLE: {
        "max_rpm": 12,       # Conservative 80% default for standard tier
        "max_tpm": 800_000,
        "max_rpd": 1200,
    },
    ProviderId.OPENROUTER: {
        "max_rpm": 20,
        "max_tpm": 200_000,
        "max_rpd": 50,       # Strict 50 free req/day allowance
    },
}


class AIMDController:
    def __init__(
        self,
        state_db: RouterStateDB,
        custom_limits: dict[ProviderId, dict[str, int]] | None = None,
        provider_registry: ProviderRegistry | None = None,
    ):
        self.state_db = state_db
        self.provider_registry = provider_registry or build_builtin_provider_registry()
        self.limits = custom_limits or DEFAULT_PUBLISHED_LIMITS

    def limits_for(self, provider_id: ProviderId) -> dict[str, int]:
        """Resolve rate ceilings from descriptor facts with legacy fallback."""

        configured = self.limits.get(provider_id)
        if configured is not None:
            return configured
        descriptor = self.provider_registry.resolve(provider_id)
        return {
            field_name: value
            for field_name, value in (
                ("max_rpm", descriptor.max_rpm),
                ("max_tpm", descriptor.max_tpm),
                ("max_rpd", descriptor.max_rpd),
            )
            if value is not None
        }

    def check_admission(
        self,
        provider_id: ProviderId,
        estimated_tokens: int = 2000,
        *,
        model_id: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Multidimensional admission check: (Concurrency) AND (RPM < Target) AND (TPM < Target) AND (RPD < Target)
        """
        state = self.state_db.get_provider_state(provider_id)
        health = state["health_status"]

        # 1. Health check & Cooldown recovery
        now = time.time()
        cooldown_until = state["cooldown_until"]
        if health == ProviderHealth.COOLDOWN.value:
            if cooldown_until and now >= cooldown_until:
                # Recover conservatively at concurrency=1
                self.state_db.set_health(provider_id, ProviderHealth.HEALTHY)
                self.state_db.update_concurrency(provider_id, 1)
                health = ProviderHealth.HEALTHY.value
            else:
                remaining = max(0.0, (cooldown_until - now) if cooldown_until else 0.0)
                return False, f"Provider {provider_id.value} in COOLDOWN ({remaining:.1f}s remaining)"

        if health in (ProviderHealth.EXHAUSTED.value, ProviderHealth.QUARANTINED.value, ProviderHealth.UNAVAILABLE.value):
            return False, f"Provider {provider_id.value} is {health}"

        if model_id:
            scoped = self.state_db.get_scoped_health(provider_id, FailureScope.MODEL, model_id)
            if scoped["health_status"] in (
                ProviderHealth.EXHAUSTED.value,
                ProviderHealth.QUARANTINED.value,
                ProviderHealth.UNAVAILABLE.value,
            ):
                return False, f"Model {model_id} is {scoped['health_status']}"

        # 2. Concurrency Limit Check
        current_limit = state["current_concurrency"]
        active = state["active_requests"]
        if active >= current_limit:
            return False, f"Concurrency limit reached ({active}/{current_limit})"

        # 3. Dynamic Ceiling Check
        limits = self.limits_for(provider_id)
        if limits:
            rpm, tpm, rpd, _ = self.state_db.get_window_usage(provider_id)
            if limits.get("max_rpm") and rpm >= limits["max_rpm"]:
                return False, f"RPM safety ceiling reached ({rpm}/{limits['max_rpm']})"
            if limits.get("max_tpm") and (tpm + estimated_tokens) >= limits["max_tpm"]:
                return False, f"TPM safety ceiling reached ({tpm + estimated_tokens}/{limits['max_tpm']})"
            if limits.get("max_rpd") and rpd >= limits["max_rpd"]:
                self.state_db.set_health(provider_id, ProviderHealth.EXHAUSTED)
                return False, f"RPD allowance exhausted ({rpd}/{limits['max_rpd']})"

        return True, None

    def on_success(self, provider_id: ProviderId, latency_ms: float) -> None:
        """
        Additive Increase (+1): Increment concurrency after 60s of healthy operation
        with 0 429s and error rate < 1%.
        """
        state = self.state_db.get_provider_state(provider_id)
        now = time.time()
        healthy_since = state["consecutive_healthy_since"] or now

        # Ensure state is HEALTHY
        if state["health_status"] != ProviderHealth.HEALTHY.value:
            self.state_db.set_health(provider_id, ProviderHealth.HEALTHY)

        if (now - healthy_since) >= 60.0:
            metrics = self.state_db.get_recent_metrics(provider_id, window_seconds=60.0)
            if metrics["recent_429_rate"] == 0.0 and metrics["error_rate"] < 0.01:
                current = state["current_concurrency"]
                max_c = state["max_concurrency"]
                if current < max_c:
                    new_c = current + 1
                    self.state_db.update_concurrency(provider_id, new_c)
                    self.state_db.set_health(provider_id, ProviderHealth.HEALTHY)

    def on_rate_limit(self, provider_id: ProviderId, error: NormalizedError) -> float:
        """
        Multiplicative Decrease (x0.5): Halve concurrency on 429, enforce cooldown.
        Returns cooldown duration in seconds.
        """
        state = self.state_db.get_provider_state(provider_id)
        current = state["current_concurrency"]
        new_c = max(1, math.floor(current * 0.5))

        cooldown = error.retry_after if (error.retry_after and error.retry_after > 0) else 30.0

        self.state_db.update_concurrency(provider_id, new_c)
        self.state_db.set_health(
            provider_id=provider_id,
            health=ProviderHealth.COOLDOWN,
            error_type=NormalizedErrorType.RATE_LIMITED,
            cooldown_seconds=cooldown,
        )
        return cooldown

    def on_error(self, provider_id: ProviderId, error: NormalizedError) -> None:
        """Handle other non-429 errors."""
        if error.error_type == NormalizedErrorType.AUTH_FAILED:
            self.state_db.set_health(provider_id, ProviderHealth.QUARANTINED, error_type=error.error_type)
        elif error.error_type == NormalizedErrorType.QUOTA_EXHAUSTED:
            # Only model-scoped observations are safe to narrow. An entitlement key may
            # represent a shared account/quota domain that is not model-addressable here;
            # keep it provider-wide until a separately governed entitlement map exists.
            if error.failure_scope is FailureScope.MODEL and error.scope_key:
                self.state_db.set_scoped_health(
                    provider_id,
                    FailureScope.MODEL,
                    error.scope_key,
                    ProviderHealth.EXHAUSTED,
                    error_type=error.error_type,
                )
            else:
                self.state_db.set_health(provider_id, ProviderHealth.EXHAUSTED, error_type=error.error_type)
        elif error.error_type == NormalizedErrorType.PROVIDER_UNAVAILABLE:
            self.state_db.set_health(
                provider_id, ProviderHealth.COOLDOWN, error_type=error.error_type, cooldown_seconds=error.retry_after or 60.0
            )
