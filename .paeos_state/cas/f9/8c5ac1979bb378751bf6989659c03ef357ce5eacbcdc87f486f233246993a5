"""B2.F tests for the Evolution Layer — stages 15-18, the self-improvement loop (PAEOS-7 §7).

A clean seal yields no guard; a remand/halt writes a scar (FR-6); a TCB-implicated *recurrence*
emits an IMPROVE_RUNTIME proposal that feeds the B2.E amendment gate. The layer applies nothing.
"""

from __future__ import annotations

from kernel.cas import CAS, InMemoryCasStore
from kernel.types import StageId
from nacl.signing import SigningKey
from runtime.amendment import AmendmentStatus, prepare_amendment
from runtime.claude_code import AgentWrite, RunOutput
from runtime.court import Verdict, VerdictOutcome
from runtime.evolution import EvolutionLayer
from runtime.memory import ScarStore
from runtime.orchestrator import RunOutcome, RunStatus
from runtime.task_package import Cost, TaskPackage, TaskStatus

_KERNEL = ("kernel/gates.py",)
_RUNTIME = ("runtime/x.py",)
_KSIG = "domain:kernel,task:t"


def _remand(goal_id: str = "g-1") -> RunOutcome:
    verdict = Verdict(
        outcome=VerdictOutcome.REMAND, artifact_hash="a" * 64,
        unmet_claims=("builds",), detail="not reproduced",
    )
    return RunOutcome(RunStatus.REMANDED, goal_id, "court remanded", verdict=verdict)


def _sealed(goal_id: str = "g-2") -> RunOutcome:
    return RunOutcome(RunStatus.SEALED, goal_id, "sealed")


def test_clean_seal_yields_no_guard() -> None:
    layer = EvolutionLayer(scar_store=ScarStore())
    result = layer.run(_sealed(), goal_signature=_KSIG, changed_paths=_KERNEL)
    assert result.scars_written == ()
    assert result.proposals == ()


def test_remand_writes_a_scar_to_the_shared_store() -> None:
    store = ScarStore()
    layer = EvolutionLayer(scar_store=store)
    result = layer.run(_remand(), goal_signature=_KSIG, changed_paths=_KERNEL)
    assert len(result.scars_written) == 1
    # the scar is now matchable for a future goal with the same signature (FR-6)
    assert store.match_scars(f"{_KSIG},stage:VERIFY,kind:court-remand")


def test_first_tcb_failure_is_a_scar_not_a_proposal() -> None:
    layer = EvolutionLayer(scar_store=ScarStore())
    result = layer.run(_remand(), goal_signature=_KSIG, changed_paths=_KERNEL)
    assert result.proposals == ()  # first occurrence → soft guard only


def test_tcb_recurrence_emits_an_improve_runtime_proposal() -> None:
    store = ScarStore()
    layer = EvolutionLayer(scar_store=store)
    layer.run(_remand("g-1"), goal_signature=_KSIG, changed_paths=_KERNEL)  # guard planted
    result = layer.run(_remand("g-2"), goal_signature=_KSIG, changed_paths=_KERNEL)  # recurs
    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.target_paths == _KERNEL


def test_soft_recurrence_emits_no_proposal() -> None:
    store = ScarStore()
    layer = EvolutionLayer(scar_store=store)
    sig = "domain:runtime,task:t"
    layer.run(_remand("g-1"), goal_signature=sig, changed_paths=_RUNTIME)
    result = layer.run(_remand("g-2"), goal_signature=sig, changed_paths=_RUNTIME)
    assert result.proposals == ()  # non-TCB recurrence stays soft


class _ScriptedAdversary:
    def run(self, package: TaskPackage) -> RunOutput:
        writes = (
            (AgentWrite(f"review/{package.goal_id}_ratification.md", b"attacked"),)
            if package.stage is StageId.ADVERSARIAL_REVIEW
            else ()
        )
        return RunOutput(TaskStatus.COMPLETE, writes, (), b"t", Cost(10, 1.0, "m"))


def test_evolution_proposal_feeds_the_amendment_gate() -> None:
    # the closed loop: a stage-18 proposal enters B2.E and halts at the human gate.
    store = ScarStore()
    layer = EvolutionLayer(scar_store=store)
    layer.run(_remand("g-1"), goal_signature=_KSIG, changed_paths=_KERNEL)
    proposal = layer.run(_remand("g-2"), goal_signature=_KSIG, changed_paths=_KERNEL).proposals[0]
    packet = prepare_amendment(
        proposal,
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()),
        adversary_runtime=_ScriptedAdversary(),
    )
    assert packet.classification == "HARD"
    assert packet.status is AmendmentStatus.AWAITING_RATIFICATION
    assert packet.applied is False
