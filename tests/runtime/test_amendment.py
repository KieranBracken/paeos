"""B2.E tests for the amendment path — the hard-loop for constitutional change (PAEOS-7 §7.4, FR-2).

A TCB-touching proposal is classified HARD, adversarially attacked, and then HALTS at the human
gate — the runtime applies NOTHING. A non-TCB proposal is not an amendment. An adversary that does
not complete blocks the gate. Nothing here ever writes `kernel/` or `constitution/`.
"""

from __future__ import annotations

import pytest
from kernel.cas import CAS, InMemoryCasStore
from kernel.types import StageId
from nacl.signing import SigningKey
from runtime.amendment import (
    AmendmentProposal,
    AmendmentStatus,
    parse_proposal,
    prepare_amendment,
)
from runtime.claude_code import AgentWrite, RunOutput
from runtime.task_package import Cost, TaskPackage, TaskStatus


class ScriptedAdversary:
    """Completes the adversarial-review stage with a report; FAILED optionally."""

    def __init__(self, status: TaskStatus = TaskStatus.COMPLETE) -> None:
        self._status = status

    def run(self, package: TaskPackage) -> RunOutput:
        writes = (
            (AgentWrite(f"review/{package.goal_id}_ratification.md", b"attacked; no break found"),)
            if package.stage is StageId.ADVERSARIAL_REVIEW
            else ()
        )
        return RunOutput(self._status, writes, (), b"trace", Cost(100, 1.0, "m"))


def _proposal(target_paths: tuple[str, ...]) -> AmendmentProposal:
    return AmendmentProposal(
        proposal_id="PAEOS-IP-9001",
        title="tighten K1 entry condition",
        target_paths=target_paths,
        safety_invariants=("K1", "FR-5"),
        diff="- old clause\n+ new clause",
        rationale="retrospective RET-42",
    )


def _prepare(proposal: AmendmentProposal, *, status: TaskStatus = TaskStatus.COMPLETE):
    return prepare_amendment(
        proposal,
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()),
        adversary_runtime=ScriptedAdversary(status),
    )


def test_tcb_proposal_awaits_ratification() -> None:
    packet = _prepare(_proposal(("kernel/gates.py",)))
    assert packet.classification == "HARD"
    assert packet.status is AmendmentStatus.AWAITING_RATIFICATION
    assert packet.applied is False  # the runtime never amends the TCB (§7.4)
    assert packet.adversary_trace_ref is not None
    assert packet.adversary_report_refs  # the adversary review is captured for the founder


def test_constitution_proposal_is_hard() -> None:
    packet = _prepare(_proposal(("constitution/PAEOS-4.md",)))
    assert packet.classification == "HARD"
    assert packet.status is AmendmentStatus.AWAITING_RATIFICATION


def test_non_tcb_proposal_is_not_an_amendment() -> None:
    packet = _prepare(_proposal(("runtime/selfhost.py",)))
    assert packet.classification == "SOFT"
    assert packet.status is AmendmentStatus.NOT_AN_AMENDMENT
    assert packet.adversary_trace_ref is None  # no adversary dispatched for non-TCB work
    assert packet.applied is False


def test_incomplete_adversary_blocks_the_gate() -> None:
    packet = _prepare(_proposal(("kernel/seal.py",)), status=TaskStatus.FAILED)
    assert packet.status is AmendmentStatus.ADVERSARY_INCOMPLETE
    assert packet.applied is False


def test_empty_target_paths_are_failsafe_hard() -> None:
    # deny-by-default: no blast-radius info ⇒ HARD (classifier fail-safe)
    packet = _prepare(_proposal(()))
    assert packet.classification == "HARD"
    assert packet.status is AmendmentStatus.AWAITING_RATIFICATION


def test_parse_proposal_rejects_non_object() -> None:
    with pytest.raises(ValueError):
        parse_proposal(["not", "an", "object"])


def test_parse_proposal_builds_a_proposal() -> None:
    proposal = parse_proposal(
        {
            "proposal_id": "PAEOS-IP-9002",
            "title": "t",
            "target_paths": ["kernel/x.py"],
            "safety_invariants": ["K3"],
            "diff": "d",
            "rationale": "r",
        }
    )
    assert proposal.proposal_id == "PAEOS-IP-9002"
    assert proposal.target_paths == ("kernel/x.py",)
    assert proposal.safety_invariants == ("K3",)
