"""Task package + result — the worker (agent) contract (PAEOS-7.6 §5).

"Claude Code is a worker, not the brain." The runtime hands an agent a **fully-scoped** package;
the agent executes and returns a **result**. The agent has *no ambient authority* — everything it
may touch is in the package's capability (§7). These are Z2 (`runtime/`) contract types, transcribed
verbatim from 7.6 §5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from kernel.evidence import EvidenceKind
from kernel.types import (
    ArtifactRef,
    CapabilityToken,
    EvidenceRef,
    GoalId,
    Hash,
    Role,
    RunId,
    StageId,
)

__all__ = [
    "Budget",
    "Cost",
    "EvidenceObligation",
    "ExecutionContext",
    "Permissions",
    "SkillRef",
    "TaskPackage",
    "TaskResult",
    "TaskStatus",
]


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """L1 Ephemeral Execution Context (IP-0004).
    
    Scoped strictly to the active run_id. Holds transient operational retry state.
    Destroyed when the execution scope terminates. NEVER written to institutional memory.
    """

    retry_hints: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkillRef:
    """A registry skill entry a task may invoke (§9), e.g. testing@2.1."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class EvidenceObligation:
    """What MUST be produced to pass the gate (FR-4)."""

    claim_id: str
    kind: EvidenceKind
    acceptance: str


@dataclass(frozen=True, slots=True)
class Permissions:
    """The scoped grants of a task package. Enforcement is by capability, not this record (T1)."""

    write_scopes: tuple[str, ...]
    read_scopes: tuple[str, ...]
    mcp_servers: tuple[str, ...]  # allow-list, e.g. ("constitution", "artifacts", "memory:read")
    skills: tuple[SkillRef, ...] = ()


@dataclass(frozen=True, slots=True)
class Budget:
    """Per-goal slice of the two-tier budget (A-7)."""

    tokens: int
    wallclock_s: int
    retries: int


@dataclass(frozen=True, slots=True)
class TaskPackage:
    """The fully-scoped unit handed to an agent session (PAEOS-7.6 §5)."""

    task_id: str
    goal_id: GoalId
    run_id: RunId
    stage: StageId
    role: Role
    objective: str
    capability: CapabilityToken  # AUTHORITY — the only privilege the agent has
    permissions: Permissions
    required_evidence: tuple[EvidenceObligation, ...]
    context_refs: tuple[ArtifactRef, ...]  # injected: design, plan, and MATCHED SCARS (FR-6)
    budget: Budget
    forbidden: tuple[str, ...] = ()  # documentation of intent; enforcement is by capability (T1)
    ephemeral_context: ExecutionContext = field(default_factory=ExecutionContext)


class TaskStatus(Enum):
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


@dataclass(frozen=True, slots=True)
class Cost:
    """What the run consumed (drives budget governance + drift audit)."""

    tokens: int
    wallclock_s: float
    model_ver: str
    skill_vers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TaskResult:
    """What an agent session returns (PAEOS-7.6 §5)."""

    task_id: str
    status: TaskStatus
    artifacts: tuple[ArtifactRef, ...]  # written to CAS
    evidence: tuple[EvidenceRef, ...]  # bound to artifact + environment (§6)
    trace_ref: Hash  # full agent I/O transcript (immutable; audit + self-improvement)
    cost: Cost = field(default_factory=lambda: Cost(0, 0.0, "unknown"))
