from __future__ import annotations

from sakg.extract import extract_tradeoff


def test_unextractable_fields_are_explicit_gaps_not_silently_dropped() -> None:
    result = extract_tradeoff({"kind": "l06", "axes": {"cost": ["low", "high"]}, "unmapped": {"secret": True}}, namespace="demo")
    paths = {gap.path for gap in result.gaps}
    assert "source.unmapped" in paths
    assert "label" in paths
    assert "summary" in paths
    assert "evidence" in paths
    assert "confidence" in paths
    assert result.node is not None
    assert "unmapped" not in result.node["facets"]


def test_gap_records_are_serializable_and_mark_required_evidence() -> None:
    result = extract_tradeoff({"kind": "l06"}, namespace="demo")
    payload = result.to_dict()
    assert payload["gaps"]
    assert any(item["path"] == "evidence" and item["required"] for item in payload["gaps"])
