from pathlib import Path

from kernel.types import CapabilityBroker, Role, StageId
from runtime.integrations.antigravity import AntigravityRuntime
from runtime.task_package import Budget, Permissions, TaskPackage

runtime = AntigravityRuntime(workspace_root=Path("/tmp/paeos_test"))
broker = CapabilityBroker()
token = broker.mint(
    goal_id="g-1",
    run_id="r-1",
    stage=StageId.PLAN,
    role=Role.PLANNER,
    session="s-1",
    operations=(),
    issued_seq=1,
    expires_seq=2,
)
package = TaskPackage(
    task_id="test",
    goal_id="g-1",
    run_id="r-1",
    role=Role.PLANNER,
    stage=StageId.PLAN,
    objective="Just say hello world and nothing else.",
    capability=token,
    context_refs=(),
    permissions=Permissions(write_scopes=(), read_scopes=(), mcp_servers=()),
    budget=Budget(1000, 60, 1),
    required_evidence=(),
)
output = runtime.run(package)
print("TRACE START:")
print(output.trace.decode("utf-8"))
print("TRACE END")
