"""
PAEOS Model Router & Free Inference Mesh Subsystem
"""
from paeos.model_router.audit_prompt import (
    AuditorPromptError,
    build_substantive_audit_prompt,
    validate_substantive_audit_prompt,
)
from paeos.model_router.auditor_receipt import (
    AUDITOR_RECEIPT_SCHEMA,
    AuditorCaptureResult,
    AuditorReceiptContract,
    AuditorReceiptError,
    PhysicalAuditorReceipt,
    capture_auditor_receipt,
    load_auditor_receipt,
    persist_auditor_receipt,
    persist_auditor_report,
    request_fingerprint,
    response_fingerprint,
    validate_auditor_receipt,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.observability import ObservabilityDiagnostics
from paeos.model_router.provider_transports import (
    ClineEnvelopeTransport,
    OpenAICompatibleConfig,
    OpenAICompatibleTransport,
    ProviderTransportRegistry,
    build_builtin_transport_registry,
)
from paeos.model_router.providers import (
    ProviderDescriptor,
    ProviderRegistry,
    normalize_provider_key,
)
from paeos.model_router.router import ModelRouter
from paeos.model_router.server import run_gateway_server
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    DataClass,
    LogicalModel,
    ModelCatalogEntry,
    ModelFamily,
    NormalizedError,
    NormalizedErrorType,
    ProviderHealth,
    ProviderId,
    RetryPolicy,
    RouterResponse,
    TaskClass,
    TaskRequest,
)

__all__ = [
    "AUDITOR_RECEIPT_SCHEMA",
    "AuditorCaptureResult",
    "AuditorPromptError",
    "AuditorReceiptContract",
    "AuditorReceiptError",
    "ClineEnvelopeTransport",
    "CredentialStore",
    "DataClass",
    "LogicalModel",
    "ModelCatalog",
    "ModelCatalogEntry",
    "ModelFamily",
    "ModelRouter",
    "NormalizedError",
    "NormalizedErrorType",
    "ObservabilityDiagnostics",
    "OpenAICompatibleConfig",
    "OpenAICompatibleTransport",
    "PhysicalAuditorReceipt",
    "ProviderDescriptor",
    "ProviderHealth",
    "ProviderId",
    "ProviderRegistry",
    "ProviderTransportRegistry",
    "RetryPolicy",
    "RouterResponse",
    "RouterStateDB",
    "TaskClass",
    "TaskRequest",
    "build_builtin_transport_registry",
    "build_substantive_audit_prompt",
    "capture_auditor_receipt",
    "load_auditor_receipt",
    "normalize_provider_key",
    "persist_auditor_receipt",
    "persist_auditor_report",
    "request_fingerprint",
    "response_fingerprint",
    "run_gateway_server",
    "validate_auditor_receipt",
    "validate_substantive_audit_prompt",
]
