"""Physical P1 production-path probes.

These tests exercise the real ``SoftLoop`` composition path with a temporary Git base.  They are
intentionally separate from the in-memory firewall tests: a successful row proves that L11 froze a
plan, L12 materialized an unpromoted candidate from the physical base, and L13 verified that
candidate before the production root stopped at the intentionally absent L14 composition hook.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from kernel.cas import CAS, InMemoryCasStore
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import StageId, WeightClass
from nacl.signing import SigningKey
from runtime.builder_transport import REQUIRED_CANARIES
from runtime.claude_code import AgentWrite, RunOutput
from runtime.court.completeness_firewall import (
    VerificationObligation,
    VerificationObligationKind,
    create_authoritative_manifest,
)
from runtime.integrations.hybrid import _l10_execution_trace
from runtime.orchestrator import (
    RunStatus,
    SoftLoop,
    _l10_sealed_context_observation,
    inspect_authoritative_path,
)
from runtime.planner_transport import LunaAdversaryBinding
from runtime.sidecar_scorer import SidecarStageScorer
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus

class _ProductionProbeRuntime:
    """A deterministic worker seam; all production gates remain real."""

    def run(self, package: TaskPackage) -> RunOutput:
        writes = (
            (AgentWrite("runtime/feature.py", b"good\n"),)
            if package.stage is StageId.IMPLEMENT
            else ()
        )
        return RunOutput(
            status=TaskStatus.COMPLETE,
            writes=writes,
            evidence=(),
            trace=("probe:" + package.stage.name).encode("ascii"),
            cost=Cost(tokens=1, wallclock_s=0.001, model_ver="openai:gpt-5.6-sol"),
            workspace_identity="probe-worker-workspace",
            environment_identity="probe-worker-environment",
        )


def _git(repo: Path, *argv: str) -> None:
    completed = subprocess.run(
        ["git", *argv], cwd=repo, capture_output=True, text=True, check=False, timeout=20
    )
    assert completed.returncode == 0, completed.stderr


def _temporary_git_base(tmp_path: Path) -> Path:
    repo = tmp_path / "base"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.email", "p1-probe@example.invalid")
    _git(repo, "config", "user.name", "P1 probe")
    (repo / "runtime").mkdir()
    (repo / "runtime" / "feature.py").write_text("bad\n", encoding="utf-8")
    (repo / "verify.py").write_text(
        "from pathlib import Path\n"
        "raise SystemExit(0 if Path('runtime/feature.py').read_text() == 'good\\n' else 17)\n",
        encoding="utf-8",
    )
    _git(repo, "add", "runtime/feature.py", "verify.py")
    _git(repo, "commit", "--quiet", "-m", "initial P1 probe base")
    return repo


def test_path_truth_does_not_self_match_detector_literals_but_catches_executable_fallback() -> None:
    """Regression discriminator for .08: detector vocabulary is not deployed behavior.

    The preserved .08 candidate was remanded because its production scanner and CANARY test
    strings contained the very marker vocabulary that the scanner searched for.  This keeps the
    negative signal focused on executable fallback constructs while retaining a real RED case.
    """
    detector_source = b'''"""No undisclosed synthetic fallback is permitted."""
def inspect(text):
    return tuple(marker for marker in ("event_pool", "synthetic fallback")
                   if marker in text)
METRIC_MARKERS = ("eom spend", "60.3%")
violations = []
violations.append(f"CF-03: Undisclosed synthetic fallback: {text}")
def _python_path_markers(text):
    synthetic.add("makeevent(")
    if name.casefold() == "event_pool":
        synthetic.add("event_pool")
'''
    detector_result = inspect_authoritative_path(
        "runtime/court/completeness_firewall.py", detector_source
    )
    assert detector_result == ((), ())

    executable_fallback = b'''def build_response():
    return "canned success"
'''
    fallback_result = inspect_authoritative_path("runtime/service.py", executable_fallback)
    assert fallback_result[0] == ("canned success",)


def test_physical_slo_claim_binding_uses_authoritative_manifest_id() -> None:
    """Regression discriminator for .08: the forged-receipt claim is not silently dropped."""
    from runtime.orchestrator import physical_slo_observations

    evidence = (
        SimpleNamespace(
            claim_id="CLAIM-CF-08-CANARY-DISCRIMINATION", hash="a" * 64
        ),
        SimpleNamespace(
            claim_id="CLAIM-CF-10-UNFORGEABLE-TRANSPORT-ATTESTATION", hash="b" * 64
        ),
    )
    observations = physical_slo_observations(evidence)
    assert observations == {
        "failing_command_remands": ("a" * 64,),
        "forged_receipt_rejected": ("b" * 64,),
    }


def test_production_softloop_materializes_and_verifies_candidate(tmp_path: Path) -> None:
    repo = _temporary_git_base(tmp_path)
    (repo / "untracked_verifier_support.py").write_text(
        "SUPPORT_MARKER = 'frozen at L11'\n", encoding="utf-8"
    )
    state_dir = tmp_path / "state"
    manifest = create_authoritative_manifest(
        manifest_id="P1-PRODUCTION-PROBE",
        milestone_id="P1-PRODUCTION-PROBE",
        expected_capabilities=("CAP-PRODUCTION-LIFECYCLE",),
        verification_obligations=(
            VerificationObligation(
                claim_id="CAP-PRODUCTION-LIFECYCLE",
                argv=("{python}", "verify.py"),
                timeout_s=30,
            ),
        ),
        verification_support_paths=("untracked_verifier_support.py",),
    )
    ledger = Ledger(InMemoryLedgerStore())
    loop = SoftLoop(
        ledger=ledger,
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()),
        agent_runtime=_ProductionProbeRuntime(),
        budget_by_class={
            WeightClass.ROUTINE: Budget(10_000, 60, 1),
            WeightClass.SUBSTANTIAL: Budget(10_000, 60, 1),
            WeightClass.KERNEL_TOUCHING: Budget(10_000, 60, 1),
        },
        sidecar_scorer=SidecarStageScorer(None),
        repo_root=repo,
        state_dir=state_dir,
    )

    outcome = loop.run(
        objective="prove the governed P1 production path",
        changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",),
        builder_evidence=(),
        verifiable=False,  # force the canonical Trace-B production ceremony
        reversible=True,
        run_id="p1-production-probe-01",
        capability_manifest=manifest,
    )

    assert outcome.status is RunStatus.REMANDED
    assert "L14 heterogeneous auditor is not wired" in outcome.detail
    assert outcome.candidate is not None
    assert outcome.candidate.status.value == "UNPROMOTED_PENDING_VERIFICATION"
    assert outcome.candidate.candidate_workspace.joinpath("runtime/feature.py").read_text() == "good\n"
    assert (
        outcome.candidate.candidate_workspace / "untracked_verifier_support.py"
    ).read_text(encoding="utf-8") == "SUPPORT_MARKER = 'frozen at L11'\n"
    assert [item.path for item in outcome.candidate.verification_support_files] == [
        "untracked_verifier_support.py"
    ]

    events = [row.event for row in ledger.read()]
    event_kinds = [event.kind for event in events]
    assert "L11_FREEZE" in event_kinds
    assert "CANDIDATE_MATERIALIZED" in event_kinds
    assert "L13_VERIFICATION" in event_kinds
    assert "L13_COMPLETENESS_CLEARED" in event_kinds
    assert "L14_AUDIT" not in event_kinds
    assert ledger.verify_chain()

    l11 = next(event for event in events if event.kind == "L11_FREEZE")
    assert l11.payload["manifest_sha256"] == manifest.manifest_sha256
    candidate_event = next(event for event in events if event.kind == "CANDIDATE_MATERIALIZED")
    assert candidate_event.payload["candidate_id"] == outcome.candidate.candidate_id
    l13 = next(event for event in events if event.kind == "L13_VERIFICATION")
    assert l13.payload["verdict"] == "PASS"
    event_positions = {event.kind: index for index, event in enumerate(events)}
    plan_position = next(
        index
        for index, event in enumerate(events)
        if event.kind == "STAGE_COMPLETED" and event.payload.get("stage") == "PLAN"
    )
    implement_position = next(
        index
        for index, event in enumerate(events)
        if event.kind == "STAGE_COMPLETED" and event.payload.get("stage") == "IMPLEMENT"
    )
    assert event_positions["L11_FREEZE"] > plan_position
    assert event_positions["L11_FREEZE"] < implement_position
    assert event_positions["L11_FREEZE"] < event_positions["CANDIDATE_MATERIALIZED"]


def test_immutable_verifier_overlap_remands_before_builder_execution(tmp_path: Path) -> None:
    repo = _temporary_git_base(tmp_path)
    (repo / "verify.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    manifest = create_authoritative_manifest(
        manifest_id="P1-OVERLAP-PROBE",
        milestone_id="P1-OVERLAP-PROBE",
        expected_capabilities=("CAP-PRODUCTION-LIFECYCLE",),
        verification_obligations=(
            VerificationObligation(
                claim_id="CAP-PRODUCTION-LIFECYCLE",
                argv=("{python}", "verify.py"),
            ),
        ),
        verification_support_paths=("verify.py",),
    )
    ledger = Ledger(InMemoryLedgerStore())
    loop = SoftLoop(
        ledger=ledger,
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()),
        agent_runtime=_ProductionProbeRuntime(),
        budget_by_class={
            WeightClass.ROUTINE: Budget(10_000, 60, 1),
            WeightClass.SUBSTANTIAL: Budget(10_000, 60, 1),
            WeightClass.KERNEL_TOUCHING: Budget(10_000, 60, 1),
        },
        sidecar_scorer=SidecarStageScorer(None),
        repo_root=repo,
        state_dir=tmp_path / "state",
    )

    outcome = loop.run(
        objective="attempt to overwrite immutable verifier support",
        changed_paths=("verify.py",),
        plan_write_scopes=("verify.py",),
        builder_evidence=(),
        verifiable=False,
        reversible=True,
        run_id="p1-overlap-probe-01",
        capability_manifest=manifest,
    )

    assert outcome.status is RunStatus.REMANDED
    assert "overlaps immutable verifier" in outcome.detail
    assert not any(
        row.event.kind == "STAGE_COMPLETED"
        and row.event.payload.get("stage") == "IMPLEMENT"
        for row in ledger.read()
    )


def test_manifest_loader_rejects_nested_interpreter_obligation(tmp_path: Path) -> None:
    manifest_path = Path(__file__).parents[2] / "ops" / "manifests" / "p1_authoritative_completeness_manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw["verification_obligations"][0]["argv"] = ["{python}", "-c", "pass"]
    malformed = tmp_path / "manifest.json"
    malformed.write_text(json.dumps(raw), encoding="utf-8")

    from runtime.court.completeness_firewall import (
        CompletenessFirewallError,
        load_authoritative_manifest,
    )

    try:
        load_authoritative_manifest(malformed)
    except CompletenessFirewallError as exc:
        assert "argv" in str(exc)
    else:  # pragma: no cover - the loader must fail closed
        raise AssertionError("nested interpreter obligation was accepted")


@pytest.mark.parametrize("kind", [None, "NOT_A_VERIFICATION_KIND"])
def test_manifest_loader_requires_explicit_valid_obligation_kind(
    tmp_path: Path, kind: str | None
) -> None:
    manifest_path = Path(__file__).parents[2] / "ops" / "manifests" / "p1_authoritative_completeness_manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if kind is None:
        raw["verification_obligations"][0].pop("kind")
    else:
        raw["verification_obligations"][0]["kind"] = kind
    malformed = tmp_path / "manifest.json"
    malformed.write_text(json.dumps(raw), encoding="utf-8")

    from runtime.court.completeness_firewall import (
        CompletenessFirewallError,
        load_authoritative_manifest,
    )

    with pytest.raises(CompletenessFirewallError, match="kind"):
        load_authoritative_manifest(malformed)


def test_authoritative_manifest_keeps_negative_control_physical_and_separate() -> None:
    from runtime.court.completeness_firewall import load_authoritative_manifest
    from runtime.verification import candidate_discrimination_commands

    manifest_path = Path(__file__).parents[2] / "ops" / "manifests" / "p1_authoritative_completeness_manifest.json"
    manifest = load_authoritative_manifest(manifest_path)
    controls = tuple(
        obligation
        for obligation in manifest.verification_obligations
        if obligation.kind is VerificationObligationKind.NEGATIVE_COURT_CONTROL
    )

    assert [item.claim_id for item in controls] == ["CLAIM-CF-08-CANARY-DISCRIMINATION"]
    assert controls[0] in manifest.verification_obligations
    assert controls[0].argv not in candidate_discrimination_commands(
        manifest.verification_obligations
    )
    assert len(candidate_discrimination_commands(manifest.verification_obligations)) == 10


def test_l13_verifier_exception_becomes_durable_remand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RED discriminator for .03: verifier infrastructure failures must not escape the loop."""
    repo = _temporary_git_base(tmp_path)
    manifest = create_authoritative_manifest(
        manifest_id="P1-L13-EXCEPTION-PROBE",
        milestone_id="P1-L13-EXCEPTION-PROBE",
        expected_capabilities=("CAP-PRODUCTION-LIFECYCLE",),
        verification_obligations=(
            VerificationObligation(
                claim_id="CAP-PRODUCTION-LIFECYCLE",
                argv=("{python}", "verify.py"),
                timeout_s=30,
            ),
        ),
    )

    def raise_snapshot_error(*_args: object, **_kwargs: object) -> tuple[str, ...]:
        raise shutil.Error("live IPC socket could not be copied")

    monkeypatch.setattr("runtime.orchestrator.vacuous_commands", raise_snapshot_error)
    ledger = Ledger(InMemoryLedgerStore())
    loop = SoftLoop(
        ledger=ledger,
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()),
        agent_runtime=_ProductionProbeRuntime(),
        budget_by_class={
            WeightClass.ROUTINE: Budget(10_000, 60, 1),
            WeightClass.SUBSTANTIAL: Budget(10_000, 60, 1),
            WeightClass.KERNEL_TOUCHING: Budget(10_000, 60, 1),
        },
        sidecar_scorer=SidecarStageScorer(None),
        repo_root=repo,
        state_dir=tmp_path / "state",
    )

    outcome = loop.run(
        objective="prove the governed P1 production path",
        changed_paths=("runtime/feature.py",),
        plan_write_scopes=("runtime/feature.py",),
        builder_evidence=(),
        verifiable=False,
        reversible=True,
        run_id="p1-l13-exception-probe",
        capability_manifest=manifest,
    )

    assert outcome.status is RunStatus.REMANDED
    assert outcome.detail == "L13 verification infrastructure failed closed: Error"
    assert any(event.event.kind == "L13_VERIFICATION_FAILURE" for event in ledger.read())


def consumer_case(tmp_path: Path):
    from tests.runtime.test_luna_adversary_subsumption import _debt0242_case

    cas, package, binding, output, transport = _debt0242_case(tmp_path)
    proof = _l10_execution_trace(package, output, binding, transport)
    result = SimpleNamespace(
        task_id=package.task_id,
        status=TaskStatus.COMPLETE,
        failure_code=None,
        trace_ref=cas.put(proof),
        cost=output.cost,
        workspace_identity=output.workspace_identity,
        environment_identity=output.environment_identity,
    )
    return cas, package, result


def test_consumer_accepts_current_runtime_proof(tmp_path: Path) -> None:
    cas, package, result = consumer_case(tmp_path)
    assert _l10_sealed_context_observation(
        cas, result, goal_id=package.goal_id, run_id=package.run_id,
        expected_context=package.context_refs,
    ) == result.trace_ref


@pytest.mark.parametrize(
    "mutation",
    [
        "plain", "stale_run", "stale_task", "wrong_model", "context", "fallback",
        "authority", "builder_write", "canary", "hash", "raw_trace", "failed_result",
        "workspace",
    ],
)
def test_consumer_rejects_forged_or_stale_proof(tmp_path: Path, mutation: str) -> None:
    cas, package, result = consumer_case(tmp_path)
    document = json.loads(cas.get(result.trace_ref))
    if mutation == "plain":
        result.trace_ref = cas.put(b"model says PASS")
    elif mutation == "failed_result":
        result.status = TaskStatus.FAILED
    elif mutation == "workspace":
        result.workspace_identity = "0" * 64
    else:
        if mutation == "stale_run":
            document["run_id"] = "old"
        elif mutation == "stale_task":
            document["task_id"] = "old"
        elif mutation == "wrong_model":
            document["model"] = "gpt-5.6-sol"
        elif mutation == "context":
            document["context_refs"] = []
        elif mutation == "fallback":
            document["observation"]["fallback_used"] = True
        elif mutation == "authority":
            del document["authorization"]
        elif mutation == "builder_write":
            document["authorization"]["production_write"] = True
        elif mutation == "canary":
            document["observation"]["canaries"]["parent_secret_invisible"] = "FAIL"
        elif mutation == "hash":
            document["request_sha256"] = "not-a-hash"
        elif mutation == "raw_trace":
            document["trace_base64"] = base64.b64encode(b"changed").decode()
        result.trace_ref = cas.put(json.dumps(document).encode())
    with pytest.raises((ValueError, RuntimeError)):
        _l10_sealed_context_observation(
            cas, result, goal_id=package.goal_id, run_id=package.run_id,
            expected_context=package.context_refs,
        )


@pytest.mark.parametrize("valid_proof", [False, True])
def test_required_l10_observation_controls_real_preaudit_path(tmp_path: Path, valid_proof: bool) -> None:
    from tests.runtime.test_luna_adversary_subsumption import _readiness

    repo = _temporary_git_base(tmp_path)
    (repo / "untracked_verifier_support.py").write_text("SUPPORT=True\n")
    cas = CAS(InMemoryCasStore())
    ledger = Ledger(InMemoryLedgerStore())
    binding = LunaAdversaryBinding.from_readiness(_readiness(tmp_path))
    stages = []

    class SyntheticWorker:
        def run(self, package: TaskPackage) -> RunOutput:
            stages.append(package.stage)
            writes = ()
            if package.stage is StageId.DESIGN:
                writes = (AgentWrite("design/test-plan.md", b"synthetic pre-Builder plan"),)
            if package.stage is StageId.IMPLEMENT:
                writes = (AgentWrite("runtime/feature.py", b"good\n"),)
            output = RunOutput(
                status=TaskStatus.COMPLETE,
                writes=writes,
                evidence=(),
                trace=b"local synthetic transcript",
                cost=Cost(tokens=1, wallclock_s=0.001, model_ver="openai:gpt-5.6-luna"),
                workspace_identity=hashlib.sha256(b"/tmp/synthetic-l10").hexdigest(),
                environment_identity="a" * 64,
            )
            if package.stage is StageId.ADVERSARIAL_REVIEW and valid_proof:
                observation = dict(
                    provider_id="codex", model_id="gpt-5.6-luna", family="gpt",
                    task_id=package.task_id, goal_id=package.goal_id, run_id=package.run_id,
                    stage=package.stage.value, workspace="/tmp/synthetic-l10",
                    workspace_id="synthetic-l10", exit_code=0, process_state="RETURNED",
                    canaries={key: "PASS" for key in REQUIRED_CANARIES}, fallback_used=False,
                    manual_chat_bridge=False, stdout_sha256=hashlib.sha256(output.trace).hexdigest(),
                    environment_fingerprint="a" * 64, profile_sha256="b" * 64,
                    supervisor_identity_sha256="a" * 64, broker_evidence_sha256="d" * 64,
                    artifact_sha256="e" * 64, request_id="f" * 32,
                )
                transport = SimpleNamespace(
                    last_observation=observation,
                    last_request_sha256="1" * 64,
                    last_response_sha256="2" * 64,
                )
                output = replace(
                    output,
                    trace=_l10_execution_trace(package, output, binding, transport),
                )
            return output

    obligation = "l10_family_match_requires_independent_sealed_context"
    manifest = create_authoritative_manifest(
        manifest_id="LOCAL-DEBT0242-TEST",
        milestone_id="LOCAL-DEBT0242-TEST",
        expected_capabilities=("CAP-PRODUCTION-LIFECYCLE",),
        verification_obligations=(VerificationObligation(
            claim_id="CAP-PRODUCTION-LIFECYCLE",
            argv=("{python}", "verify.py"), timeout_s=30,
        ),),
        verification_support_paths=("untracked_verifier_support.py",),
        slo_obligations=(obligation,), pre_audit_slo_obligations=(obligation,),
    )
    loop = SoftLoop(
        ledger=ledger, signing_key=SigningKey.generate(), cas=cas,
        agent_runtime=SyntheticWorker(),
        budget_by_class={c: Budget(10000, 60, 1) for c in (
            WeightClass.ROUTINE, WeightClass.SUBSTANTIAL, WeightClass.KERNEL_TOUCHING,
        )},
        sidecar_scorer=SidecarStageScorer(None), repo_root=repo, state_dir=tmp_path / "state",
    )
    outcome = loop.run(
        objective="local DEBT-0242 discriminator, not P1 qualification",
        changed_paths=("runtime/feature.py",), plan_write_scopes=("runtime/feature.py",),
        builder_evidence=(), verifiable=False, reversible=True,
        run_id="local-debt0242-test", capability_manifest=manifest,
    )
    events = [row.event.kind for row in ledger.read()]
    assert outcome.status is RunStatus.REMANDED
    assert ledger.verify_chain()
    if valid_proof:
        assert "L14 heterogeneous auditor is not wired" in outcome.detail
        assert "L13_COMPLETENESS_CLEARED" in events
        assert "L10_SEALED_CONTEXT_OBSERVED" in events
    else:
        assert StageId.IMPLEMENT not in stages
        assert "L13_COMPLETENESS_CLEARED" not in events
        assert outcome.candidate is None
