"""Hand-attribution safeguards for historical outcomes."""
from __future__ import annotations

from pathlib import Path

from sakg.backfill import backfill_outcomes

ROOT = Path(__file__).resolve().parents[2]
DEBT = ROOT / "ledger/debt/DEBT-0062.md"


def test_backfilled_outcomes_are_explicitly_hand_attributed_and_untrusted() -> None:
    result = backfill_outcomes((DEBT,), namespace="paeos-recovery", run_id="attribution-test")
    node = result.nodes[0]
    facets = node["facets"]
    assert isinstance(facets, dict)
    assert facets["hand_attributed"]["value"] is True
    assert facets["evidence_derived"]["value"] is False
    assert facets["attribution"]["mode"] == "hand-attributed"
    assert node["status"] == "candidate"
    assert node["confidence"] < 1
    assert node["provenance"]["author_kind"] == "ingest"
    assert node["evidence"][0]["kind"] == "source"
