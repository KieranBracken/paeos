"""ClaudeCliWorkerTransport (R5.2) — the claude-CLI-backed `WorkerTransport`.

The worker is a live `claude` CLI session (behind the B1.B `AgentRuntime` seam). Running a session
does two things at once: it **executes** the worker, and it **captures the evidence the session
declares** — a JSONL evidence file the session writes in a write scope — into a durable pool served
via `receive`/`evidence_for`. So an autonomous run's evidence comes *from the agent*, never authored
for it (toward R5): the `SoftLoop` uses one object as both `agent_runtime` (execution) and
`evidence_source` (the agent's own evidence).

This is a **vendor transport** (it wraps the `claude`-CLI execution seam) and lives under
`runtime/transports/`; the core runtime depends on `AgentRuntime` / `WorkerTransport` /
`EvidenceSource`, never on this class — the R5.1 invariant. A scripted inner `AgentRuntime` drives
the tests; deployment injects the live `ClaudeCodeRuntime`.
"""

from __future__ import annotations

import json
from pathlib import Path

from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import JsonValue
from kernel.types import Role

from runtime.claude_code import AgentRuntime, RunOutput
from runtime.orchestrator import FileCourtEvidencePool
from runtime.task_package import TaskPackage

__all__ = ["ClaudeCliWorkerTransport"]

# The write path a session declares its evidence at (one JSON evidence object per line). Must be in
# the session's write_scopes for the live runtime to keep it (B2.I collection).
EVIDENCE_SCOPE = "evidence.jsonl"
_DEFAULT_ENV_HASH = content_hash(b"paeos-claude-cli-env")


class ClaudeCliWorkerTransport:
    """A `WorkerTransport` whose worker is a live `claude` session. `run` executes the session (via
    the inner `AgentRuntime`) and captures any evidence it declared into a per-run pool; the pool is
    served through `receive`/`evidence_for`. Satisfies `AgentRuntime`, `WorkerTransport`, and
    `EvidenceSource` — the `SoftLoop` uses it as both executor and evidence source."""

    def __init__(
        self, inner: AgentRuntime, pool_dir: Path, *, evidence_scope: str = EVIDENCE_SCOPE
    ) -> None:
        self._inner = inner
        self._pool = FileCourtEvidencePool(pool_dir)
        self._scope = evidence_scope

    # ---- AgentRuntime (execution) + evidence capture --------------------------
    def run(self, package: TaskPackage) -> RunOutput:
        output = self._inner.run(package)
        for write in output.writes:
            if write.path == self._scope:  # the session's declared evidence
                for evidence in _parse_evidence_lines(write.content):
                    self._pool.submit(package.run_id, evidence)
        return output

    # ---- WorkerTransport ------------------------------------------------------
    def submit(self, run_id: str, evidence: Evidence) -> None:
        self._pool.submit(run_id, evidence)

    def status(self, run_id: str) -> str:
        return f"{len(self._pool.evidence_for(run_id))} evidence submitted for run {run_id}"

    def receive(self, run_id: str) -> tuple[Evidence, ...]:
        return self._pool.evidence_for(run_id)

    # ---- EvidenceSource (read-only facet the SoftLoop consumes) ----------------
    def evidence_for(self, run_id: str) -> tuple[Evidence, ...]:
        return self._pool.evidence_for(run_id)


def _parse_evidence_lines(content: bytes) -> list[Evidence]:
    """Parse a session's declared evidence (JSONL; one `{claim_id, kind, command, artifact_hash,
    exit_code, stdout}` per line) into `Evidence`. Malformed lines are skipped (best-effort)."""
    evidence: list[Evidence] = []
    for line in content.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        ev = _evidence_from_declaration({str(k): v for k, v in obj.items()})
        if ev is not None:
            evidence.append(ev)
    return evidence


def _evidence_from_declaration(obj: dict[str, JsonValue]) -> Evidence | None:
    command = obj.get("command")
    claim_id = obj.get("claim_id")
    artifact_hash = obj.get("artifact_hash")
    if not (
        isinstance(command, str) and isinstance(claim_id, str) and isinstance(artifact_hash, str)
    ):
        return None
    exit_code = obj.get("exit_code")
    stdout = obj.get("stdout")
    valid_exit = isinstance(exit_code, int) and not isinstance(exit_code, bool)
    result: dict[str, JsonValue] = {
        "exit_code": exit_code if valid_exit else 0,
        "stdout": stdout if isinstance(stdout, str) else "",
    }
    kind = obj.get("kind")
    ev_kind = EvidenceKind.TEST
    if isinstance(kind, str) and kind in EvidenceKind.__members__:
        ev_kind = EvidenceKind[kind]
    return Evidence(
        hash=content_hash(f"{claim_id}:{command}".encode()),
        kind=ev_kind,
        claim_id=claim_id,
        artifact_hash=artifact_hash,
        environment_hash=_DEFAULT_ENV_HASH,
        reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session="claude-cli"),
        determinism=Determinism.DETERMINISTIC,
        result=result,
        attestation="pending-kernel-sig",
    )
