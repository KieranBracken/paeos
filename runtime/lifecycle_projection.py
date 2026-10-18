"""Runtime bindings for the canonical PAEOS L01-L19 lifecycle.

Authority remains ``operations/ENGINEERING_LIFECYCLE.md`` v1.3.  This module is a derived
projection used to make the relationship between kernel runtime identifiers and lifecycle
layers explicit.  It does not define lifecycle semantics or add stages.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

from kernel.types import StageId

from runtime.ceremony import (
    Layer,
    assert_canonical_lifecycle_bound,
)

__all__ = [
    "CANONICAL_LAYER_STAGE_MAP",
    "FRONTEND_PLANNER_STAGES",
    "NON_LIFECYCLE_CONTROL_STAGES",
    "POST_PROMOTION_STAGES",
    "assert_lifecycle_projection_conformant",
]

# L14 is an independent audit gate composed outside the Builder task runtime.  It deliberately
# has no StageId: assigning ADVERSARIAL_REVIEW to both L10 and L14 would silently collapse two
# constitutionally distinct ceremonies.
CANONICAL_LAYER_STAGE_MAP = MappingProxyType(
    {
        Layer.L01: StageId.INTAKE,
        Layer.L02: StageId.TRIAGE,
        Layer.L03: StageId.RE_DERIVE,
        Layer.L04: StageId.IDEATE,
        Layer.L05: StageId.RESEARCH,
        Layer.L06: StageId.TRADEOFF,
        Layer.L07: StageId.MITIGATION,
        Layer.L08: StageId.DESIGN,
        Layer.L09: StageId.CRITIQUE,
        Layer.L10: StageId.ADVERSARIAL_REVIEW,
        Layer.L11: StageId.PLAN,
        Layer.L12: StageId.IMPLEMENT,
        Layer.L13: StageId.VERIFY,
        Layer.L14: None,
        Layer.L15: StageId.LEDGER_SYNC,
        Layer.L16: StageId.SEAL,
        Layer.L17: StageId.RETROSPECT,
        Layer.L18: StageId.MEMORY_UPDATE,
        Layer.L19: StageId.EVOLVE,
    }
)

# Kernel/runtime controls with no L-layer identity.  They must never be presented as lifecycle
# layers or used to bypass one.
NON_LIFECYCLE_CONTROL_STAGES = frozenset(
    {StageId.RAW, StageId.IMPROVE_RUNTIME, StageId.RESTART}
)

FRONTEND_PLANNER_STAGES: tuple[tuple[StageId, Layer], ...] = tuple(
    (stage, layer)
    for layer, stage in CANONICAL_LAYER_STAGE_MAP.items()
    if Layer.L03.value <= layer.value <= Layer.L11.value and stage is not None
)

POST_PROMOTION_STAGES: tuple[tuple[StageId, Layer], ...] = tuple(
    (stage, layer)
    for layer, stage in CANONICAL_LAYER_STAGE_MAP.items()
    if layer in (Layer.L17, Layer.L18) and stage is not None
)


def assert_lifecycle_projection_conformant(canonical_path: Path | None = None) -> None:
    """Fail closed if this runtime projection no longer matches the ratified baseline."""

    path = canonical_path or Path(__file__).resolve().parents[1] / "operations" / "ENGINEERING_LIFECYCLE.md"
    assert_canonical_lifecycle_bound(path)
    if tuple(CANONICAL_LAYER_STAGE_MAP) != tuple(Layer):
        raise RuntimeError("runtime lifecycle projection does not cover L01-L19 exactly")
    expected_values = {
        stage for stage in StageId if stage not in NON_LIFECYCLE_CONTROL_STAGES
    } | {None}
    if set(CANONICAL_LAYER_STAGE_MAP.values()) != expected_values:
        raise RuntimeError("runtime lifecycle projection has an unexpected stage binding")
