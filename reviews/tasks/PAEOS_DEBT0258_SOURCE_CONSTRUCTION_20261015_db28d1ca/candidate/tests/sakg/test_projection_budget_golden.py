"""Golden drop-and-count semantics over complete candidate structures."""

from __future__ import annotations

import json
from pathlib import Path

from sakg.project import enforce_budget

ROOT = Path(__file__).resolve().parents[2]


def test_budget_fixtures_match_the_projection_enforcer() -> None:
    for path in sorted((ROOT / "tests/sakg/fixtures/budget").glob("*.json")):
        case = json.loads(path.read_text())
        budgeted = enforce_budget(case["candidates"], case["request"]["budget"])
        assert [item["id"] for item in budgeted.retained] == case["expected"]["retained_ids"]
        assert budgeted.retained_tokens == case["expected"]["retained_tokens"]
        assert budgeted.omitted == case["expected"]["omitted"]
        assert budgeted.truncated is case["expected"]["truncated"]
