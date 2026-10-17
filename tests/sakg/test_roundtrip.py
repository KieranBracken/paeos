from __future__ import annotations

import json

import pytest
from sakg.report import RoundTripError, discover_bundle_paths, roundtrip_bundle, roundtrip_paths


def test_real_sealed_goal_fixture_corpus_is_lossless() -> None:
    paths = discover_bundle_paths()
    assert len(paths) >= 12
    report = roundtrip_paths(paths)
    assert report.loss_ratio == 0
    assert report.fields_lost == 0
    assert all(case.loss_ratio == 0 for case in report.bundles)


def test_machine_report_contains_exact_accounting() -> None:
    report = roundtrip_paths(discover_bundle_paths())
    payload = report.to_dict()
    bundles_evaluated = payload["bundles_evaluated"]
    fields_evaluated = payload["fields_evaluated"]
    fields_lost = payload["fields_lost"]
    loss_ratio = payload["loss_ratio"]
    lossless = payload["lossless"]
    cases = payload["cases"]
    assert isinstance(bundles_evaluated, int) and bundles_evaluated >= 12
    assert isinstance(fields_evaluated, int) and fields_evaluated > 0
    assert fields_lost == 0
    assert loss_ratio == 0
    assert lossless is True
    assert isinstance(cases, list) and len(cases) == bundles_evaluated


def test_duplicate_keys_are_rejected_instead_of_silently_dropped() -> None:
    with pytest.raises(RoundTripError, match="duplicate"):
        roundtrip_bundle(b'{"nodes":[],"nodes":[]}', source="duplicate")


def test_malformed_bundle_is_rejected() -> None:
    with pytest.raises(RoundTripError, match="non-empty nodes"):
        roundtrip_bundle(json.dumps({"nodes": []}).encode(), source="empty")
