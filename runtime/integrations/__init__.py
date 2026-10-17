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

import hashlib
import json
import os
import shutil
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kernel.cas import CasMiss
from kernel.types import ArtifactRef, Hash, Role

from runtime.claude_code import AgentWrite, RunOutput, within_scopes
from runtime.integrations.process_supervisor import (
    ProcessLifecycleState,
    ProcessObservation,
    run_bounded_process,
)
from runtime.integrations.worker_confinement import prepare_provider_launch
from runtime.task_package import Cost, TaskPackage, TaskStatus

__all__ = [
    "ClaudeCodeRuntime",
    "CliInvoker",
    "HostClineCriticTransport",
    "SessionResult",
    "SessionSpec",
    "TrustedTransportFailure",
    "build_prompt",
    "claude_cli_invoker",
]

from runtime.integrations.provider_broker import HostClineCriticTransport


@dataclass(frozen=True, slots=True)
class SessionSpec:
    """What a scoped session needs: isolated workspace, compiled prompt, tool allow-list."""

    workspace: Path
    prompt: str
    allowed_tools: tuple[str, ...]
    read_scopes: tuple[str, ...]
    timeout_s: int
    lifecycle_state_path: Path | None = None
    task_id: str = ""
    goal_id: str = ""
    run_id: str = ""
    stage: str = ""


class TrustedTransportFailure(RuntimeError):
    """A trusted worker transport rejected or failed a session without a usable result."""

    def __init__(self, code: str = "transport_protocol_failure", message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


class ContextMaterializationFailure(RuntimeError):
    """A required injected context could not be materialized; the session must not launch."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SessionResult:
    """The raw capture from a session: its JSON transcript. Files written land in the workspace."""

    transcript: str  # the `claude` CLI JSON result (result text, usage, model, duration)
    stderr: bytes = b""
    lifecycle_state: str = "RETURNED"
    executable: str = ""
    executable_version: str = ""
    cwd: str = ""
    environment_fingerprint: str = ""
    exit_code: int | None = 0
    failure_code: str | None = None
    stdout_sha256: str = ""
    stderr_sha256: str = ""
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    argv: tuple[str, ...] = ()
    profile_sha256: str = ""
    workspace: str = ""
    confinement_canaries: dict[str, object] | None = None
    actual_provider: str = ""
    actual_model: str = ""
    actual_family: str = ""


# A CliInvoker runs a scoped session and returns its raw result; files it writes land in the
# workspace. Tests inject a fake; deployment uses `claude_cli_invoker`.
CliInvoker = Callable[[SessionSpec], SessionResult]


def _bounded_session_result(
    spec: SessionSpec,
    argv: list[str],
    *,
    provider: str,
) -> SessionResult:
    """Launch a provider through the durable process boundary.

    The process supervisor owns all observations. This adapter may validate the provider's
    transcript, but it cannot supply exit codes, output, or artifact hashes itself.
    """

    effective_timeout = min(spec.timeout_s or 1800, 1800)
    confined_argv, environment, _policy = prepare_provider_launch(
        tuple(argv), workspace=spec.workspace, parent_environment=os.environ
    )
    observation: ProcessObservation = run_bounded_process(
        confined_argv,
        cwd=spec.workspace,
        environment=environment,
        start_timeout_s=min(30.0, max(1.0, float(effective_timeout))),
        execution_timeout_s=float(effective_timeout),
        state_path=spec.lifecycle_state_path or spec.workspace / ".paeos-provider-lifecycle.json",
    )
    if (
        observation.lifecycle_state is not ProcessLifecycleState.RETURNED
        or observation.exit_code != 0
        or not observation.stdout.strip()
    ):
        raise RuntimeError(
            f"{provider} CLI did not produce a completed transcript "
            f"(state={observation.lifecycle_state.value}, exit={observation.exit_code}, "
            f"stdout_sha256={hashlib.sha256(observation.stdout).hexdigest()}, "
            f"stderr_sha256={hashlib.sha256(observation.stderr).hexdigest()})"
        )
    try:
        transcript = observation.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"{provider} CLI produced a non-UTF-8 transcript") from exc
    return SessionResult(
        transcript=transcript,
        stderr=observation.stderr,
        lifecycle_state=observation.lifecycle_state.value,
        executable=observation.executable,
        executable_version=observation.executable_version,
        cwd=observation.cwd,
        environment_fingerprint=observation.environment_fingerprint,
        exit_code=observation.exit_code,
    )


def build_prompt(package: TaskPackage) -> str:
    """Compile the package into a session prompt (K5 — generated, not handwritten)."""
    lines = [
        "You are a scoped PAEOS worker session. Do ONLY the objective below, then stop.",
    ]
    if package.role is not Role.ADVERSARY:
        lines += [
            "During execution, you may freely consult the Research Backlog (`backlog/research/`)",
            "when it is relevant, but do not interrupt the mission to implement backlog items unless",
            "you can demonstrate they are prerequisites for successful completion.",
        ]
    lines += [
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
            "# Evidence boundary:",
            "  Builder prose, stdout, stderr, exit codes, test claims, and MCP submissions are non-authoritative.",
            "  Do not manufacture observations or attempt to qualify the change. The trusted runtime",
            "  materializes this workspace after L12 and independently executes the frozen L11 verifier",
            "  obligations at L13. If a Court MCP tool is unavailable, continue only with implementation",
            "  and report the limitation truthfully; the runtime will fail closed if it cannot verify.",
        ]
    elif package.role is Role.ADVERSARY:
        lines += [
            "",
            "# Review input boundary:",
            "  The sealed evidence bundle is physically materialized only under `context/`.",
            "  Inspect the candidate and evidence files in `context/`; their names identify the",
            "  content type and hash prefix. Do not search or read builder/planner source paths.",
            "# Submitting the Adversary Report:",
            f"  Your run_id is EXACTLY: {package.run_id}",
            "  Write your report to `review/adversary_report.md` and call `submit_artifact`",
            "  with path `review/adversary_report.md` so your report is sealed.",
            "  Your report MUST conclude with a line: 'VERDICT: PASS' or 'VERDICT: BLOCK'.",
        ]
    return "\n".join(lines)


def _allowed_tools(package: TaskPackage) -> tuple[str, ...]:
    tools = ["Read", "Write", "Edit"]
    if package.role in (Role.BUILDER, Role.ADVERSARY):
        tools.append("Bash")  # builder and adversary run commands to verify/attack
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
            # Headless sessions in isolated temp sandboxes cannot answer prompts.
            # `--dangerously-skip-permissions` allows Bash and MCP calls to run.
            "--dangerously-skip-permissions",
        ]
        if mcp_config_path is not None:
            cmd += ["--mcp-config", str(mcp_config_path)]
        return _bounded_session_result(spec, cmd, provider="claude")

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
        state_root: Path | None = None,
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
        self._state_root = state_root.resolve() if state_root is not None else None
        self._default_model = default_model

    def run(self, package: TaskPackage) -> RunOutput:
        mcp_cfg = self._mcp_config_path if package.role in (Role.BUILDER, Role.ADVERSARY) else None
        invoker = (
            self._invoker
            if self._invoker is not None
            else claude_cli_invoker(package, mcp_config_path=mcp_cfg)
        )
        return self._run_with_invoker(package, invoker)

    def _run_with_invoker(self, package: TaskPackage, invoker: CliInvoker) -> RunOutput:
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
                _seed_constitution(workspace, self._workspace_source)  # B2.J: the law
            if package.role is Role.ADVERSARY and self._artifact_resolver is None:
                return RunOutput(
                    status=TaskStatus.FAILED,
                    writes=(),
                    evidence=(),
                    trace=b"trusted_context_failure:sealed_bundle_resolver_missing",
                    cost=Cost(tokens=0, wallclock_s=0.0, model_ver=self._default_model),
                    workspace_identity=hashlib.sha256(str(workspace).encode("utf-8")).hexdigest(),
                    environment_identity="",
                    failure_code="sealed_bundle_resolver_missing",
                )
            if self._artifact_resolver is not None:
                # B2.J: injected context (design/plan/scars/bundle) into the workspace. A sealed
                # adversary bundle is required context: a CAS miss must prevent the worker from
                # launching rather than producing a plausible PASS over an empty chamber.
                try:
                    _materialize_context(
                        workspace,
                        package.context_refs,
                        self._artifact_resolver,
                        required=package.role is Role.ADVERSARY,
                    )
                except ContextMaterializationFailure as exc:
                    return RunOutput(
                        status=TaskStatus.FAILED,
                        writes=(),
                        evidence=(),
                        trace=f"trusted_context_failure:{exc.code}".encode("ascii"),
                        cost=Cost(tokens=0, wallclock_s=0.0, model_ver=self._default_model),
                        workspace_identity=hashlib.sha256(str(workspace).encode("utf-8")).hexdigest(),
                        environment_identity="",
                        failure_code=exc.code,
                    )
            spec = SessionSpec(
                workspace=workspace,
                prompt=build_prompt(package),
                allowed_tools=_allowed_tools(package),
                read_scopes=package.permissions.read_scopes,
                timeout_s=package.budget.wallclock_s,
                lifecycle_state_path=_session_state_path(self._state_root, package),
                task_id=package.task_id,
                goal_id=package.goal_id,
                run_id=package.run_id,
                stage=package.stage.name,
            )
            try:
                result = invoker(spec)
            except TrustedTransportFailure as exc:
                # A trusted transport rejection is already fail-closed. Preserve only its
                # bounded classification; never copy an untrusted exception string, provider
                # output, or stderr into the governed trace. Returning FAILED lets the caller
                # ledger the stage and route a durable remand instead of silently crashing the
                # parent loop.
                return RunOutput(
                    status=TaskStatus.FAILED,
                    writes=(),
                    evidence=(),
                    trace=f"trusted_transport_failure:{exc.code}".encode("ascii"),
                    cost=Cost(tokens=0, wallclock_s=0.0, model_ver=self._default_model),
                    workspace_identity=hashlib.sha256(str(spec.workspace).encode("utf-8")).hexdigest(),
                    environment_identity="",
                    failure_code=exc.code,
                )
            failure_code = result.failure_code
            failed_state = result.lifecycle_state != "RETURNED" or result.exit_code not in (0, None)
            if failed_state:
                # A supervisor failure may occur after partial workspace writes. Do not collect
                # those writes: a failed provider result can never create a candidate artifact.
                bounded_code = failure_code if isinstance(failure_code, str) else "worker_execution_failure"
                return RunOutput(
                    status=TaskStatus.FAILED,
                    writes=(),
                    evidence=(),
                    trace=f"trusted_worker_failure:{bounded_code}".encode("ascii"),
                    cost=Cost(tokens=0, wallclock_s=0.0, model_ver=self._default_model),
                    workspace_identity=hashlib.sha256(str(spec.workspace).encode("utf-8")).hexdigest(),
                    environment_identity=result.environment_fingerprint,
                    failure_code=bounded_code,
                )
            writes = _collect_writes(workspace, package.permissions.write_scopes)
            cost = _parse_cost(result.transcript, self._default_model)
            return RunOutput(
                status=TaskStatus.COMPLETE,
                writes=writes,
                evidence=(),  # the session emits evidence via the court/artifacts MCP servers
                trace=result.transcript.encode("utf-8"),
                cost=cost,
                workspace_identity=hashlib.sha256(str(spec.workspace).encode("utf-8")).hexdigest(),
                environment_identity=result.environment_fingerprint,
                failure_code=None,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


def _seed_constitution(workspace: Path, source: Path) -> None:
    """Copy the constitution into the session so agents can *read and cite the law* (B2.J) — the
    live Planner blocked without it ("constitution/ does not exist… nothing to cite")."""
    src = source / "constitution"
    if src.is_dir():
        shutil.copytree(src, workspace / "constitution", dirs_exist_ok=True)


def _session_state_path(state_root: Path | None, package: TaskPackage) -> Path | None:
    """Map a package to a stable private state path without trusting package text as a filename."""

    if state_root is None:
        return None
    identity = f"{package.goal_id}:{package.run_id}:{package.task_id}:{package.stage.name}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return state_root / "provider-runs" / f"{digest}.json"


def _materialize_context(
    workspace: Path,
    context_refs: tuple[ArtifactRef, ...],
    resolve: Callable[[Hash], bytes],
    *,
    required: bool = False,
) -> None:
    """Write each injected context artifact (design, plan, matched scars, the adversary bundle) into
    a `context/` dir so the session can actually read it (B2.J). Refs are content hashes. Required
    review refs fail closed when a blob is absent; optional planner context retains the historical
    best-effort behavior."""
    ctx = workspace / "context"
    for ref in context_refs:
        if _is_quarantined_relative(str(ref.type)):
            raise ValueError(f"quarantined context type is not readable by a worker: {ref.type!r}")
        try:
            content = resolve(ref.hash)
        except CasMiss:
            if required:
                raise ContextMaterializationFailure("sealed_bundle_context_missing") from None
            continue
        except Exception as exc:
            if required:
                raise ContextMaterializationFailure("sealed_bundle_context_resolution_failure") from exc
            raise
        ctx.mkdir(parents=True, exist_ok=True)
        (ctx / f"{ref.type}-{ref.hash[:12]}.txt").write_bytes(content)


_QUARANTINED_SEED_NAMES = frozenset(
    {"sentium", "credentials.py", ".env", ".env.local", "api_keys.json"}
)

# The trusted-worker queue/state/workspaces are runtime IPC rather than repository source.  The
# production Codex workspace currently lives below this subtree; copying it while seeding a scope
# such as ``ops/`` would recursively copy the destination into itself (DEBT-0154).
_NON_SEEDABLE_RUNTIME_NAMES = frozenset({".trusted-codex-worker"})


def _is_quarantined_relative(relative: str) -> bool:
    return any(
        part.casefold() in _QUARANTINED_SEED_NAMES or part.casefold().startswith("sentium")
        for part in Path(relative).parts
    )


def _is_trusted_credential_loader(path: Path) -> bool:
    """Recognise the tracked PAEOS credential *loader* without admitting credential values.

    ``credentials.py`` is both a source module required to import the router and a historical
    credential-shaped filename.  Only the repository's own tracked module is eligible for the
    worker source overlay; a same-named file in an untrusted/temp source tree remains quarantined.
    The loader still reads no credential value during seeding.
    """

    if path.name.casefold() != "credentials.py" or path.parent.name != "model_router":
        return False
    repository_root = path.parents[2]
    git_marker = repository_root / ".git"
    return git_marker.is_dir() or git_marker.is_file()


def _seed_ignore(_directory: str, names: list[str] | set[str]) -> set[str]:
    """Exclude sensitive and runtime-owned content from every worker overlay."""

    ignored: set[str] = set()
    for name in names:
        candidate = Path(_directory) / name
        if name.casefold() == "credentials.py" and _is_trusted_credential_loader(candidate):
            continue
        if (
            name.casefold() in _QUARANTINED_SEED_NAMES
            or name.casefold() in _NON_SEEDABLE_RUNTIME_NAMES
            or name.casefold().startswith("sentium")
        ):
            ignored.add(name)
    # A source overlay is a regular-file snapshot, not an IPC or device namespace.  In
    # particular, the trusted-worker launcher owns a live Unix socket under ``ops/``; attempting
    # to copy it makes ``copytree`` fail before the worker can start.  Ignore all non-regular,
    # non-directory entries (and symlinks) by lstat'ing the source entry without following it.
    # Any stat failure is fail-closed: the entry is omitted rather than guessed copyable.
    for name in names:
        if name in ignored:
            continue
        try:
            mode = os.lstat(Path(_directory) / name).st_mode
        except OSError:
            ignored.add(name)
            continue
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            ignored.add(name)
    return ignored


def _seed_workspace(
    workspace: Path,
    source: Path,
    write_scopes: tuple[str, ...],
    read_scopes: tuple[str, ...] = (),
) -> None:
    """Seed the complete declared read closure while preserving write-scope authority.

    The copy is limited to the package's declared union of read and write scopes.  The seed is
    still an overlay, so only write scopes are later collected as authored artifacts.  Sensitive
    and Sentium-shaped paths are excluded even if a malformed package requests them.
    """
    scopes = tuple(dict.fromkeys((*read_scopes, *write_scopes)))
    for scope in scopes:
        if not scope:
            continue
        scope_path = Path(scope)
        if scope_path.is_absolute() or ".." in scope_path.parts:
            raise ValueError(f"worker scope must remain relative to the repository: {scope!r}")
        src = source / scope
        if _is_quarantined_relative(scope):
            continue
        if src.is_symlink():
            raise ValueError(f"worker scope cannot seed a symlink: {scope!r}")
        if src.is_file():
            dst = workspace / scope
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        elif src.is_dir():
            shutil.copytree(
                src,
                workspace / scope,
                ignore=lambda directory, names: _seed_ignore(directory, set(names))
                | set(
                    shutil.ignore_patterns(
                        ".git",
                        ".venv",
                        "state_*",
                        ".pytest_cache",
                        "__pycache__",
                        ".claude",
                        "*.pyc",
                        "*.pyo",
                        ".paeos_state",
                    )(directory, names)
                ),
                dirs_exist_ok=True,
            )


def _is_build_byproduct(rel: str) -> bool:
    """A compiler by-product (Python bytecode), never authored source (DEBT-0022).

    Running a `builds` command like `python -m py_compile lib/x.py` emits `__pycache__/x.*.pyc`.
    If that `.pyc` is collected it can become `build.artifacts[0]` — the *reviewed* artifact — and
    the adversary/court then have to materialise sourceless, interpreter-version-coupled bytecode,
    which is fragile (the M3 seal/block asymmetry). Excluding it keeps the reviewed artifact the
    deterministic Python **source** the goal actually authored."""
    return rel.endswith((".pyc", ".pyo")) or "__pycache__" in rel.split("/")


_JUNK_FILENAMES = frozenset({".DS_Store", ".localized", "Thumbs.db"})


def _is_junk_artifact(rel: str, *, size: int) -> bool:
    """OS/workspace droppings and empty files are never authored work (notebook Entry 141,
    Finding K).

    24 of 25 historical seals certified junk as their artifact — 15 x a macOS `.DS_Store`
    Finder-metadata blob and 9 x a 0-byte file — because `_collect_writes` harvested whatever
    happened to sit in the workspace. A junk or empty file must never become
    `build.artifacts[0]`, the artifact the adversary reviews and the seal certifies.
    """
    return rel.rsplit("/", 1)[-1] in _JUNK_FILENAMES or size == 0


def _collect_writes(workspace: Path, write_scopes: tuple[str, ...]) -> tuple[AgentWrite, ...]:
    """Every file the session wrote in its workspace, as repo-relative paths — filtered to scope.
    A write outside `write_scopes` is dropped (never becomes an artifact); so is compiled Python
    bytecode (`__pycache__/*.pyc`), a build by-product rather than authored source (DEBT-0022);
    and OS droppings / empty files (`.DS_Store`, 0-byte) are never authored work (Entry 141,
    Finding K)."""
    writes: list[AgentWrite] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if _is_quarantined_relative(rel):
            # The tracked PAEOS credential loader is required as read-only import-time source for
            # model-router workers.  It is never an allowed write target; tolerate its presence in
            # the seeded read closure, while retaining the hard failure for every other
            # credential-shaped path and for any credential-shaped path inside write scopes.
            if rel == "paeos/model_router/credentials.py" and not within_scopes(rel, write_scopes):
                continue
            raise ValueError(f"worker attempted to author quarantined path: {rel}")
        if within_scopes(rel, write_scopes) and not _is_build_byproduct(rel):
            content = path.read_bytes()
            if _is_junk_artifact(rel, size=len(content)):
                continue
            writes.append(AgentWrite(path=rel, content=content))
    return tuple(writes)


def _parse_cost(transcript: str, default_model: str) -> Cost:
    """Best-effort cost from a CLI transcript. Unparseable ⇒ zero cost (never fabricate).

    Two shapes are understood:
    - `claude` CLI: a single JSON object with ``usage`` / ``duration_ms`` / ``model``.
    - `cline` CLI (GLM-5.3 invoker, Entry 142): an NDJSON message stream whose final
      ``run_result`` line carries ``usage`` (camelCase tokens), ``durationMs`` and ``model.id``.
    """
    try:
        data = json.loads(transcript)
    except (json.JSONDecodeError, ValueError):
        data = _cline_run_result(transcript)
    if not isinstance(data, dict):
        return Cost(tokens=0, wallclock_s=0.0, model_ver=default_model)
    usage = data.get("usage")
    tokens = 0
    if isinstance(usage, dict):
        for key in ("input_tokens", "output_tokens", "inputTokens", "outputTokens"):
            value = usage.get(key)
            if isinstance(value, int):
                tokens += value
    duration_ms = data.get("duration_ms", data.get("durationMs"))
    wallclock = duration_ms / 1000.0 if isinstance(duration_ms, int | float) else 0.0
    model = data.get("model")
    if isinstance(model, dict):  # cline run_result: {"id": "cline-pass/glm-5.3", ...}
        model = model.get("id")
    model_ver = model if isinstance(model, str) else default_model
    return Cost(tokens=tokens, wallclock_s=wallclock, model_ver=model_ver)


def _cline_run_result(transcript: str) -> dict | None:
    """The terminal ``run_result`` object of a Cline NDJSON stream, or None."""
    for ln in reversed(transcript.splitlines()):
        ln = ln.strip()
        if not ln:
            continue
        try:
            data = json.loads(ln)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and data.get("type") == "run_result":
            return data
    return None
