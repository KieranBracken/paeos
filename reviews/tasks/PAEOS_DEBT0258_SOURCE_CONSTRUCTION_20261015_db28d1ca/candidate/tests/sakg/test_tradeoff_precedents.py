from __future__ import annotations

import pytest
from sakg.methods.tradeoff_precedents import TradeoffPrecedentError, tradeoff_precedents

TID = "sakg://demo/TradeOff/01ARZ3NDEKTSV4RRFFQ69G5F01"
D1 = "sakg://demo/Decision/01ARZ3NDEKTSV4RRFFQ69G5F02"
D2 = "sakg://demo/Decision/01ARZ3NDEKTSV4RRFFQ69G5F03"
O1 = "sakg://demo/Outcome/01ARZ3NDEKTSV4RRFFQ69G5F04"
O2 = "sakg://demo/Outcome/01ARZ3NDEKTSV4RRFFQ69G5F05"


def node(identifier: str, kind: str, **extra: object) -> dict[str, object]:
    return {"id": identifier, "type": kind, "namespace": "demo", **extra}


def edge(source: str, target: str, relation: str, family: str = "tradeoff") -> dict[str, object]:
    return {
        "edge_id": f"edge:{source[-2:]}:{target[-2:]}",
        "source": source,
        "target": target,
        "family": family,
        "relation": relation,
        "properties": {},
    }


def graph() -> tuple[
    tuple[dict[str, object], ...],
    tuple[dict[str, object], ...],
    tuple[dict[str, object], ...],
    tuple[dict[str, object], ...],
]:
    tradeoffs = (node(TID, "TradeOff", facets={"axes": ["latency", "accuracy"]}, confidence=0.91),)
    decisions = (
        node(D1, "Decision", confidence=0.91),
        node(D2, "Decision", confidence=0.74),
    )
    outcomes = (
        node(O1, "Outcome", status="realized", summary="safe result"),
        node(O2, "Outcome", status="candidate", summary="not yet realized"),
    )
    edges = (
        edge(TID, D1, "resolves_to"),
        edge(TID, D2, "resolves_to"),
        edge(D1, O1, "realized_as", "causal"),
        edge(D2, O2, "realized_as", "causal"),
    )
    return tradeoffs, decisions, outcomes, edges


def test_matches_axes_walks_to_decision_and_ranks() -> None:
    tradeoffs, decisions, outcomes, edges = graph()
    result = tradeoff_precedents(tradeoffs, decisions, outcomes, edges, ("latency", "accuracy"))
    assert len(result) == 1
    assert result[0]["decision_id"] == D1
    assert result[0]["outcome"]["id"] == O1
    assert result[0]["why"] == [
        "TradeOff axes matched: latency,accuracy",
        "TradeOff resolves_to Decision",
        "Decision realized_as Outcome",
    ]


def test_all_requested_axes_are_required_and_namespace_is_gated() -> None:
    tradeoffs, decisions, outcomes, edges = graph()
    assert tradeoff_precedents(tradeoffs, decisions, outcomes, edges, ("latency", "memory")) == ()
    assert (
        tradeoff_precedents(
            tradeoffs, decisions, outcomes, edges, ("latency", "accuracy"), namespace="other"
        )
        == ()
    )


def test_query_rejects_malformed_axes() -> None:
    tradeoffs, decisions, outcomes, edges = graph()
    with pytest.raises(TradeoffPrecedentError):
        tradeoff_precedents(tradeoffs, decisions, outcomes, edges, ("latency",))
