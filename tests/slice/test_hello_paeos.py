"""B0.SLICE — the Phase-0 vertical slice capstone (PAEOS-8 §11).

Goal `hello-paeos` walks the lifecycle end to end; the ledger demonstrates all seven §11
properties. NOTE: §11's literal `INTAKE→IMPLEMENT→VERIFY→SEAL` predates PAEOS-IP-0003;
under the ratified StageId edge table those exact edges are not legal, so the slice drives the goal
through the actual lawful ROUTINE path — RAW→INTAKE→TRIAGE→IMPLEMENT→VERIFY→ADVERSARIAL_REVIEW→
LEDGER_SYNC→SEAL — which exercises the identical spine (the kernel governs on any disagreement).

If any spine piece is wrong this fails loudly; it cannot be faked green because the kernel re-runs
the evidence itself.
"""

from __future__ import annotations

from pathlib import Path

from cli.paeos import ControlPlane, GoalStates
from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.gates import PROPOSE_TRANSITION_OP
from kernel.ledger import InMemoryLedgerStore, Ledger
from kernel.projections import replay
from kernel.types import Claim, Outcome, Role, StageId, ValidationClaim, WeightClass
from nacl.signing import SigningKey

_REPO = Path(__file__).resolve().parents[2]
_HELLO_SRC = (_REPO / "runtime" / "hello.py").read_bytes()
_ARTIFACT = content_hash(_HELLO_SRC)  # the artifact under review: hello.py by content address
_ENV = content_hash(b"paeos-slice-env")
# The passing test, bound to the artifact: the kernel re-runs THIS at every gate.
_TEST_CMD = "python3 -c \"from runtime.hello import greet; assert greet() == 'hello, paeos'\""

# The ratified lawful ROUTINE path to SEAL.
_PATH = (
    (StageId.RAW, StageId.INTAKE),
    (StageId.INTAKE, StageId.TRIAGE),
    (StageId.TRIAGE, StageId.IMPLEMENT),
    (StageId.IMPLEMENT, StageId.VERIFY),
    (StageId.VERIFY, StageId.ADVERSARIAL_REVIEW),
    (StageId.ADVERSARIAL_REVIEW, StageId.LEDGER_SYNC),
    (StageId.LEDGER_SYNC, StageId.SEAL),
)


def _plane() -> ControlPlane:
    return ControlPlane(Ledger(InMemoryLedgerStore()), SigningKey.generate())


def _hello_evidence() -> Evidence:
    """Deterministic evidence: the passing hello test, bound to hello.py's hash + env hash."""
    return Evidence(
        hash=content_hash(_TEST_CMD.encode()),
        kind=EvidenceKind.TEST,
        claim_id="greets",
        artifact_hash=_ARTIFACT,
        environment_hash=_ENV,
        reproducible_command=_TEST_CMD,
        producer=EvidenceProducer(role=Role.BUILDER, session="builder"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": ""},
        attestation="kernel-sig",
    )


def _validation(evidence: Evidence, *, producer: Role = Role.BUILDER) -> ValidationClaim:
    claim = Claim(id="greets", statement="greet() is correct", evidence_refs=(evidence.hash,))
    return ValidationClaim(
        gate_id="G", claims=(claim,), producer=producer, produced_against=_ARTIFACT
    )


def _advance(plane: ControlPlane, goal: str, frm: StageId, to: StageId) -> object:
    token = plane.acquire_token(
        goal_id=goal, run_id="r-1", stage=frm, role=Role.BUILDER, session="builder",
        operations=(PROPOSE_TRANSITION_OP,),
    )
    evidence = _hello_evidence()
    plane.register_evidence(evidence)
    return plane.advance(
        token=token, goal_id=goal, run_id="r-1", from_state=frm, to_state=to,
        weight_class=WeightClass.ROUTINE, artifact_under_review=_ARTIFACT,
        validation=_validation(evidence),
    )


# ---- the end-to-end slice (points 1,2,3,6,7) ------------------------------


def test_hello_paeos_slice() -> None:
    plane = _plane()

    # (1) create-goal appends the goal at RAW; advancing to INTAKE is capability-token-authorized.
    goal = plane.create_goal("hello-paeos", WeightClass.ROUTINE)
    assert plane.inspect(goal) == "RAW"

    for frm, to in _PATH:
        # (2) reaching IMPLEMENT produces hello.py in the CAS (content-addressed).
        if to is StageId.IMPLEMENT:
            plane.store_artifact(_HELLO_SRC)
            assert plane.has_artifact(_ARTIFACT)
        result = _advance(plane, goal, frm, to)
        # (3) every advance is gated on evidence the KERNEL RE-RUNS — a pass it reproduces.
        assert result.outcome is Outcome.COMMITTED, (frm, to, result.reason)  # type: ignore[attr-defined]
        assert result.committed_seq is not None  # type: ignore[attr-defined]

    assert plane.inspect(goal) == "SEAL"

    # (6) SEAL: an idempotent Ed25519 seal; sealing twice yields the same seal_hash, committed once.
    seal_token = plane.acquire_token(
        goal_id=goal, run_id="r-1", stage=StageId.SEAL, role=Role.RATIFIER, session="ratifier",
        operations=("request_seal",),
    )
    first = plane.seal(
        token=seal_token, goal_id=goal, run_id="r-1", artifact_bundle=_ARTIFACT,
        verdict_ref="v" * 64, adversary_ref="d" * 64,
    )
    second = plane.seal(
        token=seal_token, goal_id=goal, run_id="r-1", artifact_bundle=_ARTIFACT,
        verdict_ref="v" * 64, adversary_ref="d" * 64,
    )
    assert first.seal_hash == second.seal_hash  # idempotent
    seal_events = [r for r in plane.ledger_events() if r.event.kind == "SealCommitted"]
    assert len(seal_events) == 1  # committed once

    # (7) replay reconstructs the goal's entire state byte-identically from the ledger.
    a = replay(plane._ledger, GoalStates())  # the slice inspects the raw ledger
    b = replay(plane._ledger, GoalStates())
    assert a == b
    assert a.state[goal] == "SEAL"


# ---- (4) deny-by-default: a missing evidence ref is denied -----------------


def test_missing_evidence_is_denied() -> None:
    plane = _plane()
    goal = plane.create_goal("hello-paeos", WeightClass.ROUTINE)
    token = plane.acquire_token(
        goal_id=goal, run_id="r-1", stage=StageId.RAW, role=Role.BUILDER, session="builder",
        operations=(PROPOSE_TRANSITION_OP,),
    )
    empty = ValidationClaim(
        gate_id="G",
        claims=(Claim(id="greets", statement="unbacked", evidence_refs=()),),  # NO evidence
        producer=Role.BUILDER,
        produced_against=_ARTIFACT,
    )
    result = plane.advance(
        token=token, goal_id=goal, run_id="r-1", from_state=StageId.RAW, to_state=StageId.INTAKE,
        weight_class=WeightClass.ROUTINE, artifact_under_review=_ARTIFACT, validation=empty,
    )
    assert result.outcome is not Outcome.COMMITTED  # deny-by-default
    assert [r.event.kind for r in plane.ledger_events()] == ["goal_created"]  # nothing committed


# ---- (5) separation of powers: one session may not hold two powers ---------


def test_separation_of_powers_is_denied() -> None:
    plane = _plane()
    goal = plane.create_goal("hello-paeos", WeightClass.ROUTINE)
    # a single session that already exercised BUILDER now tries to act as a conflicting power
    # (RATIFIER = the seal power): the reference monitor quarantines it (SI-3, "build and seal").
    token = plane.acquire_token(
        goal_id=goal, run_id="r-1", stage=StageId.RAW, role=Role.RATIFIER, session="solo",
        operations=(PROPOSE_TRANSITION_OP,),
    )
    evidence = _hello_evidence()
    plane.register_evidence(evidence)
    result = plane.advance(
        token=token, goal_id=goal, run_id="r-1", from_state=StageId.RAW, to_state=StageId.INTAKE,
        weight_class=WeightClass.ROUTINE, artifact_under_review=_ARTIFACT,
        validation=_validation(evidence, producer=Role.RATIFIER),
        powers_exercised={"solo": Role.BUILDER},  # this session already built
    )
    assert result.outcome is Outcome.QUARANTINE  # separation-of-powers violation denied
