"""Provider wire adapters used by the model router.

The router supplies a catalog entry and an API key; this module owns provider wire details.  All
adapters are registered explicitly at trusted startup, so a writable directory cannot inject a
transport implementation.
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

import litellm  # type: ignore[reportMissingImports]  # optional gateway dependency
import requests
from paeos.model_router.a08_enforcer import derive_family_from_actual_model
from paeos.model_router.auditor_receipt import request_fingerprint, response_fingerprint
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.errors import normalize_error
from paeos.model_router.providers import normalize_provider_key
from paeos.model_router.types import (
    DataClass,
    ModelCatalogEntry,
    NormalizedError,
    ProviderId,
    RouterResponse,
    TaskRequest,
)

litellm.num_retries = 0
litellm.telemetry = False
litellm.drop_params = True

PROVIDER_API_BASES: Mapping[ProviderId, str] = MappingProxyType(
    {
        ProviderId.GOOGLE: "https://generativelanguage.googleapis.com/v1beta/openai/",
        ProviderId.CLINE: "https://api.cline.bot/api/v1",
        ProviderId.NVIDIA: "https://integrate.api.nvidia.com/v1",
        ProviderId.KILO: "https://api.kilo.ai/api/gateway",
        ProviderId.OPENROUTER: "https://openrouter.ai/api/v1",
    }
)

_ADAPTER_KEY = re.compile(r"^[a-z][a-z0-9-]{0,62}$")


class ProviderTransport(Protocol):
    def dispatch(
        self,
        model_entry: ModelCatalogEntry,
        request: TaskRequest,
        *,
        api_key: str,
        timeout: float,
    ) -> RouterResponse: ...


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    api_base: str
    extra_headers: Mapping[str, str]
    single_tool_call_only: bool
    confidential_zdr: bool

    def __post_init__(self) -> None:
        if not isinstance(self.api_base, str) or not self.api_base.startswith(("http://", "https://")):
            raise ValueError("api_base must be an absolute HTTP(S) URL")
        if not isinstance(self.single_tool_call_only, bool) or not isinstance(
            self.confidential_zdr, bool
        ):
            raise TypeError("transport feature flags must be booleans")
        headers = dict(self.extra_headers)
        for name, value in headers.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(value, str):
                raise TypeError("extra_headers must map non-empty names to strings")
            if name.casefold() == "authorization" or value.casefold().startswith("bearer "):
                raise ValueError("extra_headers must not contain credentials")
        object.__setattr__(self, "extra_headers", MappingProxyType(headers))


class OpenAICompatibleTransport:
    def __init__(self, config: OpenAICompatibleConfig, catalog: ModelCatalog) -> None:
        self._config = config
        self._catalog = catalog

    def dispatch(
        self,
        model_entry: ModelCatalogEntry,
        request: TaskRequest,
        *,
        api_key: str,
        timeout: float,
    ) -> RouterResponse:
        cleaned_messages = request.messages
        if self._config.single_tool_call_only:
            cleaned_messages = []
            for message in request.messages:
                tool_calls = message.get("tool_calls")
                if (
                    message.get("role") == "assistant"
                    and isinstance(tool_calls, list)
                    and len(tool_calls) > 1
                ):
                    copied = dict(message)
                    copied["tool_calls"] = [tool_calls[0]]
                    cleaned_messages.append(copied)
                else:
                    cleaned_messages.append(message)

        kwargs: dict[str, Any] = {
            "model": f"openai/{model_entry.model_id}",
            "messages": cleaned_messages,
            "api_base": self._config.api_base,
            "api_key": api_key,
            "timeout": timeout,
            "num_retries": 0,
        }
        if self._config.extra_headers:
            kwargs["extra_headers"] = dict(self._config.extra_headers)
        if request.max_tokens:
            kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.tools:
            kwargs["tools"] = request.tools
        if request.tool_choice:
            kwargs["tool_choice"] = request.tool_choice
        if self._config.confidential_zdr and request.data_class is DataClass.CONFIDENTIAL:
            kwargs["extra_body"] = {"provider": {"data_collection": "deny", "zdr": True}}

        start_time = time.time()
        try:
            response = litellm.completion(**kwargs)
            choice = response.choices[0]
            message = getattr(choice, "message", None)
            if message is None:
                raise ValueError("provider response choice has no message")
            content = getattr(message, "content", None) or ""
            if not content:
                content = getattr(message, "reasoning", None) or getattr(
                    message, "reasoning_content", ""
                )
            tool_calls = _tool_calls(message)
            finish_reason = getattr(choice, "finish_reason", "stop") or (
                "tool_calls" if tool_calls else "stop"
            )
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            actual_model = getattr(response, "model", None) or model_entry.model_id
            result = RouterResponse(
                content=content,
                model_id=model_entry.model_id,
                actual_model=actual_model,
                provider_id=model_entry.provider_id,
                family=model_entry.family,
                actual_family=derive_family_from_actual_model(actual_model, self._catalog),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=(time.time() - start_time) * 1000.0,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                raw_response=response,
            )
            result.transport_request_sha256 = request_fingerprint(request)
            result.transport_response_sha256 = response_fingerprint(result)
            return result
        except Exception as exc:
            raise _normalized_error(exc, model_entry) from exc


class ClineEnvelopeTransport:
    def __init__(self, api_base: str, catalog: ModelCatalog) -> None:
        if not api_base.startswith(("http://", "https://")):
            raise ValueError("api_base must be an absolute HTTP(S) URL")
        self._api_base = api_base
        self._catalog = catalog

    def dispatch(
        self,
        model_entry: ModelCatalogEntry,
        request: TaskRequest,
        *,
        api_key: str,
        timeout: float,
    ) -> RouterResponse:
        payload: dict[str, Any] = {
            "model": model_entry.model_id,
            "messages": request.messages,
            "temperature": request.temperature if request.temperature is not None else 0.7,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = request.tools
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        start_time = time.time()
        try:
            response = requests.post(
                f"{self._api_base.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            latency_ms = (time.time() - start_time) * 1000.0
            if response.status_code != 200:
                raise normalize_error(
                    http_status=response.status_code,
                    body=response.text,
                    headers=dict(response.headers),
                    provider_id=ProviderId.CLINE,
                    model_id=model_entry.model_id,
                )
            raw = response.json()
            envelope = raw.get("data", raw)
            choices = envelope.get("choices", [])
            if not choices:
                raise normalize_error(
                    http_status=500,
                    body=raw,
                    provider_id=ProviderId.CLINE,
                    model_id=model_entry.model_id,
                )
            choice = choices[0]
            message = choice.get("message", {})
            content = message.get("content") or message.get("reasoning") or ""
            tool_calls = message.get("tool_calls")
            actual_model = raw.get("model") or envelope.get("model") or model_entry.model_id
            usage = envelope.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            result = RouterResponse(
                content=content,
                model_id=model_entry.model_id,
                actual_model=actual_model,
                provider_id=ProviderId.CLINE,
                family=model_entry.family,
                actual_family=derive_family_from_actual_model(actual_model, self._catalog),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
                tool_calls=tool_calls,
                finish_reason=choice.get("finish_reason", "stop")
                or ("tool_calls" if tool_calls else "stop"),
                raw_response=raw,
            )
            result.transport_request_sha256 = request_fingerprint(request)
            result.transport_response_sha256 = response_fingerprint(result)
            return result
        except NormalizedError:
            raise
        except Exception as exc:
            raise _normalized_error(exc, model_entry) from exc


def _tool_calls(message: Any) -> list[dict[str, Any]] | None:
    raw_calls = getattr(message, "tool_calls", None)
    if not raw_calls:
        return None
    calls: list[dict[str, Any]] = []
    for call in raw_calls:
        if isinstance(call, dict):
            calls.append(call)
            continue
        function = getattr(call, "function", None)
        calls.append(
            {
                "id": getattr(call, "id", f"call_{int(time.time() * 1000)}"),
                "type": getattr(call, "type", "function"),
                "function": {
                    "name": getattr(function, "name", "") if function else "",
                    "arguments": getattr(function, "arguments", "{}") if function else "{}",
                },
            }
        )
    return calls


def _normalized_error(exc: Exception, model_entry: ModelCatalogEntry) -> NormalizedError:
    status_code = getattr(exc, "status_code", getattr(exc, "http_status", None))
    response_body = getattr(exc, "response", getattr(exc, "message", str(exc)))
    headers = getattr(exc, "headers", None)
    return normalize_error(
        http_status=status_code,
        body=response_body,
        headers=headers,
        provider_id=model_entry.provider_id,
        model_id=model_entry.model_id,
    )


class ProviderTransportRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ProviderTransport] = {}
        self._provider_bindings: dict[str, str] = {}

    def register(self, adapter_id: str, transport: ProviderTransport) -> None:
        if _ADAPTER_KEY.fullmatch(adapter_id) is None:
            raise ValueError("transport adapter id must be a lowercase ASCII key")
        if not callable(getattr(transport, "dispatch", None)):
            raise TypeError("transport must implement dispatch")
        if adapter_id in self._adapters:
            raise ValueError(f"transport adapter {adapter_id!r} is already registered")
        self._adapters[adapter_id] = transport

    def bind_provider(self, provider: str | ProviderId, adapter_id: str) -> None:
        provider_key = normalize_provider_key(provider)
        self.resolve(adapter_id)
        if provider_key in self._provider_bindings:
            raise ValueError(f"provider {provider_key!r} is already bound")
        self._provider_bindings[provider_key] = adapter_id

    def resolve(self, adapter_id: str) -> ProviderTransport:
        if _ADAPTER_KEY.fullmatch(adapter_id) is None:
            raise ValueError("transport adapter id must be a lowercase ASCII key")
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(f"unknown transport adapter {adapter_id!r}") from exc

    def resolve_for_provider(self, provider: str | ProviderId) -> ProviderTransport:
        provider_key = normalize_provider_key(provider)
        try:
            adapter_id = self._provider_bindings[provider_key]
        except KeyError as exc:
            raise KeyError(f"no transport adapter bound for provider {provider_key!r}") from exc
        return self.resolve(adapter_id)

    def snapshot(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def build_builtin_transport_registry(catalog: ModelCatalog) -> ProviderTransportRegistry:
    registry = ProviderTransportRegistry()
    openai_compatible_options = {
        ProviderId.GOOGLE: (False, False),
        ProviderId.NVIDIA: (True, False),
        ProviderId.KILO: (False, False),
        ProviderId.OPENROUTER: (False, True),
    }
    for provider, (single_tool_call_only, confidential_zdr) in openai_compatible_options.items():
        adapter_id = f"openai-{provider.value}"
        registry.register(
            adapter_id,
            OpenAICompatibleTransport(
                OpenAICompatibleConfig(
                    api_base=PROVIDER_API_BASES[provider],
                    extra_headers={},
                    single_tool_call_only=single_tool_call_only,
                    confidential_zdr=confidential_zdr,
                ),
                catalog,
            ),
        )
        registry.bind_provider(provider, adapter_id)
    registry.register(
        "cline-envelope",
        ClineEnvelopeTransport(PROVIDER_API_BASES[ProviderId.CLINE], catalog),
    )
    registry.bind_provider(ProviderId.CLINE, "cline-envelope")
    return registry
