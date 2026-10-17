from __future__ import annotations

from kernel.types import ArtifactRef
from runtime.context_compiler import ContextCompiler


def test_context_compiler_preserves_provenance() -> None:
    compiler = ContextCompiler()
    ref1 = ArtifactRef("design", "1" * 64)
    ref2 = ArtifactRef("plan", "2" * 64)

    compiled = compiler.compile(
        objective="implement gate E",
        context_refs=(ref1, ref2),
    )
    assert len(compiled.context_refs) == 2
    assert len(compiled.content_hash) == 64

