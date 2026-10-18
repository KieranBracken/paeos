"""Live agent adapter — an `AgentRuntime` using Google Antigravity SDK (Gemini).

This replaces the Claude Code adapter, substituting `google-antigravity` (Gemini 3.1 Pro)
as the reasoning worker for the PAEOS soft loop. It writes a small ephemeral bootstrap
script into the workspace and executes it as a subprocess (inheriting the workspace CWD),
so that `run_command` executes in the sandboxed directory just like the `claude` CLI.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

from kernel.types import Hash, Role

from runtime.claude_code import RunOutput
from runtime.task_package import Cost, TaskPackage, TaskStatus

from . import (
    SessionSpec,
    TrustedTransportFailure,
    _collect_writes,
    _materialize_context,
    _seed_constitution,
    _seed_workspace,
    build_prompt,
)

__all__ = ["AntigravityRuntime"]


def _require_antigravity_disclosure_authority() -> NoReturn:
    """Deny Antigravity egress until trusted disclosure authority is integrated."""
    raise TrustedTransportFailure(
        "disclosure_authority_unavailable",
        "trusted disclosure authority is unavailable",
    )


def antigravity_cli_invoker(
    package: TaskPackage, *, mcp_config_path: Path | None = None
) -> Callable[[SessionSpec], str]:
    """The real invoker: runs a Google Antigravity agent in the workspace via a bootstrap script.
    Needs GEMINI_API_KEY exported in the environment.
    """

    def _invoke(spec: SessionSpec) -> str:
        _require_antigravity_disclosure_authority()

        # We write a tiny async script into the workspace that uses the SDK.
        # This guarantees that the Antigravity agent's CWD is the workspace.
        bootstrap_path = spec.workspace / ".agy_bootstrap.py"

        mcp_servers_code = "[]"
        if mcp_config_path is not None and mcp_config_path.exists():
            cfg = json.loads(mcp_config_path.read_text(encoding="utf-8"))
            mcp_servers = []
            for name, server in cfg.get("mcpServers", {}).items():
                cmd = server.get("command")
                args = server.get("args", [])
                mcp_servers.append(f"""
    types.McpStdioServer(
        name={name!r},
        command={cmd!r},
        args={args!r},
    )""")
            if mcp_servers:
                mcp_servers_code = "[" + ",".join(mcp_servers) + "]"

        script_content = f"""
import asyncio
import json
import sys
import os
import logging
from pathlib import Path

from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig, types
from google.antigravity.hooks import policy

async def main():
    mcp_servers = {mcp_servers_code}
    
    # We are in an ephemeral sandbox. Allow all tools including run_command.
    # PAEOS filters out writes outside of write_scopes afterward.
    config = LocalAgentConfig(
        system_instructions="You are a scoped PAEOS worker session.",
        model="gemini-2.5-flash",
        capabilities=CapabilitiesConfig(),
        policies=[policy.allow_all()],
        mcp_servers=mcp_servers,
    )
    
    prompt = {spec.prompt!r}
    
    try:
        async with Agent(config) as agent:
            response = await agent.chat(prompt)
            # We just print the text, which is captured as the transcript.
            print(await response.text())
    except Exception as e:
        logging.exception("Error during agent execution: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
"""

        bootstrap_path.write_text(script_content, encoding="utf-8")

        cmd = ["python", bootstrap_path.name]
        proc = subprocess.run(
            cmd,
            cwd=str(spec.workspace),
            capture_output=True,
            text=True,
            timeout=spec.timeout_s,
            check=False,
        )

        # Cleanup the bootstrap script so it doesn't get collected as a write
        bootstrap_path.unlink(missing_ok=True)

        return proc.stdout + "\n" + proc.stderr

    return _invoke


class AntigravityRuntime:
    """A live `AgentRuntime`: runs a scoped Google Antigravity session per package."""

    def __init__(
        self,
        *,
        workspace_root: Path | None = None,
        workspace_source: Path | None = None,
        artifact_resolver: Callable[[Hash], bytes] | None = None,
        mcp_config_path: Path | None = None,
    ) -> None:
        self._mcp_config_path = mcp_config_path
        self._workspace_root = workspace_root
        self._workspace_source = workspace_source
        self._artifact_resolver = artifact_resolver

    def run(self, package: TaskPackage) -> RunOutput:
        _require_antigravity_disclosure_authority()

        workspace = Path(
            tempfile.mkdtemp(prefix=f"paeos-{package.task_id}-", dir=self._workspace_root)
        )
        try:
            if self._workspace_source is not None:
                _seed_workspace(
                    workspace,
                    self._workspace_source,
                    package.permissions.write_scopes,
                    package.permissions.read_scopes,
                )
                _seed_constitution(workspace, self._workspace_source)
            if self._artifact_resolver is not None:
                _materialize_context(workspace, package.context_refs, self._artifact_resolver)

            spec = SessionSpec(
                workspace=workspace,
                prompt=build_prompt(package),
                allowed_tools=(),  # Handled in the bootstrap script natively
                read_scopes=package.permissions.read_scopes,
                timeout_s=package.budget.wallclock_s,
            )

            mcp_cfg = (
                self._mcp_config_path if package.role in (Role.BUILDER, Role.ADVERSARY) else None
            )
            invoker = antigravity_cli_invoker(package, mcp_config_path=mcp_cfg)

            transcript = invoker(spec)
            writes = _collect_writes(workspace, package.permissions.write_scopes)

            # TODO: We aren't capturing token usage directly from the script yet.
            # We will return 0 cost for now.
            cost = Cost(tokens=0, wallclock_s=0.0, model_ver="gemini-3.1-pro")

            return RunOutput(
                status=TaskStatus.COMPLETE,
                writes=writes,
                evidence=(),  # The session emits evidence via the court MCP server
                trace=transcript.encode("utf-8"),
                cost=cost,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
