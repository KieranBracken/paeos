"""The Court MCP server (R5.3) — the vendor edge where a live worker submits evidence over MCP.

A worker (a live `claude` session connected via `claude --mcp-config`) calls the `submit_evidence`
tool; the server writes the evidence into a durable `FileCourtEvidencePool` (`<dir>/<run_id>.jsonl`)
that the `SoftLoop` reads through `McpWorkerTransport` (an `EvidenceSource`). This module — and only
this one — imports the official MCP SDK: it is the **vendor boundary** under `runtime/transports/`.
The core runtime never imports MCP (AI-001, scoped to exclude the transports layer).

Deployment: `python -m runtime.transports.mcp.court_server <pool_dir>` is the stdio server the
`--mcp-config` launches. Tests drive `submit_evidence` in-process via `MCPServer.call_tool`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.sandbox import SandboxError, allowlisted_path, canonical_command, run_sandboxed_argv
from kernel.types import Role
from mcp.server import MCPServer

from runtime.orchestrator import FileCourtEvidencePool

__all__ = ["build_court_mcp_server", "main"]

_FORBIDDEN_COMMAND_BYTES = frozenset(";&|<>`$")
_FORBIDDEN_EXECUTABLES = frozenset({"sh", "bash", "zsh", "fish", "env", "exec", "cd"})
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _validated_identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be one safe path component")
    return value


def _validated_workspace(value: str, allowed_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ValueError("workspace_root must be an absolute regular directory")
    resolved = path.resolve(strict=True)
    if path != resolved:
        raise ValueError("workspace_root must not traverse symlinked components")
    if not resolved.is_relative_to(allowed_root.resolve(strict=True)):
        raise ValueError("workspace_root is outside the configured worker workspace root")
    return resolved


def _validated_argv(value: list[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise ValueError("argv must be a non-empty list of strings")
    if not Path(value[0]).is_absolute():
        raise ValueError("argv executable must be absolute")
    if any(Path(item).is_absolute() for item in value[1:]):
        raise ValueError("argv arguments must be relative to the verifier workspace")
    if any(any(character in _FORBIDDEN_COMMAND_BYTES for character in item) for item in value):
        raise ValueError("shell expansion is forbidden in structured argv")
    if Path(value[0]).name in _FORBIDDEN_EXECUTABLES or "-c" in value:
        raise ValueError("shell and nested interpreter commands are forbidden")
    return tuple(value)


def build_court_mcp_server(
    pool_dir: str | Path,
    *,
    workspace_root: str | Path | None = None,
) -> MCPServer:
    """An MCP server exposing `submit_evidence`, writing into the pool at `pool_dir`. The worker
    submits; the evidence is inert until the kernel adjudicates (SI-2)."""
    server = MCPServer("paeos-court")
    pool = FileCourtEvidencePool(Path(pool_dir))
    if workspace_root is None:
        allowed_workspace_root: Path | None = None
    else:
        requested_root = Path(workspace_root)
        if requested_root.is_symlink():
            raise ValueError("workspace_root must not be a symlink")
        allowed_workspace_root = requested_root.resolve(strict=True)
        if not allowed_workspace_root.is_dir() or allowed_workspace_root.is_symlink():
            raise ValueError("workspace_root must be an existing non-symlink directory")

    @server.tool()
    def submit_evidence(
        run_id: str,
        claim_id: str,
        argv: list[str],
        workspace_root: str,
        artifact_path: str,
    ) -> str:
        """Execute and submit one physically-derived deterministic observation."""
        if allowed_workspace_root is None:
            raise ValueError("MCP server has no configured worker workspace root")
        run_id = _validated_identifier(run_id, "run_id")
        claim_id = _validated_identifier(claim_id, "claim_id")
        workspace = _validated_workspace(workspace_root, allowed_workspace_root)
        command_argv = _validated_argv(argv)
        artifact = Path(artifact_path)
        if artifact.is_absolute() or ".." in artifact.parts:
            raise ValueError("artifact_path must be relative to the worker workspace")
        candidate_artifact = workspace / artifact
        artifact = candidate_artifact.resolve(strict=False)
        if candidate_artifact != artifact:
            raise ValueError("artifact_path must not traverse symlinked components")
        if artifact.is_symlink() or not artifact.is_file() or not artifact.is_relative_to(workspace):
            raise ValueError("artifact_path is not a regular file in the worker workspace")
        environment = {"PATH": allowlisted_path(), "LC_ALL": "C"}
        try:
            observation = run_sandboxed_argv(
                command_argv,
                cwd=workspace,
                environment=environment,
            )
        except SandboxError:
            raise
        exit_code = 124 if observation.timed_out else observation.exit_code
        result = {
            "argv": list(observation.argv),
            "cwd": ".",
            "environment_fingerprint": observation.environment_fingerprint,
            "executable": observation.executable,
            "executable_version": observation.executable_version,
            "exit_code": exit_code,
            "stderr_sha256": content_hash(observation.stderr.encode()),
            "stdout_sha256": content_hash(observation.stdout.encode()),
        }
        command = canonical_command(command_argv, environment=environment)
        evidence_identity = {
            "claim_id": claim_id,
            "command": command,
            "result": result,
            "artifact_hash": content_hash(artifact.read_bytes()),
        }
        pool.submit(
            run_id,
            Evidence(
                hash=content_hash(
                    json.dumps(evidence_identity, sort_keys=True, separators=(",", ":")).encode(
                        "utf-8"
                    )
                ),
                kind=EvidenceKind.TEST,
                claim_id=claim_id,
                artifact_hash=evidence_identity["artifact_hash"],
                environment_hash=observation.environment_fingerprint,
                reproducible_command=command,
                producer=EvidenceProducer(role=Role.BUILDER, session="mcp"),
                determinism=Determinism.DETERMINISTIC,
                result=result,
                attestation="pending-kernel-sig",
            ),
        )
        return f"submitted {claim_id} for run {run_id}"

    return server


def main() -> None:  # pragma: no cover - the live stdio entrypoint
    pool_dir = sys.argv[1] if len(sys.argv) > 1 else "ops/state/court"
    workspace_root = sys.argv[2] if len(sys.argv) > 2 else None
    build_court_mcp_server(pool_dir, workspace_root=workspace_root).run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
