"""Longitudinal Outcome observation and belief-revision integration tests."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest
from sakg.outcome_observer import (
    MalformedOutcomeRecord,
    OutcomeBindingError,
    OutcomeObserver,
    OutcomeState,
    OutcomeTransitionError,
)
from sakg.store import GraphStore

NAMESPACE = "paeos-history"
OBSERVED_AT = "2026-09-04T20:00:00Z"
DECISION_ID = f"sakg://{NAMESPACE}/Decision/{'1':0>26}"
TRADEOFF_ID = f"sakg://{NAMESPACE}/TradeOff/{'2':0>26}"


def _graph_node(kind: str, node_id: str) -> dict[str, object]:
    digest = hashlib.sha256(node_id.encode()).hexdigest()
    return {
        "id": node_id,
        "type": kind,
        "namespace": NAMESPACE,
        "facets": {"fixture": {"value": True}},
        "label": f"Fixture {kind}",
        "summary": f"A bound {kind} used by the outcome observer tests.",
        "provenance": {
            "origin": {"system": "test", "run_id": "task-25"},
            "author_kind": "human",
            "ingested_at": OBSERVED_AT,
            "source_hash": digest,
        },
        "evidence": [
            {
                "hash": digest,
                "uri": f"fixture://{kind.lower()}",
                "kind": "decision",
                "reverification": "re-run the focused outcome observer test",
            }
        ],
        "status": "canonical",
        "confidence": 1.0,
        "valid_from": OBSERVED_AT,
        "valid_until": None,
        "falsifier": None,
        "coordinates": {"domain": ["paeos"]},
    }


def _event(
    *,
    event_id: str = "pytest-run-42",
    event_type: str = "test_run",
    status: str = "passed",
    summary: str = "The focused verification suite passed.",
    tradeoff_ids: list[str] | None = None,
) -> dict[str, object]:
    evidence_hash = hashlib.sha256(
        f"{event_id}:{event_type}:{status}:{summary}".encode()
    ).hexdigest()
    return {
        "event_id": event_id,
        "event_type": event_type,
        "decision_id": DECISION_ID,
        "tradeoff_ids": [] if tradeoff_ids is None else tradeoff_ids,
        "status": status,
        "observed_at": OBSERVED_AT,
        "summary": summary,
        "evidence": {
            "hash": evidence_hash,
            "uri": f"receipt://{event_id}/{status}",
            "kind": "test" if event_type == "test_run" else "report",
            "reverification": "re-run the bound verification command",
        },
    }


def _seed(store: GraphStore, *, tradeoff: bool = False) -> None:
    store.append_node(_graph_node("Decision", DECISION_ID))
    if tradeoff:
        store.append_node(_graph_node("TradeOff", TRADEOFF_ID))


def test_passed_test_run_becomes_verified_outcome_with_causal_link(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "sakg.db", NAMESPACE) as store:
        _seed(store)
        result = OutcomeObserver(store).observe(_event())
        outcome = store.get_node(result.node_id)
        edge = store.edges("causal")[0]

    assert result.state is OutcomeState.VERIFIED
    assert result.nodes_appended == 1
    assert outcome is not None
    assert outcome["type"] == "Outcome"
    assert outcome["status"] == "candidate"
    assert outcome["facets"]["state"]["value"] == "VERIFIED"
    assert outcome["evidence"][0]["uri"] == "receipt://pytest-run-42/passed"
    assert edge["source"] == DECISION_ID
    assert edge["target"] == result.node_id
    assert (edge["family"], edge["relation"]) == ("causal", "outcome")
    assert edge["properties"]["typed_relation"] == "causal:outcome"


def test_identity_is_deterministic_and_reobservation_is_idempotent(tmp_path: Path) -> None:
    snapshots: list[tuple[str, tuple[dict[str, object], ...], tuple[dict[str, object], ...]]] = []
    for name in ("first.db", "second.db"):
        with GraphStore(tmp_path / name, NAMESPACE) as store:
            _seed(store)
            first = OutcomeObserver(store).observe(_event())
            second = OutcomeObserver(store).observe(_event())
            assert second.nodes_appended == 0
            assert second.nodes_replayed == 1
            assert second.edges_appended == 0
            assert second.edges_replayed == 1
            snapshots.append((first.node_id, store.nodes(), store.edges()))

    assert snapshots[0] == snapshots[1]
    assert snapshots[0][0].startswith(f"sakg://{NAMESPACE}/Outcome/")


def test_scar_falsifies_belief_and_links_decision_and_tradeoff(tmp_path: Path) -> None:
    event = _event(
        event_id="scar-0007",
        event_type="scar",
        status="recorded",
        summary="A repeated timeout invalidated the latency assumption.",
        tradeoff_ids=[TRADEOFF_ID],
    )
    with GraphStore(tmp_path / "sakg.db", NAMESPACE) as store:
        _seed(store, tradeoff=True)
        result = OutcomeObserver(store).observe(event)
        outcome = store.get_node(result.node_id)
        revision_edges = [edge for edge in store.edges("similarity")]

    assert result.state is OutcomeState.FALSIFIED
    assert outcome is not None
    assert outcome["facets"]["belief_revision"]["value"] is True
    assert {edge["target"] for edge in revision_edges} == {DECISION_ID, TRADEOFF_ID}
    assert all(edge["source"] == result.node_id for edge in revision_edges)
    assert all(edge["relation"] == "revises" for edge in revision_edges)
    assert all(
        edge["properties"]["typed_relation"] == "epistemic:revises"
        for edge in revision_edges
    )


def test_observed_verified_and_remanded_states_are_append_only_snapshots(tmp_path: Path) -> None:
    observed = _event(event_id="run-7", status="running", summary="Verification started.")
    verified = _event(event_id="run-7", status="passed", summary="Verification passed.")
    remanded = _event(
        event_id="run-7",
        event_type="court_remand",
        status="remanded",
        summary="Court mutation evidence did not reproduce.",
    )
    with GraphStore(tmp_path / "sakg.db", NAMESPACE) as store:
        _seed(store)
        observer = OutcomeObserver(store)
        results = [observer.observe(record) for record in (observed, verified, remanded)]
        outcomes = store.query_nodes("Outcome")

    assert [result.state for result in results] == [
        OutcomeState.OBSERVED,
        OutcomeState.VERIFIED,
        OutcomeState.FALSIFIED,
    ]
    assert len({result.node_id for result in results}) == 3
    assert len(outcomes) == 3
    assert all(node["status"] == "candidate" for node in outcomes)


def test_scars_db_rows_are_extracted_as_falsified_outcomes(tmp_path: Path) -> None:
    scars_db = tmp_path / "state" / "scars.db"
    scars_db.parent.mkdir()
    connection = sqlite3.connect(scars_db)
    connection.execute(
        "CREATE TABLE scars (seq INTEGER PRIMARY KEY, id TEXT, signature TEXT, "
        "lesson TEXT, detection TEXT, severity TEXT)"
    )
    connection.execute(
        "INSERT INTO scars VALUES (?, ?, ?, ?, ?, ?)",
        (
            1,
            "scar-0001",
            '["domain:sakg","kind:court-remand"]',
            "Do not accept vacuous verification.",
            "Mutation command unexpectedly passes.",
            "high",
        ),
    )
    connection.commit()
    connection.close()

    with GraphStore(tmp_path / "sakg.db", NAMESPACE) as store:
        _seed(store)
        results = OutcomeObserver(store).observe_scars_db(
            scars_db,
            decision_bindings={"scar-0001": DECISION_ID},
            observed_at=OBSERVED_AT,
        )
        outcome = store.get_node(results[0].node_id)

    assert len(results) == 1
    assert results[0].state is OutcomeState.FALSIFIED
    assert outcome is not None
    assert outcome["facets"]["runtime_event"]["type"] == "scar"
    assert outcome["facets"]["scar"]["severity"] == "high"


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ({"decision_id": f"sakg://{NAMESPACE}/Decision/{'9':0>26}"}, OutcomeBindingError),
        ({"tradeoff_ids": [DECISION_ID]}, OutcomeBindingError),
        ({"evidence": {"hash": "not-a-hash"}}, MalformedOutcomeRecord),
        ({"status": "unknowable"}, MalformedOutcomeRecord),
    ],
)
def test_invalid_or_unbound_records_fail_before_writing(
    tmp_path: Path,
    mutation: dict[str, object],
    error: type[Exception],
) -> None:
    with GraphStore(tmp_path / "sakg.db", NAMESPACE) as store:
        _seed(store)
        record = _event()
        record.update(mutation)
        before = (store.nodes(), store.edges())
        with pytest.raises(error):
            OutcomeObserver(store).observe(record)
        assert (store.nodes(), store.edges()) == before


def test_backward_state_transition_fails_without_partial_snapshot(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "sakg.db", NAMESPACE) as store:
        _seed(store)
        observer = OutcomeObserver(store)
        observer.observe(_event(event_id="run-9", status="passed"))
        before = (store.nodes(), store.edges())
        with pytest.raises(OutcomeTransitionError):
            observer.observe(_event(event_id="run-9", status="running"))
        assert (store.nodes(), store.edges()) == before
