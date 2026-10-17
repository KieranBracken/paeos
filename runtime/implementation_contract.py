"""Frozen Implementation Contracts and Execution Bindings for Worker Confinement (Gate E)."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


class ContractValidationError(ValueError):
    """Raised when a FrozenImplementationContract fails invariant validation."""


class ExecutionBindingError(ValueError):
    """Raised when an ExecutionBinding fails invariant validation."""


@dataclass(frozen=True, slots=True)
class AcceptanceCommand:
    command_id: str
    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int
    expected_exit_codes: tuple[int, ...] = (0,)

    def __post_init__(self) -> None:
        if not self.command_id or not self.command_id.strip():
            raise ContractValidationError("AcceptanceCommand.command_id must be non-empty")
        if not self.argv:
            raise ContractValidationError("AcceptanceCommand.argv must be non-empty")
        if self.timeout_seconds <= 0:
            raise ContractValidationError("AcceptanceCommand.timeout_seconds must be positive")


def compute_contract_hash(
    *,
    goal_id: str,
    run_id: str,
    ceremony_trace: str,
    base_commit: str,
    allowed_paths: Sequence[str],
    required_artifacts: Sequence[str],
    acceptance_commands: Sequence[AcceptanceCommand],
    rollback_argv: Sequence[str],
    data_class: str,
    context_manifest_hash: str,
    derivation_register_hash: str,
) -> str:
    payload = {
        "goal_id": goal_id,
        "run_id": run_id,
        "ceremony_trace": ceremony_trace,
        "base_commit": base_commit,
        "allowed_paths": sorted(allowed_paths),
        "required_artifacts": sorted(required_artifacts),
        "acceptance_commands": [
            {
                "command_id": c.command_id,
                "argv": list(c.argv),
                "cwd": c.cwd,
                "timeout_seconds": c.timeout_seconds,
                "expected_exit_codes": list(c.expected_exit_codes),
            }
            for c in acceptance_commands
        ],
        "rollback_argv": list(rollback_argv),
        "data_class": data_class,
        "context_manifest_hash": context_manifest_hash,
        "derivation_register_hash": derivation_register_hash,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenImplementationContract:
    contract_id: str
    contract_hash: str
    goal_id: str
    run_id: str
    ceremony_trace: str
    base_commit: str
    allowed_paths: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    acceptance_commands: tuple[AcceptanceCommand, ...]
    rollback_argv: tuple[str, ...]
    data_class: str
    context_manifest_hash: str
    derivation_register_hash: str


def validate_implementation_contract(contract: FrozenImplementationContract) -> None:
    if not contract.contract_id or not contract.contract_id.strip():
        raise ContractValidationError("contract_id must be non-empty")
    if not _SHA40.fullmatch(contract.base_commit):
        raise ContractValidationError(
            f"base_commit must be a 40-character SHA-1: {contract.base_commit}"
        )
    if not _SHA64.fullmatch(contract.context_manifest_hash):
        raise ContractValidationError("context_manifest_hash must be a 64-character SHA-256")
    if not _SHA64.fullmatch(contract.derivation_register_hash):
        raise ContractValidationError("derivation_register_hash must be a 64-character SHA-256")

    for path_str in contract.allowed_paths:
        path = Path(path_str)
        if path.is_absolute() or ".." in path.parts:
            raise ContractValidationError(
                f"path traversal or absolute path forbidden in allowed_paths: {path_str}"
            )

    expected_hash = compute_contract_hash(
        goal_id=contract.goal_id,
        run_id=contract.run_id,
        ceremony_trace=contract.ceremony_trace,
        base_commit=contract.base_commit,
        allowed_paths=contract.allowed_paths,
        required_artifacts=contract.required_artifacts,
        acceptance_commands=contract.acceptance_commands,
        rollback_argv=contract.rollback_argv,
        data_class=contract.data_class,
        context_manifest_hash=contract.context_manifest_hash,
        derivation_register_hash=contract.derivation_register_hash,
    )
    if contract.contract_hash != expected_hash:
        raise ContractValidationError(
            f"contract hash mismatch: expected {expected_hash}, got {contract.contract_hash}"
        )


@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    transaction_key: str
    contract_id: str
    contract_hash: str
    base_commit: str
    worktree: str
    worker_profile_hash: str
    supervisor_profile_hash: str
    policy_hash: str
    sandbox_profile_hash: str
    binary_hashes: tuple[tuple[str, str], ...]
    egress_manifest_hash: str


def validate_execution_binding(binding: ExecutionBinding) -> None:
    if not binding.transaction_key or not binding.transaction_key.strip():
        raise ExecutionBindingError("transaction_key must be non-empty")
    if not binding.contract_id or not binding.contract_id.strip():
        raise ExecutionBindingError("contract_id must be non-empty")
    if not _SHA64.fullmatch(binding.contract_hash):
        raise ExecutionBindingError("contract_hash must be a 64-character SHA-256")
    if not _SHA40.fullmatch(binding.base_commit):
        raise ExecutionBindingError("base_commit must be a 40-character SHA-1")
    if not _SHA64.fullmatch(binding.worker_profile_hash):
        raise ExecutionBindingError("worker_profile_hash must be a 64-character SHA-256")
    if not _SHA64.fullmatch(binding.supervisor_profile_hash):
        raise ExecutionBindingError("supervisor_profile_hash must be a 64-character SHA-256")
    if not _SHA64.fullmatch(binding.policy_hash):
        raise ExecutionBindingError("policy_hash must be a 64-character SHA-256")
    if not _SHA64.fullmatch(binding.sandbox_profile_hash):
        raise ExecutionBindingError("sandbox_profile_hash must be a 64-character SHA-256")
    if not _SHA64.fullmatch(binding.egress_manifest_hash):
        raise ExecutionBindingError("egress_manifest_hash must be a 64-character SHA-256")
