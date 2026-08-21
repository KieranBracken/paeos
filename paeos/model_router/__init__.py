"""
PAEOS Model Router & Free Inference Mesh Subsystem
"""
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.observability import ObservabilityDiagnostics
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
    RouterResponse,
    TaskClass,
    TaskRequest,
)

__all__ = [
    "ModelRouter",
    "ModelCatalog",
    "CredentialStore",
    "RouterStateDB",
    "ObservabilityDiagnostics",
    "run_gateway_server",
    "TaskRequest",
    "RouterResponse",
    "DataClass",
    "TaskClass",
    "LogicalModel",
    "ProviderId",
    "ModelFamily",
    "NormalizedError",
    "NormalizedErrorType",
    "ProviderHealth",
]
