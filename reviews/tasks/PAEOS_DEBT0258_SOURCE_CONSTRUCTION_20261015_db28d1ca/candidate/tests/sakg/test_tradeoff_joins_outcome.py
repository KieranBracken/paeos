from __future__ import annotations

from sakg.methods.tradeoff_precedents import tradeoff_precedents

T = "sakg://demo/TradeOff/01ARZ3NDEKTSV4RRFFQ69G5F06"
D = "sakg://demo/Decision/01ARZ3NDEKTSV4RRFFQ69G5F07"
GOOD = "sakg://demo/Outcome/01ARZ3NDEKTSV4RRFFQ69G5F08"
BAD = "sakg://demo/Outcome/01ARZ3NDEKTSV4RRFFQ69G5F09"


def test_realized_outcome_is_joined_but_candidate_is_not() -> None:
    tradeoffs = (
        {
            "id": T,
            "type": "TradeOff",
            "namespace": "demo",
            "coordinates": {"axes": ["cost", "reliability"]},
            "confidence": 0.8,
        },
    )
    decisions = ({"id": D, "type": "Decision", "namespace": "demo"},)
    outcomes = (
        {
            "id": GOOD,
            "type": "Outcome",
            "namespace": "demo",
            "status": "realized",
            "summary": "deployed safely",
        },
        {
            "id": BAD,
            "type": "Outcome",
            "namespace": "demo",
            "status": "candidate",
            "summary": "not deployed",
        },
    )
    edges = (
        {
            "source": T,
            "target": D,
            "family": "tradeoff",
            "relation": "resolves_to",
            "properties": {},
        },
        {
            "source": D,
            "target": GOOD,
            "family": "causal",
            "relation": "decision_realized_as_outcome",
            "properties": {},
        },
        {
            "source": D,
            "target": BAD,
            "family": "causal",
            "relation": "decision_realized_as_outcome",
            "properties": {},
        },
    )
    result = tradeoff_precedents(tradeoffs, decisions, outcomes, edges, ("cost", "reliability"))
    assert len(result) == 1
    assert result[0]["outcome"]["id"] == GOOD


def test_missing_realization_edge_does_not_invent_an_outcome() -> None:
    tradeoffs = ({"id": T, "type": "TradeOff", "facets": {"axes": ["cost", "reliability"]}},)
    decisions = ({"id": D, "type": "Decision"},)
    outcomes = (
        {"id": GOOD, "type": "Outcome", "status": "realized", "summary": "deployed safely"},
    )
    edges = (
        {
            "source": T,
            "target": D,
            "family": "tradeoff",
            "relation": "resolves_to",
            "properties": {},
        },
    )
    assert tradeoff_precedents(tradeoffs, decisions, outcomes, edges, ("cost", "reliability")) == ()
