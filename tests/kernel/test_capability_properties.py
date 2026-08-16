import pytest
from hypothesis import given
from hypothesis import strategies as st
from kernel.capability import (
    CapabilityBroker,
    CapabilityToken,
    ExpiredToken,
    InvalidToken,
    OperationNotPermitted,
)
from kernel.types import Role, StageId

st_goal_id = st.text(min_size=1)
st_run_id = st.text(min_size=1)
st_stage = st.sampled_from(list(StageId))
st_role = st.sampled_from(list(Role))
st_session = st.text(min_size=1)
st_op = st.text(min_size=1, max_size=10)
st_seq = st.integers(min_value=0, max_value=10000)


@given(st_goal_id, st_run_id, st_stage, st_role, st_session, st_op, st_seq, st_seq)
def test_capability_signature_and_binding(
    goal_id, run_id, stage, role, session, op, issued, offset
):
    """Token should verify correctly when all inputs match, and reject when tampered or expired."""
    expires = issued + offset
    broker = CapabilityBroker()

    token = broker.mint(
        goal_id=goal_id,
        run_id=run_id,
        stage=stage,
        role=role,
        session=session,
        operations=(op,),
        issued_seq=issued,
        expires_seq=expires,
    )

    # Genuine use
    broker.verify(
        token,
        goal_id=goal_id,
        run_id=run_id,
        stage=stage,
        role=role,
        operation=op,
        current_seq=issued,
        session=session,
    )

    # Expired use
    with pytest.raises(ExpiredToken):
        broker.verify(
            token,
            goal_id=goal_id,
            run_id=run_id,
            stage=stage,
            role=role,
            operation=op,
            current_seq=expires + 1,
            session=session,
        )

    # Operation not permitted
    with pytest.raises(OperationNotPermitted):
        broker.verify(
            token,
            goal_id=goal_id,
            run_id=run_id,
            stage=stage,
            role=role,
            operation=op + "_tamper",
            current_seq=issued,
            session=session,
        )

    # Tampered signature
    tampered_token = CapabilityToken(
        token="00" * 64,
        bound_to=token.bound_to,
        operations=token.operations,
        issued_seq=token.issued_seq,
        expires_seq=token.expires_seq,
    )
    with pytest.raises(InvalidToken):
        broker.verify(
            tampered_token,
            goal_id=goal_id,
            run_id=run_id,
            stage=stage,
            role=role,
            operation=op,
            current_seq=issued,
            session=session,
        )
