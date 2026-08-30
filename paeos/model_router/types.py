"""
PAEOS Model Router & Free Inference Mesh — Type Definitions
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DataClass(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"


class TaskClass(str, Enum):
    ARCHITECTURE = "ARCHITECTURE"
    IMPLEMENTATION = "IMPLEMENTATION"
    CODE_REVIEW = "CODE_REVIEW"
    ROUTINE = "ROUTINE"
    LONG_CONTEXT = "LONG_CONTEXT"
    AUDIT = "AUDIT"


class LogicalModel(str, Enum):
    PAEOS_AUTO = "paeos-auto"
    PAEOS_STRONG = "paeos-strong"
    PAEOS_CODE = "paeos-code"
    PAEOS_CHEAP = "paeos-cheap"
    PAEOS_AUDIT = "paeos-audit"


class ProviderId(str, Enum):
    GOOGLE = "google"
    CLINE = "cline"
    NVIDIA = "nvidia"
    KILO = "kilo"
    OPENROUTER = "openrouter"


class CostTier(str, Enum):
    FREE = "FREE"                                    # Zero monetary entitlement required
    SUBSCRIPTION_INCLUDED = "SUBSCRIPTION_INCLUDED"  # Already-paid subscription ($0 marginal inference cost)
    PAID_USAGE = "PAID_USAGE"                        # Consumes pay-as-you-go monetary credits


class ModelFamily(str, Enum):
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


class NormalizedErrorType(str, Enum):
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


class ProviderHealth(str, Enum):
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
    entitlement_notes: Optional[str] = None


@dataclass
class TaskRequest:
    messages: List[Dict[str, Any]]
    task_class: TaskClass = TaskClass.ROUTINE
    data_class: DataClass = DataClass.INTERNAL
    logical_model: Optional[LogicalModel] = None
    explicit_model: Optional[str] = None
    builder_family: Optional[ModelFamily] = None
    require_tools: bool = False
    require_json: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    stream: bool = False
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedError(Exception):
    error_type: NormalizedErrorType
    message: str
    provider_id: Optional[ProviderId] = None
    model_id: Optional[str] = None
    http_status: Optional[int] = None
    retry_after: Optional[float] = None
    raw_response: Optional[str] = None

    def __str__(self) -> str:
        return f"[{self.error_type.value}] Provider={self.provider_id} HTTP={self.http_status} RetryAfter={self.retry_after}: {self.message}"


@dataclass
class RouterResponse:
    content: str
    model_id: str                          # Catalog/model_id used for routing
    provider_id: ProviderId
    family: ModelFamily                    # Family from catalog entry
    actual_model: Optional[str] = None      # Actual upstream model returned by provider (for dynamic routes)
    actual_family: Optional[ModelFamily] = None  # Actual family derived from actual_model
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    attempts: int = 1
    fallback_chain: List[str] = field(default_factory=list)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str = "stop"
    raw_response: Any = None
    # Content-free hashes captured at the transport boundary.  These are optional for
    # backwards-compatible diagnostic responses, but required by Task 9A physical receipts.
    transport_request_sha256: Optional[str] = None
    transport_response_sha256: Optional[str] = None
