"""Discriminative mutation tests for TaskPackage worker confinement (Gate E Task 7.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from kernel.capability import CapabilityBroker
from kernel.types import ArtifactRef
from paeos.model_router.types import DataClass
from runtime.data_policy import (
    ContextEntry,
    EgressPolicyViolationError,
    PrivacyPolicySnapshot,
    compile_egress_manifest,
)
from runtime.implementation_contract import (
    AcceptanceCommand,
    ExecutionBinding,
    FrozenImplementationContract,
    compute_contract_hash,
)
from runtime.task_compiler import ProductionTaskCompiler, TaskCompilationError
from runtime.task_package import Budget
from runtime.worker_broker import (
    BrokerOperationError,
    OperationKind,
    OperationRequest,
    WorkerOperationBroker,
)


def _make_confinement_package(worktree: Path) -> tuple[object, CapabilityBroker]:
    broker = CapabilityBroker()
    compiler = ProductionTaskCompiler(broker=broker)

    cmd = AcceptanceCommand("pytest-focused", ("pytest", "-q"), ".", 30, (0,))
    contract_hash = compute_contract_hash(
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=("src/target.py",),
        required_artifacts=("reviews/tasks/TARGET_review.md",),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "restore", "."),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )
    contract = FrozenImplementationContract(
        contract_id="IC-CONF-001",
        contract_hash=contract_hash,
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=("src/target.py",),
        required_artifacts=("reviews/tasks/TARGET_review.md",),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "restore", "."),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )
    binding = ExecutionBinding(
        transaction_key="tx-001",
        contract_id="IC-CONF-001",
        contract_hash=contract_hash,
        base_commit="a" * 40,
        worktree=str(worktree),
        worker_profile_hash="1" * 64,
        supervisor_profile_hash="2" * 64,
        policy_hash="3" * 64,
        sandbox_profile_hash="4" * 64,
        binary_hashes=(("python", "5" * 64),),
        egress_manifest_hash="6" * 64,
    )
    context_entry = ContextEntry(
        ref=ArtifactRef("design", "7" * 64),
        source="repo",
        source_hash="7" * 64,
        data_class=DataClass.INTERNAL,
        trust="HIGH",
        purpose="architecture",
    )
    budget = Budget(tokens=10000, wallclock_s=300, retries=1)

    package = compiler.compile(
        contract=contract,
        binding=binding,
        context=(context_entry,),
        budget=budget,
        worker_session="session-001",
        current_seq=10,
    )
    return package, broker


def test_mutation_path_traversal_escape_killed(tmp_path: Path) -> None:
    from runtime.task_package import TaskPackage

    package, broker = _make_confinement_package(tmp_path)
    assert isinstance(package, TaskPackage)
    op_broker = WorkerOperationBroker(capability_broker=broker)

    req = OperationRequest(
        request_id="req-esc",
        task_id="IC-CONF-001",
        kind=OperationKind.READ_FILE,
        arguments={"path": "../../../etc/passwd"},
    )
    with pytest.raises(BrokerOperationError):
        op_broker.execute(package, req, current_seq=15)


def test_mutation_data_class_downgrade_killed() -> None:
    policy = PrivacyPolicySnapshot(
        provider="google",
        policy_version="2026.1",
        policy_hash="p" * 64,
        observed_at="2026-08-30T00:00:00Z",
        expires_at="2026-09-30T00:00:00Z",
        allows_internal=True,
        allows_confidential=False,
        trains_on_inputs=False,
        retains_prompts=False,
    )
    secret_entry = ContextEntry(
        ref=ArtifactRef("key", "k" * 64),
        source="vault",
        source_hash="k" * 64,
        data_class=DataClass.SECRET,
        trust="LOCAL_ONLY",
        purpose="signing",
    )
    with pytest.raises(EgressPolicyViolationError, match="SECRET"):
        compile_egress_manifest([secret_entry], policy)


def test_mutation_contract_hash_mismatch_killed(tmp_path: Path) -> None:
    broker = CapabilityBroker()
    compiler = ProductionTaskCompiler(broker=broker)

    cmd = AcceptanceCommand("pytest-focused", ("pytest", "-q"), ".", 30, (0,))
    contract = FrozenImplementationContract(
        contract_id="IC-002",
        contract_hash="1" * 64,
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
    binding = ExecutionBinding(
        transaction_key="tx-002",
        contract_id="IC-002",
        contract_hash="2" * 64,  # mismatched hash
        base_commit="a" * 40,
        worktree=str(tmp_path),
        worker_profile_hash="1" * 64,
        supervisor_profile_hash="2" * 64,
        policy_hash="3" * 64,
        sandbox_profile_hash="4" * 64,
        binary_hashes=(("python", "5" * 64),),
        egress_manifest_hash="6" * 64,
    )
    with pytest.raises(TaskCompilationError):
        compiler.compile(
            contract=contract,
            binding=binding,
            context=(),
            budget=Budget(tokens=100, wallclock_s=10, retries=0),
            worker_session="session-001",
            current_seq=1,
        )


def test_provider_environment_never_inherits_host_credentials(tmp_path: Path) -> None:
    from runtime.integrations.worker_confinement import (
        WorkerConfinementError,
        build_provider_environment,
    )

    workspace = tmp_path / "workspace"
    home = workspace / ".runtime"
    temp = workspace / ".tmp"
    env = build_provider_environment(
        {"OPENAI_API_KEY": "must-not-copy", "CODEX_HOME": "/Users/owner/.codex"},
        runtime_home=home,
        temp_root=temp,
        task_environment={"PAEOS_TASK_BROKER_TOKEN": "ephemeral"},
    )
    assert "OPENAI_API_KEY" not in env
    assert "CODEX_HOME" not in env
    assert env["PAEOS_TASK_BROKER_TOKEN"] == "ephemeral"
    assert set(env) == {"HOME", "LANG", "LC_ALL", "PATH", "TMPDIR", "PAEOS_TASK_BROKER_TOKEN"}

    with pytest.raises(WorkerConfinementError):
        build_provider_environment(
            {},
            runtime_home=home,
            temp_root=temp,
            task_environment={"CODEX_HOME": "/Users/owner/.codex"},
        )


def test_worker_confinement_rejects_caller_selected_sandbox_binary(tmp_path: Path) -> None:
    import sys

    from runtime.integrations.worker_confinement import (
        WorkerConfinementError,
        policy_for_worker,
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    policy = policy_for_worker(
        workspace=workspace,
        read_roots=(workspace,),
        write_roots=(workspace,),
        runtime_home=workspace / ".runtime",
        temp_root=workspace / ".tmp",
        sandbox_exec=Path("/bin/sh"),
    )
    with pytest.raises(WorkerConfinementError, match="pinned"):
        policy.wrap_argv((str(Path(sys.executable).resolve()), "-c", "pass"))


def test_worker_confinement_rejects_caller_supplied_permissive_profile(tmp_path: Path) -> None:
    import dataclasses
    import sys

    from runtime.integrations.worker_confinement import (
        WorkerConfinementError,
        policy_for_worker,
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    policy = policy_for_worker(
        workspace=workspace,
        read_roots=(workspace,),
        write_roots=(workspace,),
        runtime_home=workspace / ".runtime",
        temp_root=workspace / ".tmp",
    )
    forged = dataclasses.replace(policy, seatbelt_profile="(version 1)\n(allow default)")
    with pytest.raises(WorkerConfinementError, match="parent-compiled"):
        forged.wrap_argv((str(Path(sys.executable).resolve()), "-c", "pass"))
