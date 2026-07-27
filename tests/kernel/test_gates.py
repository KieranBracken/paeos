"""B0.6 acceptance tests for the gate reference monitor (PAEOS-7.6 §4 / 7 §4.3-4.4).

Table-driven per the four-tuple: a valid request COMMITs; missing/invalid Authority, Goal,
Evidence, or Validation each denies with the correctly-routed Outcome. Adversary crafts partial
four-tuples + role-relabel + forged evidence (T1/T2).
"""

from __future__ import annotations

from dataclasses import replace

from kernel.capability import CapabilityBroker
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.gates import Gate
from kernel.types import (
    CapabilityToken,
    Claim,
    Outcome,
    Role,
    StageId,
    TransitionRequest,
    ValidationClaim,
    WeightClass,
)

_ART = "a" * 64
_SESSION = "sess-1"
_OPS = ("propose_transition",)


def _evidence(*, ev_hash: str = "e" * 64, command: str = "echo ok", result: object = None,
             determinism: Determinism = Determinism.DETERMINISTIC) -> Evidence:
    if result is None:
        result = {"exit_code": 0, "stdout": "ok\n"}
    return Evidence(
        hash=ev_hash,
        kind=EvidenceKind.TEST,
        claim_id="builds",
        artifact_hash=_ART,
        environment_hash="env" + "0" * 61,
        reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session=_SESSION),
        determinism=determinism,
        result=result,  # type: ignore[arg-type]
        attestation="sig",
    )


def _token(
    broker: CapabilityBroker,
    *,
    role: Role = Role.BUILDER,
    stage: StageId = StageId.IMPLEMENT,
    ops: tuple[str, ...] = _OPS,
) -> CapabilityToken:
    return broker.mint(
        goal_id="g-1", run_id="r-1", stage=stage, role=role, session=_SESSION,
        operations=ops, issued_seq=10, expires_seq=40,
    )


def _request(token: CapabilityToken, *, to_state: StageId = StageId.VERIFY,
            producer: Role = Role.BUILDER, produced_against: str = _ART,
            evidence_refs: tuple[str, ...] = ("e" * 64,)) -> TransitionRequest:
    claim = Claim(id="builds", statement="builds green", evidence_refs=evidence_refs)
    validation = ValidationClaim(
        gate_id="G-Build", claims=(claim,), producer=producer, produced_against=produced_against
    )
    return TransitionRequest(
        authority=token,
        goal_id="g-1",
        run_id="r-1",
        from_state=StageId.IMPLEMENT,
        to_state=to_state,
        evidence=evidence_refs,
        validation=validation,
    )


def _gate(broker: CapabilityBroker, evidence: Evidence | None = None, **kw: object) -> Gate:
    if evidence is None:
        evidence = _evidence()
    store = {evidence.hash: evidence}
    return Gate(broker, store.__getitem__, **kw)  # type: ignore[arg-type]


def _propose(gate: Gate, request: TransitionRequest, **over: object) -> Outcome:
    kwargs: dict[str, object] = {
        "weight_class": WeightClass.SUBSTANTIAL,
        "current_seq": 20,
        "artifact_under_review": _ART,
    }
    kwargs.update(over)
    return gate.propose_transition(request, **kwargs).outcome  # type: ignore[arg-type]


# ---- happy path -----------------------------------------------------------


def test_valid_four_tuple_commits() -> None:
    broker = CapabilityBroker()
    ev = _evidence()
    gate = _gate(broker, ev)
    req = _request(_token(broker), evidence_refs=(ev.hash,))
    result = gate.propose_transition(
        req, weight_class=WeightClass.SUBSTANTIAL, current_seq=20, artifact_under_review=_ART
    )
    assert result.outcome is Outcome.COMMITTED
    assert result.reason == ""


# ---- 1. Authority ---------------------------------------------------------


def test_forged_authority_quarantines() -> None:
    broker = CapabilityBroker()
    ev = _evidence()
    forged = replace(_token(broker), token="00" * 64)  # bad signature
    out = _propose(_gate(broker, ev), _request(forged, evidence_refs=(ev.hash,)))
    assert out is Outcome.QUARANTINE


def test_expired_authority_rejects() -> None:
    broker = CapabilityBroker()
    ev = _evidence()
    assert _propose(_gate(broker, ev), _request(_token(broker), evidence_refs=(ev.hash,)),
                    current_seq=99) is Outcome.REJECT


def test_role_relabel_quarantines() -> None:
    # token is BUILDER, but the request claims producer VERIFIER → broker BindingMismatch → QUAR
    broker = CapabilityBroker()
    ev = _evidence()
    req = _request(
        _token(broker, role=Role.BUILDER), producer=Role.VERIFIER, evidence_refs=(ev.hash,)
    )
    assert _propose(_gate(broker, ev), req) is Outcome.QUARANTINE


def test_missing_operation_grant_quarantines() -> None:
    broker = CapabilityBroker()
    ev = _evidence()
    token = _token(broker, ops=("cas:write:x",))  # lacks propose_transition
    out = _propose(_gate(broker, ev), _request(token, evidence_refs=(ev.hash,)))
    assert out is Outcome.QUARANTINE


# ---- 2. Goal --------------------------------------------------------------


def test_illegal_edge_rejects() -> None:
    broker = CapabilityBroker()
    ev = _evidence()
    # IMPLEMENT -> SEAL is not a legal edge
    req = _request(_token(broker), to_state=StageId.SEAL, evidence_refs=(ev.hash,))
    assert _propose(_gate(broker, ev), req) is Outcome.REJECT


# ---- 3. Evidence ----------------------------------------------------------


def test_missing_evidence_remands() -> None:
    broker = CapabilityBroker()
    gate = _gate(broker)
    req = _request(_token(broker), evidence_refs=())  # no evidence for the claim
    assert _propose(gate, req) is Outcome.REMAND


def test_stale_evidence_remands() -> None:
    broker = CapabilityBroker()
    stale = _evidence()
    stale = replace(stale, artifact_hash="b" * 64)  # bound to another artifact
    req = _request(_token(broker), evidence_refs=(stale.hash,))
    assert _propose(_gate(broker, stale), req) is Outcome.REMAND


def test_validation_not_bound_remands() -> None:
    broker = CapabilityBroker()
    ev = _evidence()
    req = _request(_token(broker), produced_against="c" * 64, evidence_refs=(ev.hash,))
    assert _propose(_gate(broker, ev), req) is Outcome.REMAND


def test_forged_evidence_quarantines() -> None:
    # T2: claimed result the command does not produce → kernel re-run catches → QUARANTINE
    broker = CapabilityBroker()
    forged = _evidence(command="echo real", result={"exit_code": 0, "stdout": "FORGED\n"})
    req = _request(_token(broker), evidence_refs=(forged.hash,))
    assert _propose(_gate(broker, forged), req) is Outcome.QUARANTINE


def test_unreproducible_evidence_remands() -> None:
    broker = CapabilityBroker()
    bad = _evidence(command="this_command_does_not_exist_xyz")
    req = _request(_token(broker), evidence_refs=(bad.hash,))
    assert _propose(_gate(broker, bad), req) is Outcome.REMAND


# ---- 4. Validation: separation of powers ----------------------------------


def test_power_fusion_quarantines() -> None:
    # the same session already exercised VERIFIER; now acting as BUILDER → SI-3 violation
    broker = CapabilityBroker()
    ev = _evidence()
    req = _request(_token(broker, role=Role.BUILDER), evidence_refs=(ev.hash,))
    out = _propose(_gate(broker, ev), req, powers_exercised={_SESSION: Role.VERIFIER})
    assert out is Outcome.QUARANTINE


def test_same_power_reuse_is_allowed() -> None:
    broker = CapabilityBroker()
    ev = _evidence()
    req = _request(_token(broker, role=Role.BUILDER), evidence_refs=(ev.hash,))
    out = _propose(_gate(broker, ev), req, powers_exercised={_SESSION: Role.BUILDER})
    assert out is Outcome.COMMITTED


def test_non_separated_power_does_not_conflict() -> None:
    # a session that did PLANNER work (not a separated power) can still BUILD
    broker = CapabilityBroker()
    ev = _evidence()
    req = _request(_token(broker, role=Role.BUILDER), evidence_refs=(ev.hash,))
    out = _propose(_gate(broker, ev), req, powers_exercised={_SESSION: Role.PLANNER})
    assert out is Outcome.COMMITTED


# ---- 5. TCB classifier hook -----------------------------------------------


def test_hard_change_routes_to_amendment() -> None:
    broker = CapabilityBroker()
    ev = _evidence()
    gate = _gate(broker, ev, classify_change=lambda _req: "HARD")
    assert _propose(gate, _request(_token(broker), evidence_refs=(ev.hash,))) is Outcome.REJECT


def test_soft_change_commits() -> None:
    broker = CapabilityBroker()
    ev = _evidence()
    gate = _gate(broker, ev, classify_change=lambda _req: "SOFT")
    assert _propose(gate, _request(_token(broker), evidence_refs=(ev.hash,))) is Outcome.COMMITTED
