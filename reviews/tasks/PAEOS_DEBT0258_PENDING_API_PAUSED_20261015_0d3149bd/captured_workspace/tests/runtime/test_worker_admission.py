"""RED tests: Task 2 worker admission.

Plan: 2026-08-26-paeos-cline-worker-admission.md, lines 168-369.

runtime.worker_admission does not exist until Step 2.4, so these fail at import (RED). Assumed
shapes for Step 2.4: ToolDecisionRecord exposes tool_name/approved/reason_code; RawWorkerRun
holds probe_id, receipt, tool_decisions, artifact_name, artifact_hash (sha256 hex),
artifact_size; AdmissionResult exposes verdict/reasons; assess_worker_run(contract, run);
editor input keys are path/old_text/new_text.
"""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from paeos.model_router.a08_enforcer import A08EnforcementResult, A08Verdict
from paeos.model_router.types import ModelFamily
from runtime.worker_admission import (
    AdmissionError,
    AdmissionResult,
    AdmissionVerdict,
    PhysicalModelReceipt,
    ProbeContract,
    RawWorkerRun,
    ToolDecisionRecord,
    VerificationReceipt,
    WorkerBinding,
    admitted_worker_binding,
    assess_worker_run,
    enforce_receipt_decorrelation,
    evaluate_tool_request,
    validate_physical_receipt,
)

ev = evaluate_tool_request
PROVIDER, MODEL = "cline-pass", "cline-pass/qwen3.8-max"
SESSION_ID, PID, TRANSPORT = "session-001", 4242, "headless:cline-cli-3.0.56"
OLD_TEXT, NEW_TEXT = "baseline-worker\n", "admitted-worker\n"
VERIFY = "python3 verify_probe.py"
EXPECTED_BYTES = NEW_TEXT.encode()
EXPECTED_HASH = hashlib.sha256(EXPECTED_BYTES).hexdigest()
HASHES = {f"{n}_hash": c * 64 for n, c in zip(
    ("argv", "stdout", "stderr", "manifest", "messages"), "abcde", strict=True)}


@pytest.fixture()
def contract(tmp_path: Path) -> ProbeContract:
    return ProbeContract(
        probe_id="probe-001", sandbox=tmp_path / "probe" / "sandbox", provider_id=PROVIDER,
        model_id=MODEL, expected_family=ModelFamily.QWEN, artifact_name="artifact.txt",
        initial_bytes=OLD_TEXT.encode(), expected_bytes=EXPECTED_BYTES,
        verification_command=VERIFY)


def physical_receipt(c: ProbeContract) -> PhysicalModelReceipt:
    return PhysicalModelReceipt(
        transport_id=TRANSPORT, session_id=SESSION_ID, pid=PID,
        configured_provider_id=PROVIDER, configured_model_id=MODEL, actual_provider_id=PROVIDER,
        actual_model_id=MODEL, actual_family=c.expected_family, manifest_provider_id=PROVIDER,
        manifest_model_id=MODEL, message_models=(MODEL,), **HASHES)


def approval_request(tool_name: str, tool_input: object) -> dict[str, object]:
    return {"requestId": "call-001", "sessionId": SESSION_ID,
            "createdAt": "2026-08-26T10:00:00+00:00", "toolCallId": "call-001",
            "toolName": tool_name, "input": tool_input, "iteration": 1}


def editor_input(c: ProbeContract, path: object = None, old_text: str = OLD_TEXT,
                 new_text: str = NEW_TEXT) -> dict[str, object]:
    return {"path": str(c.artifact_path if path is None else path), "old_text": old_text,
            "new_text": new_text}


def command_request(*commands: str) -> dict[str, object]:
    return approval_request("run_commands", {"commands": list(commands)})


def denied(c: ProbeContract, request: object, prior: tuple = ()) -> ToolDecisionRecord:
    d = ev(c, request, prior)
    assert not d.approved and d.reason_code
    return d


def ok_editor(c: ProbeContract) -> ToolDecisionRecord:
    d = ev(c, approval_request("editor", editor_input(c)))
    assert d.approved
    return d


def ok_runner(c: ProbeContract) -> ToolDecisionRecord:
    d = ev(c, command_request(VERIFY), (ok_editor(c),))
    assert d.approved
    return d


# Step 2.1: receipt consistency


def test_physical_receipt_requires_all_sources_to_match(contract):
    receipt = physical_receipt(contract)
    validate_physical_receipt(receipt, contract)
    with pytest.raises(AdmissionError, match="model mismatch"):
        validate_physical_receipt(
            replace(receipt, message_models=("cline-pass/deepseek-v4-flash",)), contract)


def test_unknown_family_fails_closed(contract):
    receipt = replace(physical_receipt(contract), actual_model_id="unattributable-model",
                      actual_family=ModelFamily.UNKNOWN,
                      manifest_model_id="unattributable-model",
                      message_models=("unattributable-model",))
    with pytest.raises(AdmissionError, match="unknown physical family"):
        validate_physical_receipt(receipt, replace(contract, model_id="unattributable-model"))


def test_receipt_hash_changes_when_raw_evidence_changes(contract):
    receipt = physical_receipt(contract)
    assert receipt.receipt_hash != replace(receipt, stderr_hash="f" * 64).receipt_hash


# Step 2.2: pure tool policy


def test_editor_approves_exact_contract_edit(contract):
    d = ev(contract, approval_request("editor", editor_input(contract)))
    assert isinstance(d, ToolDecisionRecord) and d.approved and d.tool_name == "editor"


@pytest.mark.parametrize("old_text,new_text", [
    ("wrong-baseline\n", NEW_TEXT), (OLD_TEXT, "wrong-target\n"),
    (OLD_TEXT.upper(), NEW_TEXT.upper()), (OLD_TEXT, OLD_TEXT)])
def test_editor_requires_exact_old_and_new_text(contract, old_text, new_text):
    denied(contract, approval_request(
        "editor", editor_input(contract, old_text=old_text, new_text=new_text)))


def test_editor_requires_exact_contained_artifact_path(contract, tmp_path):
    for bad_path in (contract.sandbox.parent / "other.txt", tmp_path / "outside.txt",
                     "/etc/passwd"):
        denied(contract, approval_request("editor", editor_input(contract, path=bad_path)))


def test_editor_denies_symlink_escape(contract, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"secret\n")
    contract.sandbox.mkdir(parents=True, exist_ok=True)
    link = contract.sandbox / contract.artifact_name
    link.symlink_to(outside)
    denied(contract, approval_request("editor", editor_input(contract, path=link)))


def test_run_commands_denied_before_editor_approval(contract):
    denied(contract, command_request(VERIFY))


def test_run_commands_approves_exact_command_only_after_editor(contract):
    d = ev(contract, command_request(VERIFY), (ok_editor(contract),))
    assert d.approved and d.tool_name == "run_commands"


@pytest.mark.parametrize("command", [
    f"cd /tmp/probe/sandbox && {VERIFY}", f"{VERIFY} && echo done", f"{VERIFY} --fast",
    "/usr/bin/python3 verify_probe.py", f"{VERIFY}; {VERIFY}"])
def test_run_commands_denies_altered_command(contract, command):
    denied(contract, command_request(command), (ok_editor(contract),))


def test_run_commands_denies_two_commands(contract):
    denied(contract, command_request(VERIFY, "echo done"), (ok_editor(contract),))


def test_run_commands_denied_after_single_use(contract):
    editor, runner = ok_editor(contract), ok_runner(contract)
    denied(contract, command_request(VERIFY), (editor, runner))


@pytest.mark.parametrize("tool_name", [
    "read_files", "search_codebase", "skills", "spawn_agent", "team_run_task", "quantum_probe"])
def test_prohibited_and_unknown_tools_denied(contract, tool_name):
    denied(contract, approval_request(tool_name, {"path": "/etc/passwd"}))


@pytest.mark.parametrize("raw_request", [
    None, 42, "editor", [], {}, {"toolName": "editor"},
    {"toolName": 42, "input": {}}, {"toolName": "editor", "input": None}])
def test_malformed_requests_denied_without_exceptions(contract, raw_request):
    d = denied(contract, raw_request)
    assert isinstance(d, ToolDecisionRecord)


# Step 2.2: assess_worker_run


def admitted_run(contract, receipt=None) -> RawWorkerRun:
    return RawWorkerRun(
        probe_id=contract.probe_id, receipt=receipt or physical_receipt(contract),
        tool_decisions=(ok_editor(contract), ok_runner(contract)),
        artifact_name=contract.artifact_name, artifact_hash=EXPECTED_HASH,
        artifact_size=len(EXPECTED_BYTES), verification=VerificationReceipt(
            argv=("python3", "verify_probe.py"),
            argv_hash=hashlib.sha256(
                json.dumps(
                    ("python3", "verify_probe.py"), separators=(",", ":")
                ).encode()
            ).hexdigest(),
            baseline_artifact_hash=hashlib.sha256(OLD_TEXT.encode()).hexdigest(),
            baseline_exit_code=1, baseline_stdout_hash="1" * 64,
            baseline_stderr_hash="2" * 64,
            candidate_artifact_hash=EXPECTED_HASH, candidate_exit_code=0,
            candidate_stdout_hash="3" * 64, candidate_stderr_hash="4" * 64,
            mutation_hash=hashlib.sha256(b"seeded-mutation\n").hexdigest(),
            mutation_exit_code=1, mutation_stdout_hash="5" * 64,
            mutation_stderr_hash="6" * 64, artifact_restored_hash=EXPECTED_HASH,
            restored_exit_code=0, restored_stdout_hash="7" * 64,
            restored_stderr_hash="8" * 64,
        ))


def assert_rejected(run: RawWorkerRun, contract) -> AdmissionResult:
    result = assess_worker_run(contract, run)
    assert result.verdict is AdmissionVerdict.REJECTED and result.reasons
    return result


def test_assess_admits_exact_approved_run(contract):
    result = assess_worker_run(contract, admitted_run(contract))
    assert isinstance(result, AdmissionResult)
    assert result.verdict is AdmissionVerdict.ADMITTED and not result.reasons


def test_assess_requires_both_decisions_in_exact_order(contract):
    editor, runner = admitted_run(contract).tool_decisions
    for decisions in ((), (editor,), (runner,), (runner, editor)):
        assert_rejected(replace(admitted_run(contract), tool_decisions=decisions), contract)


def test_assess_rejects_any_denial_or_extra_tool_event(contract):
    run = admitted_run(contract)
    editor, runner = run.tool_decisions
    extra = denied(contract, approval_request(
        "editor", editor_input(contract, old_text="bogus\n")), (editor, runner))
    assert_rejected(replace(run, tool_decisions=(editor, runner, extra)), contract)


def test_assess_validates_receipt_independently(contract):
    bad = replace(physical_receipt(contract),
                  message_models=("cline-pass/deepseek-v4-flash",))
    assert_rejected(admitted_run(contract, receipt=bad), contract)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("baseline_exit_code", 0),
        ("candidate_exit_code", 1),
        ("mutation_exit_code", 0),
        ("restored_exit_code", 1),
        ("artifact_restored_hash", "0" * 64),
        ("argv_hash", "0" * 64),
        ("mutation_hash", "0" * 64),
    ],
)
def test_assess_requires_discriminative_verification(contract, field, value):
    run = admitted_run(contract)
    bad_verification = replace(run.verification, **{field: value})
    assert_rejected(replace(run, verification=bad_verification), contract)


@pytest.mark.parametrize("artifact_name,artifact_hash,artifact_size", [
    ("artifact.txt", "f" * 64, len(EXPECTED_BYTES)),
    ("artifact.txt", EXPECTED_HASH, 0),
    (".DS_Store", EXPECTED_HASH, len(EXPECTED_BYTES))])
def test_assess_requires_exact_nonempty_artifact(
        contract, artifact_name, artifact_hash, artifact_size):
    assert_rejected(replace(admitted_run(contract), artifact_name=artifact_name,
                            artifact_hash=artifact_hash, artifact_size=artifact_size),
                    contract)


# ---------------------------------------------------------------------------
# Task 5: admitted worker bindings and receipt decorrelation
# ---------------------------------------------------------------------------


def evidence_binding(
    provider: str,
    model: str,
    family: ModelFamily,
    session: str = SESSION_ID,
    pid: int = PID,
    transport: str = TRANSPORT,
) -> WorkerBinding:
    """An authoritative binding built from valid contract + RawWorkerRun evidence."""
    contract = ProbeContract(
        probe_id="probe-001", sandbox=Path("/probe/sandbox"), provider_id=provider,
        model_id=model, expected_family=family, artifact_name="artifact.txt",
        initial_bytes=OLD_TEXT.encode(), expected_bytes=EXPECTED_BYTES,
        verification_command=VERIFY)
    # Built from the actual parameters — the module-level physical_receipt()
    # helper is hard-wired to the PROVIDER/MODEL probe constants.
    receipt = PhysicalModelReceipt(
        transport_id=transport, session_id=session, pid=pid,
        configured_provider_id=provider, configured_model_id=model,
        actual_provider_id=provider, actual_model_id=model, actual_family=family,
        manifest_provider_id=provider, manifest_model_id=model,
        message_models=(model,), **HASHES)
    return WorkerBinding(contract, admitted_run(contract, receipt=receipt))


def qwen_builder() -> WorkerBinding:
    return evidence_binding(PROVIDER, MODEL, ModelFamily.QWEN)


def gpt_auditor() -> WorkerBinding:
    return evidence_binding("codex", "gpt-5.6-sol", ModelFamily.GPT,
                            session="session-002", pid=4243,
                            transport="headless:codex-cli")


def test_binding_requires_admitted_verdict(contract):
    binding = admitted_worker_binding(contract, admitted_run(contract))
    assert isinstance(binding, WorkerBinding)
    rejected = replace(admitted_run(contract), artifact_hash="f" * 64)
    with pytest.raises(AdmissionError, match="worker not admitted"):
        admitted_worker_binding(contract, rejected)


def test_binding_identity_comes_from_validated_receipt_only(contract):
    receipt = physical_receipt(contract)
    binding = admitted_worker_binding(contract, admitted_run(contract, receipt=receipt))
    assert (binding.transport, binding.session, binding.pid) == (
        receipt.transport_id, receipt.session_id, receipt.pid)
    assert binding.tty is None  # headless probe receipts carry no TTY evidence
    assert (binding.provider, binding.model) == (
        receipt.actual_provider_id, receipt.actual_model_id)
    assert binding.family is receipt.actual_family
    assert binding.receipt_hash == receipt.receipt_hash


def test_binding_rejects_receipt_that_fails_revalidation(contract):
    tampered = replace(physical_receipt(contract), actual_family=ModelFamily.GPT)
    with pytest.raises(AdmissionError, match="family mismatch"):
        admitted_worker_binding(contract, admitted_run(contract, receipt=tampered))


def test_enforce_receipt_decorrelation_returns_a08_result():
    result = enforce_receipt_decorrelation(qwen_builder(), gpt_auditor())
    assert isinstance(result, A08EnforcementResult)
    assert result.verdict is A08Verdict.PASS and result.passed


def test_enforce_receipt_decorrelation_fails_same_physical_family():
    same = evidence_binding(PROVIDER, MODEL, ModelFamily.QWEN,
                            session="session-003", pid=4243)
    result = enforce_receipt_decorrelation(qwen_builder(), same)
    assert result.verdict is A08Verdict.FAIL_SAME_FAMILY and not result.passed


def test_unknown_family_evidence_fails_closed_before_dispatch():
    """Unknown family evidence cannot form an authoritative binding at all: the
    constructor boundary fails closed before A-08 is consulted. A08Enforcer
    retains its FAIL_UNKNOWN_* verdicts as defense in depth for direct calls."""
    with pytest.raises(AdmissionError, match="unknown physical family"):
        evidence_binding("openrouter", "free-router-selected-model",
                         ModelFamily.UNKNOWN)


def test_opaque_or_conflicting_family_evidence_fails_closed():
    # Opaque model identifiers cannot produce an attributable receipt binding.
    with pytest.raises(AdmissionError, match="unknown physical family"):
        evidence_binding("openrouter", "free-router-selected-model",
                         ModelFamily.UNKNOWN)
    # A claimed family that conflicts with the physical model identifier is
    # rejected by receipt re-validation on every construction path.
    with pytest.raises(AdmissionError, match="family mismatch"):
        evidence_binding(PROVIDER, MODEL, ModelFamily.GPT)


def test_binding_revalidates_admission_on_any_construction_path(contract):
    # Every construction path re-assesses admission, so tampered evidence and
    # replace()-style forgery of an existing binding both fail closed.
    forged = replace(admitted_run(contract), artifact_hash="f" * 64)
    with pytest.raises(AdmissionError, match="worker not admitted"):
        WorkerBinding(contract, forged)
    binding = admitted_worker_binding(contract, admitted_run(contract))
    with pytest.raises(AdmissionError, match="worker not admitted"):
        replace(binding, run=forged)


def test_assess_rejects_cross_probe_replay(contract):
    replayed = replace(admitted_run(contract), probe_id="probe-999")
    result = assess_worker_run(contract, replayed)
    assert result.verdict is AdmissionVerdict.REJECTED
    assert "probe ID mismatch" in result.reasons


def test_binding_cannot_be_constructed_from_cross_probe_replay(contract):
    with pytest.raises(AdmissionError, match="probe ID mismatch"):
        admitted_worker_binding(
            contract, replace(admitted_run(contract), probe_id="probe-999"))


def test_binding_rejects_direct_identity_construction():
    with pytest.raises(TypeError):
        WorkerBinding(
            transport="headless:forge", session="forged-session", pid=1, tty=None,
            provider=PROVIDER, model=MODEL, family=ModelFamily.QWEN,
            receipt_hash="c" * 64)
