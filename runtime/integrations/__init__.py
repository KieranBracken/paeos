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

from kernel.cas import CasMiss
from kernel.types import ArtifactRef, Hash, Role

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
        "During execution, you may freely consult the Research Backlog (`backlog/research/`) when it is relevant, but do not interrupt the mission to implement backlog items unless you can demonstrate they are prerequisites for successful completion.",
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
    # The court is the BUILDER's channel to submit probative evidence about the artifact it
    # produces (R5.3). Planner stages produce artifacts adjudicated by their own stage gates, not
    # the court pool — so only the Builder is told to submit, and only the Builder gets the tool.
    if package.role is Role.BUILDER:
        lines += [
            "",
            "# Submitting evidence to the court (autonomous, R5.3):",
            f"  Your run_id is EXACTLY: {package.run_id}",
            "  After you write the artifact, call the MCP tool `submit_evidence` once per required claim above.",
            "  If no required claims are listed above, you MUST submit at least one claim (claim_id: 'builds') verifying your artifact.",
            "  Pass: run_id (exactly the run_id above), claim_id, command (a REAL, PROBATIVE shell command,",
            "  e.g., pytest or test -f, whose result would DIFFER if your change were absent, run against ONLY",
            "  the file(s) you wrote), artifact_hash (sha256 of the file you wrote), exit_code, and stdout.",
            "  Vacuous evidence that does not discriminate your change from its absence will be rejected by the court.",
        ]
    return "\n".join(lines)


def _allowed_tools(package: TaskPackage) -> tuple[str, ...]:
    """The session's tool allow-list: scoped Read/Write/Edit (+ Bash for the BUILDER) + one entry
    per MCP server.

    `Bash` is required so an autonomous **builder** can RUN its reproduction command and hash the
    artifact — the probative `exit_code`/`stdout` the court's `submit_evidence` needs (DEBT-0019).
    Under `--permission-mode acceptEdits` a headless session cannot approve command execution, so
    without Bash on the allow-list every command is declined and no evidence is ever submitted.

    It is granted **only to `Role.BUILDER`** (DEBT-0021, least privilege / FP-7): PLANNER and DESIGN
    sessions produce design/plan artifacts, never run code, so they get no command-execution
    authority. This does not widen the builder's authority either — it runs in an isolated,
    ephemeral workspace; writes are filtered to `write_scopes`; and the court's independent kernel
    re-run (T2) is the real anti-forgery monitor. It is a scoped allow-list entry, not the blanket
    `--dangerously-skip-permissions`."""
    tools = ["Read", "Write", "Edit"]
    if package.role is Role.BUILDER:
        tools.append("Bash")  # only the builder RUNS its reproduction command (DEBT-0019 / 0021)
    tools.extend(f"mcp:{server}" for server in package.permissions.mcp_servers)
    return tuple(tools)


def claude_cli_invoker(package: TaskPackage, *, mcp_config_path: Path | None = None) -> CliInvoker:
    """The real invoker: run the `claude` CLI headless in the workspace. Needs auth + the target env
    (so it is not exercised by unit tests). Kept as a factory so the model/flags can be tuned. When
    `mcp_config_path` is given, the session gets `--mcp-config` so it can call the court MCP tool
    (autonomous evidence submission, R5.3)."""

    def _invoke(spec: SessionSpec) -> SessionResult:
        allowed = list(spec.allowed_tools)
        if mcp_config_path is not None:
            allowed.append("mcp__paeos-court__submit_evidence")  # autonomous evidence tool (R5.3)
        cmd = [
            "claude",
            "-p",
            spec.prompt,
            "--output-format",
            "json",
            "--allowedTools",
            ",".join(allowed),
            # Headless sessions in isolated temp sandboxes cannot answer interactive permission prompts.
            # `--dangerously-skip-permissions` allows Bash and MCP tool calls to execute without hanging.
            "--dangerously-skip-permissions",
        ]
        if mcp_config_path is not None:
            cmd += ["--mcp-config", str(mcp_config_path)]
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
        workspace_source: Path | None = None,
        artifact_resolver: Callable[[Hash], bytes] | None = None,
        mcp_config_path: Path | None = None,
        default_model: str = "claude-code",
    ) -> None:
        self._invoker = invoker  # None ⇒ built per-package from claude_cli_invoker at run()
        self._mcp_config_path = mcp_config_path  # --mcp-config for live sessions (autonomous, R5.3)
        self._workspace_root = workspace_root
        # Repo root to seed each session's workspace from, so an *edit* objective has the current
        # file content to modify (B2.I) and the constitution to cite (B2.J). None ⇒ empty workspace.
        self._workspace_source = workspace_source
        # Resolves an injected context ref (design, plan, matched scars, the adversary bundle) to
        # its bytes to materialise into the workspace (B2.J). Typically `CAS.get`.
        self._artifact_resolver = artifact_resolver
        self._default_model = default_model

    def run(self, package: TaskPackage) -> RunOutput:
        workspace = Path(
            tempfile.mkdtemp(prefix=f"paeos-{package.task_id}-", dir=self._workspace_root)
        )
        try:
            if self._workspace_source is not None:
                _seed_workspace(workspace, self._workspace_source, package.permissions.write_scopes)
                _seed_constitution(workspace, self._workspace_source)  # B2.J: the law
            if self._artifact_resolver is not None:
                # B2.J: injected context (design/plan/scars/bundle) into the workspace
                _materialize_context(workspace, package.context_refs, self._artifact_resolver)
            spec = SessionSpec(
                workspace=workspace,
                prompt=build_prompt(package),
                allowed_tools=_allowed_tools(package),
                read_scopes=package.permissions.read_scopes,
                timeout_s=package.budget.wallclock_s,
            )
            # Only the Builder submits to the court (its evidence channel); Planner stages must
            # not write the run's evidence pool (their citations aren't court-reproducible).
            mcp_cfg = self._mcp_config_path if package.role is Role.BUILDER else None
            invoker = (
                self._invoker
                if self._invoker is not None
                else claude_cli_invoker(package, mcp_config_path=mcp_cfg)
            )
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


def _seed_constitution(workspace: Path, source: Path) -> None:
    """Copy the constitution into the session so agents can *read and cite the law* (B2.J) — the
    live Planner blocked without it ("constitution/ does not exist… nothing to cite")."""
    src = source / "constitution"
    if src.is_dir():
        shutil.copytree(src, workspace / "constitution", dirs_exist_ok=True)


def _materialize_context(
    workspace: Path, context_refs: tuple[ArtifactRef, ...], resolve: Callable[[Hash], bytes]
) -> None:
    """Write each injected context artifact (design, plan, matched scars, the adversary bundle) into
    a `context/` dir so the session can actually read it (B2.J). Refs are content hashes; a ref
    whose blob is absent is skipped (best-effort — evidence refs need not be blobs)."""
    ctx = workspace / "context"
    for ref in context_refs:
        try:
            content = resolve(ref.hash)
        except CasMiss:
            continue
        ctx.mkdir(parents=True, exist_ok=True)
        (ctx / f"{ref.type}-{ref.hash[:12]}.txt").write_bytes(content)


def _seed_workspace(workspace: Path, source: Path, write_scopes: tuple[str, ...]) -> None:
    """Copy the current repo files into the session workspace, skipping heavy build/temp dirs."""
    ignore = shutil.ignore_patterns(
        ".git", ".venv", "state_*", ".pytest_cache", "__pycache__", ".claude", "*.pyc", "*.pyo"
    )
    shutil.copytree(source, workspace, ignore=ignore, dirs_exist_ok=True)


def _is_build_byproduct(rel: str) -> bool:
    """A compiler by-product (Python bytecode), never authored source (DEBT-0022).

    Running a `builds` command like `python -m py_compile lib/x.py` emits `__pycache__/x.*.pyc`.
    If that `.pyc` is collected it can become `build.artifacts[0]` — the *reviewed* artifact — and
    the adversary/court then have to materialise sourceless, interpreter-version-coupled bytecode,
    which is fragile (the M3 seal/block asymmetry). Excluding it keeps the reviewed artifact the
    deterministic Python **source** the goal actually authored."""
    return rel.endswith((".pyc", ".pyo")) or "__pycache__" in rel.split("/")


def _collect_writes(workspace: Path, write_scopes: tuple[str, ...]) -> tuple[AgentWrite, ...]:
    """Every file the session wrote in its workspace, as repo-relative paths — filtered to scope.
    A write outside `write_scopes` is dropped (never becomes an artifact); so is compiled Python
    bytecode (`__pycache__/*.pyc`), a build by-product rather than authored source (DEBT-0022)."""
    writes: list[AgentWrite] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if within_scopes(rel, write_scopes) and not _is_build_byproduct(rel):
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
