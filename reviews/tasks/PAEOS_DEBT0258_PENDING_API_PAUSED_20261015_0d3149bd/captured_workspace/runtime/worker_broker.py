"""Typed, capability-checked worker operation broker for TaskPackage confinement (Gate E)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from kernel.capability import CapabilityBroker, CapabilityError
from kernel.types import Role, StageId

from runtime.implementation_contract import ExecutionBinding
from runtime.task_package import TaskPackage


class OperationKind(StrEnum):
    READ_FILE = "READ_FILE"
    APPLY_PATCH = "APPLY_PATCH"
    RUN_ACCEPTANCE = "RUN_ACCEPTANCE"
    REQUEST_SCOPE = "REQUEST_SCOPE"
    SUBMIT_ARTIFACT = "SUBMIT_ARTIFACT"


class BrokerOperationError(RuntimeError):
    """Raised when an operation is denied or fails execution."""


@dataclass(frozen=True, slots=True)
class OperationRequest:
    request_id: str
    task_id: str
    kind: OperationKind
    arguments: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class OperationReceipt:
    request_hash: str
    operation: str
    exit_code: int | None
    stdout_hash: str | None
    artifact_hash: str | None
    ledger_seq: int


class WorkerOperationBroker:
    """Brokers typed operations using verified capability tokens and bound worktrees."""

    def __init__(self, capability_broker: CapabilityBroker | None = None) -> None:
        self._capability_broker = capability_broker or CapabilityBroker()

    def execute(
        self, package: TaskPackage, request: OperationRequest, *, current_seq: int
    ) -> OperationReceipt:
        binding = package.execution_binding
        if not isinstance(binding, ExecutionBinding):
            raise BrokerOperationError("production task package missing ExecutionBinding")

        path_str = ""
        # Map kind to exact capability operation string
        if request.kind == OperationKind.READ_FILE:
            path_str = str(request.arguments.get("path", ""))
            operation_str = f"file:read:{path_str}"
        elif request.kind == OperationKind.APPLY_PATCH:
            path_str = str(request.arguments.get("path", ""))
            operation_str = f"patch:apply:{path_str}"
        elif request.kind == OperationKind.RUN_ACCEPTANCE:
            cmd_id = str(request.arguments.get("command_id", ""))
            operation_str = f"test:run:{cmd_id}"
        elif request.kind == OperationKind.REQUEST_SCOPE:
            operation_str = "scope:request"
        elif request.kind == OperationKind.SUBMIT_ARTIFACT:
            path_str = str(request.arguments.get("path", ""))
            operation_str = f"artifact:submit:{path_str}"
        else:
            raise BrokerOperationError(f"unrecognized operation kind: {request.kind}")

        # Verify capability token
        try:
            self._capability_broker.verify(
                token=package.capability,
                goal_id=package.goal_id,
                run_id=package.run_id,
                stage=StageId.IMPLEMENT,
                role=Role.BUILDER,
                operation=operation_str,
                current_seq=current_seq,
                session=package.capability.bound_to.session,
            )
        except CapabilityError as e:
            raise BrokerOperationError(f"operation not permitted by capability: {e}") from e

        worktree_path = Path(binding.worktree)
        exit_code = 0
        stdout_hash = None
        artifact_hash = None

        if request.kind == OperationKind.READ_FILE:
            target_path = (worktree_path / path_str).resolve()
            if not str(target_path).startswith(str(worktree_path.resolve())):
                raise BrokerOperationError("path traversal escape denied")
            if not target_path.exists():
                raise BrokerOperationError(f"file not found: {path_str}")
            content = target_path.read_bytes()
            stdout_hash = hashlib.sha256(content).hexdigest()

        req_encoded = json.dumps(
            {
                "request_id": request.request_id,
                "task_id": request.task_id,
                "kind": request.kind.value,
                "operation": operation_str,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        req_hash = hashlib.sha256(req_encoded).hexdigest()

        return OperationReceipt(
            request_hash=req_hash,
            operation=operation_str,
            exit_code=exit_code,
            stdout_hash=stdout_hash,
            artifact_hash=artifact_hash,
            ledger_seq=current_seq,
        )
