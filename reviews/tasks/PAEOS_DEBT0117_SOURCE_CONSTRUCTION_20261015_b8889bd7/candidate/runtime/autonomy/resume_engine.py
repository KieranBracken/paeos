"""Durable parent checkpointing, monotonic fencing tokens, and exact-once resume engine."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from runtime.autonomy.mdg import MissionDependencyGraph, TaskNode, TaskStatus


class StaleFencingTokenError(RuntimeError):
    """Resume rejected due to stale or duplicate fencing token."""


class CheckpointCorruptError(ValueError):
    """CAS checkpoint hash does not match payload or is invalid."""


@dataclass(frozen=True, slots=True)
class TaskCheckpoint:
    task_id: str
    root_mission_id: str
    stage_id: str
    captured_at_unix: float
    state_payload: dict[str, Any]

    def serialize(self) -> bytes:
        return json.dumps(
            {
                "task_id": self.task_id,
                "root_mission_id": self.root_mission_id,
                "stage_id": self.stage_id,
                "captured_at_unix": self.captured_at_unix,
                "state_payload": self.state_payload,
            },
            sort_keys=True,
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()


class FencingTokenManager:
    """Tracks and issues strictly monotonic fencing tokens per task across restarts."""

    def __init__(self, graph: MissionDependencyGraph | None = None) -> None:
        self.graph = graph
        self._tokens: dict[str, int] = {}

    def _get_base_token(self, task_id: str) -> int:
        mem = self._tokens.get(task_id, 0)
        graph_tok = 0
        if self.graph and task_id in self.graph.tasks:
            graph_tok = self.graph.tasks[task_id].fencing_token
        return max(mem, graph_tok)

    def current_token(self, task_id: str) -> int:
        return self._get_base_token(task_id)

    def next_token(self, task_id: str) -> int:
        curr = self._get_base_token(task_id)
        new_tok = curr + 1
        self._tokens[task_id] = new_tok
        return new_tok

    def validate_and_advance(self, task_id: str, presented_token: int | None = None) -> int:
        curr = self._get_base_token(task_id)
        if presented_token is not None:
            if presented_token <= curr:
                raise StaleFencingTokenError(
                    f"Presented token {presented_token} is <= current active token {curr} for task {task_id}"
                )
            self._tokens[task_id] = presented_token
            return presented_token
        new_tok = curr + 1
        self._tokens[task_id] = new_tok
        return new_tok


class ResumeEngine:
    """Exact-once parent task resume coordinator with CAS checkpointing and durable lease tracking."""

    def __init__(
        self,
        graph: MissionDependencyGraph,
        fencing_manager: FencingTokenManager | None = None,
        cas: Any | None = None,
        ledger: Any | None = None,
    ) -> None:
        self.graph = graph
        self.fencing = fencing_manager or FencingTokenManager(graph=graph)
        self.cas = cas
        self.ledger = ledger
        self._checkpoints: dict[str, bytes] = {}
        self._task_leases: dict[str, tuple[int, float]] = {}  # task_id -> (fencing_token, expire_at)
        if ledger is not None:
            self.sync_from_ledger()

    def _commit_event(self, kind: str, payload: dict[str, Any]) -> int:
        if self.ledger is not None:
            from kernel.ledger import Event
            return self.ledger.append(Event(1, kind, payload))
        return 0

    def sync_from_ledger(self) -> None:
        """Hydrate leases and active fencing state from the durable ledger."""
        if self.ledger is None:
            return
        head = self.ledger.head()
        if head is None:
            return
        now = time.time()
        rows = self.ledger.read(1, head.seq + 1)
        for row in rows:
            if row.event.kind == "MDG_LEASE_RECORD":
                p = dict(row.event.payload)
                exp = float(p.get("expire_at_unix", 0.0))
                if exp > now:
                    self._task_leases[p["task_id"]] = (p["fencing_token"], exp)
                else:
                    self._task_leases.pop(p["task_id"], None)
                self.fencing._tokens[p["task_id"]] = max(
                    self.fencing._tokens.get(p["task_id"], 0),
                    p["fencing_token"],
                )

    def store_checkpoint(self, checkpoint: TaskCheckpoint) -> str:
        raw = checkpoint.serialize()
        digest = checkpoint.digest
        if self.cas is not None:
            cas_ref = self.cas.put(raw)
            return cas_ref
        self._checkpoints[digest] = raw
        return digest

    def restore_checkpoint(self, checkpoint_ref: str) -> TaskCheckpoint:
        if self.cas is not None:
            try:
                raw = self.cas.get(checkpoint_ref)
            except Exception as exc:
                raise CheckpointCorruptError(f"Checkpoint {checkpoint_ref} not found in CAS: {exc}") from exc
        else:
            raw = self._checkpoints.get(checkpoint_ref)
            if raw is None:
                raise CheckpointCorruptError(f"Checkpoint {checkpoint_ref} not found")

        computed = hashlib.sha256(raw).hexdigest()
        if computed != checkpoint_ref:
            raise CheckpointCorruptError(f"Checkpoint hash mismatch: {computed} != {checkpoint_ref}")

        data = json.loads(raw.decode("utf-8"))
        return TaskCheckpoint(
            task_id=data["task_id"],
            root_mission_id=data["root_mission_id"],
            stage_id=data["stage_id"],
            captured_at_unix=data["captured_at_unix"],
            state_payload=data["state_payload"],
        )

    def suspend_parent_task(
        self,
        task_id: str,
        stage_id: str,
        state_payload: dict[str, Any],
    ) -> str:
        task = self.graph.tasks[task_id]
        cp = TaskCheckpoint(
            task_id=task_id,
            root_mission_id=task.root_mission_id,
            stage_id=stage_id,
            captured_at_unix=time.time(),
            state_payload=state_payload,
        )
        digest = self.store_checkpoint(cp)
        self.graph.suspend_task(task_id, digest)
        return digest

    def attempt_resume(
        self,
        task_id: str,
        presented_token: int | None = None,
        lease_seconds: float = 30.0,
    ) -> tuple[bool, str, TaskNode | None]:
        """Attempt exact-once resume of a suspended parent task."""
        current_token = self.fencing.current_token(task_id)
        if presented_token is not None and presented_token <= current_token:
            return False, f"Stale or replay resume token: presented {presented_token} <= current {current_token}", None

        task = self.graph.tasks.get(task_id)
        if task is None:
            return False, f"Task {task_id} not found", None
        if task.status != TaskStatus.SUSPENDED:
            return False, f"Task {task_id} not in SUSPENDED state (current: {task.status.value})", None

        if not self.graph.can_resume_task(task_id):
            active_blockers = self.graph.get_active_blockers_for_task(task_id)
            return (
                False,
                f"Cannot resume task {task_id}: {len(active_blockers)} active blockers remain",
                None,
            )

        if not task.checkpoint_ref:
            return False, f"Task {task_id} has no checkpoint to resume", None
        try:
            checkpoint = self.restore_checkpoint(task.checkpoint_ref)
        except (ValueError, TypeError, KeyError) as exc:
            return False, f"Cannot resume task {task_id}: invalid checkpoint: {exc}", None
        if checkpoint.task_id != task_id or checkpoint.root_mission_id != task.root_mission_id:
            return False, f"Cannot resume task {task_id}: checkpoint task or root mismatch", None

        try:
            token = self.fencing.validate_and_advance(task_id, presented_token)
        except StaleFencingTokenError as exc:
            return False, f"Stale or replay resume token: {exc}", None

        expire_at = time.time() + lease_seconds
        self._task_leases[task_id] = (token, expire_at)
        self._commit_event("MDG_LEASE_RECORD", {
            "task_id": task_id,
            "fencing_token": token,
            "expire_at_unix": expire_at,
        })
        resumed_node = self.graph.resume_task(task_id, token)
        return True, f"Task {task_id} resumed with fencing token {token}", resumed_node

    def recover_interrupted_resume(
        self,
        task_id: str,
        lease_seconds: float = 30.0,
    ) -> tuple[bool, str, TaskNode | None]:
        """Recover from a crash between resume and worker launch when lease expires."""
        lease = self._task_leases.get(task_id)
        now = time.time()
        if lease is not None:
            token, expire_at = lease
            if now < expire_at:
                return False, "Active lease has not yet expired", None

        # Lease is expired or missing: issue fresh fencing token
        fresh_token = self.fencing.next_token(task_id)
        expire_at = now + lease_seconds
        self._task_leases[task_id] = (fresh_token, expire_at)
        self._commit_event("MDG_LEASE_RECORD", {
            "task_id": task_id,
            "fencing_token": fresh_token,
            "expire_at_unix": expire_at,
        })
        # Force graph task to ACTIVE with fresh token
        task = self.graph.tasks[task_id]
        updated = TaskNode(
            task_id=task.task_id,
            root_mission_id=task.root_mission_id,
            parent_task_id=task.parent_task_id,
            nesting_depth=task.nesting_depth,
            status=TaskStatus.ACTIVE,
            checkpoint_ref=task.checkpoint_ref,
            fencing_token=fresh_token,
            ceremony_trace=task.ceremony_trace,
            metadata=task.metadata,
        )
        self.graph._tasks[task_id] = updated
        self.graph._commit_event("MDG_TASK_RESUMED", {
            "task_id": task_id,
            "root_mission_id": task.root_mission_id,
            "parent_task_id": task.parent_task_id,
            "nesting_depth": task.nesting_depth,
            "status": TaskStatus.ACTIVE.value,
            "checkpoint_ref": task.checkpoint_ref,
            "fencing_token": fresh_token,
            "ceremony_trace": task.ceremony_trace.value,
            "metadata": task.metadata,
        })
        return True, f"Recovered interrupted resume with fresh token {fresh_token}", updated
