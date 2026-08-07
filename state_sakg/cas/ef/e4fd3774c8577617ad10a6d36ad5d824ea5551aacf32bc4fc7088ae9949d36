"""Context compiler — compile a task's context into one authoritative bundle (PAEOS-9A / K2).

The runtime does not hand an agent raw markdown; it *compiles* the context — the objective plus the
injected artifact references (design, plan, and always the MATCHED SCARS, FR-6) — into a
deterministic `CompiledContext` with a content hash. Determinism is the load-bearing property
(PAEOS-9A §…): the same inputs always produce the same `content_hash`, so identical contexts yield
identical prompts and the binding can detect staleness (K2).

This is the Phase-1 core of PAEOS-9A: deterministic assembly + freshness binding. The fuller
compiler (canonical loading order, truncation budgets, overlay) elaborates behind this same
`compile()` seam.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from kernel.types import ArtifactRef

__all__ = ["CompiledContext", "ContextCompiler"]


@dataclass(frozen=True, slots=True)
class CompiledContext:
    """A compiled, content-addressed task context."""

    objective: str
    context_refs: tuple[ArtifactRef, ...]  # deterministic order (sorted by (type, hash))
    content_hash: str  # sha256 over the canonical compiled context — same inputs ⇒ same hash


class ContextCompiler:
    """Compiles an objective + injected refs (+ matched scars) into a deterministic bundle."""

    def compile(
        self,
        *,
        objective: str,
        context_refs: tuple[ArtifactRef, ...] = (),
        scars: tuple[ArtifactRef, ...] = (),
    ) -> CompiledContext:
        # FR-6: matched scars are always on the path. Deduplicate and order deterministically so
        # the same set of refs always compiles to the same content hash (K2 / PAEOS-9A determinism).
        merged = {(ref.type, ref.hash): ref for ref in (*context_refs, *scars)}
        ordered = tuple(sorted(merged.values(), key=lambda r: (r.type, r.hash)))
        canonical = json.dumps(
            {
                "objective": objective,
                "context_refs": [[r.type, r.hash] for r in ordered],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        content_hash = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        return CompiledContext(objective=objective, context_refs=ordered, content_hash=content_hash)
