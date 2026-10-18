"""Model-router transport dispatcher.

Provider wire behavior lives in :mod:`provider_transports`; this module only resolves credentials
and delegates one request to the explicitly registered adapter.
"""

from __future__ import annotations

from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.errors import normalize_error
from paeos.model_router.provider_transports import (
    PROVIDER_API_BASES,
    ProviderTransportRegistry,
    build_builtin_transport_registry,
    litellm,  # noqa: F401 - compatibility patch point
)
from paeos.model_router.types import (
    ModelCatalogEntry,
    NormalizedError,
    NormalizedErrorType,
    RouterResponse,
    TaskRequest,
)

__all__ = ["PROVIDER_API_BASES", "LiteLLMTransport"]


class LiteLLMTransport:
    """Credential-aware dispatcher with no provider-specific wire branches."""

    def __init__(
        self,
        credentials: CredentialStore,
        catalog: ModelCatalog | None = None,
        registry: ProviderTransportRegistry | None = None,
    ) -> None:
        self.credentials = credentials
        self.catalog = catalog or ModelCatalog()
        self.registry = registry or build_builtin_transport_registry(self.catalog)

    def dispatch(
        self,
        model_entry: ModelCatalogEntry,
        request: TaskRequest,
        timeout: float = 60.0,
    ) -> RouterResponse:
        api_key = self.credentials.get_key(model_entry.provider_id)
        if not api_key:
            raise NormalizedError(
                error_type=NormalizedErrorType.AUTH_FAILED,
                message=f"Missing API key for provider {model_entry.provider_id.value}",
                provider_id=model_entry.provider_id,
                model_id=model_entry.model_id,
            )
        try:
            adapter = self.registry.resolve_for_provider(model_entry.provider_id)
            return adapter.dispatch(
                model_entry,
                request,
                api_key=api_key,
                timeout=timeout,
            )
        except NormalizedError:
            raise
        except (KeyError, ValueError) as exc:
            raise normalize_error(
                http_status=500,
                body=str(exc),
                provider_id=model_entry.provider_id,
                model_id=model_entry.model_id,
            ) from exc
