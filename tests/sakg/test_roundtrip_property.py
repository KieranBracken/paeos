from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from sakg.report import canonical_roundtrip

json_scalar = st.one_of(
    st.none(), st.booleans(), st.integers(-100000, 100000), st.text(max_size=30)
)
json_value = st.recursive(
    json_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.text(min_size=1, max_size=12), children, max_size=4),
    ),
    max_leaves=25,
)


@settings(max_examples=100, deadline=None)
@given(extra=json_value)
def test_hypothesis_generated_bundle_is_lossless(extra: object) -> None:
    bundle = {
        "bundle_id": "sakg-bundle:hypothesis",
        "schema_version": "paeos.sakg.emission-bundle/v1",
        "goal_id": "g-hypothesis",
        "sealed_at": "2026-09-02T00:00:00Z",
        "namespace": "demo",
        "producer": {"system": "hypothesis", "version": "1"},
        "nodes": [{"id": "node", "facets": {"generated": extra}}],
    }
    value, first, second = canonical_roundtrip(bundle)
    assert value == bundle
    assert first == second
