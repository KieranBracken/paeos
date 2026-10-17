"""PAEOS Autonomy, Mission Dependency Graph (MDG), and Self-Remediation Package."""

from __future__ import annotations

from runtime.autonomy.authority import (
    ActionPermission,
    AuthorityClassifier,
    AuthorityEnvelope,
    AuthorityExpansionForbiddenError,
    AuthorityTier,
    FindingClass,
    FounderDecisionPacket,
    FounderStopPredicate,
    FounderStopRequiredError,
    RootEnvelopeAuthorityResolver,
)
from runtime.autonomy.cycle_detector import CycleDetectedError, topological_sort, would_cause_cycle
from runtime.autonomy.mdg import (
    BlockerNode,
    BlockerStatus,
    CeremonyTrace,
    DependencyEdge,
    EdgeType,
    MissionDependencyGraph,
    TaskNode,
    TaskStatus,
)
from runtime.autonomy.mission_controller import PersistentMissionController
from runtime.autonomy.orca_lineage import OrcaLineageProjection, handle_orca_lineage_request
from runtime.autonomy.recovery_controller import (
    CircuitBreakerDiagnostic,
    CircuitBreakerPolicy,
    CircuitBreakerTrippedError,
    RecoveryController,
)
from runtime.autonomy.resume_engine import (
    CheckpointCorruptError,
    FencingTokenManager,
    ResumeEngine,
    StaleFencingTokenError,
    TaskCheckpoint,
)
from runtime.autonomy.weakness_finder import ContinuousWeaknessFinder
from runtime.autonomy.weakness_finder_probes import ProbeFinding, ProbeSeverity, WeaknessFinderProbes

__all__ = [
    "ActionPermission",
    "AuthorityClassifier",
    "AuthorityEnvelope",
    "AuthorityExpansionForbiddenError",
    "AuthorityTier",
    "BlockerNode",
    "BlockerStatus",
    "CeremonyTrace",
    "CheckpointCorruptError",
    "CircuitBreakerDiagnostic",
    "CircuitBreakerPolicy",
    "CircuitBreakerTrippedError",
    "ContinuousWeaknessFinder",
    "CycleDetectedError",
    "DependencyEdge",
    "EdgeType",
    "FencingTokenManager",
    "FindingClass",
    "FounderDecisionPacket",
    "FounderStopPredicate",
    "FounderStopRequiredError",
    "MissionDependencyGraph",
    "OrcaLineageProjection",
    "PersistentMissionController",
    "ProbeFinding",
    "ProbeSeverity",
    "RecoveryController",
    "ResumeEngine",
    "RootEnvelopeAuthorityResolver",
    "StaleFencingTokenError",
    "TaskCheckpoint",
    "TaskNode",
    "TaskStatus",
    "WeaknessFinderProbes",
    "handle_orca_lineage_request",
    "topological_sort",
    "would_cause_cycle",
]
