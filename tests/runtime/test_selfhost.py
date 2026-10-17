"""Phase-2 tests for the self-hosting driver (PAEOS-8 §12 R3→R4).

PAEOS pulls a backlog of intakes and runs each through one shared soft loop — scars accumulate
across runs (soft-loop self-improvement), and every run is recorded on the shared ledger.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kernel.cas import CAS, InMemoryCasStore, content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.types import Role, StageId, WeightClass
from nacl.signing import SigningKey
from runtime.claude_code import AgentWrite, RunOutput
from runtime.evolution import EvolutionLayer
from runtime.memory import ScarDraft, ScarStore
from runtime.orchestrator import Intake, RunStatus, SelfHostRunner, SoftLoop
from runtime.sidecar_scorer import SidecarStageScorer
from runtime.task_package import Budget, Cost, TaskPackage, TaskStatus

_CODE = b"def x() -> int:\n    return 1\n"
_ART = content_hash(_CODE)
_BUDGETS = {
    WeightClass.ROUTINE: Budget(100_000, 3600, 5),
    WeightClass.SUBSTANTIAL: Budget(300_000, 7200, 5),
    WeightClass.KERNEL_TOUCHING: Budget(600_000, 10800, 5),
}


class ScriptedRuntime:
    def __init__(self) -> None:
        self.packages: dict[StageId, TaskPackage] = {}
        self._writes = {
            StageId.DESIGN: (AgentWrite("design/design.md", b"design"),),
            StageId.PLAN: (AgentWrite("plan/plan.md", b"plan"),),
            StageId.IMPLEMENT: (AgentWrite("runtime/x.py", _CODE),),
            StageId.ADVERSARIAL_REVIEW: (
                AgentWrite("review/adversary_report.md", b"ok\nVERDICT: PASS\n"),
            ),
        }

    def run(self, package: TaskPackage) -> RunOutput:
        self.packages[package.stage] = package
        return RunOutput(
            TaskStatus.COMPLETE, self._writes.get(package.stage, ()), (),
            b"trace", Cost(1000, 1.0, "m"),
        )


def _ev(claim_id: str, stdout: str) -> Evidence:
    return Evidence(
        hash=content_hash(f"{claim_id}:{stdout}".encode()), kind=EvidenceKind.TEST,
        claim_id=claim_id, artifact_hash=_ART, environment_hash="e" * 64,
        reproducible_command="echo built",
        producer=EvidenceProducer(role=Role.BUILDER, session="b"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": stdout}, attestation="s",
    )


_GOOD = (_ev("builds", "built\n"),)  # echo built reproduces "built\n" → PASS
_FORGED = (_ev("builds", "FORGED\n"),)  # claims "FORGED" → court remand


def _runner(runtime: ScriptedRuntime, scar_store: ScarStore | None = None) -> SelfHostRunner:
    loop = SoftLoop(
        ledger=Ledger(InMemoryLedgerStore()), signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()), agent_runtime=runtime, budget_by_class=_BUDGETS,
        scar_store=scar_store,
        sidecar_scorer=SidecarStageScorer(None),  # DEBT-0057: explicitly non-persistent
    )
    return SelfHostRunner(loop)


def _intake(evidence: tuple[Evidence, ...], *, signature: str = "domain:runtime,task:t",
            reversible: bool = True) -> Intake:
    return Intake(
        objective="add x()", changed_paths=("runtime/x.py",),
        plan_write_scopes=("runtime/x.py",), builder_evidence=evidence, goal_signature=signature,
        reversible=reversible,
    )


# ---- pulls and runs a backlog ---------------------------------------------


def test_runs_a_backlog_of_goals() -> None:
    runtime = ScriptedRuntime()
    runner = _runner(runtime)
    outcomes = runner.run_backlog([_intake(_GOOD), _intake(_FORGED)])
    assert [o.status for o in outcomes] == [RunStatus.SEALED, RunStatus.REMANDED]
    assert outcomes[0].seal is not None


# ---- L1/L3 boundary: the loop writes no scar; Evolution authors it (B2.G) --


def test_loop_writes_no_scar_and_evolution_authors_it() -> None:
    runner = _runner(ScriptedRuntime())
    sig = "domain:runtime,task:t"  # the default _intake signature
    query = f"{sig},stage:VERIFY,kind:court-remand"
    assert runner.scar_store.match_scars(query) == []
    outcomes = runner.run_backlog([_intake(_FORGED)])  # court remands
    # the operational loop produces only L1 context and authors NO L3 scar (IP-0005 Axiom 1)
    assert outcomes[0].ephemeral_context is not None
    assert runner.scar_store.match_scars(query) == []
    # the Evolution Layer is the sole L3 author (Stage 17)
    EvolutionLayer(scar_store=runner.scar_store).run(
        outcomes[0], goal_signature=sig, changed_paths=("runtime/x.py",)
    )
    assert len(runner.scar_store.match_scars(query)) == 1


def test_stored_scar_is_injected_into_a_later_design() -> None:
    scar_store = ScarStore()
    scar_store.propose_scar(
        ScarDraft(frozenset({"domain:runtime", "kind:seam"}), "watch the seams", "sig")
    )
    runtime = ScriptedRuntime()
    _runner(runtime, scar_store).run_backlog(
        [_intake(_GOOD, signature="domain:runtime,kind:seam,task:t", reversible=False)]
    )
    design_pkg = runtime.packages[StageId.DESIGN]
    assert any(ref.type == "scar" for ref in design_pkg.context_refs)  # prior lesson on the path


def test_infer_write_scopes() -> None:
    from runtime.selfhost import infer_write_scopes

    scopes = infer_write_scopes(
        objective="Create sakg/store.py and test in tests/sakg/test_store.py",
        accept=("test -f sakg/store.py", "pytest tests/sakg/test_store.py"),
        explicit_changed=("runtime/selfhost.py",),
        explicit_scopes=(),
    )
    assert scopes == ("runtime/selfhost.py",)


def test_informational_path_references_cannot_broaden_builder_authority() -> None:
    from runtime.selfhost import infer_write_scopes

    scopes = infer_write_scopes(
        objective=(
            "Repair runtime/selfhost.py while preserving immutable verification support "
            "in runtime/court/completeness_firewall.py and tests/runtime/test_completeness_firewall.py."
        ),
        accept=(
            "Run pytest tests/runtime/test_completeness_firewall.py and inspect kernel/sandbox.py.",
        ),
        explicit_changed=("runtime/selfhost.py",),
        explicit_scopes=(),
    )
    assert scopes == ("runtime/selfhost.py",)


def test_declared_file_scopes_are_not_collapsed_by_informational_directory_mentions() -> None:
    from runtime.selfhost import infer_write_scopes

    scopes = infer_write_scopes(
        objective=(
            "Update runtime/selfhost.py and tests/runtime/test_selfhost.py; inspect "
            "runtime/court/ and tests/runtime/ for immutable verification support."
        ),
        accept=(
            "Run pytest tests/runtime/test_selfhost.py and review runtime/court/ only.",
        ),
        explicit_changed=("runtime/selfhost.py", "tests/runtime/test_selfhost.py"),
        explicit_scopes=("runtime/selfhost.py", "tests/runtime/test_selfhost.py"),
    )
    assert scopes == ("runtime/selfhost.py", "tests/runtime/test_selfhost.py")


def test_explicit_directory_scope_does_not_collapse_explicit_candidate_paths() -> None:
    from runtime.selfhost import infer_write_scopes

    scopes = infer_write_scopes(
        objective="The prose is informational even when it names kernel/sandbox.py.",
        accept=("Inspect tests/runtime/test_completeness_firewall.py.",),
        explicit_changed=("runtime/selfhost.py", "tests/runtime/test_selfhost.py"),
        explicit_scopes=("runtime/",),
    )
    assert scopes == ("runtime/", "runtime/selfhost.py", "tests/runtime/test_selfhost.py")


def test_parse_backlog_preserves_structured_candidate_paths_and_scope_authority() -> None:
    from runtime.selfhost import parse_backlog

    (intake,) = parse_backlog(
        [
            {
                "objective": "Inspect kernel/sandbox.py while updating the declared candidate.",
                "accept": ["pytest tests/runtime/test_completeness_firewall.py"],
                "changed_paths": ["runtime/selfhost.py"],
                "plan_write_scopes": ["tests/runtime/test_selfhost.py"],
            }
        ]
    )
    assert intake.changed_paths == ("runtime/selfhost.py",)
    assert intake.plan_write_scopes == (
        "runtime/selfhost.py",
        "tests/runtime/test_selfhost.py",
    )


def test_prose_alone_grants_no_builder_mutation_authority() -> None:
    from runtime.selfhost import parse_backlog

    (intake,) = parse_backlog(
        [
            {
                "objective": "Modify runtime/selfhost.py.",
                "accept": ["pytest tests/runtime/test_selfhost.py"],
            }
        ]
    )
    assert intake.changed_paths == ()
    assert intake.plan_write_scopes == ()


def test_selfhost_default_run_creates_no_repository_relative_evaluations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from runtime.selfhost import run_backlog

    monkeypatch.chdir(tmp_path)
    outcomes = run_backlog(
        [_intake(_GOOD)],
        ledger=Ledger(InMemoryLedgerStore()),
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()),
        agent_runtime=ScriptedRuntime(),
    )
    assert outcomes
    assert not (tmp_path / ".paeos_state").exists()
