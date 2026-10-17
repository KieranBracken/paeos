"""Tests for frozen implementation contracts and execution bindings."""

from __future__ import annotations

import pytest


def test_frozen_implementation_contract_creation_and_canonical_hash() -> None:
    from runtime.implementation_contract import (
        AcceptanceCommand,
        FrozenImplementationContract,
        compute_contract_hash,
        validate_implementation_contract,
    )

    cmd = AcceptanceCommand(
        command_id="pytest-focused",
        argv=("pytest", "-q", "tests/test_foo.py"),
        cwd=".",
        timeout_seconds=60,
        expected_exit_codes=(0,),
    )
    contract_hash = compute_contract_hash(
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=("src/foo.py", "tests/test_foo.py"),
        required_artifacts=("reviews/tasks/FOO_review.md",),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "checkout", "HEAD", "--", "src/foo.py"),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )

    contract = FrozenImplementationContract(
        contract_id="IC-001",
        contract_hash=contract_hash,
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=("src/foo.py", "tests/test_foo.py"),
        required_artifacts=("reviews/tasks/FOO_review.md",),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "checkout", "HEAD", "--", "src/foo.py"),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )

    validate_implementation_contract(contract)
    assert contract.contract_hash == contract_hash


def test_contract_validation_rejects_hash_mismatch() -> None:
    from runtime.implementation_contract import (
        AcceptanceCommand,
        ContractValidationError,
        FrozenImplementationContract,
        validate_implementation_contract,
    )

    cmd = AcceptanceCommand("test", ("pytest",), ".", 30, (0,))
    contract = FrozenImplementationContract(
        contract_id="IC-001",
        contract_hash="0" * 64,  # wrong hash
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=("src/foo.py",),
        required_artifacts=(),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "restore", "."),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )
    with pytest.raises(ContractValidationError, match="hash mismatch"):
        validate_implementation_contract(contract)


def test_contract_validation_rejects_path_traversal() -> None:
    from runtime.implementation_contract import (
        AcceptanceCommand,
        ContractValidationError,
        FrozenImplementationContract,
        compute_contract_hash,
        validate_implementation_contract,
    )

    cmd = AcceptanceCommand("test", ("pytest",), ".", 30, (0,))
    allowed_paths = ("../outside.py",)
    chash = compute_contract_hash(
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=allowed_paths,
        required_artifacts=(),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "restore", "."),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )
    contract = FrozenImplementationContract(
        contract_id="IC-001",
        contract_hash=chash,
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=allowed_paths,
        required_artifacts=(),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "restore", "."),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )
    with pytest.raises(ContractValidationError, match="path traversal"):
        validate_implementation_contract(contract)


def test_execution_binding_validation() -> None:
    from runtime.implementation_contract import (
        ExecutionBinding,
        ExecutionBindingError,
        validate_execution_binding,
    )

    binding = ExecutionBinding(
        transaction_key="tx-001",
        contract_id="IC-001",
        contract_hash="1" * 64,
        base_commit="a" * 40,
        worktree="/tmp/worktree",
        worker_profile_hash="2" * 64,
        supervisor_profile_hash="3" * 64,
        policy_hash="4" * 64,
        sandbox_profile_hash="5" * 64,
        binary_hashes=(("python", "6" * 64),),
        egress_manifest_hash="7" * 64,
    )
    validate_execution_binding(binding)

    # Missing field / invalid hash
    invalid_binding = ExecutionBinding(
        transaction_key="",
        contract_id="IC-001",
        contract_hash="1" * 64,
        base_commit="a" * 40,
        worktree="/tmp/worktree",
        worker_profile_hash="2" * 64,
        supervisor_profile_hash="3" * 64,
        policy_hash="4" * 64,
        sandbox_profile_hash="5" * 64,
        binary_hashes=(("python", "6" * 64),),
        egress_manifest_hash="7" * 64,
    )
    with pytest.raises(ExecutionBindingError):
        validate_execution_binding(invalid_binding)

