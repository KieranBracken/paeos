"""B1.B tests for the context compiler (PAEOS-9A / K2): deterministic + scars always injected."""

from __future__ import annotations

from kernel.types import ArtifactRef
from runtime.context_compiler import ContextCompiler

_PLAN = ArtifactRef(hash="c" * 64, type="plan")
_DESIGN = ArtifactRef(hash="d" * 64, type="design")
_SCAR = ArtifactRef(hash="9" * 64, type="scar")


def test_same_inputs_same_content_hash() -> None:
    c = ContextCompiler()
    a = c.compile(objective="impl X", context_refs=(_PLAN, _DESIGN), scars=(_SCAR,))
    b = c.compile(objective="impl X", context_refs=(_DESIGN, _PLAN), scars=(_SCAR,))  # reordered
    assert a.content_hash == b.content_hash  # order-independent → deterministic (K2)


def test_scars_are_always_on_the_path() -> None:
    c = ContextCompiler()
    compiled = c.compile(objective="impl X", context_refs=(_PLAN,), scars=(_SCAR,))
    assert _SCAR in compiled.context_refs  # FR-6: matched scars injected


def test_dedup_and_deterministic_order() -> None:
    c = ContextCompiler()
    compiled = c.compile(objective="X", context_refs=(_PLAN, _PLAN), scars=(_SCAR,))
    assert compiled.context_refs == tuple(
        sorted((_PLAN, _SCAR), key=lambda r: (r.type, r.hash))
    )


def test_different_objective_changes_hash() -> None:
    c = ContextCompiler()
    assert c.compile(objective="A").content_hash != c.compile(objective="B").content_hash
