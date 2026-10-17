"""Trusted, descriptor-driven registry for supervisor adapters."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from paeos.model_router.providers import normalize_provider_key

from runtime.supervisors.protocol import SupervisorAdapter

_ADAPTER_ID = re.compile(r"^[a-z][a-z0-9-]{0,62}$")


@dataclass(frozen=True, slots=True)
class SupervisorAdapterDescriptor:
    adapter_id: str
    adapter_version: str
    provider_key: str
    factory: Callable[[], SupervisorAdapter]

    def __post_init__(self) -> None:
        if _ADAPTER_ID.fullmatch(self.adapter_id) is None:
            raise ValueError("adapter_id must be a lowercase identifier")
        if not self.adapter_version or not isinstance(self.adapter_version, str):
            raise ValueError("adapter_version must be non-empty")
        object.__setattr__(self, "provider_key", normalize_provider_key(self.provider_key))
        if not callable(self.factory):
            raise TypeError("factory must be callable")


class SupervisorAdapterRegistry:
    """Explicit startup registry; no filesystem discovery or dynamic imports."""

    def __init__(self, descriptors: Iterable[SupervisorAdapterDescriptor] = ()) -> None:
        self._descriptors: dict[str, SupervisorAdapterDescriptor] = {}
        for descriptor in descriptors:
            self.register(descriptor)

    def register(self, descriptor: SupervisorAdapterDescriptor) -> None:
        if not isinstance(descriptor, SupervisorAdapterDescriptor):
            raise TypeError("registry accepts SupervisorAdapterDescriptor values only")
        if descriptor.adapter_id in self._descriptors:
            raise ValueError(f"adapter {descriptor.adapter_id!r} is already registered")
        self._descriptors[descriptor.adapter_id] = descriptor

    def resolve(self, adapter_id: str) -> SupervisorAdapterDescriptor:
        if not isinstance(adapter_id, str) or _ADAPTER_ID.fullmatch(adapter_id) is None:
            raise KeyError("adapter_id is invalid")
        try:
            return self._descriptors[adapter_id]
        except KeyError as exc:
            raise KeyError(f"unknown supervisor adapter {adapter_id!r}") from exc

    def snapshot(self) -> tuple[SupervisorAdapterDescriptor, ...]:
        return tuple(self._descriptors[key] for key in sorted(self._descriptors))

    def instantiate(self, adapter_id: str) -> SupervisorAdapter:
        return self.resolve(adapter_id).factory()
