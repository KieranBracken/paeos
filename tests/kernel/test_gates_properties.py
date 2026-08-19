"""Hypothesis property tests for Kernel Gates legality matrix (RB-0013)."""

from __future__ import annotations

from hypothesis import given, strategies as st

from kernel.gates import is_legal
from kernel.types import StageId, WeightClass


@given(st.sampled_from(list(StageId)), st.sampled_from(list(StageId)), st.sampled_from(list(WeightClass)))
def test_gate_legality_determinism_property(from_stage: StageId, to_stage: StageId, weight: WeightClass) -> None:
    # Invariant 1: Gate legality decision is a total deterministic function
    res1 = is_legal(from_stage, to_stage, weight)
    res2 = is_legal(from_stage, to_stage, weight)
    assert res1 == res2
    assert isinstance(res1, bool)
