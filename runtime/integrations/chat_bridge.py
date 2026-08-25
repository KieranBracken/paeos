"""Fail-closed compatibility bridge with explicit, isolated state routing."""

from __future__ import annotations

import contextlib
import hashlib
import re
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from kernel.types import Hash

from runtime.claude_code import RunOutput
from runtime.task_package import Cost, TaskPackage, TaskStatus

from . import (
    _collect_writes,
    _materialize_context,
    _seed_constitution,
    _seed_workspace,
)
from .bridge_protocol import BridgePaths, write_once_bytes

__all__ = ["ChatBridgeRuntime"]

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")


def _exchange_id(package: TaskPackage) -> str:
    components = (
        package.run_id,
        package.task_id,
        package.stage.name.lower(),
    )
    if any(_SAFE_COMPONENT.fullmatch(part) is None for part in components):
        raise ValueError("unsafe bridge exchange identifier")
    return "--".join(components)


def _failed_run(code: str, message: str) -> RunOutput:
    return RunOutput(
        status=TaskStatus.FAILED,
        writes=(),
        evidence=(),
        trace=f"{code}: {message}".encode(),
        cost=Cost(
            tokens=0,
            wallclock_s=0.0,
            model_ver="chat-bridge-compatibility",
        ),
    )


def _binding_matches(package: TaskPackage) -> bool:
    binding = package.capability.bound_to
    return bool(binding.session.strip()) and (
        binding.goal_id == package.goal_id
        and binding.run_id == package.run_id
        and binding.stage is package.stage
        and binding.role is package.role
    )


def _quarantine_raw(
    paths: BridgePaths,
    *,
    exchange_id: str,
    reason: str,
    payload: bytes,
) -> Path:
    digest = hashlib.sha256(payload).hexdigest()
    destination = paths.quarantine / f"{exchange_id}--{reason}--{digest}.raw"
    with contextlib.suppress(FileExistsError):
        write_once_bytes(destination, payload)
    return destination


class ChatBridgeRuntime:
    """Compatibility transport bound to one explicit state root and worker capability."""

    def __init__(
        self,
        *,
        state_root: Path,
        workspace_root: Path | None = None,
        workspace_source: Path | None = None,
        artifact_resolver: Callable[[Hash], bytes] | None = None,
        mcp_config_path: Path | None = None,
        timeout_seconds: float = 300.0,
        poll_seconds: float = 0.25,
    ) -> None:
        self._paths = BridgePaths(state_root)
        self._paths.ensure()
        self._workspace_root = workspace_root
        self._workspace_source = (
            workspace_source.resolve() if workspace_source is not None else None
        )
        self._artifact_resolver = artifact_resolver
        self._mcp_config_path = mcp_config_path
        self._timeout_seconds = timeout_seconds
        self._poll_seconds = poll_seconds

    def run(self, package: TaskPackage) -> RunOutput:
        if not _binding_matches(package):
            return _failed_run(
                "BRIDGE_UNBOUND_WORKER",
                "capability binding does not exactly identify this package and session",
            )

        try:
            exchange_id = _exchange_id(package)
        except ValueError as exc:
            return _failed_run("BRIDGE_UNSAFE_EXCHANGE_ID", str(exc))

        prompt_path = self._paths.requests / f"{exchange_id}.prompt.md"
        output_path = self._paths.responses / f"{exchange_id}.response.md"

        if prompt_path.exists():
            return _failed_run(
                "BRIDGE_DUPLICATE_REQUEST",
                f"immutable request already exists for {exchange_id}",
            )

        if output_path.exists():
            stale = output_path.read_bytes()
            _quarantine_raw(
                self._paths,
                exchange_id=exchange_id,
                reason="stale-response",
                payload=stale,
            )
            return _failed_run(
                "BRIDGE_STALE_RESPONSE",
                f"response existed before request delivery for {exchange_id}",
            )

        workspace = Path(
            tempfile.mkdtemp(
                prefix=f"paeos-{package.task_id}-bridge-",
                dir=self._workspace_root,
            )
        )
        try:
            if self._workspace_source is not None:
                _seed_workspace(
                    workspace,
                    self._workspace_source,
                    package.permissions.write_scopes,
                )
                _seed_constitution(workspace, self._workspace_source)
            if self._artifact_resolver is not None:
                _materialize_context(
                    workspace,
                    package.context_refs,
                    self._artifact_resolver,
                )

            prompt = package.objective
            source_root = self._workspace_source or workspace
            court_path = self._paths.state_root / "court"

            prompt_content = f"""# PAEOS Task: {package.goal_id} ({package.run_id})
**Stage:** {package.stage.name} | **Role:** {package.role.name}
**Bound worker session:** {package.capability.bound_to.session}

## Objective
{package.objective}

## Strict Workspace Binding
Execute all work inside the isolated sandboxed workspace:
`{workspace.absolute()}`

The workspace source for this compatibility run is:
`{source_root}`

Do not modify repository files outside the sandbox. The capability is already bound to this
worker session. Do not spawn subagents, invoke skills, change terminals, ratify, promote to
main/trunk, or claim lifecycle advancement.

## Package Prompt
```
{prompt}
```

## Court Evidence for Builder Roles
Use real, kernel-reproducible values only. Replace both required values, then run this script
inside the sandbox:

```python
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "{source_root}")
from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.types import Role
from runtime.orchestrator import FileCourtEvidencePool

artifact_path = Path("REPLACE_WITH_THE_ARTIFACT_YOU_ACTUALLY_BUILT")
command = "REPLACE_WITH_THE_REAL_VERIFICATION_COMMAND"

proc = subprocess.run(
    shlex.split(command),
    capture_output=True,
    text=True,
    timeout=600,
)
pool = FileCourtEvidencePool(Path("{court_path}"))
pool.submit(
    "{package.run_id}",
    Evidence(
        hash=content_hash(f"{{command}}:{{proc.returncode}}".encode()),
        kind=EvidenceKind.TEST,
        claim_id="builds",
        artifact_hash=content_hash(artifact_path.read_bytes()),
        environment_hash=content_hash(sys.executable.encode()),
        reproducible_command=command,
        producer=EvidenceProducer(
            role=Role.BUILDER,
            session="{package.capability.bound_to.session}",
        ),
        determinism=Determinism.DETERMINISTIC,
        result={{"exit_code": proc.returncode, "stdout": proc.stdout}},
        attestation="pending-kernel-sig",
    ),
)
```

When complete, write the full response bytes as strict UTF-8 exactly once to:
`{output_path.absolute()}`
"""

            try:
                write_once_bytes(prompt_path, prompt_content.encode("utf-8"))
            except FileExistsError:
                return _failed_run(
                    "BRIDGE_DUPLICATE_REQUEST",
                    f"immutable request already exists for {exchange_id}",
                )

            deadline = time.monotonic() + self._timeout_seconds
            try:
                while not output_path.exists():
                    if time.monotonic() >= deadline:
                        return _failed_run(
                            "BRIDGE_RESPONSE_TIMEOUT",
                            f"no correlated response before timeout for {exchange_id}",
                        )
                    time.sleep(self._poll_seconds)
            except KeyboardInterrupt:
                return RunOutput(
                    status=TaskStatus.ABANDONED,
                    writes=(),
                    evidence=(),
                    trace=b"[ABANDONED via KeyboardInterrupt]",
                    cost=Cost(
                        tokens=0,
                        wallclock_s=0.0,
                        model_ver="chat-bridge-compatibility",
                    ),
                )

            raw_response = output_path.read_bytes()
            try:
                response_text = raw_response.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                _quarantine_raw(
                    self._paths,
                    exchange_id=exchange_id,
                    reason="malformed-response",
                    payload=raw_response,
                )
                return _failed_run(
                    "BRIDGE_MALFORMED_RESPONSE",
                    f"response is not strict UTF-8 for {exchange_id}",
                )
            if not response_text.strip():
                _quarantine_raw(
                    self._paths,
                    exchange_id=exchange_id,
                    reason="malformed-response",
                    payload=raw_response,
                )
                return _failed_run(
                    "BRIDGE_MALFORMED_RESPONSE",
                    f"response is empty or whitespace-only for {exchange_id}",
                )

            writes = _collect_writes(
                workspace,
                package.permissions.write_scopes,
            )
            return RunOutput(
                status=TaskStatus.COMPLETE,
                writes=writes,
                evidence=(),
                trace=raw_response,
                cost=Cost(
                    tokens=0,
                    wallclock_s=0.0,
                    model_ver="chat-bridge-compatibility",
                ),
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)