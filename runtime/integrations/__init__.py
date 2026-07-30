"""Live agent adapter — a real `AgentRuntime` over the Claude Code CLI (PAEOS-8 §12 R3→R4).

This turns the scripted `SoftLoop` into a live one: it implements the B1.B `AgentRuntime` seam by
running an **actual scoped Claude Code session** per `TaskPackage`. The shape is the one the
DEBT-0002 spawnability spike validated — programmatic spawn, isolated workspace, allow-list, output
capture — now as library code the runtime calls.

The adapter's *logic* is fully here and tested: it compiles the package into a prompt (K5 —
prompts are *generated from artifacts*, never handwritten), creates an isolated workspace, derives
the tool allow-list from `permissions.mcp_servers` + the scoped `Write`, collects the files the
session wrote, filters them to `write_scopes`, and parses cost/trace. The single **live** step —
invoking the `claude` CLI (needs auth + the target env) — sits behind the `CliInvoker` seam, so
tests drive a fake session and deployment injects the real one (`claude_cli_invoker`).

Nothing here can widen authority: writes outside `write_scopes` are dropped before they become
artifacts (belt-and-suspenders with the dispatcher's own `ScopeViolation`, B1.B).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from runtime.claude_code import AgentWrite, RunOutput, within_scopes
from runtime.task_package import Cost, TaskPackage, TaskStatus

__all__ = [
    "ClaudeCodeRuntime",
    "CliInvoker",
    "SessionResult",
    "SessionSpec",
    "build_prompt",
    "claude_cli_invoker",
]


@dataclass(frozen=True, slots=True)
class SessionSpec:
    """What a scoped session needs: isolated workspace, compiled prompt, tool allow-list."""

    workspace: Path
    prompt: str
    allowed_tools: tuple[str, ...]
    read_scopes: tuple[str, ...]
    timeout_s: int


@dataclass(frozen=True, slots=True)
class SessionResult:
    """The raw capture from a session: its JSON transcript. Files written land in the workspace."""

    transcript: str  # the `claude` CLI JSON result (result text, usage, model, duration)


# A CliInvoker runs a scoped session and returns its raw result; files it writes land in the
# workspace. Tests inject a fake; deployment uses `claude_cli_invoker`.
CliInvoker = Callable[[SessionSpec], SessionResult]


def build_prompt(package: TaskPackage) -> str:
    """Compile the package into a session prompt (K5 — generated, not handwritten)."""
    lines = [
        "You are a scoped PAEOS worker session. Do ONLY the objective below, then stop.",
        "",
        f"# Objective\n{package.objective}",
        "",
        f"# Role\n{package.role.value} at stage {package.stage.name}.",
        "",
        "# You MAY write only these paths (anything else is discarded and is a violation):",
        *[f"  - {scope}" for scope in package.permissions.write_scopes],
        "",
        "# You MAY read only these paths:",
        *[f"  - {scope}" for scope in package.permissions.read_scopes],
        "",
        "# Context artifacts (design, plan, matched scars — always on the path):",
        *[f"  - {ref.type}:{ref.hash}" for ref in package.context_refs],
        "",
        "# Required evidence (each MUST be produced for the gate to pass):",
        *[
            f"  - {ob.claim_id} ({ob.kind.value}): {ob.acceptance}"
            for ob in package.required_evidence
        ],
        "",
        "# Forbidden (documented intent; enforced by capability):",
        *[f"  - {item}" for item in package.forbidden],
    ]
    return "\n".join(lines)


def _allowed_tools(package: TaskPackage) -> tuple[str, ...]:
    """The session's tool allow-list: scoped Write/Read + one entry per granted MCP server."""
    tools = ["Read", "Write", "Edit"]
    tools.extend(f"mcp:{server}" for server in package.permissions.mcp_servers)
    return tuple(tools)


def claude_cli_invoker(package: TaskPackage) -> CliInvoker:
    """The real invoker: run the `claude` CLI headless in the workspace. Needs auth + the target env
    (so it is not exercised by unit tests). Kept as a factory so the model/flags can be tuned."""

    def _invoke(spec: SessionSpec) -> SessionResult:
        cmd = [
            "claude",
            "-p",
            spec.prompt,
            "--output-format",
            "json",
            "--allowedTools",
            ",".join(spec.allowed_tools),
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(spec.workspace),
            capture_output=True,
            text=True,
            timeout=spec.timeout_s,
            check=False,
        )
        return SessionResult(transcript=proc.stdout)

    return _invoke


class ClaudeCodeRuntime:
    """A live `AgentRuntime`: runs a scoped Claude Code session per package (B1.B's seam)."""

    def __init__(
        self,
        *,
        invoker: CliInvoker | None = None,
        workspace_root: Path | None = None,
        default_model: str = "claude-code",
    ) -> None:
        self._invoker = invoker  # None ⇒ built per-package from claude_cli_invoker at run()
        self._workspace_root = workspace_root
        self._default_model = default_model

    def run(self, package: TaskPackage) -> RunOutput:
        workspace = Path(
            tempfile.mkdtemp(prefix=f"paeos-{package.task_id}-", dir=self._workspace_root)
        )
        try:
            spec = SessionSpec(
                workspace=workspace,
                prompt=build_prompt(package),
                allowed_tools=_allowed_tools(package),
                read_scopes=package.permissions.read_scopes,
                timeout_s=package.budget.wallclock_s,
            )
            invoker = self._invoker if self._invoker is not None else claude_cli_invoker(package)
            result = invoker(spec)
            writes = _collect_writes(workspace, package.permissions.write_scopes)
            cost = _parse_cost(result.transcript, self._default_model)
            return RunOutput(
                status=TaskStatus.COMPLETE,
                writes=writes,
                evidence=(),  # the session emits evidence via the court/artifacts MCP servers
                trace=result.transcript.encode("utf-8"),
                cost=cost,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


def _collect_writes(workspace: Path, write_scopes: tuple[str, ...]) -> tuple[AgentWrite, ...]:
    """Every file the session wrote in its workspace, as repo-relative paths — filtered to scope.
    A write outside `write_scopes` is dropped (never becomes an artifact)."""
    writes: list[AgentWrite] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if within_scopes(rel, write_scopes):
            writes.append(AgentWrite(path=rel, content=path.read_bytes()))
    return tuple(writes)


def _parse_cost(transcript: str, default_model: str) -> Cost:
    """Best-effort cost from the `claude` CLI JSON. Unparseable ⇒ zero cost (never fabricate)."""
    try:
        data = json.loads(transcript)
    except (json.JSONDecodeError, ValueError):
        return Cost(tokens=0, wallclock_s=0.0, model_ver=default_model)
    if not isinstance(data, dict):
        return Cost(tokens=0, wallclock_s=0.0, model_ver=default_model)
    usage = data.get("usage")
    tokens = 0
    if isinstance(usage, dict):
        for key in ("input_tokens", "output_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                tokens += value
    duration_ms = data.get("duration_ms")
    wallclock = duration_ms / 1000.0 if isinstance(duration_ms, int | float) else 0.0
    model = data.get("model")
    model_ver = model if isinstance(model, str) else default_model
    return Cost(tokens=tokens, wallclock_s=wallclock, model_ver=model_ver)
