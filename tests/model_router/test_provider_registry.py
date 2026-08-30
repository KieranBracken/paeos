from __future__ import annotations

import pytest
from paeos.model_router.providers import (
    ProviderDescriptor,
    ProviderRegistry,
    build_builtin_provider_registry,
    normalize_provider_key,
)
from paeos.model_router.types import LogicalModel, ProviderId, TaskClass


def descriptor(key: str = "google") -> ProviderDescriptor:
    return ProviderDescriptor(
        key=key,
        credential_env="PAEOS_GOOGLE_API_KEY",
        transport_adapter_id="openai-compatible",
        trains_on_inputs=False,
        retains_prompts=False,
        allows_internal=True,
        allows_confidential=True,
        max_rpm=60,
        max_tpm=100_000,
        max_rpd=None,
        preference_rank={LogicalModel.PAEOS_AUTO: 1},
        task_fit={TaskClass.ROUTINE: 0.8},
        quality_bias=0.2,
        latency_bias=0.1,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("google", "google"), (ProviderId.GOOGLE, "google"), ("future-provider", "future-provider")],
)
def test_provider_keys_normalize_legacy_enum_and_future_values(
    value: str | ProviderId,
    expected: str,
) -> None:
    assert normalize_provider_key(value) == expected


@pytest.mark.parametrize("value", ["", "Google", "../google", "google/provider", "google\n"])
def test_provider_keys_reject_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_provider_key(value)


def test_registry_is_deterministic_duplicate_free_and_immutable() -> None:
    registry = ProviderRegistry()
    registry.register(descriptor("z-provider"))
    registry.register(descriptor("google"))
    assert tuple(item.key for item in registry.snapshot()) == ("google", "z-provider")
    assert registry.resolve(ProviderId.GOOGLE).key == "google"
    with pytest.raises(TypeError):
        registry.resolve("google").preference_rank[LogicalModel.PAEOS_AUTO] = 3  # type: ignore[index]
    with pytest.raises(ValueError, match="already registered"):
        registry.register(descriptor("google"))
    with pytest.raises(KeyError, match="unknown provider"):
        registry.resolve("missing")


def test_synthetic_provider_requires_no_enum_member_and_has_secret_free_repr() -> None:
    candidate = descriptor("future-provider")
    assert candidate.key == "future-provider"
    assert "sk-" not in repr(candidate)
    assert candidate.credential_env == "PAEOS_GOOGLE_API_KEY"


def test_builtin_registry_preserves_legacy_provider_facts() -> None:
    registry = build_builtin_provider_registry()
    assert tuple(item.key for item in registry.snapshot()) == (
        "cline",
        "google",
        "kilo",
        "nvidia",
        "openrouter",
    )
    assert registry.resolve(ProviderId.KILO).allows_internal is False
    assert registry.resolve(ProviderId.OPENROUTER).credential_env == "OPENROUTER_API_KEY"
    assert registry.resolve(ProviderId.GOOGLE).preference_rank[LogicalModel.PAEOS_STRONG] == 0
