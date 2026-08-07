"""B0.8 acceptance tests for the capability broker (PAEOS-7.6 §7 / 7.5 T1, A-6).

Covers: mint→verify round-trip; forged/tampered tokens denied (unforgeable); expired tokens
denied (TTL); role/goal binding immutable in use (no relabeling); out-of-scope operation denied
(no escalation); no self-grant (a token cannot be fabricated without the kernel key). The
Adversary attacks are T1 (escalation) and A-6 (stale-token reuse).
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from kernel.capability import (
    BindingMismatch,
    CapabilityBroker,
    ExpiredToken,
    InvalidToken,
    OperationNotPermitted,
)
from kernel.types import CapabilityToken, Role, StageId


def _mint(
    broker: CapabilityBroker,
    *,
    goal_id: str = "g-1",
    run_id: str = "r-1",
    stage: StageId = StageId.IMPLEMENT,
    role: Role = Role.BUILDER,
    session: str = "sess-1",
    operations: tuple[str, ...] = ("propose_transition", "cas:write:kernel/x.py"),
    issued_seq: int = 10,
    expires_seq: int = 40,
) -> CapabilityToken:
    return broker.mint(
        goal_id=goal_id,
        run_id=run_id,
        stage=stage,
        role=role,
        session=session,
        operations=operations,
        issued_seq=issued_seq,
        expires_seq=expires_seq,
    )


def _verify(
    broker: CapabilityBroker,
    token: CapabilityToken,
    *,
    goal_id: str = "g-1",
    run_id: str = "r-1",
    stage: StageId = StageId.IMPLEMENT,
    role: Role = Role.BUILDER,
    operation: str = "propose_transition",
    current_seq: int = 20,
    session: str | None = None,
) -> None:
    broker.verify(
        token,
        goal_id=goal_id,
        run_id=run_id,
        stage=stage,
        role=role,
        operation=operation,
        current_seq=current_seq,
        session=session,
    )


# ---- happy path -----------------------------------------------------------


def test_mint_then_verify_round_trips() -> None:
    broker = CapabilityBroker()
    token = _mint(broker)
    _verify(broker, token)  # no raise
    _verify(broker, token, session="sess-1")  # session also matches


def test_mint_rejects_inverted_ttl() -> None:
    broker = CapabilityBroker()
    with pytest.raises(ValueError):
        _mint(broker, issued_seq=40, expires_seq=10)


# ---- unforgeable (T1) -----------------------------------------------------


def test_hand_fabricated_token_is_denied() -> None:
    # No self-grant: an agent without the kernel key cannot fabricate a valid token.
    broker = CapabilityBroker()
    fake = CapabilityToken(
        token="00" * 64,
        bound_to=_mint(broker).bound_to,
        operations=("seal", "merge"),
        issued_seq=0,
        expires_seq=10**9,
    )
    with pytest.raises(InvalidToken):
        _verify(broker, fake, operation="seal", current_seq=1)


def test_tampering_bound_to_breaks_signature() -> None:
    broker = CapabilityBroker()
    token = _mint(broker, role=Role.BUILDER)
    relabelled = replace(token, bound_to=replace(token.bound_to, role=Role.VERIFIER))
    with pytest.raises(InvalidToken):  # signature covers bound_to → tamper caught
        _verify(broker, relabelled, role=Role.VERIFIER)


def test_tampering_operations_breaks_signature() -> None:
    broker = CapabilityBroker()
    token = _mint(broker, operations=("propose_transition",))
    escalated = replace(token, operations=("propose_transition", "seal"))
    with pytest.raises(InvalidToken):
        _verify(broker, escalated, operation="seal")


def test_extending_ttl_breaks_signature() -> None:
    broker = CapabilityBroker()
    token = _mint(broker, expires_seq=40)
    extended = replace(token, expires_seq=10**9)
    with pytest.raises(InvalidToken):
        _verify(broker, extended, current_seq=500)


def test_token_from_another_broker_is_denied() -> None:
    minter = CapabilityBroker()
    other = CapabilityBroker()  # different key
    token = _mint(minter)
    _verify(minter, token)  # genuine for its own broker
    with pytest.raises(InvalidToken):
        _verify(other, token)  # a different kernel key rejects it


# ---- TTL / stale-token reuse (A-6) ----------------------------------------


def test_expired_token_denied() -> None:
    broker = CapabilityBroker()
    token = _mint(broker, issued_seq=10, expires_seq=40)
    with pytest.raises(ExpiredToken):
        _verify(broker, token, current_seq=41)  # past expiry
    with pytest.raises(ExpiredToken):
        _verify(broker, token, current_seq=9)  # before issue
    _verify(broker, token, current_seq=10)  # boundary inclusive
    _verify(broker, token, current_seq=40)  # boundary inclusive


# ---- binding immutable in use (SI-3, no relabeling) -----------------------


def test_genuine_token_cannot_be_used_for_another_role() -> None:
    broker = CapabilityBroker()
    builder_token = _mint(broker, role=Role.BUILDER)
    with pytest.raises(BindingMismatch):
        _verify(broker, builder_token, role=Role.VERIFIER)  # SI-3: separation of powers


def test_binding_checks_goal_run_stage_session() -> None:
    broker = CapabilityBroker()
    token = _mint(broker, goal_id="g-1", run_id="r-1", stage=StageId.IMPLEMENT, session="s-1")
    with pytest.raises(BindingMismatch):
        _verify(broker, token, goal_id="g-2")
    with pytest.raises(BindingMismatch):
        _verify(broker, token, run_id="r-9")
    with pytest.raises(BindingMismatch):
        _verify(broker, token, stage=StageId.SEAL)
    with pytest.raises(BindingMismatch):
        _verify(broker, token, session="s-9")


# ---- least authority / no escalation --------------------------------------


def test_out_of_scope_operation_denied() -> None:
    broker = CapabilityBroker()
    token = _mint(broker, operations=("propose_transition",))
    with pytest.raises(OperationNotPermitted):
        _verify(broker, token, operation="seal")  # escalation attempt
    _verify(broker, token, operation="propose_transition")  # granted op ok


def test_verify_order_signature_before_binding() -> None:
    # A forged token with a mismatched role must fail on signature (InvalidToken), not leak via
    # the binding path — signature is checked first.
    broker = CapabilityBroker()
    token = _mint(broker, role=Role.BUILDER)
    forged = replace(token, bound_to=replace(token.bound_to, role=Role.VERIFIER), token="ab" * 64)
    with pytest.raises(InvalidToken):
        _verify(broker, forged, role=Role.VERIFIER)
