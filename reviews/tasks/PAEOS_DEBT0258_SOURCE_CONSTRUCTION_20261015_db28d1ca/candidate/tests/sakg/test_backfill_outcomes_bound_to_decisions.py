"""Decision binding and append-only store integration."""

from __future__ import annotations

from pathlib import Path

from sakg.backfill import backfill_outcomes
from sakg.store import GraphStore

ROOT = Path(__file__).resolve().parents[2]
DEBT = ROOT / "ledger/debt/DEBT-0062.md"
DECISION = "sakg://paeos-recovery/Decision/01J00000000000000000000F01"


def _decision() -> dict[str, object]:
    return {
        "id": DECISION,
        "type": "Decision",
        "namespace": "paeos-recovery",
        "facets": {"fixture": {"value": True}},
        "label": "Decision",
        "summary": "Fixture Decision",
        "provenance": {
            "origin": {"system": "fixture", "run_id": "r"},
            "author_kind": "human",
            "ingested_at": "2026-09-02T00:00:00Z",
            "source_hash": "0" * 64,
        },
        "evidence": [
            {
                "hash": "0" * 64,
                "uri": "fixture://decision",
                "kind": "decision",
                "reverification": "re-read",
            }
        ],
        "status": "canonical",
        "confidence": 1.0,
        "valid_from": "2026-09-02T00:00:00Z",
        "valid_until": None,
        "falsifier": None,
        "coordinates": {},
    }


def test_every_backfilled_outcome_is_bound_to_an_existing_decision() -> None:
    with GraphStore(":memory:", "paeos-recovery") as store:
        store.append_node(_decision())
        result = backfill_outcomes(
            (DEBT,), namespace="paeos-recovery", run_id="bound-test", store=store
        )
        assert len(result.nodes) == 1
        assert len(store.edges()) == 1
        edge = store.edges()[0]
        assert edge["source"] == DECISION
        assert edge["target"] == result.nodes[0]["id"]
        assert store.get_node(edge["target"]) is not None


def test_reread_is_idempotent() -> None:
    with GraphStore(":memory:", "paeos-recovery") as store:
        store.append_node(_decision())
        first = backfill_outcomes(
            (DEBT,), namespace="paeos-recovery", run_id="bound-test", store=store
        )
        second = backfill_outcomes(
            (DEBT,), namespace="paeos-recovery", run_id="bound-test", store=store
        )
        assert first.nodes == second.nodes
        assert len(store.nodes()) == 2
        assert len(store.edges()) == 1
