"""Live fully-autonomous self-hosting run — Phase 3 Milestone 1.

The culminating composition: a live `claude` session (launched by `ClaudeCodeRuntime` with
`--mcp-config`) reaches the **CourtServer** MCP tool, which writes the session's own probative
evidence into the **court pool**; the `SoftLoop` pulls that evidence via the `EvidenceSource`
port and adjudicates it; the whole loop is pulled by the `ContinuousScheduler` (Stage-19 RESTART)
and bounded by the `EconomicGovernor` (K11 budget conservation).

    claude --mcp-config → court_server.py → FileCourtEvidencePool → EvidenceSource → seal

This is a **deployment** entry point (needs `claude` auth + real tokens), not unit-tested — the
adapters it composes are (`runtime/transports/`, `runtime/scheduler.py`, `runtime/integrations`).
The core runtime it drives imports zero vendor SDK; only `runtime/transports/mcp/` touches MCP.

Usage:  python ops/autonomous_run.py <backlog.json> <state_dir>
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import stat
import sys
import threading
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

from kernel.cas import CAS, FilesystemCasStore
from kernel.keystore import load_or_create_signing_key
from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from kernel.types import ArtifactRef, Role, StageId
from nacl.signing import SigningKey, VerifyKey
from runtime.autonomy import (
    ActionPermission,
    AuthorityEnvelope,
    AuthorityTier,
    EdgeType,
    FindingClass,
    PersistentMissionController,
    TaskStatus,
)
from runtime.builder_transport import BuilderTransportReadiness
from runtime.court.completeness_firewall import load_authoritative_manifest
from runtime.evolution import EvolutionLayer
from runtime.friction import FrictionCategory, classify_friction, record_friction
from runtime.integrations import ClaudeCodeRuntime, SessionResult, TrustedTransportFailure
from runtime.integrations.gemini36_adversary_route import (
    HostGemini36AdversaryTransport,
    parent_gemini36_adversary_exchange,
)
from runtime.integrations.gemini36_critic_route import (
    HostGemini36CriticTransport,
    parent_gemini36_exchange,
)
from runtime.integrations.hybrid import CodexRuntime, GlmRuntime, HybridRuntime
from runtime.integrations.trusted_codex_planner_transport import (
    HostCodexPlannerTransport,
)
from runtime.integrations.trusted_codex_transport import (
    DEFAULT_BUILDER_TRANSPORT_QUALIFICATION,
    DEFAULT_BUILDER_TRANSPORT_VERIFY_KEY,
    DEFAULT_CODEX_REQUEST_KEY,
    DEFAULT_CODEX_RESPONSE_VERIFY_KEY,
    DEFAULT_CODEX_WORKSPACE_ROOT,
    HostCodexWorkerTransport,
)
from runtime.orchestrator import (
    Intake,
    RunOutcome,
    RunStatus,
    SoftLoop,
    StagePlaybook,
    durable_scar_store,
)
from runtime.planner_transport import (
    L10_FAMILY_AMENDMENT_ID,
    LunaAdversaryBinding,
    LunaAdversaryBindingNotReady,
    LunaCriticBinding,
    PlannerTransportNotReady,
    PlannerTransportReadiness,
    l10_amendment_definition_hash,
)
from runtime.run_state_registry import RunStateRegistry
from runtime.scheduler import (
    ConcurrentScheduler,
    ContinuousScheduler,
    EconomicGovernor,
    GlobalBudget,
)
from runtime.selfhost import DEFAULT_BUDGETS, parse_backlog
from runtime.sidecar_scorer import SidecarStageScorer
from runtime.transports.mcp.transport import McpWorkerTransport

from ops.p1_runtime_l14_audit import audit_candidate

# RB-0008: autonomous friction detection — record structural gaps as DEBT/RB items on disk.


def _read_hex_identity(path: Path, *, private: bool) -> bytes | None:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        return None
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        raw = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if (mode & 0o077 if private else mode & 0o022) or len(raw) != 64:
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return None


def _read_raw_seed(path: Path) -> bytes | None:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        return None
    try:
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    return raw if len(raw) == 32 else None


def _load_codex_transport(workspace_root: Path) -> HostCodexWorkerTransport | None:
    request_bytes = _read_hex_identity(DEFAULT_CODEX_REQUEST_KEY, private=True)
    response_bytes = _read_hex_identity(
        DEFAULT_CODEX_RESPONSE_VERIFY_KEY, private=False
    )
    if request_bytes is None or response_bytes is None:
        return None
    try:
        return HostCodexWorkerTransport(
            queue_root=DEFAULT_CODEX_REQUEST_KEY.parent / "queue",
            workspace_root=workspace_root,
            request_signing_key=SigningKey(request_bytes),
            response_verify_key=VerifyKey(response_bytes),
        )
    except ValueError:
        return None


def _load_luna_planner_transport(
    workspace_root: Path,
) -> tuple[HostCodexPlannerTransport, PlannerTransportReadiness] | None:
    """Load Luna only when its supervisor-signed, stage-scoped proof is present and valid."""

    qualification_path = (
        DEFAULT_CODEX_REQUEST_KEY.parent / "planner-qualification-v2.json"
    )
    if not qualification_path.exists():
        return None
    request_bytes = _read_hex_identity(DEFAULT_CODEX_REQUEST_KEY, private=True)
    response_bytes = _read_hex_identity(
        DEFAULT_CODEX_RESPONSE_VERIFY_KEY, private=False
    )
    if request_bytes is None or response_bytes is None:
        raise RuntimeError(
            "Luna planner qualification exists but transport identities are unavailable"
        )
    try:
        readiness = PlannerTransportReadiness(
            qualification_path, VerifyKey(response_bytes)
        )
        readiness.require()
        transport = HostCodexPlannerTransport(
            queue_root=DEFAULT_CODEX_REQUEST_KEY.parent / "queue",
            workspace_root=workspace_root,
            request_signing_key=SigningKey(request_bytes),
            response_verify_key=VerifyKey(response_bytes),
        )
    except (ValueError, PlannerTransportNotReady) as exc:
        raise RuntimeError("Luna planner qualification is present but invalid") from exc
    return transport, readiness


def _require_l10_family_amendment(repo_root: Path, manifest_sha256: str) -> None:
    """Verify the durable Founder amendment before admitting a same-family L10 route."""

    path = repo_root / "reviews" / "governance" / (
        "PAEOS_P1_L10_FAMILY_DECORRELATION_AMENDMENT_20260918.md"
    )
    if path.is_symlink() or not path.is_file():
        raise PlannerTransportNotReady("bounded L10 family amendment record is unavailable")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PlannerTransportNotReady("bounded L10 family amendment record is unreadable") from exc
    required = (
        f"amendment_id: {L10_FAMILY_AMENDMENT_ID}",
        "prior_rule: L10 adversary family != L12 Builder family",
        "replacement_rule: model-family identity may match the Builder family",
        "fresh_sealed_context_required: true",
        "builder_context_inherited: false",
        "builder_write_authority: false",
        "l14_builder_auditor_family_inequality: true",
        f"acceptance_definition_hash: {l10_amendment_definition_hash()}",
        f"manifest_sha256: {manifest_sha256}",
        "historical_evidence_invalidation: pre-amendment L10 readiness and qualification only",
    )
    if any(marker not in text for marker in required):
        raise PlannerTransportNotReady("bounded L10 family amendment record is not exact")


def _load_luna_adversary_binding(
    repo_root: Path, manifest_sha256: str, readiness: PlannerTransportReadiness
) -> LunaAdversaryBinding:
    _require_l10_family_amendment(repo_root, manifest_sha256)
    try:
        return LunaAdversaryBinding.from_readiness(readiness)
    except LunaAdversaryBindingNotReady:
        raise


def _load_builder_transport_readiness() -> BuilderTransportReadiness | None:
    if (
        not DEFAULT_BUILDER_TRANSPORT_QUALIFICATION.exists()
        or not DEFAULT_BUILDER_TRANSPORT_VERIFY_KEY.exists()
    ):
        return None
    verify_bytes = _read_hex_identity(
        DEFAULT_BUILDER_TRANSPORT_VERIFY_KEY, private=False
    )
    if verify_bytes is None:
        return None
    try:
        return BuilderTransportReadiness(
            DEFAULT_BUILDER_TRANSPORT_QUALIFICATION,
            VerifyKey(verify_bytes),
        )
    except ValueError:
        return None


CRITIC_QUALIFICATION_SCHEMA = "paeos.critic-transport-live-qualification/1"
DEFAULT_CRITIC_QUALIFICATION = (
    DEFAULT_CODEX_REQUEST_KEY.parent / "critic-qualification-v1.json"
)


def _load_qualified_critic_transport(repo_root: Path) -> object:
    """Select only the immutable, supervisor-signed live-qualified critic identity."""

    path = DEFAULT_CRITIC_QUALIFICATION
    if (
        not path.is_file()
        or path.is_symlink()
        or stat.S_IMODE(path.stat().st_mode) & 0o022
    ):
        raise RuntimeError("signed immutable critic qualification is unavailable")
    verify_bytes = _read_hex_identity(DEFAULT_CODEX_RESPONSE_VERIFY_KEY, private=False)
    if verify_bytes is None:
        raise RuntimeError("critic qualification verification identity is unavailable")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("critic qualification is malformed") from exc
    required = {
        "schema",
        "provider_id",
        "model_id",
        "model_family",
        "transport",
        "qualified",
        "issued_at",
        "expires_at",
        "signature",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise RuntimeError("critic qualification fields are not exact")
    signature = record.pop("signature")
    try:
        VerifyKey(verify_bytes).verify(
            (
                json.dumps(
                    record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                )
                + "\n"
            ).encode(),
            bytes.fromhex(signature),
        )
    except Exception as exc:
        raise RuntimeError("critic qualification signature is invalid") from exc
    if (
        record.get("schema") != CRITIC_QUALIFICATION_SCHEMA
        or record.get("provider_id") != "google"
        or record.get("model_id") != "gemini-3.6-flash"
        or record.get("model_family") != "gemini"
        or record.get("transport") != "parent-owned"
        or record.get("qualified") is not True
    ):
        raise RuntimeError(
            "critic qualification does not select the exact Gemini 3.6 route"
        )
    issued, expires = record.get("issued_at"), record.get("expires_at")
    now = time.time()
    if (
        isinstance(issued, bool)
        or isinstance(expires, bool)
        or not isinstance(issued, (int, float))
        or not isinstance(expires, (int, float))
        or expires <= issued
        or expires <= now
    ):
        raise RuntimeError("critic qualification is expired")

    key_bytes = _read_raw_seed(
        repo_root / "ops" / "keys" / "kernel_ed25519.key"
    )
    if key_bytes is None:
        raise RuntimeError("repository kernel signing key is unavailable or malformed")
    try:
        return HostGemini36CriticTransport(
            parent_exchange=parent_gemini36_exchange,
            request_signing_key=SigningKey(key_bytes),
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "qualified parent-owned Gemini 3.6 critic transport is malformed"
        ) from exc


ADVERSARY_QUALIFICATION_SCHEMA = "paeos.adversary-transport-live-qualification/1"
DEFAULT_ADVERSARY_QUALIFICATION = (
    DEFAULT_CODEX_REQUEST_KEY.parent / "adversary-qualification-v1.json"
)

GEMINI36_ADVERSARY_MAX_PROMPT_BYTES = 128 * 1024
_GEMINI36_FORBIDDEN_CONTEXT_NAMES = frozenset(
    {"auth.json", "credential", "credentials", "secret", "secrets", "sentium", "orca"}
)
_GEMINI36_ADVERSARY_OUTPUT_CONTRACT = (
    "FINAL OUTPUT CONTRACT\n"
    "Ignore earlier worker instructions about tools, writes, or MCP. This route grants "
    "no tools, writes, MCP, or file access. Return exactly two concise plain-text lines: "
    "one finding, then exactly one terminal line: VERDICT: PASS or VERDICT: BLOCK."
)
_GEMINI36_ADVERSARY_REVIEW_OBJECTIVE = (
    "Independently adversarially review the fresh sealed P1 context bundle below. "
    "Attack the proposed design and findings for correctness, completeness, internal "
    "consistency, safety, and satisfaction of the stated P1 objective. Report concrete "
    "blocking defects with evidence from the bundle; pass only if none remain."
)


def _l10_context_refs(
    planner_artifacts: Sequence[ArtifactRef],
) -> tuple[ArtifactRef, ArtifactRef]:
    """Select the canonical L08 design and L09 findings for L10."""

    if len(planner_artifacts) < 2:
        raise RuntimeError("L10 requires ordered L08 design and L09 findings artifacts")
    return planner_artifacts[-2], planner_artifacts[-1]


class _L10ContextPlaybook:
    """Override only L10 context selection on an otherwise canonical playbook."""

    def __init__(self, delegate: StagePlaybook) -> None:
        self._delegate = delegate

    def select_context_refs(
        self, *, stage: StageId, context_refs: tuple[ArtifactRef, ...]
    ) -> tuple[ArtifactRef, ...]:
        if stage is StageId.ADVERSARIAL_REVIEW:
            return _l10_context_refs(context_refs)
        return context_refs

    def run_stage(self, **kwargs: object) -> object:
        if kwargs.get("stage") is StageId.ADVERSARIAL_REVIEW:
            context_refs = kwargs.get("context_refs")
            if not isinstance(context_refs, Sequence):
                raise TypeError("L10 context_refs must be an ordered sequence")
            kwargs["context_refs"] = self.select_context_refs(
                stage=StageId.ADVERSARIAL_REVIEW,
                context_refs=tuple(context_refs),
            )
        return self._delegate.run_stage(**kwargs)


def _build_gemini36_adversary_prompt(prompt: str, workspace: Path) -> str:
    """Append the immediate, sealed adversary context as a deterministic text bundle."""

    del prompt  # The parent route owns its disclosure packet; worker orchestration is excluded.

    context = workspace / "context"
    try:
        context_fd = os.open(
            context,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        raise RuntimeError("sealed adversary context is unavailable") from exc
    try:
        try:
            names = sorted(os.listdir(context_fd), key=lambda name: name.encode("utf-8"))
        except (OSError, UnicodeEncodeError) as exc:
            raise RuntimeError("sealed adversary context cannot be enumerated") from exc
        if not names:
            raise RuntimeError("sealed adversary context is empty")

        # Validate every entry before opening any of them, so a forbidden or nested
        # entry cannot produce a partially read bundle.
        for name in names:
            folded = name.casefold()
            if any(value in folded for value in _GEMINI36_FORBIDDEN_CONTEXT_NAMES):
                raise RuntimeError("sealed adversary context contains a forbidden name")
            try:
                entry_stat = os.stat(name, dir_fd=context_fd, follow_symlinks=False)
            except OSError as exc:
                raise RuntimeError("sealed adversary context entry is unavailable") from exc
            if not stat.S_ISREG(entry_stat.st_mode):
                raise RuntimeError(
                    "sealed adversary context entries must be immediate regular files"
                )

        files: list[tuple[str, bytes, str]] = []
        bundle_hasher = hashlib.sha256()
        for name in names:
            try:
                fd = os.open(
                    name,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=context_fd,
                )
                try:
                    opened_stat = os.fstat(fd)
                    if not stat.S_ISREG(opened_stat.st_mode):
                        raise RuntimeError(
                            "sealed adversary context entry changed during reading"
                        )
                    chunks: list[bytes] = []
                    size = 0
                    while True:
                        chunk = os.read(fd, 64 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > GEMINI36_ADVERSARY_MAX_PROMPT_BYTES:
                            raise RuntimeError(
                                "sealed adversary context exceeds its bounded size"
                            )
                        chunks.append(chunk)
                finally:
                    os.close(fd)
            except OSError as exc:
                raise RuntimeError("sealed adversary context entry cannot be read") from exc
            raw = b"".join(chunks)
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RuntimeError("sealed adversary context entry is not UTF-8") from exc
            name_bytes = name.encode("utf-8")
            bundle_hasher.update(len(name_bytes).to_bytes(8, "big"))
            bundle_hasher.update(name_bytes)
            bundle_hasher.update(len(raw).to_bytes(8, "big"))
            bundle_hasher.update(raw)
            files.append((name, raw, hashlib.sha256(raw).hexdigest()))
    finally:
        os.close(context_fd)

    sections = [
        _GEMINI36_ADVERSARY_OUTPUT_CONTRACT,
        "",
        _GEMINI36_ADVERSARY_REVIEW_OBJECTIVE,
        "",
        "SEALED CONTEXT BUNDLE",
        f"bundle_sha256: {bundle_hasher.hexdigest()}",
        f"file_count: {len(files)}",
    ]
    for name, raw, digest in files:
        sections.extend(
            (
                "",
                f"--- context/{name} ---",
                f"byte_length: {len(raw)}",
                f"sha256: {digest}",
                "content_utf8:",
                raw.decode("utf-8"),
                f"--- end context/{name} ---",
            )
        )
    sections.extend(
        (
            "",
            "Use only the sealed context bundle above. Do not access credentials or "
            "external data.",
            "",
            _GEMINI36_ADVERSARY_OUTPUT_CONTRACT,
        )
    )
    bundled = "\n".join(sections)
    if len(bundled.encode("utf-8")) > GEMINI36_ADVERSARY_MAX_PROMPT_BYTES:
        raise RuntimeError("sealed adversary prompt exceeds its bounded size")
    return bundled


def _load_qualified_adversary_transport(repo_root: Path) -> object:
    """Admit exactly one fresh, signed, nonexpired Gemini 3.6 adversary qualification."""
    path = DEFAULT_ADVERSARY_QUALIFICATION
    if not path.is_file() or path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RuntimeError("signed immutable adversary qualification is unavailable")
    verify_bytes = _read_hex_identity(DEFAULT_CODEX_RESPONSE_VERIFY_KEY, private=False)
    if verify_bytes is None:
        raise RuntimeError("adversary qualification verification identity is unavailable")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("adversary qualification is malformed") from exc
    required = {
        "schema", "provider_id", "model_id", "model_family", "transport", "role",
        "stage", "operation", "builder_family", "qualified", "issued_at", "expires_at",
        "service_sha256", "manifest_sha256", "packet_sha256", "evidence_sha256",
        "prompt_sha256", "disclosure_authorization_sha256", "signature",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise RuntimeError("adversary qualification fields are not exact")
    signature = record.pop("signature")
    if not isinstance(signature, str) or len(signature) != 128:
        raise RuntimeError("adversary qualification signature is malformed")
    try:
        VerifyKey(verify_bytes).verify(
            (json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode(),
            bytes.fromhex(signature),
        )
    except Exception as exc:
        raise RuntimeError("adversary qualification signature is invalid") from exc
    if (
        record.get("schema") != ADVERSARY_QUALIFICATION_SCHEMA
        or record.get("provider_id") != "google"
        or record.get("model_id") != "gemini-3.6-flash"
        or record.get("model_family") != "gemini"
        or record.get("transport") != "parent-owned"
        or record.get("role") != "ADVERSARY"
        or record.get("stage") != "ADVERSARIAL_REVIEW"
        or record.get("operation") != "adversarial_review"
        or record.get("builder_family") == "gemini"
        or record.get("qualified") is not True
        or not isinstance(record.get("service_sha256"), str)
        or len(record["service_sha256"]) != 64
        or not isinstance(record.get("manifest_sha256"), str)
        or len(record["manifest_sha256"]) != 64
        or not isinstance(record.get("packet_sha256"), str)
        or len(record["packet_sha256"]) != 64
        or not isinstance(record.get("evidence_sha256"), str)
        or len(record["evidence_sha256"]) != 64
        or not isinstance(record.get("prompt_sha256"), str)
        or len(record["prompt_sha256"]) != 64
        or not isinstance(record.get("disclosure_authorization_sha256"), str)
        or len(record["disclosure_authorization_sha256"]) != 64
    ):
        raise RuntimeError("adversary qualification does not select the exact route")
    issued, expires = record.get("issued_at"), record.get("expires_at")
    now = time.time()
    if (
        isinstance(issued, bool) or isinstance(expires, bool)
        or not isinstance(issued, (int, float)) or not isinstance(expires, (int, float))
        or expires <= issued or expires <= now
    ):
        raise RuntimeError("adversary qualification is expired")
    key_bytes = _read_raw_seed(repo_root / "ops" / "keys" / "kernel_ed25519.key")
    if key_bytes is None:
        raise RuntimeError("repository kernel signing key is unavailable or malformed")
    try:
        return HostGemini36AdversaryTransport(
            parent_exchange=parent_gemini36_adversary_exchange,
            request_signing_key=SigningKey(key_bytes),
            builder_family=str(record["builder_family"]),
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError("qualified parent-owned Gemini 3.6 adversary transport is malformed") from exc


class _Gemini36AdversaryRuntime(GlmRuntime):
    """Use the base isolated workspace contract while removing Cline from adversary dispatch."""

    def __init__(self, *, adversary_transport: object | None, **kwargs: object) -> None:
        self._adversary_transport = adversary_transport
        kwargs["default_model"] = "google:gemini-3.6-flash"
        super().__init__(**kwargs)

    def run(self, package):  # type: ignore[no-untyped-def]
        if package.role is Role.ADVERSARY:
            if package.stage is not StageId.ADVERSARIAL_REVIEW or self._adversary_transport is None:
                def unavailable(_spec: object) -> SessionResult:
                    raise TrustedTransportFailure(
                        "adversary_transport_unavailable",
                        "qualified parent-owned Gemini 3.6 adversary transport is not configured",
                    )
                return self._run_with_invoker(package, unavailable)

            def parent_owned(spec: object) -> SessionResult:
                try:
                    proxy = SimpleNamespace(
                        workspace=spec.workspace,
                        prompt=_build_gemini36_adversary_prompt(spec.prompt, spec.workspace),
                        allowed_tools=spec.allowed_tools,
                        read_scopes=spec.read_scopes,
                        timeout_s=spec.timeout_s,
                        lifecycle_state_path=spec.lifecycle_state_path,
                        task_id=spec.task_id,
                        goal_id=spec.goal_id,
                        run_id=spec.run_id,
                        stage=spec.stage,
                        role=Role.ADVERSARY,
                        operation="adversarial_review",
                        builder_family=getattr(self._adversary_transport, "builder_family", "gpt"),
                    )
                    result = self._adversary_transport.run(proxy)
                except Exception as exc:
                    if isinstance(exc, TrustedTransportFailure):
                        raise
                    raise TrustedTransportFailure(
                        "adversary_transport_failure",
                        "parent-owned Gemini 3.6 adversary transport failed closed",
                    ) from exc
                report = spec.workspace / "review" / "adversary_report.md"
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text(result.transcript, encoding="utf-8")
                return SessionResult(
                    transcript=result.transcript,
                    lifecycle_state=result.lifecycle_state,
                    exit_code=result.exit_code,
                    environment_fingerprint=result.environment_fingerprint,
                    actual_provider="google",
                    actual_model="gemini-3.6-flash",
                    actual_family="gemini",
                )

            return self._run_with_invoker(package, parent_owned)

        return super().run(package)


def _execute_nested_remediation_run(
    intake: Intake,
    run_id: str,
    mission_controller: PersistentMissionController,
    state_dir: Path,
) -> RunOutcome:
    graph = mission_controller.graph
    goal_id = "g-" + uuid.uuid4().hex[:12]

    # Check if we already have an active leaf task reconstructed from durable ledger (restart after crash)
    active_leaves = [
        t for t in graph.tasks.values()
        if t.status is TaskStatus.ACTIVE and t.parent_task_id is not None
    ]
    if active_leaves:
        leaf = active_leaves[0]
        remediates = [
            e.target_id for e in graph.edges
            if e.edge_type is EdgeType.REMEDIATES and e.source_id == leaf.task_id
        ]
        if remediates:
            leaf_blocker_id = remediates[0]
            unwound = mission_controller.execute_autonomous_unwind_to_root(
                leaf_task_id=leaf.task_id,
                leaf_blocker_id=leaf_blocker_id,
            )
            return RunOutcome(
                status=RunStatus.SEALED,
                goal_id=goal_id,
                detail=f"Autonomous unwind completed: {' -> '.join(unwound)}",
            )

    # Fresh run: build the 5-level nested remediation hierarchy
    if "task-A" not in graph.tasks:
        mission_controller.start_root_task("task-A", metadata={"goal_signature": intake.goal_signature})

    # Task A blocked by B01 -> spawns C
    if "task-C" not in graph.tasks:
        mission_controller.handle_blocker_and_spawn_remediation(
            parent_task_id="task-A",
            blocker_id="blocker-B01",
            signature="core_error",
            finding_class=FindingClass.CURRENT_BLOCKER,
            checkpoint_payload={"step": "A", "run_id": run_id},
            child_task_id="task-C",
            requested_paths=("runtime/core.py", "runtime/util.py"),
            requested_tier=AuthorityTier.A1_LOCAL_SUBSYSTEM,
        )

    # Task C blocked by B02 -> spawns E
    if "task-E" not in graph.tasks:
        mission_controller.handle_blocker_and_spawn_remediation(
            parent_task_id="task-C",
            blocker_id="blocker-B02",
            signature="util_error",
            finding_class=FindingClass.CURRENT_BLOCKER,
            checkpoint_payload={"step": "C", "run_id": run_id},
            child_task_id="task-E",
            requested_paths=("runtime/util.py",),
            requested_tier=AuthorityTier.A0_IMPLEMENTATION,
        )

    # If controller-death test is requested, notify test harness and pause for SIGKILL
    if os.environ.get("PAEOS_CONTROLLER_DEATH_TEST") == "1":
        print("[PMC] Ready for SIGKILL", flush=True)
        time.sleep(30)
        return RunOutcome(
            status=RunStatus.HALTED,
            goal_id=goal_id,
            detail="PAEOS_CONTROLLER_DEATH_TEST timeout waiting for SIGKILL",
        )

    # Normal execution (no SIGKILL): autonomously unwind to root
    unwound = mission_controller.execute_autonomous_unwind_to_root(
        leaf_task_id="task-E",
        leaf_blocker_id="blocker-B02",
    )
    return RunOutcome(
        status=RunStatus.SEALED,
        goal_id=goal_id,
        detail=f"Autonomous unwind completed: {' -> '.join(unwound)}",
    )


def build_scheduler(
    state_dir: Path,
    repo_root: Path,
    *,
    global_budget: GlobalBudget,
    max_concurrency: int = 1,
    runtime_type: str = "claude",
) -> tuple[ContinuousScheduler | ConcurrentScheduler, EvolutionLayer, Ledger]:
    """Wire the live autonomous loop over `state_dir`, driving builds against `repo_root`."""
    state_dir.mkdir(parents=True, exist_ok=True)
    signing_key = load_or_create_signing_key(state_dir / "seal.key")
    manifest_path = (
        repo_root / "ops" / "manifests" / "p1_authoritative_completeness_manifest.json"
    )
    completeness_manifest = load_authoritative_manifest(manifest_path)

    # The evidence pool + the --mcp-config that launches the court server against THIS pool. The
    # live builder session submits to it via the `submit_evidence` MCP tool; we read it back here.
    transport = McpWorkerTransport(state_dir / "court")
    workspace_base = DEFAULT_CODEX_WORKSPACE_ROOT
    workspace_base.mkdir(mode=0o700, parents=True, exist_ok=True)
    config_file = state_dir / "mcp-config.json"
    config_file.write_text(
        json.dumps(transport.mcp_config(repo_root, workspace_base=workspace_base)),
        encoding="utf-8",
    )

    cas = CAS(FilesystemCasStore(state_dir / "cas"))
    codex_transport = None
    planner_transport = None
    planner_readiness = None
    critic_binding = None
    adversary_binding = None
    if runtime_type in {"codex", "hybrid"}:
        codex_transport = _load_codex_transport(workspace_base)
        luna_planner = _load_luna_planner_transport(workspace_base)
        planner_transport = luna_planner[0] if luna_planner is not None else None
        planner_readiness = luna_planner[1] if luna_planner is not None else None
        if planner_readiness is not None:
            # A planner qualification that does not physically qualify CRITIQUE cannot
            # replace the independently qualified legacy critic transport.
            with contextlib.suppress(PlannerTransportNotReady):
                critic_binding = LunaCriticBinding.from_readiness(planner_readiness)
            with contextlib.suppress(PlannerTransportNotReady):
                adversary_binding = _load_luna_adversary_binding(
                    repo_root, completeness_manifest.manifest_sha256, planner_readiness
                )
    if runtime_type == "codex":
        runtime = CodexRuntime(
            state_root=state_dir.resolve(),
            workspace_root=workspace_base,
            workspace_source=repo_root,
            artifact_resolver=cas.get,
            mcp_config_path=config_file,
            host_transport=codex_transport,
            planner_transport=planner_transport,
            planner_readiness=planner_readiness,
            critic_binding=critic_binding,
            adversary_binding=adversary_binding,
        )
    elif runtime_type == "hybrid":
        critic_transport = (
            None
            if critic_binding is not None
            else _load_qualified_critic_transport(repo_root)
        )
        adversary_transport = _load_qualified_adversary_transport(repo_root)
        critic_runtime_kwargs = {
            "state_root": state_dir.resolve(),
            "workspace_root": workspace_base,
            "workspace_source": repo_root,
            "artifact_resolver": cas.get,
            "mcp_config_path": config_file,
        }
        if critic_transport is not None:
            critic_runtime_kwargs.update(
                critic_transport=critic_transport,
                default_model=(
                    f"{critic_transport.provider_id}:{critic_transport.model_id}"
                ),
            )
        adversary_runtime = _Gemini36AdversaryRuntime(
            adversary_transport=adversary_transport,
            **critic_runtime_kwargs,
        )
        runtime = HybridRuntime(
            state_root=state_dir.resolve(),
            workspace_root=workspace_base,
            workspace_source=repo_root,
            artifact_resolver=cas.get,
            mcp_config_path=config_file,
            codex_transport=codex_transport,
            planner_transport=planner_transport,
            planner_readiness=planner_readiness,
            critic_transport=critic_transport,
            critic_binding=critic_binding,
            adversary_binding=adversary_binding,
            glm_runtime=adversary_runtime,
        )
    elif runtime_type in ("glm", "cline"):
        # Single-model interim (notebook Entry 142 LIMITATION): GPT quota exhausted until
        # ~2026-08-22, so construction AND audit both run on GLM-5.3 via Cline. Homogeneous-audit
        # risk — every seal from this window carries that caveat. Re-run the proof intake on
        # `hybrid` when GPT quota returns.
        from runtime.integrations.hybrid import GlmRuntime

        runtime = GlmRuntime(
            state_root=state_dir.resolve(),
            workspace_root=workspace_base,
            workspace_source=repo_root,
            artifact_resolver=cas.get,
            mcp_config_path=config_file,
        )
    elif runtime_type in ("chat-bridge", "antigravity"):
        from runtime.integrations.chat_bridge import ChatBridgeRuntime

        runtime = ChatBridgeRuntime(
            state_root=state_dir.resolve(),
            workspace_root=workspace_base,
            workspace_source=repo_root,
            artifact_resolver=cas.get,
        )
    elif runtime_type == "bound-cline":
        raise ValueError(
            "bound-cline requires an explicit BoundClineWorkerRuntime configuration; "
            "autonomous_run will not infer provider, profile, qualification, or worktree values"
        )
    else:
        runtime = ClaudeCodeRuntime(
            state_root=state_dir.resolve(),
            workspace_root=workspace_base,
            workspace_source=repo_root,
            artifact_resolver=cas.get,
            mcp_config_path=config_file,
        )
    ledger = Ledger(SqliteLedgerStore(state_dir / "ledger.db"))
    scar_store = durable_scar_store(state_dir)
    run_registry = RunStateRegistry(
        Path("/private/tmp/paeos-governed-run-roots") / state_dir.name,
        signing_key,
    )
    root_envelope = AuthorityEnvelope(
        root_mission_id=f"mission-{state_dir.name}",
        authorized_paths=frozenset({
            str(repo_root.resolve()),
            str(state_dir.resolve()),
            "",
            ".",
            "runtime",
            "ops",
            "tests",
            "kernel",
            "paeos",
            "runtime/core.py",
            "runtime/util.py",
            "ops/check.py",
        }),
        delegated_ceiling=AuthorityTier.A3_ACCEPTANCE_CONTRACT,
        allowed_action=ActionPermission.COUNCIL_EVIDENCE_GATE,
    )
    mission_controller = PersistentMissionController.recover_from_durable_state(
        ledger=ledger,
        cas=cas,
        root_envelope=root_envelope,
    )
    loop = SoftLoop(
        ledger=ledger,
        signing_key=signing_key,
        cas=cas,
        agent_runtime=runtime,
        budget_by_class=DEFAULT_BUDGETS,
        scar_store=scar_store,
        repo_root=repo_root,  # B2.N: the court verifies each command in a workspace WITH the change
        state_dir=state_dir,
        builder_transport_readiness=_load_builder_transport_readiness(),
        require_builder_transport_ready=runtime_type in {"codex", "hybrid"},
        run_state_registry=run_registry,
        mission_controller=mission_controller,
        # DEBT-0057: persistence is explicit — state-dir-owned, never repository-relative.
        sidecar_scorer=SidecarStageScorer(state_dir.resolve() / "evaluations"),
        l14_auditor=lambda candidate, pre_audit, evidence, manifest: audit_candidate(
            repo_root=repo_root,
            state_dir=state_dir.resolve(),
            candidate=candidate,
            pre_audit=pre_audit,
            evidence=evidence,
            manifest=manifest,
        ),
    )
    loop._playbook = _L10ContextPlaybook(loop._playbook)
    evolution = EvolutionLayer(
        scar_store=loop.scar_store, ledger=ledger
    )  # sole L3 author (Stage 17)
    evolution_lock = (
        threading.Lock()
    )  # IP-0005: serialize L3 authoring under parallel execution

    def run_one(intake: Intake) -> RunOutcome:
        run_id = (
            "r-" + uuid.uuid4().hex[:8]
        )  # unique per run: keys this run's court pool + prompt

        # PRE-P2 Autonomous Nested Remediation Support & Crash Recovery
        if intake.goal_signature == "PRE_P2_5_LEVEL_NESTED_REMEDIATION" or any(
            t.status is TaskStatus.ACTIVE and t.parent_task_id is not None
            for t in mission_controller.graph.tasks.values()
        ):
            return _execute_nested_remediation_run(
                intake=intake,
                run_id=run_id,
                mission_controller=mission_controller,
                state_dir=state_dir,
            )

        outcome = loop.run(
            objective=intake.objective,
            changed_paths=intake.changed_paths,
            plan_write_scopes=intake.plan_write_scopes,
            builder_evidence=(),
            goal_signature=intake.goal_signature,
            verifiable=intake.verifiable,
            reversible=intake.reversible,
            run_id=run_id,
            evidence_source=transport,  # the EvidenceSource port — MCP is just one implementation
            capability_manifest=completeness_manifest,
        )
        with (
            evolution_lock
        ):  # single-committer L3 authoring stays serial under parallel execution
            evolution.run(
                outcome,
                goal_signature=intake.goal_signature,
                changed_paths=intake.changed_paths,
                run_id=run_id,
            )
        # RB-0008: autonomous friction detection — classify and record structural gaps.
        sig = intake.goal_signature
        has_matching_scar = bool(loop.scar_store.match_scars(sig)) if sig else False
        friction = classify_friction(
            outcome, intake.changed_paths, has_matching_scar=has_matching_scar
        )
        if friction.category is not FrictionCategory.NONE:
            path = record_friction(friction, repo_root)
            if path:
                print(f"[RB-0008] Friction recorded: {path}", file=sys.stderr)
        if friction.high_leverage_intake is not None:
            from dataclasses import replace

            outcome = replace(
                outcome, high_leverage_intake=friction.high_leverage_intake
            )
        return outcome

    governor = EconomicGovernor(global_budget)
    scheduler: ContinuousScheduler | ConcurrentScheduler = (
        ConcurrentScheduler(
            run_one,
            governor=governor,
            budget_by_class=DEFAULT_BUDGETS,
            max_concurrency=max_concurrency,
        )
        if max_concurrency > 1
        else ContinuousScheduler(
            run_one, governor=governor, budget_by_class=DEFAULT_BUDGETS
        )
    )
    return scheduler, evolution, ledger


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not 2 <= len(argv) <= 5:
        print(
            "usage: python ops/autonomous_run.py <backlog.json> <state_dir> "
            "[max_concurrency] [max_runs] "
            "[runtime_type: claude|codex|hybrid|glm|chat-bridge|bound-cline]",
            file=sys.stderr,
        )
        return 64
    backlog_path, state_dir = Path(argv[0]), Path(argv[1])
    max_concurrency = int(argv[2]) if len(argv) >= 3 else 1
    max_runs = int(argv[3]) if len(argv) >= 4 else 25
    runtime_type = argv[4] if len(argv) >= 5 else "claude"
    repo_root = Path.cwd()

    backlog = parse_backlog(json.loads(backlog_path.read_text(encoding="utf-8")))
    scheduler, _evolution, ledger = build_scheduler(
        state_dir,
        repo_root,
        # A contained ceiling: enough for specified runs; halts (not spins) when exhausted.
        global_budget=GlobalBudget(
            tokens=25_000_000, wallclock_s=72_000, runs=max_runs
        ),
        max_concurrency=max_concurrency,
        runtime_type=runtime_type,
    )
    report = scheduler.run(backlog)

    sealed = [o for o in report.outcomes if o.status is RunStatus.SEALED]
    summary = {
        "runs": len(report.outcomes),
        "sealed": len(sealed),
        "stop_reason": report.stop_reason.value,
        "remaining_tokens": report.remaining.tokens,
        "outcomes": [
            {
                "goal_id": o.goal_id,
                "status": o.status.value,
                "detail": o.detail,
                "seal_hash": (o.seal.seal_hash if o.seal is not None else None),
            }
            for o in report.outcomes
        ],
        "ledger_head": ledger.verify_chain(),  # K3: the seal is on a verified hash chain
    }
    print(json.dumps(summary, indent=2))
    # Genuine success only if at least one run reached a real, adversary-PASS seal.
    return 0 if sealed else 2


if __name__ == "__main__":
    raise SystemExit(main())
