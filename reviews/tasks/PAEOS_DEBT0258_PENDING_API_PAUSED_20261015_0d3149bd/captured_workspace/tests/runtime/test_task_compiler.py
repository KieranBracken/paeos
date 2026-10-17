"""Tests for ProductionTaskCompiler (Gate E Task 3)."""

from __future__ import annotations

from kernel.capability import CapabilityBroker
from kernel.types import ArtifactRef
from paeos.model_router.types import DataClass
from runtime.data_policy import ContextEntry
from runtime.implementation_contract import (
    AcceptanceCommand,
    ExecutionBinding,
    FrozenImplementationContract,
    compute_contract_hash,
)
from runtime.task_package import Budget, TaskPackage


def test_production_task_compiler_creates_valid_task_package() -> None:
    from runtime.task_compiler import ProductionTaskCompiler

    broker = CapabilityBroker()
    compiler = ProductionTaskCompiler(broker=broker)

    cmd = AcceptanceCommand("pytest-focused", ("pytest", "-q"), ".", 30, (0,))
    contract_hash = compute_contract_hash(
        goal_id="G-001",
        run_id="R-001",
        ceremony_trace="TRACE_A",
        base_commit="a" * 40,
        allowed_paths=("src/foo.py",),
        required_artifacts=("reviews/tasks/FOO_review.md",),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "restore", "."),
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
        allowed_paths=("src/foo.py",),
        required_artifacts=("reviews/tasks/FOO_review.md",),
        acceptance_commands=(cmd,),
        rollback_argv=("git", "restore", "."),
        data_class="INTERNAL",
        context_manifest_hash="c" * 64,
        derivation_register_hash="d" * 64,
    )
    binding = ExecutionBinding(
        transaction_key="tx-001",
        contract_id="IC-001",
        contract_hash=contract_hash,
        base_commit="a" * 40,
        worktree="/tmp/worktree",
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

    assert isinstance(package, TaskPackage)
    assert package.task_id == "IC-001"
    assert package.execution_binding == binding
    assert package.budget == budget
    assert len(package.context_refs) == 1

    # Verify capability token operations
    token = package.capability
    assert "file:read:src/foo.py" in token.operations
    assert "patch:apply:src/foo.py" in token.operations
    assert "test:run:pytest-focused" in token.operations
    assert "scope:request" in token.operations
    assert "artifact:submit:reviews/tasks/FOO_review.md" in token.operations
