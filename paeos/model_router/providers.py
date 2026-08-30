"""Validated, provider-neutral descriptors for the model-router registry."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from paeos.model_router.types import LogicalModel, ProviderId, ProviderKey, TaskClass

_PROVIDER_KEY = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_ENVIRONMENT_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_ADAPTER_KEY = re.compile(r"^[a-z][a-z0-9-]{0,62}$")


def normalize_provider_key(value: str | ProviderId) -> ProviderKey:
    """Return the canonical lowercase key while retaining enum compatibility."""

    if isinstance(value, ProviderId):
        value = value.value
    if not isinstance(value, str) or _PROVIDER_KEY.fullmatch(value) is None:
        raise ValueError(
            "provider key must be lowercase ASCII starting with a letter and contain only "
            "letters, digits, or hyphens"
        )
    return value


def _bounded_limit(value: int | None, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer or None")


def _score(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Trusted local facts needed to route to one provider.

    Descriptors contain only an environment-variable *name* for credentials. Secret values,
    arbitrary import paths, and runtime plugin code are intentionally not representable.
    """

    key: ProviderKey
    credential_env: str
    transport_adapter_id: str
    trains_on_inputs: bool
    retains_prompts: bool
    allows_internal: bool
    allows_confidential: bool
    max_rpm: int | None
    max_tpm: int | None
    max_rpd: int | None
    preference_rank: Mapping[LogicalModel, int]
    task_fit: Mapping[TaskClass, float]
    quality_bias: float
    latency_bias: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", normalize_provider_key(self.key))
        if _ENVIRONMENT_KEY.fullmatch(self.credential_env) is None:
            raise ValueError("credential_env must be an environment-variable name")
        if _ADAPTER_KEY.fullmatch(self.transport_adapter_id) is None:
            raise ValueError("transport_adapter_id must be a validated adapter key")
        for field_name, value in (
            ("trains_on_inputs", self.trains_on_inputs),
            ("retains_prompts", self.retains_prompts),
            ("allows_internal", self.allows_internal),
            ("allows_confidential", self.allows_confidential),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a boolean")
        _bounded_limit(self.max_rpm, "max_rpm")
        _bounded_limit(self.max_tpm, "max_tpm")
        _bounded_limit(self.max_rpd, "max_rpd")

        preference_rank = dict(self.preference_rank)
        for model, rank in preference_rank.items():
            if not isinstance(model, LogicalModel):
                raise TypeError("preference_rank keys must be LogicalModel values")
            if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0:
                raise ValueError("preference_rank values must be non-negative integers")
        task_fit = dict(self.task_fit)
        for task_class, score in task_fit.items():
            if not isinstance(task_class, TaskClass):
                raise TypeError("task_fit keys must be TaskClass values")
            _score(score, "task_fit score")
            if not 0.0 <= float(score) <= 1.0:
                raise ValueError("task_fit scores must be between 0 and 1")
        _score(self.quality_bias, "quality_bias")
        _score(self.latency_bias, "latency_bias")
        object.__setattr__(self, "preference_rank", MappingProxyType(preference_rank))
        object.__setattr__(self, "task_fit", MappingProxyType(task_fit))


class ProviderRegistry:
    """Deterministic in-memory registry assembled from trusted local descriptors."""

    def __init__(self, descriptors: Iterable[ProviderDescriptor] = ()) -> None:
        self._descriptors: dict[ProviderKey, ProviderDescriptor] = {}
        for descriptor in descriptors:
            self.register(descriptor)

    def register(self, descriptor: ProviderDescriptor) -> None:
        if not isinstance(descriptor, ProviderDescriptor):
            raise TypeError("registry accepts only ProviderDescriptor values")
        key = normalize_provider_key(descriptor.key)
        if key in self._descriptors:
            raise ValueError(f"provider {key!r} is already registered")
        self._descriptors[key] = descriptor

    def resolve(self, key: str | ProviderId) -> ProviderDescriptor:
        normalized = normalize_provider_key(key)
        try:
            return self._descriptors[normalized]
        except KeyError as exc:
            raise KeyError(f"unknown provider {normalized!r}") from exc

    def snapshot(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(self._descriptors[key] for key in sorted(self._descriptors))


def build_builtin_provider_registry() -> ProviderRegistry:
    """Assemble the trusted legacy provider facts as descriptor data."""

    strong = {
        LogicalModel.PAEOS_STRONG: 0,
        LogicalModel.PAEOS_AUTO: 0,
        LogicalModel.PAEOS_CODE: 3,
        LogicalModel.PAEOS_CHEAP: 4,
        LogicalModel.PAEOS_AUDIT: 0,
    }
    descriptors = (
        ProviderDescriptor(
            key=ProviderId.GOOGLE.value,
            credential_env="GEMINI_API_KEY",
            transport_adapter_id="openai-google",
            trains_on_inputs=False,
            retains_prompts=False,
            allows_internal=True,
            allows_confidential=True,
            max_rpm=12,
            max_tpm=800_000,
            max_rpd=1_500,
            preference_rank=strong,
            task_fit={TaskClass.ARCHITECTURE: 1.0, TaskClass.AUDIT: 1.0},
            quality_bias=0.95,
            latency_bias=0.2,
        ),
        ProviderDescriptor(
            key=ProviderId.CLINE.value,
            credential_env="CLINE_API_KEY",
            transport_adapter_id="cline-envelope",
            trains_on_inputs=False,
            retains_prompts=False,
            allows_internal=True,
            allows_confidential=True,
            max_rpm=None,
            max_tpm=None,
            max_rpd=None,
            preference_rank={
                LogicalModel.PAEOS_STRONG: 2,
                LogicalModel.PAEOS_CODE: 0,
                LogicalModel.PAEOS_CHEAP: 2,
                LogicalModel.PAEOS_AUTO: 2,
                LogicalModel.PAEOS_AUDIT: 2,
            },
            task_fit={TaskClass.IMPLEMENTATION: 1.0, TaskClass.CODE_REVIEW: 0.9},
            quality_bias=0.85,
            latency_bias=0.3,
        ),
        ProviderDescriptor(
            key=ProviderId.NVIDIA.value,
            credential_env="NVIDIA_API_KEY",
            transport_adapter_id="openai-nvidia",
            trains_on_inputs=False,
            retains_prompts=False,
            allows_internal=True,
            allows_confidential=True,
            max_rpm=20,
            max_tpm=200_000,
            max_rpd=1_000,
            preference_rank={
                LogicalModel.PAEOS_STRONG: 1,
                LogicalModel.PAEOS_CODE: 4,
                LogicalModel.PAEOS_CHEAP: 3,
                LogicalModel.PAEOS_AUTO: 1,
                LogicalModel.PAEOS_AUDIT: 1,
            },
            task_fit={TaskClass.IMPLEMENTATION: 0.9, TaskClass.AUDIT: 0.9},
            quality_bias=0.86,
            latency_bias=0.4,
        ),
        ProviderDescriptor(
            key=ProviderId.KILO.value,
            credential_env="KILO_API_KEY",
            transport_adapter_id="openai-kilo",
            trains_on_inputs=True,
            retains_prompts=True,
            allows_internal=False,
            allows_confidential=False,
            max_rpm=20,
            max_tpm=200_000,
            max_rpd=500,
            preference_rank={
                LogicalModel.PAEOS_STRONG: 3,
                LogicalModel.PAEOS_CODE: 2,
                LogicalModel.PAEOS_CHEAP: 0,
                LogicalModel.PAEOS_AUTO: 3,
                LogicalModel.PAEOS_AUDIT: 3,
            },
            task_fit={TaskClass.ROUTINE: 1.0},
            quality_bias=0.75,
            latency_bias=0.5,
        ),
        ProviderDescriptor(
            key=ProviderId.OPENROUTER.value,
            credential_env="OPENROUTER_API_KEY",
            transport_adapter_id="openai-openrouter",
            trains_on_inputs=False,
            retains_prompts=False,
            allows_internal=True,
            allows_confidential=True,
            max_rpm=20,
            max_tpm=200_000,
            max_rpd=200,
            preference_rank={
                LogicalModel.PAEOS_STRONG: 4,
                LogicalModel.PAEOS_CODE: 1,
                LogicalModel.PAEOS_CHEAP: 1,
                LogicalModel.PAEOS_AUTO: 4,
                LogicalModel.PAEOS_AUDIT: 4,
            },
            task_fit={TaskClass.ROUTINE: 1.0, TaskClass.IMPLEMENTATION: 0.8},
            quality_bias=0.70,
            latency_bias=0.6,
        ),
    )
    return ProviderRegistry(descriptors)
