"""Hypothesis property tests for Capability Broker unforgeability (RB-0013)."""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from kernel.capability import CapabilityBroker, InvalidToken
from kernel.types import Role, StageId


@given(st.text(), st.text(), st.integers(min_value=1, max_value=100))
def test_capability_broker_unforgeability_property(goal_id: str, run_id: str, seq: int) -> None:
    broker = CapabilityBroker()
    token = broker.mint(
        goal_id=goal_id,
        run_id=run_id,
        stage=StageId.IDEATE,
        role=Role.PLANNER,
        session="sess-1",
        operations=("read", "write"),
        issued_seq=seq,
        expires_seq=seq + 10,
    )

    # Invariant 1: Minted genuine token verifies cleanly
    broker.verify(
        token=token,
        goal_id=goal_id,
        run_id=run_id,
        stage=StageId.IDEATE,
        role=Role.PLANNER,
        session="sess-1",
        operation="read",
        current_seq=seq + 1,
    )

    # Invariant 2: Tampered signature string fails verification (unforgeable)
    tampered_sig = token.token[:-2] + ("00" if token.token[-2:] != "00" else "11")
    forged_token = type(token)(
        token=tampered_sig,
        bound_to=token.bound_to,
        operations=token.operations,
        issued_seq=token.issued_seq,
        expires_seq=token.expires_seq,
    )
    with pytest.raises(InvalidToken):
        broker.verify(
            token=forged_token,
            goal_id=goal_id,
            run_id=run_id,
            stage=StageId.IDEATE,
            role=Role.PLANNER,
            session="sess-1",
            operation="read",
            current_seq=seq + 1,
        )
