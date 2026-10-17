"""PAEOS Semantic-Assurance Kernel.

Exposes the core types, obligation lineage tracker, L11 freeze guard,
and bidirectional delta analysis engine.
"""

from paeos.semantic.delta_engine import SemanticDeltaEngine
from paeos.semantic.freeze_guard import L11SemanticFreezeGuard
from paeos.semantic.lineage import SemanticLineageDAG
from paeos.semantic.types import (
    AuthoritativeSourceTier,
    L11FreezeDeniedError,
    ObligationNature,
    SemanticAssuranceError,
    SemanticDelta,
    SemanticDeltaClassification,
    SemanticDeltaReport,
    SemanticDispositionKind,
    SemanticObligation,
    SemanticObligationDisposition,
    SemanticRequalificationStatus,
    SemanticScopeNarrowingError,
)

__all__ = [
    "AuthoritativeSourceTier",
    "L11FreezeDeniedError",
    "L11SemanticFreezeGuard",
    "ObligationNature",
    "SemanticAssuranceError",
    "SemanticDelta",
    "SemanticDeltaClassification",
    "SemanticDeltaEngine",
    "SemanticDeltaReport",
    "SemanticDispositionKind",
    "SemanticLineageDAG",
    "SemanticObligation",
    "SemanticObligationDisposition",
    "SemanticRequalificationStatus",
    "SemanticScopeNarrowingError",
]
