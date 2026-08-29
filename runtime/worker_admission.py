"""Fail-closed worker admission contract and receipt validation.

Provider-neutral admission contracts, physical model receipts, tool-policy
evaluation, and worker-run assessment for disposable route-qualification probes.
No worker prose is trusted. Unknown, absent, or conflicting identity fails closed.
"""

from __future__ import annotations

import hashlib
import json
import shlex
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path

from paeos.model_router.a08_enforcer import (
    A08EnforcementResult,
    A08Enforcer,
    derive_family_from_actual_model,
)
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.types import ModelFamily


class AdmissionError(RuntimeError):
    """Raised when a physical receipt or admission check fails closed."""


class AdmissionVerdict(StrEnum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


def _canonical_hash(obj: object) -> str:
    """Deterministic SHA-256 of all dataclass fields in declaration order."""
    parts: list[str] = []
    for f in fields(obj):  # type: ignore[arg-type]
        val = getattr(obj, f.name)
        if isinstance(val, tuple):
            parts.append(f"{f.name}={','.join(str(v) for v in val)}")
        else:
            parts.append(f"{f.name}={val}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _is_hex64(s: str) -> bool:
    """Check that a string is exactly 64 lowercase hex characters."""
    return len(s) == 64 and all(c in "0123456789abcdef" for c in s)


# ---------------------------------------------------------------------------
# Immutable contracts and records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProbeContract:
    """Defines what a disposable admission probe must do and prove."""

    probe_id: str
    sandbox: Path
    provider_id: str
    model_id: str
    expected_family: ModelFamily
    artifact_name: str
    initial_bytes: bytes
    expected_bytes: bytes
    verification_command: str

    @property
    def artifact_path(self) -> Path:
        return (self.sandbox / self.artifact_name).resolve()


@dataclass(frozen=True, slots=True)
class PhysicalModelReceipt:
    """Hash-bound record of what the local transport actually observed."""

    transport_id: str
    session_id: str
    pid: int
    configured_provider_id: str
    configured_model_id: str
    actual_provider_id: str
    actual_model_id: str
    actual_family: ModelFamily
    manifest_provider_id: str
    manifest_model_id: str
    message_models: tuple[str, ...]
    argv_hash: str
    stdout_hash: str
    stderr_hash: str
    manifest_hash: str
    messages_hash: str

    @property
    def receipt_hash(self) -> str:
        return _canonical_hash(self)


@dataclass(frozen=True, slots=True)
class ToolDecisionRecord:
    """Immutable record of a single tool-policy decision."""

    tool_name: str
    approved: bool
    reason_code: str


@dataclass(frozen=True, slots=True)
class VerificationReceipt:
    """Hash-only evidence for baseline/candidate/mutation/restoration verification."""

    argv: tuple[str, ...]
    argv_hash: str
    baseline_artifact_hash: str
    baseline_exit_code: int
    baseline_stdout_hash: str
    baseline_stderr_hash: str
    candidate_artifact_hash: str
    candidate_exit_code: int
    candidate_stdout_hash: str
    candidate_stderr_hash: str
    mutation_hash: str
    mutation_exit_code: int
    mutation_stdout_hash: str
    mutation_stderr_hash: str
    artifact_restored_hash: str
    restored_exit_code: int
    restored_stdout_hash: str
    restored_stderr_hash: str


@dataclass(frozen=True, slots=True)
class RawWorkerRun:
    """Structured evidence from a completed worker probe invocation."""

    probe_id: str
    receipt: PhysicalModelReceipt
    tool_decisions: tuple[ToolDecisionRecord, ...]
    artifact_name: str
    artifact_hash: str
    artifact_size: int
    verification: VerificationReceipt


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    """Final admission verdict with machine-readable reasons."""

    verdict: AdmissionVerdict
    reasons: tuple[str, ...]


# ---------------------------------------------------------------------------
# Receipt validation
# ---------------------------------------------------------------------------


def validate_physical_receipt(
    receipt: PhysicalModelReceipt,
    contract: ProbeContract,
) -> None:
    """Validate all receipt fields against the contract. Raises AdmissionError."""
    # Positive PID and non-empty identifiers
    if receipt.pid <= 0:
        raise AdmissionError("invalid PID")
    if not receipt.session_id:
        raise AdmissionError("empty session_id")
    if not receipt.transport_id:
        raise AdmissionError("empty transport_id")

    # Family must not be UNKNOWN — check this early
    if receipt.actual_family == ModelFamily.UNKNOWN:
        raise AdmissionError("unknown physical family")

    # Derive family from actual model and verify consistency
    catalog = ModelCatalog()
    derived = derive_family_from_actual_model(receipt.actual_model_id, catalog)
    if derived != receipt.actual_family:
        raise AdmissionError(
            f"family mismatch: derived {derived} != receipt {receipt.actual_family}"
        )

    # Configured must match contract
    if receipt.configured_provider_id != contract.provider_id:
        raise AdmissionError("provider mismatch: configured does not match contract")
    if receipt.configured_model_id != contract.model_id:
        raise AdmissionError("model mismatch: configured does not match contract")

    # Actual must match configured
    if receipt.actual_provider_id != receipt.configured_provider_id:
        raise AdmissionError("provider mismatch: actual does not match configured")
    if receipt.actual_model_id != receipt.configured_model_id:
        raise AdmissionError("model mismatch: actual does not match configured")

    # Family must match contract expectation after exact identity has been
    # reconciled, so a substituted model is reported as an identity conflict.
    if receipt.actual_family != contract.expected_family:
        raise AdmissionError("family mismatch: actual does not match contract expected")

    # Manifest must match configured
    if receipt.manifest_provider_id != receipt.configured_provider_id:
        raise AdmissionError("provider mismatch: manifest does not match configured")
    if receipt.manifest_model_id != receipt.configured_model_id:
        raise AdmissionError("model mismatch: manifest does not match configured")

    # Every message model must match actual
    for msg_model in receipt.message_models:
        if msg_model and msg_model != receipt.actual_model_id:
            raise AdmissionError("model mismatch: message model does not match actual")

    # All hash fields must be valid 64-char lowercase hex
    for hash_field in (
        "argv_hash",
        "stdout_hash",
        "stderr_hash",
        "manifest_hash",
        "messages_hash",
    ):
        if not _is_hex64(getattr(receipt, hash_field)):
            raise AdmissionError(f"invalid hash: {hash_field}")


# ---------------------------------------------------------------------------
# Pure tool-policy evaluation
# ---------------------------------------------------------------------------

_DENIED = False
_APPROVED = True


def _deny(tool_name: str, reason_code: str) -> ToolDecisionRecord:
    return ToolDecisionRecord(tool_name=tool_name, approved=_DENIED, reason_code=reason_code)


def evaluate_tool_request(
    contract: ProbeContract,
    request: object,
    prior_decisions: tuple[ToolDecisionRecord, ...] = (),
) -> ToolDecisionRecord:
    """Evaluate a single tool request against the probe contract.

    Never raises. Always returns a ToolDecisionRecord. Never executes a tool.
    """
    # Handle non-dict requests
    if not isinstance(request, dict):
        return _deny("<malformed>", "MALFORMED_REQUEST")

    tool_name = request.get("toolName")
    if not isinstance(tool_name, str):
        return _deny("<malformed>", "MALFORMED_REQUEST")

    tool_input = request.get("input")
    if tool_input is None:
        return _deny(tool_name, "MALFORMED_REQUEST")

    # Only editor and run_commands are allowed
    if tool_name == "editor":
        return _evaluate_editor(contract, tool_input, prior_decisions)
    if tool_name == "run_commands":
        return _evaluate_run_commands(contract, tool_input, prior_decisions)

    return _deny(tool_name, "UNAUTHORIZED_TOOL")


def _evaluate_editor(
    contract: ProbeContract,
    tool_input: object,
    prior_decisions: tuple[ToolDecisionRecord, ...],
) -> ToolDecisionRecord:
    """Evaluate an editor tool request. Approves only the exact contract edit once."""
    name = "editor"

    if not isinstance(tool_input, dict):
        return _deny(name, "MALFORMED_INPUT")

    # Editor is single-use
    if any(d.approved and d.tool_name == "editor" for d in prior_decisions):
        return _deny(name, "EDITOR_ALREADY_USED")

    path_str = tool_input.get("path")
    old_text = tool_input.get("old_text")
    new_text = tool_input.get("new_text")

    if (
        not isinstance(path_str, str)
        or not isinstance(old_text, str)
        or not isinstance(new_text, str)
    ):
        return _deny(name, "MALFORMED_INPUT")

    # Exact text match required — no normalization
    if old_text != contract.initial_bytes.decode():
        return _deny(name, "WRONG_OLD_TEXT")
    if new_text != contract.expected_bytes.decode():
        return _deny(name, "WRONG_NEW_TEXT")

    # Path validation: symlink check, then resolve and containment
    try:
        input_path = Path(path_str)
        # Explicit symlink escape detection
        if input_path.is_symlink():
            return _deny(name, "SYMLINK_ESCAPE")
        resolved = input_path.resolve()
    except (ValueError, OSError):
        return _deny(name, "INVALID_PATH")

    # Construct expected path from sandbox without following symlinks on artifact
    sandbox_resolved = contract.sandbox.resolve()
    expected_resolved = sandbox_resolved / contract.artifact_name

    # Containment check
    try:
        if not resolved.is_relative_to(sandbox_resolved):
            return _deny(name, "PATH_OUTSIDE_SANDBOX")
    except (TypeError, ValueError):
        return _deny(name, "PATH_OUTSIDE_SANDBOX")

    # Exact artifact path match
    if resolved != expected_resolved:
        return _deny(name, "PATH_OUTSIDE_SANDBOX")

    return ToolDecisionRecord(tool_name=name, approved=_APPROVED, reason_code="")


def _evaluate_run_commands(
    contract: ProbeContract,
    tool_input: object,
    prior_decisions: tuple[ToolDecisionRecord, ...],
) -> ToolDecisionRecord:
    """Evaluate a run_commands request. Approves only the exact verification command once."""
    name = "run_commands"

    if not isinstance(tool_input, dict):
        return _deny(name, "MALFORMED_INPUT")

    # Editor must be approved first
    if not any(d.approved and d.tool_name == "editor" for d in prior_decisions):
        return _deny(name, "EDITOR_NOT_APPROVED")

    # Single use
    if any(d.approved and d.tool_name == "run_commands" for d in prior_decisions):
        return _deny(name, "RUN_ALREADY_USED")

    commands = tool_input.get("commands")
    if not isinstance(commands, list) or len(commands) != 1:
        return _deny(name, "WRONG_COMMAND_COUNT")

    # Exact byte-for-byte command equality — no shell expansion
    if commands[0] != contract.verification_command:
        return _deny(name, "COMMAND_MISMATCH")

    return ToolDecisionRecord(tool_name=name, approved=_APPROVED, reason_code="")


# ---------------------------------------------------------------------------
# Worker-run assessment
# ---------------------------------------------------------------------------


def assess_worker_run(
    contract: ProbeContract,
    run: RawWorkerRun,
) -> AdmissionResult:
    """Assess a completed worker run. Returns ADMITTED or REJECTED with reasons."""
    reasons: list[str] = []

    # A run is evidence only for its own probe; cross-probe replay fails closed.
    if run.probe_id != contract.probe_id:
        reasons.append("probe ID mismatch")

    # Validate receipt independently
    try:
        validate_physical_receipt(run.receipt, contract)
    except AdmissionError as e:
        reasons.append(f"receipt: {e}")

    # Require exactly two approved decisions: editor then run_commands
    decisions = run.tool_decisions
    if len(decisions) != 2:
        reasons.append(f"expected 2 tool decisions, got {len(decisions)}")
    else:
        if not (decisions[0].approved and decisions[0].tool_name == "editor"):
            reasons.append("first decision must be approved editor")
        if not (decisions[1].approved and decisions[1].tool_name == "run_commands"):
            reasons.append("second decision must be approved run_commands")

    # Any denied decision is a rejection
    if any(not d.approved for d in decisions):
        reasons.append("denied tool decision present")

    # Artifact checks
    if run.artifact_name == ".DS_Store":
        reasons.append("artifact is .DS_Store junk")

    expected_hash = hashlib.sha256(contract.expected_bytes).hexdigest()
    if run.artifact_hash != expected_hash:
        reasons.append("artifact hash mismatch")

    if run.artifact_size == 0:
        reasons.append("artifact is empty")

    verification = run.verification
    if verification.argv != tuple(shlex.split(contract.verification_command)):
        reasons.append("verification argv mismatch")
    expected_argv_hash = hashlib.sha256(
        json.dumps(verification.argv, separators=(",", ":")).encode()
    ).hexdigest()
    if verification.argv_hash != expected_argv_hash:
        reasons.append("verification argv hash mismatch")
    if verification.baseline_artifact_hash != hashlib.sha256(
        contract.initial_bytes
    ).hexdigest():
        reasons.append("verification baseline artifact mismatch")
    if verification.candidate_artifact_hash != expected_hash:
        reasons.append("verification candidate artifact mismatch")
    if verification.artifact_restored_hash != expected_hash:
        reasons.append("verification restoration artifact mismatch")
    if verification.mutation_hash != hashlib.sha256(
        b"seeded-mutation\n"
    ).hexdigest():
        reasons.append("verification mutation hash mismatch")
    if verification.baseline_exit_code == 0:
        reasons.append("baseline verification did not fail")
    if verification.candidate_exit_code != 0:
        reasons.append("candidate verification did not pass")
    if verification.mutation_exit_code == 0:
        reasons.append("seeded mutation verification did not fail")
    if verification.restored_exit_code != 0:
        reasons.append("restored verification did not pass")
    for name in (
        "argv_hash",
        "baseline_stdout_hash",
        "baseline_stderr_hash",
        "candidate_stdout_hash",
        "candidate_stderr_hash",
        "mutation_hash",
        "mutation_stdout_hash",
        "mutation_stderr_hash",
        "restored_stdout_hash",
        "restored_stderr_hash",
    ):
        if not _is_hex64(getattr(verification, name)):
            reasons.append(f"invalid verification hash: {name}")

    if reasons:
        return AdmissionResult(
            verdict=AdmissionVerdict.REJECTED, reasons=tuple(reasons)
        )

    return AdmissionResult(verdict=AdmissionVerdict.ADMITTED, reasons=())


# ---------------------------------------------------------------------------
# Task 5: admitted worker bindings and receipt decorrelation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkerBinding:
    """Validated worker identity backed by admitted probe evidence.

    The constructor accepts only the evidence pair (ProbeContract,
    RawWorkerRun) and re-assesses admission on every construction path, so
    identity fields are never caller-supplied and no binding can exist without
    an AdmissionVerdict.ADMITTED assessment. Identity is derived internally
    from the validated structured physical receipt.
    """

    contract: ProbeContract
    run: RawWorkerRun

    def __post_init__(self) -> None:
        result = assess_worker_run(self.contract, self.run)
        if result.verdict is not AdmissionVerdict.ADMITTED:
            raise AdmissionError("worker not admitted: " + "; ".join(result.reasons))

    @property
    def transport(self) -> str:
        return self.run.receipt.transport_id

    @property
    def session(self) -> str:
        return self.run.receipt.session_id

    @property
    def pid(self) -> int:
        return self.run.receipt.pid

    @property
    def tty(self) -> str | None:
        return None  # headless probe receipts carry no TTY evidence

    @property
    def provider(self) -> str:
        return self.run.receipt.actual_provider_id

    @property
    def model(self) -> str:
        return self.run.receipt.actual_model_id

    @property
    def family(self) -> ModelFamily:
        return self.run.receipt.actual_family

    @property
    def receipt_hash(self) -> str:
        return self.run.receipt.receipt_hash


def admitted_worker_binding(
    contract: ProbeContract, run: RawWorkerRun
) -> WorkerBinding:
    """Return the validated binding for an admitted worker run.

    Delegates to the WorkerBinding evidence constructor, which re-assesses
    admission and rejects anything other than AdmissionVerdict.ADMITTED.
    Identity is derived only from the validated structured physical receipt —
    never from caller arguments or worker prose.
    """
    return WorkerBinding(contract, run)


def enforce_receipt_decorrelation(
    builder: WorkerBinding, auditor: WorkerBinding
) -> A08EnforcementResult:
    """Fail-closed A-08 decorrelation between builder and auditor bindings.

    Provider, model, and family facts come exclusively from evidence-backed
    WorkerBinding instances — every construction path re-assessed admission —
    and are delegated to the existing A08Enforcer, which fails closed on same
    or unknown families. Usable both before auditor dispatch (candidate
    receipt) and against the auditor's post-dispatch physical receipt.
    """
    return A08Enforcer(ModelCatalog()).enforce(
        builder_provider=builder.provider,
        builder_model_id=builder.model,
        builder_family=builder.family,
        auditor_provider=auditor.provider,
        auditor_model_id=auditor.model,
        auditor_family=auditor.family,
    )
