"""Hybrid & Multi-Provider Agent Runtimes (B1.B / B2.A).

Provides stage-aware routing across heterogeneous LLM providers (e.g. Codex / GPT-5.6 Sol for
main construction chain vs. GLM-5.3 / Cline for heterogeneous adversarial audit).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path

from kernel.types import Hash, Role, StageId

from runtime.builder_transport import REQUIRED_CANARIES
from runtime.claude_code import AgentRuntime, RunOutput
from runtime.integrations import (
    ClaudeCodeRuntime,
    CliInvoker,
    SessionResult,
    SessionSpec,
    TrustedTransportFailure,
)
from runtime.integrations.process_supervisor import (
    ProcessLifecycleState,
    ProcessObservation,
    run_bounded_process,
)
from runtime.integrations.provider_broker import HostClineCriticTransport, ProviderBrokerError
from runtime.integrations.trusted_codex_planner_transport import HostCodexPlannerTransport
from runtime.integrations.trusted_codex_transport import HostCodexWorkerTransport
from runtime.integrations.worker_confinement import prepare_provider_launch
from runtime.planner_transport import (
    PLANNER_STAGES,
    LunaAdversaryBinding,
    LunaAdversaryBindingNotReady,
    LunaCriticBinding,
    PlannerTransportNotReady,
    PlannerTransportReadiness,
)
from runtime.task_package import Cost, TaskPackage, TaskStatus

logger = logging.getLogger(__name__)

__all__ = [
    "CodexRuntime",
    "GlmRuntime",
    "HybridRuntime",
    "codex_cli_invoker",
    "glm_cli_invoker",
    "host_supervised_codex_invoker",
    "host_supervised_codex_planner_invoker",
]


def _provider_state_path(spec: SessionSpec, provider: str) -> Path:
    """Choose a durable state path; the runtime supplies a state-root path in production."""

    return spec.lifecycle_state_path or spec.workspace / f".paeos-{provider}-lifecycle.json"


def _run_provider_process(
    argv: list[str],
    spec: SessionSpec,
    *,
    provider: str,
) -> SessionResult:
    """Run a provider through the common bounded supervisor and retain physical metadata."""

    effective_timeout = min(spec.timeout_s or 1800, 1800)
    confined_argv, child_environment, _policy = prepare_provider_launch(
        tuple(argv), workspace=spec.workspace, parent_environment=os.environ
    )
    observation: ProcessObservation = run_bounded_process(
        confined_argv,
        cwd=spec.workspace,
        environment=child_environment,
        start_timeout_s=min(30.0, max(1.0, float(effective_timeout))),
        execution_timeout_s=float(effective_timeout),
        state_path=_provider_state_path(spec, provider),
    )
    if (
        observation.lifecycle_state is not ProcessLifecycleState.RETURNED
        or observation.exit_code != 0
        or not observation.stdout.strip()
    ):
        raise TrustedTransportFailure(
            "provider_execution_failure",
            f"{provider} CLI did not produce a completed transcript "
            f"(state={observation.lifecycle_state.value}, exit={observation.exit_code}, "
            f"stdout_sha256={_sha_bytes(observation.stdout)}, "
            f"stderr_sha256={_sha_bytes(observation.stderr)})",
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


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _l10_execution_trace(
    package: TaskPackage, output: RunOutput, binding: LunaAdversaryBinding, transport: object
) -> bytes:
    """Seal the host-owned proof envelope for a successful trusted Luna L10 run."""

    if (
        output.status is not TaskStatus.COMPLETE
        or not isinstance(output.trace, bytes)
        or not output.trace
        or output.failure_code is not None
        or output.cost.model_ver != "openai:gpt-5.6-luna"
        or package.role is not Role.ADVERSARY
        or package.stage is not StageId.ADVERSARIAL_REVIEW
    ):
        raise ValueError("L10 execution trace input is not a successful adversarial run")
    authorization = binding.authorize_task(package)
    if not isinstance(authorization, dict):
        raise ValueError("L10 authorization is malformed")
    if (
        authorization.get("provider") != "codex"
        or authorization.get("model") != "gpt-5.6-luna"
        or authorization.get("family") != "gpt"
        or authorization.get("role") != Role.ADVERSARY.value
        or authorization.get("stage") != StageId.ADVERSARIAL_REVIEW.value
        or authorization.get("fresh_context_required") is not True
        or authorization.get("builder_context_inherited") is not False
        or authorization.get("production_write") is not False
        or authorization.get("fallback_used") is not False
        or authorization.get("manual_chat_bridge") is not False
    ):
        raise ValueError("L10 authorization is not the exact trusted Luna contract")
    observation = getattr(transport, "last_observation", None)
    if not isinstance(observation, Mapping) or not observation:
        raise ValueError("trusted Luna observation is missing")
    if "transcript" in observation:
        observation = dict(observation)
        observation.pop("transcript")
    else:
        observation = dict(observation)
    if any(not isinstance(value, str) or not value for value in observation.values() if value is None):
        raise ValueError("trusted Luna observation is malformed")
    if (
        observation.get("provider_id") != "codex"
        or observation.get("model_id") != "gpt-5.6-luna"
        or observation.get("family") != "gpt"
        or observation.get("task_id") != package.task_id
        or observation.get("goal_id") != package.goal_id
        or observation.get("run_id") != package.run_id
        or observation.get("stage") != StageId.ADVERSARIAL_REVIEW.value
        or observation.get("exit_code") != 0
        or observation.get("process_state") != "RETURNED"
        or observation.get("workspace_id") != Path(str(observation.get("workspace", ""))).name
        or not Path(str(observation.get("workspace", ""))).is_absolute()
        or observation.get("fallback_used") is not False
        or observation.get("manual_chat_bridge") is not False
    ):
        raise ValueError("trusted Luna observation identity is invalid")
    canaries = observation.get("canaries")
    if not isinstance(canaries, Mapping) or any(
        canaries.get(name) != "PASS" for name in REQUIRED_CANARIES
    ):
        raise ValueError("trusted Luna canaries are incomplete")
    required_observation_fields = {
        "stdout_sha256",
        "environment_fingerprint",
        "profile_sha256",
        "supervisor_identity_sha256",
        "broker_evidence_sha256",
        "artifact_sha256",
        "request_id",
    }
    if not required_observation_fields.issubset(observation):
        raise ValueError("trusted Luna observation fields are incomplete")
    if not isinstance(observation["request_id"], str) or not observation["request_id"]:
        raise ValueError("trusted Luna request ID is invalid")
    hash_fields = {
        key for key in observation if key.endswith("_sha256") or key == "environment_fingerprint"
    }
    for key in hash_fields:
        value = observation[key]
        if not isinstance(value, str) or len(value) != 64 or value != value.lower() or any(
            character not in "0123456789abcdef" for character in value
        ):
            raise ValueError(f"invalid trusted Luna hash: {key}")
    workspace = str(observation["workspace"])
    workspace_identity = _sha_bytes(workspace.encode("utf-8"))
    if output.workspace_identity != workspace_identity or output.environment_identity != observation["environment_fingerprint"]:
        raise ValueError("runtime identity does not match trusted Luna observation")
    if observation.get("stdout_sha256") != _sha_bytes(output.trace):
        raise ValueError("trusted Luna stdout does not match the execution trace")
    refs = []
    seen = set()
    for ref in package.context_refs:
        if not isinstance(ref.type, str) or not isinstance(ref.hash, str) or ref.hash in seen:
            raise ValueError("L10 context references are malformed or duplicated")
        if len(ref.hash) != 64 or ref.hash != ref.hash.lower() or any(c not in "0123456789abcdef" for c in ref.hash):
            raise ValueError("L10 context reference hash is invalid")
        seen.add(ref.hash)
        refs.append({"type": ref.type, "hash": ref.hash})
    if not refs:
        raise ValueError("L10 context references are missing")
    request_sha256 = getattr(transport, "last_request_sha256", None)
    response_sha256 = getattr(transport, "last_response_sha256", None)
    for value in (request_sha256, response_sha256):
        if not isinstance(value, str) or len(value) != 64 or value != value.lower() or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("trusted Luna request/response hash is invalid")
    envelope = {
        "schema": "paeos.l10-sealed-context-execution/1",
        "task_id": package.task_id,
        "goal_id": package.goal_id,
        "run_id": package.run_id,
        "role": Role.ADVERSARY.value,
        "stage": StageId.ADVERSARIAL_REVIEW.value,
        "provider": "codex",
        "model": "gpt-5.6-luna",
        "family": "gpt",
        "context_refs": sorted(refs, key=lambda ref: (ref["type"], ref["hash"])),
        "authorization": authorization,
        "observation": observation,
        "request_sha256": request_sha256,
        "response_sha256": response_sha256,
        "trace_base64": base64.b64encode(output.trace).decode("ascii"),
        "trace_sha256": _sha_bytes(output.trace),
    }
    return (json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def codex_cli_invoker(package: TaskPackage, *, mcp_config_path: Path | None = None) -> CliInvoker:
    """Legacy direct invoker retained only for hermetic adapter tests.

    The production ``CodexRuntime`` below never calls this function: it requires the trusted host
    supervisor and therefore has no nested-Seatbelt or alternate-provider fallback.
    """
    import shutil

    if not shutil.which("codex"):
        raise RuntimeError(
            "Codex/GPT-5.6 Sol construction chain requires the `codex` CLI on PATH; "
            "silent fallback to another provider is forbidden."
        )

    def _invoke(spec: SessionSpec) -> SessionResult:
        cmd = [
            "codex",
            "exec",
            spec.prompt,
            "-m",
            "gpt-5.6-sol",
            "-c",
            'model_reasoning_effort="high"',
            "--json",
            "--dangerously-bypass-approvals-and-sandbox",
            # Worker workspaces are deliberately VCS-free overlays; Codex must not reject a
            # valid isolated workspace merely because the runtime, not the worker, owns Git.
            "--skip-git-repo-check",
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
            except (OSError, TypeError, ValueError, KeyError) as error:
                raise RuntimeError("Codex MCP configuration is malformed") from error
        return _run_provider_process(cmd, spec, provider="codex")

    return _invoke


def host_supervised_codex_invoker(transport: HostCodexWorkerTransport) -> CliInvoker:
    """Build the production Codex invoker over the trusted host supervisor only."""

    def _invoke(spec: SessionSpec) -> SessionResult:
        return transport.run(spec)

    return _invoke


def host_supervised_codex_planner_invoker(transport: HostCodexPlannerTransport) -> CliInvoker:
    """Build the production Luna planner invoker over the same trusted supervisor."""

    def _invoke(spec: SessionSpec) -> SessionResult:
        return transport.run(spec)

    return _invoke


CLINE_BINARY = "cline"
CLINE_PROVIDER = "cline-pass"
CLINE_MODEL = "cline-pass/glm-5.3"
CLINE_MODEL_TAG = "glm-5.3"

def _court_pool_dir(mcp_config_path: Path | None) -> Path | None:
    """Extract the court evidence-pool directory from the PAEOS MCP config (the `paeos-court`
    server's positional argument). This is retained for configuration diagnostics only. Cline
    builder sessions fail closed when a trusted MCP evidence boundary is unavailable; they never
    receive a worker-writable helper that can write directly into the Court pool."""
    if mcp_config_path is None or not mcp_config_path.is_file():
        return None
    try:
        servers = json.loads(mcp_config_path.read_text(encoding="utf-8")).get("mcpServers", {})
    except (OSError, ValueError):
        return None
    for name, conf in servers.items():
        if "court" not in name:
            continue
        args = [str(a) for a in conf.get("args", [])]
        try:
            module_index = args.index("runtime.transports.mcp.court_server")
            return Path(args[module_index + 1])
        except (ValueError, IndexError):
            continue
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

    if package.role is Role.CRITIC:
        raise RuntimeError(
            "direct confined Cline startup is forbidden for CRITIC; "
            "the parent-owned HostClineCriticTransport is required"
        )

    if not shutil.which(CLINE_BINARY):
        # Fail-loud (CRITICAL-002): silent fallback to `claude` destroyed the *heterogeneous*
        # property of the audit chain — reviews meant for GLM-5.3 were silently executed by
        # Claude, defeating the entire purpose of the adversarial stage.
        raise RuntimeError(
            "GLM-5.3 heterogeneous audit requires the `cline` CLI on PATH; silent fallback to "
            "another provider is forbidden (audit-chain homogenisation)."
        )

    pool_dir = _court_pool_dir(mcp_config_path)
    if pool_dir is not None and package.role is Role.BUILDER:
        raise RuntimeError(
            "Cline cannot submit Court evidence through a trusted MCP boundary; "
            "builder work must use a provider runtime with the Court MCP transport"
        )

    def _invoke(spec: SessionSpec) -> SessionResult:
        prompt = spec.prompt

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
        result = _run_provider_process(cmd, spec, provider=CLINE_BINARY)

        # Validate the NDJSON stream: a terminal run_result with a real completion and the
        # correct model attribution. Anything else is a failed session, not a success.
        run_result = None
        for ln in reversed(result.transcript.splitlines()):
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
                f"{result.transcript[-800:]!r})"
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
        return result

    return _invoke


_legacy_noncritic_glm_invoker = glm_cli_invoker


class CodexRuntime(ClaudeCodeRuntime):
    """AgentRuntime for the fixed Sol Builder and qualified Luna planner routes."""

    def __init__(
        self,
        *,
        critic_binding: LunaCriticBinding | None = None,
        adversary_binding: LunaAdversaryBinding | None = None,
        **kwargs: object,
    ) -> None:
        host_transport = kwargs.pop("host_transport", None)
        if host_transport is not None and not isinstance(host_transport, HostCodexWorkerTransport):
            raise TypeError("host_transport must be a HostCodexWorkerTransport")
        planner_transport = kwargs.pop("planner_transport", None)
        if planner_transport is not None and not isinstance(
            planner_transport, HostCodexPlannerTransport
        ):
            raise TypeError("planner_transport must be a HostCodexPlannerTransport")
        planner_readiness = kwargs.pop("planner_readiness", None)
        if planner_readiness is not None and not isinstance(
            planner_readiness, PlannerTransportReadiness
        ):
            raise TypeError("planner_readiness must be a PlannerTransportReadiness")
        if (planner_transport is None) != (planner_readiness is None):
            raise TypeError("planner transport and readiness must be configured together")
        if critic_binding is not None and not isinstance(critic_binding, LunaCriticBinding):
            raise TypeError("critic_binding must be a LunaCriticBinding")
        if critic_binding is not None and planner_transport is None:
            raise TypeError("critic binding requires planner transport and readiness")
        if adversary_binding is not None and not isinstance(adversary_binding, LunaAdversaryBinding):
            raise TypeError("adversary_binding must be a LunaAdversaryBinding")
        if adversary_binding is not None and planner_transport is None:
            raise TypeError("adversary binding requires planner transport and readiness")
        self._host_transport = host_transport
        self._planner_transport = planner_transport
        self._planner_readiness = planner_readiness
        self._critic_binding = critic_binding
        self._adversary_binding = adversary_binding
        kwargs["default_model"] = "openai:gpt-5.6-sol"
        super().__init__(**kwargs)  # type: ignore[arg-type]

    def run(self, package: TaskPackage) -> RunOutput:
        if package.role is Role.ADVERSARY and package.stage is StageId.ADVERSARIAL_REVIEW:
            if self._adversary_binding is None:
                output = self._run_with_invoker(
                    package,
                    self._unavailable_transport(),
                )
                return replace(
                    output,
                    cost=replace(output.cost, model_ver="openai:gpt-5.6-luna"),
                )
        planner_route = False
        if (
            self._planner_transport is not None
            and self._planner_readiness is not None
            and (
                (package.role is Role.PLANNER and package.stage.name in PLANNER_STAGES)
                or (package.role is Role.CRITIC and self._critic_binding is not None)
                or (package.role is Role.ADVERSARY and self._adversary_binding is not None)
            )
        ):
            try:
                if package.role is Role.CRITIC:
                    assert self._critic_binding is not None
                    self._critic_binding.authorize_task(package)
                elif package.role is Role.ADVERSARY:
                    assert self._adversary_binding is not None
                    self._adversary_binding.authorize_task(package)
                qualification = self._planner_readiness.require()
                if package.stage.name not in qualification.qualified_stages:
                    raise PlannerTransportNotReady(
                        "requested planner stage is not qualified"
                    )
            except PlannerTransportNotReady:
                # A configured-but-invalid qualification is a structured transport failure, not
                # permission to silently use a different model.
                def _unready(_spec: SessionSpec) -> SessionResult:
                    raise TrustedTransportFailure(
                        "planner_readiness_failure",
                        "signed Luna planner qualification is unavailable",
                    )

                output = self._run_with_invoker(package, _unready)
                return replace(
                    output,
                    cost=replace(output.cost, model_ver="openai:gpt-5.6-luna"),
                )
            planner_route = package.stage.name in qualification.qualified_stages
        invoker = (
            self._invoker
            if self._invoker is not None
            else (
                host_supervised_codex_planner_invoker(self._planner_transport)
                if planner_route and self._planner_transport is not None
                else (
                    host_supervised_codex_invoker(self._host_transport)
                    if self._host_transport is not None
                    else self._unavailable_transport()
                )
            )
        )
        output = self._run_with_invoker(package, invoker)
        expected_models = (
            {"openai:gpt-5.6-luna", "gpt-5.6-luna"}
            if planner_route
            else {"openai:gpt-5.6-sol", "gpt-5.6-sol"}
        )
        if output.status is TaskStatus.COMPLETE:
            # The Codex transcript may omit its model identity. The trusted host transport has
            # already signature-validated the actual observation; derive attribution from that
            # observation, never from worker prose or the runtime default.
            transport = self._planner_transport if planner_route else self._host_transport
            observation = getattr(transport, "last_observation", None)
            observed_model = observation.get("model_id") if isinstance(observation, dict) else None
            configured_model = getattr(transport, "model_id", None)
            if (
                not isinstance(observed_model, str)
                or not isinstance(configured_model, str)
                or observed_model != configured_model
            ):
                raise RuntimeError(
                    "trusted transport model observation is missing or mismatched; "
                    "planner/Builder attribution is not trustworthy"
                )
            output = replace(
                output,
                cost=replace(output.cost, model_ver=f"openai:{observed_model}"),
            )
            if (
                planner_route
                and package.role is Role.ADVERSARY
                and package.stage is StageId.ADVERSARIAL_REVIEW
            ):
                assert self._adversary_binding is not None
                assert self._planner_transport is not None
                output = replace(
                    output,
                    trace=_l10_execution_trace(
                        package, output, self._adversary_binding, self._planner_transport
                    ),
                )
        if output.status is TaskStatus.COMPLETE and output.cost.model_ver not in expected_models:
            raise RuntimeError(
                "Codex construction session returned an unexpected model identity; "
                "planner/Builder attribution is not trustworthy"
            )
        return replace(
            output,
            cost=replace(
                output.cost,
                model_ver="openai:gpt-5.6-luna" if planner_route else "openai:gpt-5.6-sol",
            ),
        )

    @staticmethod
    def _unavailable_transport() -> CliInvoker:
        def _invoke(_spec: SessionSpec) -> SessionResult:
            raise RuntimeError(
                "trusted host Codex supervisor is not configured; direct or unrestricted fallback is forbidden"
            )

        return _invoke


class GlmRuntime(ClaudeCodeRuntime):
    """AgentRuntime backing the heterogeneous audit stages on GLM-5.3."""

    def __init__(self, **kwargs: object) -> None:
        critic_transport = kwargs.pop("critic_transport", None)
        if critic_transport is not None and not isinstance(
            critic_transport, HostClineCriticTransport
        ):
            raise TypeError("critic_transport must be a HostClineCriticTransport")
        self._critic_transport = critic_transport
        # Failed Cline sessions still need truthful route attribution.  The base Claude
        # adapter defaults to ``claude-code`` for its generic test seam; retaining that default
        # here mislabels a real Cline/GLM failure in the governed ledger and can obscure which
        # heterogeneous route actually failed.
        kwargs.setdefault("default_model", CLINE_MODEL)
        super().__init__(**kwargs)

    def run(self, package: TaskPackage) -> RunOutput:
        if package.role is Role.CRITIC:
            # Explicit invokers are the hermetic adapter-test seam. Production constructs this
            # runtime without one and therefore cannot bypass the parent-owned transport.
            if self._invoker is not None:
                return self._run_with_invoker(package, self._invoker)
            if self._critic_transport is None:
                def _unavailable(_spec: SessionSpec) -> SessionResult:
                    raise TrustedTransportFailure(
                        "critic_transport_unavailable",
                        "parent-owned Cline critic transport is not configured",
                    )
                return self._run_with_invoker(package, _unavailable)
            def _parent_owned(spec: SessionSpec) -> SessionResult:
                try:
                    return self._critic_transport.run(spec)
                except ProviderBrokerError as exc:
                    raise TrustedTransportFailure(
                        "critic_transport_failure", "parent-owned critic transport failed closed"
                    ) from exc
            return self._run_with_invoker(package, _parent_owned)
        mcp_cfg = self._mcp_config_path if package.role in (Role.BUILDER, Role.ADVERSARY) else None
        invoker = (
            self._invoker
            if self._invoker is not None
            else _legacy_noncritic_glm_invoker(package, mcp_config_path=mcp_cfg)
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
        state_root: Path | None = None,
        codex_transport: HostCodexWorkerTransport | None = None,
        planner_transport: HostCodexPlannerTransport | None = None,
        planner_readiness: PlannerTransportReadiness | None = None,
        critic_transport: HostClineCriticTransport | None = None,
        critic_binding: LunaCriticBinding | None = None,
        adversary_binding: LunaAdversaryBinding | None = None,
    ) -> None:
        if (planner_transport is None) != (planner_readiness is None):
            raise TypeError("planner transport and readiness must be configured together")
        if critic_binding is not None and not isinstance(critic_binding, LunaCriticBinding):
            raise TypeError("critic_binding must be a LunaCriticBinding")
        if critic_binding is not None and planner_readiness is None:
            raise TypeError("critic binding requires planner transport and readiness")
        if adversary_binding is not None and not isinstance(adversary_binding, LunaAdversaryBinding):
            raise TypeError("adversary_binding must be a LunaAdversaryBinding")
        if adversary_binding is not None and planner_readiness is None:
            raise TypeError("adversary binding requires planner transport and readiness")
        self._planner_transport = planner_transport
        self._planner_readiness = planner_readiness
        self._critic_binding = critic_binding
        self._adversary_binding = adversary_binding
        self._codex = codex_runtime or CodexRuntime(
            workspace_root=workspace_root,
            workspace_source=workspace_source,
            artifact_resolver=artifact_resolver,
            mcp_config_path=mcp_config_path,
            state_root=state_root,
            host_transport=codex_transport,
            planner_transport=planner_transport,
            planner_readiness=planner_readiness,
            critic_binding=critic_binding,
            adversary_binding=adversary_binding,
        )
        fixed_critic_transport = critic_transport
        if glm_runtime is None and fixed_critic_transport is None:
            fixed_critic_transport = HostClineCriticTransport()
        self._glm = glm_runtime or GlmRuntime(
            workspace_root=workspace_root,
            workspace_source=workspace_source,
            artifact_resolver=artifact_resolver,
            mcp_config_path=mcp_config_path,
            state_root=state_root,
            critic_transport=fixed_critic_transport,
        )

    def run(self, package: TaskPackage) -> RunOutput:
        if package.role is Role.ADVERSARY and package.stage is StageId.ADVERSARIAL_REVIEW:
            if (
                self._adversary_binding is None
                or self._planner_transport is None
                or self._planner_readiness is None
            ):
                return RunOutput(
                    status=TaskStatus.FAILED,
                    writes=(),
                    evidence=(),
                    trace=b"l10_adversary_binding_unavailable",
                    cost=Cost(tokens=0, wallclock_s=0.0, model_ver="openai:gpt-5.6-luna"),
                    failure_code="l10_adversary_binding_unavailable",
                )
            try:
                self._adversary_binding.authorize_task(package)
                self._planner_readiness.require(StageId.ADVERSARIAL_REVIEW.name)
            except (LunaAdversaryBindingNotReady, PlannerTransportNotReady):
                return RunOutput(
                    status=TaskStatus.FAILED,
                    writes=(),
                    evidence=(),
                    trace=b"l10_adversary_binding_invalid",
                    cost=Cost(tokens=0, wallclock_s=0.0, model_ver="openai:gpt-5.6-luna"),
                    failure_code="l10_adversary_binding_invalid",
                )
            logger.info("Routing amended L10 adversary to Codex / GPT-5.6 Luna")
            return self._codex.run(package)

        if (
            package.role is Role.CRITIC
            and package.stage is StageId.CRITIQUE
            and self._critic_binding is not None
        ):
            assert self._planner_readiness is not None
            self._critic_binding.authorize_task(package)
            self._planner_readiness.require(StageId.CRITIQUE.name)
            logger.info("Routing authorized critic CRITIQUE to Codex / GPT-5.6 Luna")
            return self._codex.run(package)

        if (
            package.role is Role.PLANNER
            and package.stage is StageId.CRITIQUE
            and self._planner_transport is not None
            and self._planner_readiness is not None
        ):
            # The route boundary must independently prove that this exact stage is covered.
            # CodexRuntime repeats the readiness check before dispatching through the trusted
            # Luna supervisor, so neither layer permits an unqualified or fallback route.
            self._planner_readiness.require(StageId.CRITIQUE.name)
            logger.info("Routing qualified planner CRITIQUE to Codex / GPT-5.6 Luna")
            return self._codex.run(package)

        # Route Heterogeneous Audit stages (CRITIQUE & ADVERSARIAL_REVIEW) to GLM-5.3
        if package.stage in (StageId.CRITIQUE, StageId.ADVERSARIAL_REVIEW):
            logger.info("Routing stage %s to GLM-5.3 (Heterogeneous Audit)", package.stage)
            return self._glm.run(package)

        # Route Main Construction Chain (RE_DERIVE, IDEATE, DESIGN, PLAN, IMPLEMENT, etc.) to Codex / GPT-5.6 Sol
        logger.info(
            "Routing stage %s to Codex / GPT-5.6 Sol (Main Construction Chain)", package.stage
        )
        return self._codex.run(package)
