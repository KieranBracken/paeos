from __future__ import annotations

import json
from pathlib import Path

from sakg.methods.tradeoff_precedents import tradeoff_precedents

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/sakg/fixtures/tradeoff"


def _node(identifier: str, kind: str, **extra: object) -> dict[str, object]:
    return {"id": identifier, "type": kind, "namespace": "paeos-recovery", **extra}


def _run(fixture: dict[str, object]) -> tuple[dict[str, object], ...]:
    query = fixture["query"]
    expected = fixture["expected"]["results"]
    axes = query["axes"]
    tradeoffs: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    outcomes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    for index, item in enumerate(expected):
        decision_id = item["decision_id"]
        outcome = item["outcome"]
        tradeoff_id = f"sakg://paeos-recovery/TradeOff/01J00000000000000000000E{index + 1:02d}"
        tradeoffs.append(
            _node(tradeoff_id, "TradeOff", facets={"axes": axes}, confidence=item["score"])
        )
        decisions.append(_node(decision_id, "Decision", confidence=item["score"]))
        outcomes.append(
            _node(outcome["id"], "Outcome", status="realized", summary=outcome["summary"])
        )
        edges.extend(
            (
                {
                    "edge_id": f"resolves:{index}",
                    "source": tradeoff_id,
                    "target": decision_id,
                    "family": "tradeoff",
                    "relation": "resolves_to",
                    "properties": {},
                },
                {
                    "edge_id": f"realized:{index}",
                    "source": decision_id,
                    "target": outcome["id"],
                    "family": "causal",
                    "relation": "realized_as",
                    "properties": {},
                },
            )
        )
    return tradeoff_precedents(
        tradeoffs, decisions, outcomes, edges, axes, namespace="paeos-recovery"
    )


def test_five_archaeological_fixtures_produce_expected_ranked_paths() -> None:
    files = sorted(FIXTURES.glob("*.json"))
    assert len(files) >= 5
    for path in files:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        actual = _run(fixture)
        expected = fixture["expected"]["results"]
        assert [item["decision_id"] for item in actual] == [
            item["decision_id"] for item in expected
        ]
        assert [item["outcome"] for item in actual] == [item["outcome"] for item in expected]
        assert [item["why"] for item in actual] == [item["why"] for item in expected]
        assert [item["score"] for item in actual] == [item["score"] for item in expected]
