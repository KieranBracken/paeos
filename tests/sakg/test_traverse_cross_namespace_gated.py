"""Cross-namespace traversal requires bilateral disclosure."""
from __future__ import annotations

import pytest

from sakg.traverse import CrossNamespaceDenied, DisclosurePolicy, cross_namespace_allowed, walk_ids

A = "sakg://alpha/Decision/01J000000000000000000000001"
B = "sakg://beta/Outcome/01J000000000000000000000002"
EDGE = {"edge_id": "cross", "namespace": "alpha", "source": A, "target": B, "family": "causal", "relation": "projects_to", "properties": {}, "evidence": [], "created_at": "2026-09-02T00:00:00Z"}


def policies(outbound: bool = True, inbound: bool = True) -> dict[str, DisclosurePolicy]:
    return {"alpha": DisclosurePolicy("alpha", frozenset({"beta"}) if outbound else frozenset(), frozenset()), "beta": DisclosurePolicy("beta", frozenset(), frozenset({"alpha"}) if inbound else frozenset())}


def test_bilateral_disclosure_is_required_and_sufficient() -> None:
    assert cross_namespace_allowed(policies()["alpha"], policies()["beta"])
    assert walk_ids((EDGE,), A, "causal", disclosure_policies=policies()) == (B,)


def test_missing_policies_fail_closed() -> None:
    with pytest.raises(CrossNamespaceDenied):
        walk_ids((EDGE,), A, "causal")


def test_one_sided_disclosure_is_denied() -> None:
    with pytest.raises(CrossNamespaceDenied):
        walk_ids((EDGE,), A, "causal", disclosure_policies=policies(inbound=False))
