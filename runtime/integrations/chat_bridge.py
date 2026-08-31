"""Fail-closed compatibility bridge with explicit, isolated state routing."""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
from .bound_cline_transport import (
    BoundWorkerConfig,
    HandoffRecord,
    WorkerDispatchSuccess,
    _persist_handoff_once,
    _quarantine_failure_once,
    dispatch_once,
)
from .bridge_protocol import (
    BridgePaths,
    Disposition,
    RequestEnvelope,
    canonical_json,
    content_hash,
    transaction_key,
    write_once_bytes,
)

__all__ = ["BoundClineWorkerRuntime", "ChatBridgeRuntime"]

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


class BoundClineWorkerRuntime:
    """Opt-in adapter that runs one package through the bound framed transport.

    A caller must provide a configuration factory with explicit physical model and
    qualification identifiers. No provider, profile, or worktree is inferred from an
    alias such as ``paeos (main)``.
    """

    def __init__(
        self,
        *,
        state_root: Path,
        recovery_worktree: Path,
        config_factory: Callable[[TaskPackage, Path], BoundWorkerConfig],
        workspace_root: Path | None = None,
        workspace_source: Path | None = None,
        artifact_resolver: Callable[[Hash], bytes] | None = None,
        verification_command: str | None = None,
    ) -> None:
        self._paths = BridgePaths(state_root)
        self._paths.ensure()
        self._recovery_worktree = recovery_worktree.resolve()
        self._config_factory = config_factory
        self._workspace_root = workspace_root
        self._workspace_source = workspace_source
        self._artifact_resolver = artifact_resolver
        self._verification_command = verification_command

    def run(self, package: TaskPackage) -> RunOutput:
        if not _binding_matches(package):
            return _failed_run("BOUND_CLINE_UNBOUND_WORKER", "package capability does not match")
        if not package.permissions.write_scopes:
            return _failed_run("BOUND_CLINE_NO_WRITE_SCOPE", "bound runtime requires a write scope")
        exchange_id = _exchange_id(package)
        workspace = Path(
            tempfile.mkdtemp(
                prefix=f"paeos-{package.task_id}-bound-",
                dir=self._workspace_root or self._recovery_worktree,
            )
        )
        try:
            if self._workspace_source is not None:
                _seed_workspace(workspace, self._workspace_source, package.permissions.write_scopes)
                _seed_constitution(workspace, self._workspace_source)
            if self._artifact_resolver is not None:
                _materialize_context(workspace, package.context_refs, self._artifact_resolver)
            config = self._config_factory(package, workspace)
            if config.recovery_worktree.resolve() != self._recovery_worktree:
                return _failed_run(
                    "BOUND_CLINE_WORKTREE_MISMATCH", "factory returned another worktree"
                )
            now = datetime.now(UTC)
            expires = now + timedelta(seconds=max(1, package.budget.wallclock_s))
            prompt = (
                f"PAEOS bound worker task {package.goal_id}/{package.run_id}/{package.task_id}\n"
                f"Stage={package.stage.name} Role={package.role.name}\n"
                f"Workspace={workspace}\n\n{package.objective}\n"
                "Worker is implementation-only. Do not ratify, promote, spawn, or route tools."
            )
            request = RequestEnvelope(
                schema_version="paeos-bridge-v2",
                request_id=exchange_id,
                transaction_key=transaction_key(
                    request_id=exchange_id,
                    run_id=package.run_id,
                    stage_id=package.stage.name,
                    semantic_hash=content_hash(package.objective),
                    evidence_manifest_hash=content_hash(canonical_json(package.context_refs)),
                    payload_hash=content_hash(prompt),
                ),
                created_at=now.isoformat().replace("+00:00", "Z"),
                expires_at=expires.isoformat().replace("+00:00", "Z"),
                goal_id=package.goal_id,
                run_id=package.run_id,
                stage_id=package.stage.name,
                role=package.role.name,
                workspace_root=str(workspace),
                worker_transport_id="headless:bound-cline",
                worker_session_id=config.session_id,
                worker_pid=1,
                worker_tty=None,
                worker_model_provider=config.provider_id,
                worker_model_id=config.model_id,
                worker_model_family=config.model_family.value,
                semantic_hash=content_hash(package.objective),
                evidence_manifest_hash=content_hash(canonical_json(package.context_refs)),
                payload_hash=content_hash(prompt),
                allowed_dispositions=(Disposition.CONTINUE, Disposition.REMAND),
            )
            request_path = self._paths.requests / f"{exchange_id}.json"
            prompt_path = self._paths.requests / f"{exchange_id}.prompt.md"
            policy_path = self._paths.requests / f"{exchange_id}.policy.json"
            policy = {
                "allowed_tools": [
                    "editor",
                    *(["run_commands"] if self._verification_command else []),
                ],
                "artifact_path": None,
                "request_payload_hash": request.payload_hash,
                "verification_command": self._verification_command,
                "write_scopes": list(package.permissions.write_scopes),
            }
            policy_bytes = (
                json.dumps(policy, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode()
            write_once_bytes(request_path, (canonical_json(request) + "\n").encode())
            write_once_bytes(prompt_path, prompt.encode())
            write_once_bytes(policy_path, policy_bytes)
            config = replace(
                config,
                policy_path=policy_path,
                policy_sha256=hashlib.sha256(policy_bytes).hexdigest(),
            )
            result = dispatch_once(request_path, prompt_path, config)
            if isinstance(result, WorkerDispatchSuccess):
                writes = _collect_writes(workspace, package.permissions.write_scopes)
                _persist_handoff_once(
                    self._paths,
                    HandoffRecord(
                        request_id=exchange_id,
                        transaction_key=request.transaction_key,
                        candidate_head=config.candidate_head,
                        branch_name=config.branch_name,
                        session_id=config.session_id,
                        provider_id=config.provider_id,
                        model_id=config.model_id,
                        model_family=config.model_family.value,
                        policy_sha256=config.policy_sha256,
                        stdout_hash=result.stdout_hash,
                        stderr_hash=result.stderr_hash,
                        next_action="AWAIT_OVERSEER_REVIEW",
                    ),
                )
                trace = (canonical_json(result.terminal_payload) + "\n").encode()
                return RunOutput(
                    status=TaskStatus.COMPLETE,
                    writes=writes,
                    evidence=(),
                    trace=trace,
                    cost=Cost(tokens=0, wallclock_s=0.0, model_ver=config.model_id),
                )
            quarantine = _quarantine_failure_once(self._paths, result.failure)
            _persist_handoff_once(
                self._paths,
                HandoffRecord(
                    request_id=exchange_id,
                    transaction_key=request.transaction_key,
                    candidate_head=config.candidate_head,
                    branch_name=config.branch_name,
                    session_id=config.session_id,
                    provider_id=config.provider_id,
                    model_id=config.model_id,
                    model_family=config.model_family.value,
                    policy_sha256=config.policy_sha256,
                    stdout_hash=result.failure.stdout_hash,
                    stderr_hash=result.failure.stderr_hash,
                    next_action="AWAIT_OVERSEER_REVIEW",
                ),
            )
            return _failed_run(result.failure.kind.value, quarantine.failure_hash)
        except (OSError, ValueError, TypeError) as exc:
            return _failed_run("BOUND_CLINE_CONFIGURATION", str(exc))
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
