"""Predictive Quota Tracker & Economy of Reasoning Governor.

Implements:
- SCO-033: Dynamic token budget and predictive quota management.
- SCO-034: Graceful pre-429 state checkpointing recommendation before API crash.
- SCO-035: Economy of Reasoning: match task complexity to model capability tier.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum


class RecommendedQuotaAction(StrEnum):
    PROCEED = "PROCEED"
    THROTTLE = "THROTTLE"
    CHECKPOINT_AND_SUSPEND = "CHECKPOINT_AND_SUSPEND"


@dataclass(frozen=True, slots=True)
class QuotaStatus:
    """Predictive quota status for a provider/model pair."""

    provider_id: str
    model_id: str
    utilization_ratio: float
    pre_429_warning: bool
    recommended_action: RecommendedQuotaAction
    detail: str


class QuotaTracker:
    """Predictive quota monitor tracking usage velocity to prevent 429 exhaustion."""

    def __init__(self, high_watermark_ratio: float = 0.85) -> None:
        self.high_watermark_ratio = high_watermark_ratio
        self._usage_window: dict[str, list[tuple[float, int]]] = {}  # key -> [(timestamp, tokens)]

    def record_usage(self, provider_id: str, model_id: str, tokens: int) -> None:
        key = f"{provider_id}:{model_id}"
        now = time.time()
        if key not in self._usage_window:
            self._usage_window[key] = []
        self._usage_window[key].append((now, tokens))

    def evaluate_quota(
        self,
        provider_id: str,
        model_id: str,
        estimated_tokens: int,
        rpm_ceiling: int = 60,
        tpm_ceiling: int = 100_000,
    ) -> QuotaStatus:
        key = f"{provider_id}:{model_id}"
        now = time.time()
        records = self._usage_window.get(key, [])
        # Filter window to last 60 seconds
        recent = [r for r in records if now - r[0] < 60.0]
        self._usage_window[key] = recent

        current_rpm = len(recent)
        current_tpm = sum(r[1] for r in recent) + estimated_tokens

        rpm_ratio = current_rpm / max(1, rpm_ceiling)
        tpm_ratio = current_tpm / max(1, tpm_ceiling)
        max_ratio = max(rpm_ratio, tpm_ratio)

        if max_ratio >= 0.95:
            return QuotaStatus(
                provider_id=provider_id,
                model_id=model_id,
                utilization_ratio=max_ratio,
                pre_429_warning=True,
                recommended_action=RecommendedQuotaAction.CHECKPOINT_AND_SUSPEND,
                detail=f"Exhaustion threshold imminent ({max_ratio * 100:.1f}%). Checkpoint and suspend task.",
            )
        elif max_ratio >= self.high_watermark_ratio:
            return QuotaStatus(
                provider_id=provider_id,
                model_id=model_id,
                utilization_ratio=max_ratio,
                pre_429_warning=True,
                recommended_action=RecommendedQuotaAction.THROTTLE,
                detail=f"High utilization warning ({max_ratio * 100:.1f}%). Throttle dispatch.",
            )
        else:
            return QuotaStatus(
                provider_id=provider_id,
                model_id=model_id,
                utilization_ratio=max_ratio,
                pre_429_warning=False,
                recommended_action=RecommendedQuotaAction.PROCEED,
                detail=f"Quota headroom nominal ({max_ratio * 100:.1f}%).",
            )


class EconomyOfReasoningGovernor:
    """Matches task criticality to model capability tier (SCO-035).

    Preserves scarce frontier model reasoning quotas for architectural design,
    adversarial review, and kernel-touching tasks.
    """

    @staticmethod
    def select_model_tier(task_criticality: str) -> str:
        crit = task_criticality.upper()
        if crit in ("ROUTINE", "LOW", "MAINTENANCE"):
            return "FAST_TIER"  # Free worker pool / light models
        elif crit in ("SUBSTANTIAL", "MEDIUM"):
            return "BALANCED_TIER"
        elif crit in ("KERNEL_TOUCHING", "CRITICAL", "CONSTITUTIONAL"):
            return "FRONTIER_TIER"  # High reasoning models
        return "BALANCED_TIER"
