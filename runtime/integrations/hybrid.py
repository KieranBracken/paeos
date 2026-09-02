"""Hybrid & Multi-Provider Agent Runtimes (B1.B / B2.A).

Provides stage-aware routing across heterogeneous LLM providers (e.g. Codex / GPT-5.6 Sol for
main construction chain vs. GLM-5.3 / Cline for heterogeneous adversarial audit).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from kernel.types import Hash, Role, StageId

from runtime.claude_code import AgentRuntime, RunOutput
from runtime.integrations import (
    ClaudeCodeRuntime,
    CliInvoker,
    SessionResult,
    SessionSpec,
)
from runtime.task_package import TaskPackage

logger = logging.getLogger(__name__)

__all__ = ["CodexRuntime", "GlmRuntime", "HybridRuntime", "codex_cli_invoker", "glm_cli_invoker"]


def codex_cli_invoker(package: TaskPackage, *, mcp_config_path: Path | None = None) -> CliInvoker:
    """Invoker for Codex / GPT-5.6 Sol CLI. Runs `codex -p` or falls back to `claude` CLI."""
    import shutil
    import subprocess

    if shutil.which("codex"):
        binary = "codex"
    elif shutil.which("openai"):
        binary = "openai"
    else:
        # Fail-loud (CRITICAL-002): silent fallback to `claude` homogenised the construction
        # chain and masked provider unavailability as zero-cost success.
        raise RuntimeError(
            "Codex/GPT-5.6 Sol construction chain requires the `codex` (or `openai`) CLI on PATH; "
            "silent fallback to another provider is forbidden."
        )

    def _invoke(spec: SessionSpec) -> SessionResult:
        allowed = list(spec.allowed_tools)
        if mcp_config_path is not None:
            allowed.append("mcp__paeos-court__submit_evidence")
        if binary == "codex":
            cmd = [
                "codex",
                "exec",
                spec.prompt,
                "-c",
                'model_reasoning_effort="high"',
                "--json",
                "--dangerously-bypass-approvals-and-sandbox",
            ]
            if mcp_config_path is not None and mcp_config_path.exists():
                try:
                    cfg_data = json.loads(mcp_config_path.read_text(encoding="utf-8"))
                    mcp_servers = cfg_data.get("mcpServers", {})
                    for srv_name, srv_conf in mcp_servers.items():
                        cmd += [
                            "-c",
                            f"mcp_servers.{srv_name}.command={json.dumps(srv_conf['command'])}",
                            "-c",
                            f"mcp_servers.{srv_name}.args={json.dumps(srv_conf.get('args', []))}",
                        ]
                        if "env" in srv_conf:
                            for env_k, env_v in srv_conf["env"].items():
                                cmd += [
                                    "-c",
                                    f"mcp_servers.{srv_name}.env.{env_k}={json.dumps(env_v)}",
                                ]
                except Exception as e:
                    logger.warning("Could not parse mcp_config_path for codex: %s", e)
        else:
            cmd = [
                binary,
                "-p",
                spec.prompt,
                "--output-format",
                "json",
                "--allowedTools",
                ",".join(allowed),
                "--dangerously-skip-permissions",
            ]
            if mcp_config_path is not None:
                cmd += ["--mcp-config", str(mcp_config_path)]
        effective_timeout = min(spec.timeout_s or 1800, 1800)
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(spec.workspace),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            # Fail-loud (CRITICAL-002): a timeout previously returned a transcript that the
            # runtime recorded as a zero-cost COMPLETE success.
            stdout_str = (
                e.stdout.decode("utf-8") if isinstance(e.stdout, bytes) else (e.stdout or "")
            )
            stderr_str = (
                e.stderr.decode("utf-8") if isinstance(e.stderr, bytes) else (e.stderr or "")
            )
            raise RuntimeError(
                f"{binary} CLI session timed out after {effective_timeout}s "
                f"(stdout tail: {stdout_str[-500:]!r}, stderr tail: {stderr_str[-500:]!r})"
            ) from e
        if proc.returncode != 0 or not proc.stdout.strip():
            # Fail-loud (CRITICAL-002): nonzero exit or empty transcript previously became a
            # silent zero-cost COMPLETE run.
            raise RuntimeError(
                f"{binary} CLI failed (exit {proc.returncode}): {proc.stderr[-2000:]!r}"
            )
        return SessionResult(transcript=proc.stdout)

    return _invoke


CLINE_BINARY = "cline"
CLINE_PROVIDER = "cline-pass"
CLINE_MODEL = "cline-pass/glm-5.3"
CLINE_MODEL_TAG = "glm-5.3"

_EVIDENCE_HELPER_NAME = "submit_evidence.py"

_EVIDENCE_HELPER_SOURCE = '''#!/usr/bin/env python3
"""Seed the PAEOS court with REAL evidence (file-based submission, no MCP required).

Usage: submit_evidence.py <pool_dir> <run_id> <claim_id> <command> <artifact_path>

Runs <command> in the current directory, records its REAL exit code and stdout, hashes the
REAL artifact at <artifact_path>, and appends a genuine Evidence row to the court pool.
Never fabricates results: if the command fails, the evidence records the failure.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.types import Role
from runtime.orchestrator import FileCourtEvidencePool


def main() -> int:
    if len(sys.argv) != 6:
        print(__doc__, file=sys.stderr)
        return 2
    pool_dir, run_id, claim_id, command, artifact_path = sys.argv[1:6]
    proc = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
    artifact = Path(artifact_path)
    if artifact.is_file():
        artifact_hash = content_hash(artifact.read_bytes())
    else:
        artifact_hash = content_hash(b"missing-artifact:" + artifact_path.encode("utf-8"))
    evidence = Evidence(
        hash=content_hash(f"{claim_id}:{command}".encode("utf-8")),
        kind=EvidenceKind.TEST,
        claim_id=claim_id,
        artifact_hash=artifact_hash,
        environment_hash=content_hash(b"paeos-mcp-court-env"),
        reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session="cline-file-submit"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": proc.returncode, "stdout": proc.stdout[-2000:]},
        attestation="pending-kernel-sig",
    )
    FileCourtEvidencePool(Path(pool_dir)).submit(run_id, evidence)
    print(
        f"submitted evidence {evidence.hash[:12]} for claim {claim_id!r} "
        f"(run {run_id}, exit_code={proc.returncode})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _court_pool_dir(mcp_config_path: Path | None) -> Path | None:
    """Extract the court evidence-pool directory from the PAEOS MCP config (the `paeos-court`
    server's trailing positional argument). The Cline CLI has no headless MCP configuration
    (`cline mcp add` is a TTY wizard), so the config is used only to *locate* the pool; evidence
    is submitted file-based via a helper seeded into the workspace."""
    if mcp_config_path is None or not mcp_config_path.is_file():
        return None
    try:
        servers = json.loads(mcp_config_path.read_text(encoding="utf-8")).get("mcpServers", {})
    except (OSError, ValueError):
        return None
    for name, conf in servers.items():
        if "court" not in name:
            continue
        args = [str(a) for a in conf.get("args", []) if not str(a).startswith("-")]
        if args:
            return Path(args[-1])
    return None


def glm_cli_invoker(package: TaskPackage, *, mcp_config_path: Path | None = None) -> CliInvoker:
    """Invoker for GLM-5.3 heterogeneous audit via the Cline CLI (ClinePass subscription).

    Cline-native contract (verified empirically against `cline --help` + a live probe,
    2026-08-18, hallucination notebook Entry 142):

        cline -P cline-pass -m cline-pass/glm-5.3 --json --auto-approve true \\
              -t <timeout_s> -c <workspace> "<prompt>"

    emits an NDJSON message stream whose final ``run_result`` line carries ``usage``,
    ``durationMs``, ``text`` and ``model`` attribution. The previous invocation passed
    Claude-Code flags the Cline CLI rejects (``--output-format json``, ``--allowedTools``,
    ``--dangerously-skip-permissions``, ``--mcp-config``); every session died at argv parsing
    and was recorded as a zero-cost success (CRITICAL-002).

    Hard guarantees:
    1. **Model attribution enforced** — a ``run_result`` whose ``model.id`` is not the GLM
       model fails loudly (audit-chain homogenisation is forbidden, CANARY-0002).
    2. **Real completion required** — the stream must end in ``run_result`` with
       ``finishReason == "completed"``; anything else raises.
    """
    import shutil
    import subprocess

    if not shutil.which(CLINE_BINARY):
        # Fail-loud (CRITICAL-002): silent fallback to `claude` destroyed the *heterogeneous*
        # property of the audit chain — reviews meant for GLM-5.3 were silently executed by
        # Claude, defeating the entire purpose of the adversarial stage.
        raise RuntimeError(
            "GLM-5.3 heterogeneous audit requires the `cline` CLI on PATH; silent fallback to "
            "another provider is forbidden (audit-chain homogenisation)."
        )

    pool_dir = _court_pool_dir(mcp_config_path)

    def _invoke(spec: SessionSpec) -> SessionResult:
        prompt = spec.prompt
        if pool_dir is not None:
            # File-based court submission (Cline has no headless MCP): seed the helper and
            # instruct the agent to submit REAL evidence with it.
            helper = spec.workspace / _EVIDENCE_HELPER_NAME
            helper.write_text(_EVIDENCE_HELPER_SOURCE, encoding="utf-8")
            claims = ", ".join(ob.claim_id for ob in package.required_evidence) or "(none declared)"
            prompt += (
                f"\n\n# Court evidence submission (MANDATORY for builder work)\n"
                f"A `submit_evidence.py` helper sits at the workspace root. For EACH required "
                f"evidence claim ({claims}) run it with REAL values — it executes the command "
                f"itself and records the real exit code, stdout and artifact hash:\n"
                f"```\npython3 submit_evidence.py {pool_dir} {package.run_id} <claim_id> "
                f"'<command>' <artifact_path>\n```\n"
                f"NEVER fabricate results, hashes or output text."
            )

        effective_timeout = min(spec.timeout_s or 1800, 1800)
        # Stage-aware reasoning effort (run-6 post-mortem + refinement, notebook Entry 143):
        # the per-turn max-output-token cap is server-side (provider-enforced; no CLI flag to
        # raise it) and covers thinking + emitted content TOGETHER. So effort is allocated by
        # each stage's reasoning:emission ratio:
        #   * IMPLEMENT is the proven collision point (run 6) — code emission is the product
        #     and needs the output budget; MITIGATION is cheap scaffolding. → medium
        #   * DESIGN / PLAN / CRITIQUE are reasoning-heavy, low emission volume (documents),
        #     and design flaws propagate downstream — quality is the product. → high
        #   * The adversarial audit keeps high — rigor is the product (unchanged).
        if package.role is Role.ADVERSARY or package.stage in (
            StageId.ADVERSARIAL_REVIEW,
            StageId.DESIGN,
            StageId.PLAN,
            StageId.CRITIQUE,
        ):
            thinking = "high"
        else:
            thinking = "medium"
        cmd = [
            CLINE_BINARY,
            "-P",
            CLINE_PROVIDER,
            "-m",
            CLINE_MODEL,
            "--json",
            "--auto-approve",
            "true",
            "--thinking",
            thinking,
            "-t",
            str(effective_timeout),
            "-c",
            str(spec.workspace),
            prompt,
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(spec.workspace),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            # Fail-loud (CRITICAL-002): a timeout previously returned a transcript that the
            # runtime recorded as a zero-cost COMPLETE success.
            stdout_str = (
                e.stdout.decode("utf-8") if isinstance(e.stdout, bytes) else (e.stdout or "")
            )
            stderr_str = (
                e.stderr.decode("utf-8") if isinstance(e.stderr, bytes) else (e.stderr or "")
            )
            raise RuntimeError(
                f"{CLINE_BINARY} CLI session timed out after {effective_timeout}s "
                f"(stdout tail: {stdout_str[-500:]!r}, stderr tail: {stderr_str[-500:]!r})"
            ) from e
        if proc.returncode != 0 or not proc.stdout.strip():
            raise RuntimeError(
                f"{CLINE_BINARY} CLI failed (exit {proc.returncode}): {proc.stderr[-2000:]!r}"
            )

        # Validate the NDJSON stream: a terminal run_result with a real completion and the
        # correct model attribution. Anything else is a failed session, not a success.
        run_result = None
        for ln in reversed(proc.stdout.splitlines()):
            ln = ln.strip()
            if not ln:
                continue
            try:
                data = json.loads(ln)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(data, dict) and data.get("type") == "run_result":
                run_result = data
                break
        if run_result is None:
            raise RuntimeError(
                f"{CLINE_BINARY} CLI produced no run_result line (stdout tail: "
                f"{proc.stdout[-800:]!r})"
            )
        if run_result.get("finishReason") != "completed":
            raise RuntimeError(
                f"{CLINE_BINARY} CLI session did not complete (finishReason="
                f"{run_result.get('finishReason')!r})"
            )
        model = run_result.get("model")
        model_id = model.get("id") if isinstance(model, dict) else None
        if not isinstance(model_id, str) or CLINE_MODEL_TAG not in model_id:
            raise RuntimeError(
                f"{CLINE_BINARY} CLI session ran on model {model_id!r} — "
                f"the GLM-5.3 audit stage must run on the GLM model (audit-chain "
                f"homogenisation is forbidden, CANARY-0002)."
            )
        return SessionResult(transcript=proc.stdout)

    return _invoke


class CodexRuntime(ClaudeCodeRuntime):
    """AgentRuntime backing the main construction chain on Codex / GPT-5.6 Sol."""

    def run(self, package: TaskPackage) -> RunOutput:
        mcp_cfg = self._mcp_config_path if package.role in (Role.BUILDER, Role.ADVERSARY) else None
        invoker = (
            self._invoker
            if self._invoker is not None
            else codex_cli_invoker(package, mcp_config_path=mcp_cfg)
        )
        return self._run_with_invoker(package, invoker)


class GlmRuntime(ClaudeCodeRuntime):
    """AgentRuntime backing the heterogeneous audit stages on GLM-5.3."""

    def run(self, package: TaskPackage) -> RunOutput:
        mcp_cfg = self._mcp_config_path if package.role in (Role.BUILDER, Role.ADVERSARY) else None
        invoker = (
            self._invoker
            if self._invoker is not None
            else glm_cli_invoker(package, mcp_config_path=mcp_cfg)
        )
        return self._run_with_invoker(package, invoker)


class HybridRuntime:
    """Stage-aware router: routes construction chain to Codex (GPT-5.6 Sol) and audit to GLM-5.3."""

    def __init__(
        self,
        *,
        codex_runtime: AgentRuntime | None = None,
        glm_runtime: AgentRuntime | None = None,
        workspace_root: Path | None = None,
        workspace_source: Path | None = None,
        artifact_resolver: Callable[[Hash], bytes] | None = None,
        mcp_config_path: Path | None = None,
    ) -> None:
        self._codex = codex_runtime or CodexRuntime(
            workspace_root=workspace_root,
            workspace_source=workspace_source,
            artifact_resolver=artifact_resolver,
            mcp_config_path=mcp_config_path,
        )
        self._glm = glm_runtime or GlmRuntime(
            workspace_root=workspace_root,
            workspace_source=workspace_source,
            artifact_resolver=artifact_resolver,
            mcp_config_path=mcp_config_path,
        )

    def run(self, package: TaskPackage) -> RunOutput:
        # Route Heterogeneous Audit stages (CRITIQUE & ADVERSARIAL_REVIEW) to GLM-5.3
        if package.stage in (StageId.CRITIQUE, StageId.ADVERSARIAL_REVIEW):
            logger.info("Routing stage %s to GLM-5.3 (Heterogeneous Audit)", package.stage)
            return self._glm.run(package)

        # Route Main Construction Chain (RE_DERIVE, IDEATE, DESIGN, PLAN, IMPLEMENT, etc.) to Codex / GPT-5.6 Sol
        logger.info(
            "Routing stage %s to Codex / GPT-5.6 Sol (Main Construction Chain)", package.stage
        )
        return self._codex.run(package)
