"""Discriminating fail-closed probes for the S2 tradeoff precedent method."""

from __future__ import annotations

import pytest
from sakg.methods.tradeoff_precedents import TradeoffPrecedentError, execute

RECOVERY = "paeos-recovery"
ARCHIVE = "paeos-archive"


def node(identifier: str, kind: str | None, namespace: str, **extra: object) -> dict[str, object]:
    record: dict[str, object] = {"id": identifier, "namespace": namespace, **extra}
    if kind is not None:
        record["type"] = kind
    return record


def edge(source: str, target: str, relation: str) -> dict[str, object]:
    return {
        "source": source,
        "target": target,
        "family": "causal" if "realized" in relation else "tradeoff",
        "relation": relation,
        "properties": {},
    }


def request(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "method": "tradeoff_precedents",
        "axes": ["latency", "accuracy"],
    }
    value.update(overrides)
    return value


def test_p1_negated_resolving_link_is_not_admitted() -> None:
    tradeoff = "sakg://paeos-recovery/TradeOff/T1"
    decision = "sakg://paeos-recovery/Decision/D1"
    outcome = "sakg://paeos-recovery/Outcome/O1"
    nodes = (
        node(tradeoff, "TradeOff", RECOVERY, facets={"axes": ["latency", "accuracy"]}),
        node(decision, "Decision", RECOVERY),
        node(outcome, "Outcome", RECOVERY, status="realized", summary="valid outcome"),
    )
    edges = (edge(tradeoff, decision, "unresolved_decision"), edge(decision, outcome, "realized_as"))

    assert execute(request(namespace=RECOVERY), nodes, edges)["results"] == []


def test_p2_negated_realization_link_is_not_admitted() -> None:
    tradeoff = "sakg://paeos-recovery/TradeOff/T2"
    decision = "sakg://paeos-recovery/Decision/D2"
    outcome = "sakg://paeos-recovery/Outcome/O2"
    nodes = (
        node(tradeoff, "TradeOff", RECOVERY, facets={"axes": ["latency", "accuracy"]}),
        node(decision, "Decision", RECOVERY),
        node(outcome, "Outcome", RECOVERY, status="realized", summary="must not join"),
    )
    edges = (edge(tradeoff, decision, "resolves_to"), edge(decision, outcome, "unrealized_as_outcome"))

    assert execute(request(namespace=RECOVERY), nodes, edges)["results"] == []


def test_p3_execute_namespace_gates_every_hop() -> None:
    recovery_tradeoff = "sakg://paeos-recovery/TradeOff/T3"
    recovery_decision = "sakg://paeos-recovery/Decision/D3"
    recovery_outcome = "sakg://paeos-recovery/Outcome/O3"
    archive_tradeoff = "sakg://paeos-archive/TradeOff/T3"
    archive_decision = "sakg://paeos-archive/Decision/D3"
    archive_outcome = "sakg://paeos-archive/Outcome/O3"
    nodes = (
        node(recovery_tradeoff, "TradeOff", RECOVERY, facets={"axes": ["latency", "accuracy"]}),
        node(recovery_decision, "Decision", RECOVERY),
        node(recovery_outcome, "Outcome", RECOVERY, status="realized", summary="recovery"),
        node(archive_tradeoff, "TradeOff", ARCHIVE, facets={"axes": ["latency", "accuracy"]}),
        node(archive_decision, "Decision", ARCHIVE),
        node(archive_outcome, "Outcome", ARCHIVE, status="realized", summary="archive"),
    )
    edges = (
        edge(recovery_tradeoff, recovery_decision, "resolves_to"),
        edge(recovery_decision, recovery_outcome, "realized_as"),
        edge(archive_tradeoff, archive_decision, "resolves_to"),
        edge(archive_decision, archive_outcome, "realized_as"),
    )

    results = execute(request(namespace=RECOVERY), nodes, edges)["results"]
    assert len(results) == 1
    assert results[0]["outcome"]["id"] == recovery_outcome


def test_p4_execute_enforces_minimum_confidence() -> None:
    tradeoff = "sakg://paeos-recovery/TradeOff/T4"
    decision = "sakg://paeos-recovery/Decision/D4"
    outcome = "sakg://paeos-recovery/Outcome/O4"
    nodes = (
        node(
            tradeoff,
            "TradeOff",
            RECOVERY,
            facets={"axes": ["latency", "accuracy"]},
            confidence=0.8,
        ),
        node(decision, "Decision", RECOVERY),
        node(outcome, "Outcome", RECOVERY, status="realized", summary="below threshold"),
    )
    edges = (edge(tradeoff, decision, "resolves_to"), edge(decision, outcome, "realized_as"))

    results = execute(request(namespace=RECOVERY, min_confidence=0.95), nodes, edges)["results"]
    assert results == []


def test_p5_untyped_nodes_cannot_form_a_precedent() -> None:
    tradeoff = "bare-tradeoff"
    decision = "bare-decision"
    outcome = "bare-outcome"
    nodes = (
        node(tradeoff, None, RECOVERY, facets={"axes": ["latency", "accuracy"]}),
        node(decision, None, RECOVERY),
        node(outcome, None, RECOVERY, status="realized", summary="untyped"),
    )
    edges = (edge(tradeoff, decision, "resolves_to"), edge(decision, outcome, "realized_as"))

    assert execute(request(namespace=RECOVERY), nodes, edges)["results"] == []


def test_malformed_confidence_is_rejected_instead_of_ignored() -> None:
    with pytest.raises(TradeoffPrecedentError, match="min_confidence"):
        execute(request(min_confidence="high"), (), ())
