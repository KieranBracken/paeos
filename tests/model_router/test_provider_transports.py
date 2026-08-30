from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.provider_transports import (
    ClineEnvelopeTransport,
    OpenAICompatibleConfig,
    OpenAICompatibleTransport,
    ProviderTransport,
    ProviderTransportRegistry,
    build_builtin_transport_registry,
)
from paeos.model_router.transport import LiteLLMTransport
from paeos.model_router.types import (
    CostTier,
    DataClass,
    ModelCatalogEntry,
    ModelFamily,
    ProviderId,
    RouterResponse,
    TaskRequest,
)


def entry() -> ModelCatalogEntry:
    return ModelCatalogEntry(
        model_id="synthetic/model",
        provider_id=ProviderId.OPENROUTER,
        family=ModelFamily.GPT,
        cost_tier=CostTier.FREE,
    )


@dataclass
class SyntheticTransport:
    calls: int = 0

    def dispatch(
        self,
        model_entry: ModelCatalogEntry,
        request: TaskRequest,
        *,
        api_key: str,
        timeout: float,
    ) -> RouterResponse:
        self.calls += 1
        assert model_entry.model_id == "synthetic/model"
        assert request.messages == [{"role": "user", "content": "hello"}]
        assert api_key == "test-key"
        assert timeout == 2.0
        return RouterResponse(
            content="synthetic response",
            model_id=model_entry.model_id,
            provider_id=model_entry.provider_id,
            family=model_entry.family,
        )


def test_registry_accepts_synthetic_transport_without_provider_enum() -> None:
    registry = ProviderTransportRegistry()
    transport: ProviderTransport = SyntheticTransport()
    registry.register("synthetic-adapter", transport)
    assert registry.resolve("synthetic-adapter") is transport
    assert registry.snapshot() == ("synthetic-adapter",)


def test_registry_rejects_duplicate_and_unknown_adapters() -> None:
    registry = ProviderTransportRegistry()
    registry.register("synthetic-adapter", SyntheticTransport())
    with pytest.raises(ValueError, match="already registered"):
        registry.register("synthetic-adapter", SyntheticTransport())
    with pytest.raises(KeyError, match="unknown transport adapter"):
        registry.resolve("missing-adapter")


def test_openai_compatible_config_is_immutable_and_secret_free() -> None:
    config = OpenAICompatibleConfig(
        api_base="https://example.invalid/v1",
        extra_headers={"X-Test": "enabled"},
        single_tool_call_only=True,
        confidential_zdr=True,
    )
    assert config.api_base.endswith("/v1")
    assert "sk-" not in repr(config)
    with pytest.raises(TypeError):
        config.extra_headers["X-Test"] = "changed"  # type: ignore[index]


def test_registry_snapshot_is_sorted() -> None:
    registry = ProviderTransportRegistry()
    registry.register("z-adapter", SyntheticTransport())
    registry.register("a-adapter", SyntheticTransport())
    assert registry.snapshot() == ("a-adapter", "z-adapter")


def test_litellm_dispatch_uses_bound_synthetic_adapter() -> None:
    registry = ProviderTransportRegistry()
    synthetic = SyntheticTransport()
    registry.register("synthetic-adapter", synthetic)
    registry.bind_provider(ProviderId.OPENROUTER, "synthetic-adapter")
    credentials = CredentialStore()
    credentials._keys = {"OPENROUTER_API_KEY": "test-key"}

    result = LiteLLMTransport(credentials, registry=registry).dispatch(
        entry(),
        TaskRequest(messages=[{"role": "user", "content": "hello"}]),
        timeout=2.0,
    )

    assert result.content == "synthetic response"
    assert synthetic.calls == 1


def test_openai_compatible_adapter_preserves_endpoint_and_tool_normalization() -> None:
    model_entry = ModelCatalogEntry(
        model_id="nvidia/model",
        provider_id=ProviderId.NVIDIA,
        family=ModelFamily.LLAMA,
        cost_tier=CostTier.FREE,
    )
    adapter = OpenAICompatibleTransport(
        OpenAICompatibleConfig(
            api_base="https://nvidia.example/v1",
            extra_headers={"X-Route": "test"},
            single_tool_call_only=True,
            confidential_zdr=False,
        ),
        ModelCatalog(),
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="ok", tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3),
        model="nvidia/model",
    )
    request = TaskRequest(
        messages=[
            {
                "role": "assistant",
                "content": "tool result",
                "tool_calls": [{"id": "one"}, {"id": "two"}],
            }
        ],
        data_class=DataClass.CONFIDENTIAL,
    )
    with patch(
        "paeos.model_router.provider_transports.litellm.completion",
        return_value=response,
    ) as call:
        result = adapter.dispatch(model_entry, request, api_key="test-key", timeout=2.0)
    kwargs = call.call_args.kwargs
    assert kwargs["api_base"] == "https://nvidia.example/v1"
    assert kwargs["extra_headers"] == {"X-Route": "test"}
    assert kwargs["messages"][0]["tool_calls"] == [{"id": "one"}]
    assert "extra_body" not in kwargs
    assert result.content == "ok"


def test_openai_compatible_adapter_adds_confidential_zdr_body() -> None:
    model_entry = entry()
    adapter = OpenAICompatibleTransport(
        OpenAICompatibleConfig(
            api_base="https://router.example/v1",
            extra_headers={},
            single_tool_call_only=False,
            confidential_zdr=True,
        ),
        ModelCatalog(),
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="ok", tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        model="synthetic/model",
    )
    with patch(
        "paeos.model_router.provider_transports.litellm.completion",
        return_value=response,
    ) as call:
        adapter.dispatch(
            model_entry,
            TaskRequest(messages=[], data_class=DataClass.CONFIDENTIAL),
            api_key="test-key",
            timeout=2.0,
        )
    assert call.call_args.kwargs["extra_body"] == {
        "provider": {"data_collection": "deny", "zdr": True}
    }


def test_cline_adapter_unwraps_data_envelope_and_uses_exact_endpoint() -> None:
    model_entry = ModelCatalogEntry(
        model_id="cline/model",
        provider_id=ProviderId.CLINE,
        family=ModelFamily.MINIMAX,
        cost_tier=CostTier.FREE,
    )
    adapter = ClineEnvelopeTransport("https://cline.example/api/v1", ModelCatalog())
    response = SimpleNamespace(
        status_code=200,
        headers={},
        text="",
        json=lambda: {
            "data": {
                "model": "cline/model",
                "choices": [
                    {"message": {"content": "cline ok"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 5},
            }
        },
    )
    with patch(
        "paeos.model_router.provider_transports.requests.post",
        return_value=response,
    ) as post:
        result = adapter.dispatch(
            model_entry,
            TaskRequest(messages=[{"role": "user", "content": "hello"}]),
            api_key="test-key",
            timeout=2.0,
        )
    assert post.call_args.args[0] == "https://cline.example/api/v1/chat/completions"
    assert post.call_args.kwargs["json"]["model"] == "cline/model"
    assert result.content == "cline ok"
    assert result.total_tokens == 9


def test_builtin_registry_binds_all_legacy_provider_surfaces() -> None:
    registry = build_builtin_transport_registry(ModelCatalog())
    assert registry.snapshot() == (
        "cline-envelope",
        "openai-google",
        "openai-kilo",
        "openai-nvidia",
        "openai-openrouter",
    )
    for provider in ProviderId:
        assert registry.resolve_for_provider(provider) is not None
