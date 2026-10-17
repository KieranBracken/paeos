"""Frozen Implementation Contracts and Execution Bindings for Worker Confinement (Gate E)."""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_CONTRACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")


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
    executable_sha256: str = ""
    allowed_executable_hashes: tuple[tuple[str, str], ...] = ()
    sandbox_exec_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.command_id or not self.command_id.strip():
            raise ContractValidationError("AcceptanceCommand.command_id must be non-empty")
        if not self.argv:
            raise ContractValidationError("AcceptanceCommand.argv must be non-empty")
        if self.timeout_seconds <= 0:
            raise ContractValidationError("AcceptanceCommand.timeout_seconds must be positive")
        if not isinstance(self.executable_sha256, str):
            raise ContractValidationError("AcceptanceCommand.executable_sha256 must be a string")
        if not isinstance(self.sandbox_exec_sha256, str):
            raise ContractValidationError("AcceptanceCommand.sandbox_exec_sha256 must be a string")
        if any(not isinstance(part, str) or not part or "\x00" in part for part in self.argv):
            raise ContractValidationError("AcceptanceCommand.argv must contain non-empty strings")

        supplied = Path(self.argv[0])
        if not supplied.is_absolute():
            located = shutil.which(self.argv[0])
            if located is None:
                raise ContractValidationError("AcceptanceCommand executable cannot be resolved")
            supplied = Path(located)
        try:
            executable = supplied.resolve(strict=True)
            if not executable.is_file() or not executable.stat().st_mode & 0o111:
                raise ContractValidationError("AcceptanceCommand executable is not runnable")
            observed_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
        except OSError as exc:
            raise ContractValidationError("AcceptanceCommand executable is unavailable") from exc
        object.__setattr__(self, "argv", (str(executable), *self.argv[1:]))
        if not self.executable_sha256:
            object.__setattr__(self, "executable_sha256", observed_hash)
        if not self.sandbox_exec_sha256:
            try:
                sandbox_exec = _SANDBOX_EXEC.resolve(strict=True)
                if (
                    sandbox_exec != _SANDBOX_EXEC
                    or not sandbox_exec.is_file()
                    or not sandbox_exec.stat().st_mode & 0o111
                ):
                    raise ContractValidationError("Seatbelt sandbox executable is not canonical")
                sandbox_digest = hashlib.sha256(sandbox_exec.read_bytes()).hexdigest()
            except OSError as exc:
                raise ContractValidationError("Seatbelt sandbox executable is unavailable") from exc
            object.__setattr__(self, "sandbox_exec_sha256", sandbox_digest)
        if not isinstance(self.allowed_executable_hashes, tuple):
            raise ContractValidationError(
                "AcceptanceCommand.allowed_executable_hashes must be a tuple"
            )
        pins: list[tuple[str, str]] = []
        if any(
            not isinstance(item, tuple)
            or len(item) != 2
            or any(not isinstance(value, str) for value in item)
            for item in self.allowed_executable_hashes
        ):
            raise ContractValidationError(
                "AcceptanceCommand.allowed_executable_hashes must contain string pairs"
            )
        for path_text, digest in self.allowed_executable_hashes:
            path = Path(path_text)
            try:
                resolved = path.resolve(strict=True)
            except OSError as exc:
                raise ContractValidationError(
                    "AcceptanceCommand allowed executable is unavailable"
                ) from exc
            if not path.is_absolute() or resolved != path or not path.is_file() or not path.stat().st_mode & 0o111:
                raise ContractValidationError(
                    "AcceptanceCommand allowed executable must be canonical and runnable"
                )
            pins.append((str(path), digest))
        primary = str(executable)
        if primary in {path for path, _ in pins}:
            if dict(pins)[primary] != self.executable_sha256:
                raise ContractValidationError(
                    "AcceptanceCommand primary executable pin is inconsistent"
                )
        else:
            pins.append((primary, self.executable_sha256))
        object.__setattr__(self, "allowed_executable_hashes", tuple(sorted(pins)))


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
                "executable_sha256": c.executable_sha256,
                "allowed_executable_hashes": [list(item) for item in c.allowed_executable_hashes],
                "sandbox_exec_sha256": c.sandbox_exec_sha256,
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
    if not isinstance(contract.contract_id, str) or not _CONTRACT_ID.fullmatch(contract.contract_id):
        raise ContractValidationError("contract_id must be a canonical path-safe identifier")
    for label in ("goal_id", "run_id", "ceremony_trace"):
        value = getattr(contract, label)
        if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
            raise ContractValidationError(f"{label} must be a canonical non-empty string")
    if not _SHA40.fullmatch(contract.base_commit):
        raise ContractValidationError(
            f"base_commit must be a 40-character SHA-1: {contract.base_commit}"
        )
    if not _SHA64.fullmatch(contract.context_manifest_hash):
        raise ContractValidationError("context_manifest_hash must be a 64-character SHA-256")
    if not _SHA64.fullmatch(contract.derivation_register_hash):
        raise ContractValidationError("derivation_register_hash must be a 64-character SHA-256")

    if not contract.allowed_paths or len(set(contract.allowed_paths)) != len(contract.allowed_paths):
        raise ContractValidationError("allowed_paths must be non-empty and unique")
    for path_str in contract.allowed_paths:
        path = Path(path_str)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path_str
            or "\\" in path_str
            or posixpath.normpath(path_str) != path_str
        ):
            raise ContractValidationError(
                f"path traversal or absolute path forbidden in allowed_paths: {path_str}"
            )
    if not contract.acceptance_commands:
        raise ContractValidationError("acceptance_commands must not be empty")
    for command in contract.acceptance_commands:
        if not isinstance(command.executable_sha256, str) or not _SHA64.fullmatch(
            command.executable_sha256
        ):
            raise ContractValidationError(
                f"acceptance command {command.command_id!r} lacks an executable SHA-256 pin"
            )
        if not isinstance(command.sandbox_exec_sha256, str) or not _SHA64.fullmatch(
            command.sandbox_exec_sha256
        ):
            raise ContractValidationError(
                f"acceptance command {command.command_id!r} lacks a sandbox executable SHA-256 pin"
            )
        if not Path(command.argv[0]).is_absolute():
            raise ContractValidationError(
                f"acceptance command {command.command_id!r} executable must be absolute"
            )
        if (
            not command.allowed_executable_hashes
            or len({path for path, _ in command.allowed_executable_hashes})
            != len(command.allowed_executable_hashes)
            or any(
                not Path(path).is_absolute()
                or any(character in path for character in ('"', "\n", "\r"))
                or not _SHA64.fullmatch(digest)
                for path, digest in command.allowed_executable_hashes
            )
            or dict(command.allowed_executable_hashes).get(command.argv[0])
            != command.executable_sha256
        ):
            raise ContractValidationError(
                f"acceptance command {command.command_id!r} executable allowlist is invalid"
            )
    if not contract.rollback_argv or any(not part for part in contract.rollback_argv):
        raise ContractValidationError("rollback_argv must be non-empty")
    if contract.data_class not in {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "SECRET"}:
        raise ContractValidationError("data_class is unknown")

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


def canonical_implementation_contract_bytes(contract: FrozenImplementationContract) -> bytes:
    """Return the exact canonical JSON representation accepted as an L11 CAS artifact."""
    validate_implementation_contract(contract)
    payload = {
        "contract_id": contract.contract_id,
        "contract_hash": contract.contract_hash,
        "goal_id": contract.goal_id,
        "run_id": contract.run_id,
        "ceremony_trace": contract.ceremony_trace,
        "base_commit": contract.base_commit,
        "allowed_paths": list(contract.allowed_paths),
        "required_artifacts": list(contract.required_artifacts),
        "acceptance_commands": [
            {
                "command_id": command.command_id,
                "argv": list(command.argv),
                "executable_sha256": command.executable_sha256,
                "allowed_executable_hashes": [
                    list(item) for item in command.allowed_executable_hashes
                ],
                "sandbox_exec_sha256": command.sandbox_exec_sha256,
                "cwd": command.cwd,
                "timeout_seconds": command.timeout_seconds,
                "expected_exit_codes": list(command.expected_exit_codes),
            }
            for command in contract.acceptance_commands
        ],
        "rollback_argv": list(contract.rollback_argv),
        "data_class": contract.data_class,
        "context_manifest_hash": contract.context_manifest_hash,
        "derivation_register_hash": contract.derivation_register_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def implementation_contract_from_canonical_json(raw: bytes) -> FrozenImplementationContract:
    """Decode a strict, duplicate-free L11 contract artifact and verify its canonical bytes."""

    def object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ContractValidationError(f"duplicate contract JSON member {key!r}")
            result[key] = value
        return result

    def strings(value: object, label: str) -> tuple[str, ...]:
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise ContractValidationError(f"{label} must be a non-empty-string array")
        return tuple(value)

    fields = {
        "contract_id", "contract_hash", "goal_id", "run_id", "ceremony_trace",
        "base_commit", "allowed_paths", "required_artifacts", "acceptance_commands",
        "rollback_argv", "data_class", "context_manifest_hash", "derivation_register_hash",
    }
    command_fields = {
        "command_id", "argv", "executable_sha256", "allowed_executable_hashes",
        "sandbox_exec_sha256", "cwd", "timeout_seconds", "expected_exit_codes",
    }
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=object_without_duplicates)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError("L11 contract artifact is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ContractValidationError("L11 contract artifact has missing or unknown fields")
    commands_value = payload["acceptance_commands"]
    if not isinstance(commands_value, list):
        raise ContractValidationError("acceptance_commands must be an array")
    commands: list[AcceptanceCommand] = []
    for item in commands_value:
        if not isinstance(item, dict) or set(item) != command_fields:
            raise ContractValidationError("acceptance command has missing or unknown fields")
        timeout = item["timeout_seconds"]
        exit_codes = item["expected_exit_codes"]
        allowed_executables = item["allowed_executable_hashes"]
        if type(timeout) is not int or not isinstance(exit_codes, list) or any(
            type(code) is not int for code in exit_codes
        ):
            raise ContractValidationError("acceptance command numeric fields are invalid")
        if not isinstance(allowed_executables, list) or any(
            not isinstance(pair, list)
            or len(pair) != 2
            or any(not isinstance(value, str) for value in pair)
            for pair in allowed_executables
        ):
            raise ContractValidationError("allowed_executable_hashes must be string pairs")
        if not isinstance(item["command_id"], str) or not isinstance(item["cwd"], str):
            raise ContractValidationError("acceptance command text fields are invalid")
        if not isinstance(item["executable_sha256"], str):
            raise ContractValidationError("acceptance executable hash must be a string")
        if not isinstance(item["sandbox_exec_sha256"], str):
            raise ContractValidationError("sandbox executable hash must be a string")
        commands.append(
            AcceptanceCommand(
                command_id=item["command_id"],
                argv=strings(item["argv"], "acceptance argv"),
                cwd=item["cwd"],
                timeout_seconds=timeout,
                expected_exit_codes=tuple(exit_codes),
                executable_sha256=item["executable_sha256"],
                allowed_executable_hashes=tuple(
                    (pair[0], pair[1]) for pair in allowed_executables
                ),
                sandbox_exec_sha256=item["sandbox_exec_sha256"],
            )
        )
    text_fields = (
        "contract_id", "contract_hash", "goal_id", "run_id", "ceremony_trace",
        "base_commit", "data_class", "context_manifest_hash", "derivation_register_hash",
    )
    if any(not isinstance(payload[field], str) for field in text_fields):
        raise ContractValidationError("L11 contract text fields are invalid")
    contract = FrozenImplementationContract(
        contract_id=payload["contract_id"],
        contract_hash=payload["contract_hash"],
        goal_id=payload["goal_id"],
        run_id=payload["run_id"],
        ceremony_trace=payload["ceremony_trace"],
        base_commit=payload["base_commit"],
        allowed_paths=strings(payload["allowed_paths"], "allowed_paths"),
        required_artifacts=strings(payload["required_artifacts"], "required_artifacts"),
        acceptance_commands=tuple(commands),
        rollback_argv=strings(payload["rollback_argv"], "rollback_argv"),
        data_class=payload["data_class"],
        context_manifest_hash=payload["context_manifest_hash"],
        derivation_register_hash=payload["derivation_register_hash"],
    )
    validate_implementation_contract(contract)
    if canonical_implementation_contract_bytes(contract) != raw:
        raise ContractValidationError("L11 contract artifact is not canonically encoded")
    return contract


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


@dataclass(frozen=True, slots=True)
class ExecutionBindingProfile:
    """Runtime-authored environment facts combined with a controller-resolved L11 contract."""

    worktree: str
    worker_profile_hash: str
    supervisor_profile_hash: str
    policy_hash: str
    sandbox_profile_hash: str
    binary_hashes: tuple[tuple[str, str], ...]
    egress_manifest_hash: str


def validate_execution_binding_profile(profile: ExecutionBindingProfile) -> None:
    if not isinstance(profile, ExecutionBindingProfile):
        raise ExecutionBindingError("execution binding profile has an invalid type")
    if not Path(profile.worktree).is_absolute():
        raise ExecutionBindingError("profile worktree must be an absolute path")
    for label in (
        "worker_profile_hash",
        "supervisor_profile_hash",
        "policy_hash",
        "sandbox_profile_hash",
        "egress_manifest_hash",
    ):
        if not _SHA64.fullmatch(getattr(profile, label)):
            raise ExecutionBindingError(f"{label} must be a 64-character SHA-256")
    if not profile.binary_hashes or len({name for name, _ in profile.binary_hashes}) != len(
        profile.binary_hashes
    ):
        raise ExecutionBindingError("profile binary_hashes must contain unique identities")
    if any(not name or not _SHA64.fullmatch(digest) for name, digest in profile.binary_hashes):
        raise ExecutionBindingError("profile binary_hashes contains an invalid identity or digest")


def validate_execution_binding(binding: ExecutionBinding) -> None:
    if not binding.transaction_key or not binding.transaction_key.strip():
        raise ExecutionBindingError("transaction_key must be non-empty")
    if not binding.contract_id or not binding.contract_id.strip():
        raise ExecutionBindingError("contract_id must be non-empty")
    if not _SHA64.fullmatch(binding.contract_hash):
        raise ExecutionBindingError("contract_hash must be a 64-character SHA-256")
    if not _SHA40.fullmatch(binding.base_commit):
        raise ExecutionBindingError("base_commit must be a 40-character SHA-1")
    if not Path(binding.worktree).is_absolute():
        raise ExecutionBindingError("worktree must be an absolute path")
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
    if not binding.binary_hashes or len({name for name, _ in binding.binary_hashes}) != len(
        binding.binary_hashes
    ):
        raise ExecutionBindingError("binary_hashes must contain unique binary identities")
    if any(not name or not _SHA64.fullmatch(digest) for name, digest in binding.binary_hashes):
        raise ExecutionBindingError("binary_hashes contains an invalid identity or digest")
