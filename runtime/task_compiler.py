"""Production Task Compiler for Frozen Contracts (Gate E)."""

from __future__ import annotations

from kernel.capability import CapabilityBroker
from kernel.types import Role, StageId

from runtime.data_policy import ContextEntry
from runtime.implementation_contract import (
    ExecutionBinding,
    FrozenImplementationContract,
    validate_execution_binding,
    validate_implementation_contract,
)
from runtime.task_package import Budget, Permissions, TaskPackage


class TaskCompilationError(RuntimeError):
    """Raised when compilation of a production task package fails."""


class ProductionTaskCompiler:
    """Compiles a frozen implementation contract and execution binding into a TaskPackage."""

    def __init__(self, broker: CapabilityBroker | None = None) -> None:
        self._broker = broker or CapabilityBroker()

    def compile(
        self,
        *,
        contract: FrozenImplementationContract,
        binding: ExecutionBinding,
        context: tuple[ContextEntry, ...],
        budget: Budget,
        worker_session: str,
        current_seq: int,
    ) -> TaskPackage:
        try:
            validate_implementation_contract(contract)
            validate_execution_binding(binding)
        except (ValueError, RuntimeError) as e:
            raise TaskCompilationError(f"contract or binding invalid: {e}") from e

        if contract.contract_id != binding.contract_id:
            raise TaskCompilationError("contract_id mismatch between contract and binding")
        if contract.contract_hash != binding.contract_hash:
            raise TaskCompilationError("contract_hash mismatch between contract and binding")

        # Compile precise capability operations
        operations: list[str] = []
        for path in contract.allowed_paths:
            operations.append(f"file:read:{path}")
            operations.append(f"patch:apply:{path}")

        for cmd in contract.acceptance_commands:
            operations.append(f"test:run:{cmd.command_id}")

        operations.append("scope:request")

        for req in contract.required_artifacts:
            operations.append(f"artifact:submit:{req}")

        # Mint capability token
        token = self._broker.mint(
            goal_id=contract.goal_id,
            run_id=contract.run_id,
            stage=StageId.IMPLEMENT,
            role=Role.BUILDER,
            session=worker_session,
            operations=tuple(sorted(operations)),
            issued_seq=current_seq,
            expires_seq=current_seq + 100,
        )


        permissions = Permissions(
            write_scopes=contract.allowed_paths,
            read_scopes=contract.allowed_paths,
            mcp_servers=(),
            skills=(),
        )

        return TaskPackage(
            task_id=contract.contract_id,
            goal_id=contract.goal_id,
            run_id=contract.run_id,
            stage=StageId.IMPLEMENT,
            role=Role.BUILDER,
            objective=(
                f"Implement {contract.contract_id} under frozen contract "
                f"{contract.contract_hash[:8]}"
            ),
            capability=token,
            permissions=permissions,
            required_evidence=(),
            context_refs=tuple(c.ref for c in context),
            budget=budget,
            execution_binding=binding,
        )



