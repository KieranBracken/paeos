"""Agent dispatcher — productionizes the DEBT-0002 spawnability spike (PAEOS-8 §10 B1.B / 7.6 §5).

The dispatcher is the runtime component that turns a stage's need into a **scoped Claude Code
session** and back into a `TaskResult` the kernel can gate:

  1. **Mint** a capability token bound to (goal, run, stage, role, session) with an operation
     allow-list (the agent's *only* authority — 7.6 §7).
  2. **Compile** the context (`ContextCompiler`, PAEOS-9A) into the package's `context_refs`.
  3. **Build** the fully-scoped `TaskPackage` (7.6 §5).
  4. **Spawn** a scoped session via the `AgentRuntime` seam — the mechanism validated by the
     DEBT-0002 spike (programmatic spawn + scoped workspace + capability allow-list + output
     capture). The real adapter (Claude Agent SDK / `claude` CLI) implements this Protocol; tests
     use a mock.
  5. **Enforce `write_scopes`**: every path the session wrote MUST be inside its declared scopes,
     else the write is rejected (`ScopeViolation`, Adversary T9). In-scope writes are put in the
     CAS (content-addressed); the full transcript is persisted as the `trace_ref`.

The agent holds **no ambient authority**: what it may touch is only what its capability grants; the
dispatcher additionally refuses any out-of-scope write before it can become an artifact.
"""

from __future__ import annotations

import posixpath
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from kernel.capability import CapabilityBroker
from kernel.cas import CAS
from kernel.types import ArtifactRef, EvidenceRef, GoalId, Role, RunId, StageId, Ts

from runtime.context_compiler import ContextCompiler
from runtime.task_package import (
    Budget,
    Cost,
    EvidenceObligation,
    Permissions,
    TaskPackage,
    TaskResult,
    TaskStatus,
)

__all__ = [
    "AgentDispatcher",
    "AgentRuntime",
    "AgentWrite",
    "RunOutput",
    "ScopeViolation",
    "within_scopes",
]

Clock = Callable[[], Ts]


class ScopeViolation(Exception):
    """A session wrote outside its `write_scopes` — refused before it can become an artifact."""


@dataclass(frozen=True, slots=True)
class AgentWrite:
    """One file the session wrote in its scoped workspace."""

    path: str
    content: bytes


@dataclass(frozen=True, slots=True)
class RunOutput:
    """What the `AgentRuntime` spawn seam returns for a package."""

    status: TaskStatus
    writes: tuple[AgentWrite, ...]
    evidence: tuple[EvidenceRef, ...]
    trace: bytes  # full I/O transcript
    cost: Cost = field(default_factory=lambda: Cost(0, 0.0, "unknown"))


class AgentRuntime(Protocol):
    """The spawn seam: run a scoped Claude Code session for a package and capture its output. The
    real adapter (validated by DEBT-0002) spawns a session with an isolated workspace + MCP
    allow-list from `package.permissions`; tests supply a mock."""

    def run(self, package: TaskPackage) -> RunOutput: ...


def _normalize(path: str) -> str | None:
    if not path or not path.strip():
        return None
    normalized = posixpath.normpath(path.strip().replace("\\", "/")).lstrip("/")
    if normalized in ("", ".") or normalized == ".." or normalized.startswith("../"):
        return None  # tree-escaping ⇒ never in scope
    return normalized


def within_scopes(path: str, write_scopes: tuple[str, ...]) -> bool:
    """True iff `path` (normalised) falls under one of `write_scopes`. Traversal cannot escape."""
    norm = _normalize(path)
    if norm is None:
        return False
    for scope in write_scopes:
        s = _normalize(scope)
        if s is None:
            continue
        if norm == s or norm.startswith(s.rstrip("/") + "/"):
            return True
    return False


class AgentDispatcher:
    """Builds scoped packages, dispatches sessions through the `AgentRuntime` seam, and enforces
    scope on the result."""

    def __init__(
        self,
        broker: CapabilityBroker,
        cas: CAS,
        runtime: AgentRuntime,
        *,
        compiler: ContextCompiler | None = None,
        clock: Clock,
    ) -> None:
        self._broker = broker
        self._cas = cas
        self._runtime = runtime
        self._compiler = compiler if compiler is not None else ContextCompiler()
        self._now = clock

    @staticmethod
    def _operations(mcp_servers: tuple[str, ...]) -> tuple[str, ...]:
        # An MCP allow-list entry "constitution" / "memory:read" ⇒ token op "mcp:constitution" / …
        return tuple(f"mcp:{entry}" for entry in mcp_servers)

    def dispatch(
        self,
        *,
        goal_id: GoalId,
        run_id: RunId,
        stage: StageId,
        role: Role,
        session: str,
        objective: str,
        write_scopes: tuple[str, ...],
        read_scopes: tuple[str, ...] = (),
        mcp_servers: tuple[str, ...] = (),
        required_evidence: tuple[EvidenceObligation, ...] = (),
        context_refs: tuple[ArtifactRef, ...] = (),
        scars: tuple[ArtifactRef, ...] = (),
        budget: Budget,
        ttl: int = 1800,
    ) -> TaskResult:
        now = self._now()
        token = self._broker.mint(
            goal_id=goal_id, run_id=run_id, stage=stage, role=role, session=session,
            operations=self._operations(mcp_servers), issued_seq=now, expires_seq=now + ttl,
        )
        compiled = self._compiler.compile(
            objective=objective, context_refs=context_refs, scars=scars
        )
        package = TaskPackage(
            task_id="t-" + uuid.uuid4().hex[:12],
            goal_id=goal_id, run_id=run_id, stage=stage, role=role,
            objective=compiled.objective, capability=token,
            permissions=Permissions(write_scopes, read_scopes, mcp_servers),
            required_evidence=required_evidence, context_refs=compiled.context_refs, budget=budget,
        )

        output = self._runtime.run(package)  # the scoped, DEBT-0002-validated spawn

        artifacts: list[ArtifactRef] = []
        for write in output.writes:
            if not within_scopes(write.path, write_scopes):
                raise ScopeViolation(
                    f"session wrote {write.path!r} outside its write_scopes {write_scopes}"
                )
            artifacts.append(ArtifactRef(hash=self._cas.put(write.content), type="artifact"))

        trace_ref = self._cas.put(output.trace)  # persist the full transcript (immutable, in CAS)
        return TaskResult(
            task_id=package.task_id,
            status=output.status,
            artifacts=tuple(artifacts),
            evidence=output.evidence,
            trace_ref=trace_ref,
            cost=output.cost,
        )
