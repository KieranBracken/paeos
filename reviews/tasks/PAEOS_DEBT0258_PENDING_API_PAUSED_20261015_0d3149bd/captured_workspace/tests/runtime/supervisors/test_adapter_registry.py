"""Supervisor adapter registry extension and boundary tests."""

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
from runtime.supervisors.protocol import AdapterResult, SupervisorRequest
from runtime.supervisors.registry import SupervisorAdapterDescriptor, SupervisorAdapterRegistry


@dataclass
class FakeAdapter:
    def invoke(
        self, request: SupervisorRequest, context: bytes
    ) -> AdapterResult:  # pragma: no cover
        raise NotImplementedError


def test_synthetic_adapter_registers_and_resolves_without_core_edits() -> None:
    registry = SupervisorAdapterRegistry()
    descriptor = SupervisorAdapterDescriptor(
        adapter_id="future-supervisor",
        adapter_version="1.0.0",
        provider_key="future-provider",
        factory=FakeAdapter,
    )
    registry.register(descriptor)
    assert registry.resolve("future-supervisor") is descriptor
    assert isinstance(registry.instantiate("future-supervisor"), FakeAdapter)
    assert registry.snapshot() == (descriptor,)


def test_duplicate_unknown_and_invalid_ids_fail_closed() -> None:
    descriptor = SupervisorAdapterDescriptor(
        adapter_id="future-supervisor",
        adapter_version="1.0.0",
        provider_key="future-provider",
        factory=FakeAdapter,
    )
    registry = SupervisorAdapterRegistry([descriptor])
    with pytest.raises(ValueError, match="already registered"):
        registry.register(descriptor)
    with pytest.raises(KeyError, match="unknown"):
        registry.resolve("missing-supervisor")
    with pytest.raises(KeyError, match="invalid"):
        registry.resolve("../escape")


@pytest.mark.parametrize("field", ["adapter_id", "provider_key"])
def test_invalid_descriptor_keys_are_rejected(field: str) -> None:
    kwargs = {
        "adapter_id": "future-supervisor",
        "adapter_version": "1.0.0",
        "provider_key": "future-provider",
        "factory": FakeAdapter,
    }
    kwargs[field] = "../unsafe"
    with pytest.raises((ValueError, TypeError)):
        SupervisorAdapterDescriptor(**kwargs)


def test_supervisor_core_has_no_provider_specific_imports_or_branches() -> None:
    root = Path(__file__).parents[3]
    paths = (root / "runtime/supervisors/checkpoint.py", root / "runtime/supervisors/registry.py")
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any("google" in (node.module or "").casefold() for node in imports)
        assert not any("cline" in (node.module or "").casefold() for node in imports)
        assert not any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.casefold() in {"google", "cline", "nvidia", "kilo", "openrouter"}
            for node in ast.walk(tree)
        )
