"""B0.12 acceptance tests for the CLI control plane (PAEOS-8 §10).

End-to-end: an operator creates a goal, acquires a token, and drives it through stages — every
committed action appears on the ledger; replay verifies; no privileged op runs without a token
(the Adversary's unauthenticated seal is refused).
"""

from __future__ import annotations

import pytest
from cli.paeos import (
    GOAL_CREATED,
    TRANSITION_COMMITTED,
    ControlPlane,
    GoalNotAtStage,
    Unauthenticated,
    make_deterministic_evidence,
    run_demo,
)
from kernel.gates import PROPOSE_TRANSITION_OP
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.seal import SEAL_EVENT_KIND
from kernel.types import Claim, Role, StageId, ValidationClaim, WeightClass
from nacl.signing import SigningKey

_ART = "a" * 64
_RUN = "r-1"


def _plane() -> ControlPlane:
    return ControlPlane(Ledger(InMemoryLedgerStore()), SigningKey.generate())


def _advance(plane: ControlPlane, goal: str, frm: StageId, to: StageId) -> object:
    token = plane.acquire_token(
        goal_id=goal, run_id=_RUN, stage=frm, role=Role.BUILDER, session="op",
        operations=(PROPOSE_TRANSITION_OP,),
    )
    ev = make_deterministic_evidence("advances", _ART, "echo ok")
    plane.register_evidence(ev)
    validation = ValidationClaim(
        gate_id="G",
        claims=(Claim(id="advances", statement="ok", evidence_refs=(ev.hash,)),),
        producer=Role.BUILDER,
        produced_against=_ART,
    )
    return plane.advance(
        token=token, goal_id=goal, run_id=_RUN, from_state=frm, to_state=to,
        weight_class=WeightClass.SUBSTANTIAL, artifact_under_review=_ART, validation=validation,
    )


# ---- drive a goal through states ------------------------------------------


def test_operator_drives_goal_through_states() -> None:
    plane = _plane()
    goal = plane.create_goal("drive me", WeightClass.SUBSTANTIAL)
    assert plane.inspect(goal) == "RAW"
    from kernel.types import Outcome

    for frm, to in (
        (StageId.RAW, StageId.RE_DERIVE),
        (StageId.RE_DERIVE, StageId.INTAKE),
        (StageId.INTAKE, StageId.TRIAGE),
    ):
        result = _advance(plane, goal, frm, to)
        assert result.outcome is Outcome.COMMITTED  # type: ignore[attr-defined]
        assert result.committed_seq is not None  # type: ignore[attr-defined]
    assert plane.inspect(goal) == "TRIAGE"


def test_all_actions_appear_on_the_ledger() -> None:
    plane = _plane()
    goal = plane.create_goal("x", WeightClass.SUBSTANTIAL)
    _advance(plane, goal, StageId.RAW, StageId.RE_DERIVE)
    kinds = [row.event.kind for row in plane.ledger_events()]
    assert kinds == [GOAL_CREATED, TRANSITION_COMMITTED]  # every action ledgered, in order


def test_replay_verifies_after_driving() -> None:
    plane = _plane()
    goal = plane.create_goal("x", WeightClass.SUBSTANTIAL)
    _advance(plane, goal, StageId.RAW, StageId.RE_DERIVE)
    projection = plane.replay_and_verify()  # raises if stale/poisoned
    assert projection.state[goal] == "RE_DERIVE"


def test_advance_from_wrong_stage_is_refused() -> None:
    plane = _plane()
    goal = plane.create_goal("x", WeightClass.SUBSTANTIAL)
    with pytest.raises(GoalNotAtStage):
        _advance(plane, goal, StageId.IMPLEMENT, StageId.VERIFY)  # goal is at RAW


def test_denied_transition_is_not_ledgered() -> None:
    # an illegal edge is denied by the gate → no transition_committed event
    plane = _plane()
    goal = plane.create_goal("x", WeightClass.SUBSTANTIAL)
    token = plane.acquire_token(
        goal_id=goal, run_id=_RUN, stage=StageId.RAW, role=Role.BUILDER, session="op",
        operations=(PROPOSE_TRANSITION_OP,),
    )
    ev = make_deterministic_evidence("advances", _ART, "echo ok")
    plane.register_evidence(ev)
    validation = ValidationClaim(
        gate_id="G",
        claims=(Claim(id="advances", statement="ok", evidence_refs=(ev.hash,)),),
        producer=Role.BUILDER,
        produced_against=_ART,
    )
    from kernel.types import Outcome

    result = plane.advance(
        token=token, goal_id=goal, run_id=_RUN, from_state=StageId.RAW, to_state=StageId.SEAL,
        weight_class=WeightClass.SUBSTANTIAL, artifact_under_review=_ART, validation=validation,
    )
    assert result.outcome is not Outcome.COMMITTED
    assert [r.event.kind for r in plane.ledger_events()] == [GOAL_CREATED]  # nothing committed


# ---- seal: token-gated (Adversary: unauthenticated seal) ------------------


def test_seal_requires_a_token() -> None:
    plane = _plane()
    goal = plane.create_goal("x", WeightClass.SUBSTANTIAL)
    with pytest.raises(Unauthenticated):
        plane.seal(
            token=None, goal_id=goal, run_id=_RUN, artifact_bundle=_ART,
            verdict_ref="v" * 64, adversary_ref="d" * 64,
        )


def test_seal_requires_the_request_seal_operation() -> None:
    # a token that does not grant request_seal cannot seal (no escalation)
    plane = _plane()
    goal = plane.create_goal("x", WeightClass.SUBSTANTIAL)
    token = plane.acquire_token(
        goal_id=goal, run_id=_RUN, stage=StageId.SEAL, role=Role.RATIFIER, session="op",
        operations=(PROPOSE_TRANSITION_OP,),  # lacks request_seal
    )
    with pytest.raises(Unauthenticated):
        plane.seal(
            token=token, goal_id=goal, run_id=_RUN, artifact_bundle=_ART,
            verdict_ref="v" * 64, adversary_ref="d" * 64,
        )


def test_authorised_seal_commits_to_ledger() -> None:
    plane = _plane()
    goal = plane.create_goal("x", WeightClass.SUBSTANTIAL)
    token = plane.acquire_token(
        goal_id=goal, run_id=_RUN, stage=StageId.SEAL, role=Role.RATIFIER, session="op",
        operations=("request_seal",),
    )
    record = plane.seal(
        token=token, goal_id=goal, run_id=_RUN, artifact_bundle=_ART,
        verdict_ref="v" * 64, adversary_ref="d" * 64,
    )
    assert record.artifact_bundle == _ART
    assert any(r.event.kind == SEAL_EVENT_KIND for r in plane.ledger_events())


# ---- metering + demo ------------------------------------------------------


def test_actions_are_metered() -> None:
    plane = _plane()
    goal = plane.create_goal("x", WeightClass.SUBSTANTIAL)
    _advance(plane, goal, StageId.RAW, StageId.RE_DERIVE)
    actions = [row.action for row in plane.meter.rows]
    assert "create_goal" in actions
    assert "acquire_capability" in actions
    assert "propose_transition" in actions


def test_demo_runs_end_to_end() -> None:
    plane = run_demo()
    assert len(plane.goal_states()) == 1
    assert next(iter(plane.goal_states().values())) == "TRIAGE"
