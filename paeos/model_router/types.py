"""
PAEOS Model Router & Free Inference Mesh — Type Definitions
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DataClass(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"


class TaskClass(StrEnum):
    ARCHITECTURE = "ARCHITECTURE"
    IMPLEMENTATION = "IMPLEMENTATION"
    CODE_REVIEW = "CODE_REVIEW"
    ROUTINE = "ROUTINE"
    LONG_CONTEXT = "LONG_CONTEXT"
    AUDIT = "AUDIT"


class LogicalModel(StrEnum):
    PAEOS_AUTO = "paeos-auto"
    PAEOS_STRONG = "paeos-strong"
    PAEOS_CODE = "paeos-code"
    PAEOS_CHEAP = "paeos-cheap"
    PAEOS_AUDIT = "paeos-audit"


class ProviderId(StrEnum):
    GOOGLE = "google"
    CLINE = "cline"
    NVIDIA = "nvidia"
    KILO = "kilo"
    OPENROUTER = "openrouter"


# Canonical provider identity is an extensible validated string; ProviderId remains a
# compatibility enum for existing callers.
ProviderKey = str


class CostTier(StrEnum):
    FREE = "FREE"                                    # Zero monetary entitlement required
    SUBSCRIPTION_INCLUDED = "SUBSCRIPTION_INCLUDED"  # Already-paid subscription ($0 marginal inference cost)
    PAID_USAGE = "PAID_USAGE"                        # Consumes pay-as-you-go monetary credits


class ModelFamily(StrEnum):
    GEMINI = "gemini"
    GLM = "glm"
    LLAMA = "llama"
    DEEPSEEK = "deepseek"
    MINIMAX = "minimax"
    LAGUNA = "laguna"
    HY3 = "hy3"
    NEMOTRON = "nemotron"
    GPT = "gpt"
    QWEN = "qwen"
    UNKNOWN = "unknown"


class NormalizedErrorType(StrEnum):
    CONTEXT_EXCEEDED = "CONTEXT_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    AUTH_FAILED = "AUTH_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    BAD_REQUEST = "BAD_REQUEST"
    CONTENT_POLICY = "CONTENT_POLICY"
    TIMEOUT = "TIMEOUT"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class RetryPolicy(StrEnum):
    NONE = "none"
    SINGLE_RATE_LIMIT = "single-rate-limit"


class ProviderHealth(StrEnum):
    HEALTHY = "HEALTHY"
    THROTTLED = "THROTTLED"
    COOLDOWN = "COOLDOWN"
    EXHAUSTED = "EXHAUSTED"
    UNAVAILABLE = "UNAVAILABLE"
    QUARANTINED = "QUARANTINED"
    UNRESOLVED_ENTITLEMENT = "UNRESOLVED_ENTITLEMENT"


@dataclass
class ProviderDataPolicy:
    provider_id: ProviderId
    trains_on_inputs: bool = False
    retains_prompts: bool = False
    allows_internal: bool = True
    allows_confidential: bool = True


@dataclass
class ModelCatalogEntry:
    model_id: str
    provider_id: ProviderId
    family: ModelFamily
    cost_tier: CostTier = CostTier.FREE
    pricing_verified_free: bool = True      # Documented zero-cost or subscription-included pricing
    live_verified: bool = False             # Empirically verified via successful live probe
    available: bool = True                  # Admitted into operational routing
    context_window: int = 32_000
    supports_tools: bool = True
    supports_json: bool = True
    verified_at: float = 0.0
    base_quality_score: float = 0.5
    entitlement_notes: str | None = None


@dataclass
class TaskRequest:
    messages: list[dict[str, Any]]
    task_class: TaskClass = TaskClass.ROUTINE
    data_class: DataClass = DataClass.INTERNAL
    logical_model: LogicalModel | None = None
    explicit_model: str | None = None
    builder_family: ModelFamily | None = None
    require_tools: bool = False
    require_json: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    stream: bool = False
    max_tokens: int | None = None
    temperature: float = 0.7
    metadata: dict[str, Any] = field(default_factory=dict)
    retry_policy: RetryPolicy = RetryPolicy.SINGLE_RATE_LIMIT
    allow_fallback: bool = True


@dataclass
class NormalizedError(Exception):
    error_type: NormalizedErrorType
    message: str
    provider_id: ProviderId | None = None
    model_id: str | None = None
    http_status: int | None = None
    retry_after: float | None = None
    raw_response: str | None = None

    def __str__(self) -> str:
        return f"[{self.error_type.value}] Provider={self.provider_id} HTTP={self.http_status} RetryAfter={self.retry_after}: {self.message}"


@dataclass
class RouterResponse:
    content: str
    model_id: str                          # Catalog/model_id used for routing
    provider_id: ProviderId
    family: ModelFamily                    # Family from catalog entry
    actual_model: str | None = None      # Actual upstream model returned by provider (for dynamic routes)
    actual_family: ModelFamily | None = None  # Actual family derived from actual_model
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    attempts: int = 1
    fallback_chain: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str = "stop"
    raw_response: Any = None
    # Content-free hashes captured at the transport boundary.  These are optional for
    # backwards-compatible diagnostic responses, but required by Task 9A physical receipts.
    transport_request_sha256: str | None = None
    transport_response_sha256: str | None = None
