from hypothesis import given
from hypothesis import strategies as st
from kernel.lifecycle import is_legal
from kernel.types import StageId, WeightClass

st_stage = st.sampled_from(list(StageId))
st_weight = st.sampled_from(list(WeightClass))


@given(st_stage, st_stage, st_weight)
def test_gate_matrix_validity(from_stage, to_stage, weight_class):
    """Assert is_legal completes without exception over arbitrary StageId pairs."""
    result = is_legal(from_stage, to_stage, weight_class)
    assert isinstance(result, bool)
