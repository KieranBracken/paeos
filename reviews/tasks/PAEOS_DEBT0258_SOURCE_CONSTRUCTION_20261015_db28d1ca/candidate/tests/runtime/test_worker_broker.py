"""Tests for WorkerOperationBroker (Gate E Task 4)."""

from __future__ import annotations

from pathlib import Path

import pytest
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
from runtime.task_compiler import ProductionTaskCompiler
from runtime.task_package import Budget


def _make_package(worktree: str) -> tuple[object, CapabilityBroker]:
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
        worktree=worktree,
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


def test_worker_broker_executes_allowed_read_file(tmp_path: Path) -> None:
    from runtime.task_package import TaskPackage
    from runtime.worker_broker import (
        OperationKind,
        OperationReceipt,
        OperationRequest,
        WorkerOperationBroker,
    )

    worktree = str(tmp_path)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "foo.py").write_text("print('hello')", encoding="utf-8")

    package, broker = _make_package(worktree)
    assert isinstance(package, TaskPackage)
    op_broker = WorkerOperationBroker(capability_broker=broker)

    req = OperationRequest(
        request_id="req-001",
        task_id="IC-001",
        kind=OperationKind.READ_FILE,
        arguments={"path": "src/foo.py"},
    )
    receipt = op_broker.execute(package, req, current_seq=15)
    assert isinstance(receipt, OperationReceipt)
    assert receipt.exit_code == 0


def test_worker_broker_rejects_unallowed_path(tmp_path: Path) -> None:
    from runtime.task_package import TaskPackage
    from runtime.worker_broker import (
        BrokerOperationError,
        OperationKind,
        OperationRequest,
        WorkerOperationBroker,
    )

    worktree = str(tmp_path)
    package, broker = _make_package(worktree)
    assert isinstance(package, TaskPackage)
    op_broker = WorkerOperationBroker(capability_broker=broker)

    req = OperationRequest(
        request_id="req-002",
        task_id="IC-001",
        kind=OperationKind.READ_FILE,
        arguments={"path": "secret.txt"},
    )
    with pytest.raises(BrokerOperationError, match="not permitted"):
        op_broker.execute(package, req, current_seq=15)

