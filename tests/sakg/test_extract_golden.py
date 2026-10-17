from __future__ import annotations

import hashlib

from sakg.extract import canonical_json, extract_tradeoff


def test_tradeoff_extraction_has_stable_golden_bytes() -> None:
    source = {
        "kind": "l06",
        "id": "sakg://demo/TradeOff/01J00000000000000000000001",
        "label": "Latency versus assurance",
        "summary": "Choose the smallest safe latency tradeoff.",
        "axes": {"latency": ["low", "high"], "assurance": ["standard", "strict"]},
        "evidence": ["a" * 64],
    }
    first = extract_tradeoff(source, namespace="demo").node
    second = extract_tradeoff(source, namespace="demo").node
    assert first == second
    assert first is not None
    assert canonical_json(first) == canonical_json(second)
    assert (
        hashlib.sha256(canonical_json(first)).hexdigest()
        == "f7151e50d7e18311dc39135a8795780cfc21329e0dd5396f2a22e6f804e7a876"
    )
