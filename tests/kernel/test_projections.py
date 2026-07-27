"""B0.10 acceptance tests for projections + replay (PAEOS-8 §10 / §6).

Covers: deterministic byte-identical replay (incl. the 1k-event corpus), verify_against_head on
a fresh projection, and detection of a STALE projection (head moved) and a POISONED projection
(state tampered, T7) before use.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest
from kernel.ledger import Event, InMemoryLedgerStore, Ledger, LedgerRow
from kernel.projections import (
    PoisonedProjection,
    Projection,
    StaleProjection,
    replay,
    verify_against_head,
)


class GoalStages:
    """A concrete projector: folds `advance` events into {goal_id: stage}."""

    def initial(self) -> dict[str, str]:
        return {}

    def fold(self, state: dict[str, str], row: LedgerRow) -> dict[str, str]:
        if row.event.kind != "advance":
            return state
        goal = row.event.payload["goal"]
        stage = row.event.payload["stage"]
        assert isinstance(goal, str) and isinstance(stage, str)
        return {**state, goal: stage}

    def digest(self, state: dict[str, str]) -> str:
        blob = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(blob.encode("ascii")).hexdigest()


def _ledger_with(n_goals: int = 3, advances_per_goal: int = 2) -> Ledger:
    ledger = Ledger(InMemoryLedgerStore())
    for step in range(advances_per_goal):
        for g in range(n_goals):
            ledger.append(Event(1, "advance", {"goal": f"g{g}", "stage": f"stage{step}"}))
    return ledger


# ---- deterministic replay -------------------------------------------------


def test_replay_rebuilds_state() -> None:
    ledger = _ledger_with()
    proj = replay(ledger, GoalStages())
    assert proj.state == {"g0": "stage1", "g1": "stage1", "g2": "stage1"}
    assert proj.head_hash == ledger.head_hash()


def test_replay_is_byte_identical_across_runs() -> None:
    ledger = _ledger_with()
    a = replay(ledger, GoalStages())
    b = replay(ledger, GoalStages())
    assert a == b  # same state, head_hash, and digest
    assert a.state_digest == b.state_digest


def test_empty_ledger_projects_empty_state() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    proj = replay(ledger, GoalStages())
    assert proj.state == {}
    verify_against_head(ledger, GoalStages(), proj)  # trivially valid


# ---- the 1k-event corpus (byte-identical state + head) --------------------


def test_thousand_event_replay_is_deterministic() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    for i in range(1000):
        ledger.append(Event(1, "advance", {"goal": f"g{i % 50}", "stage": f"s{i}"}))
    first = replay(ledger, GoalStages())
    second = replay(ledger, GoalStages())
    assert first.state_digest == second.state_digest  # byte-identical state
    assert first.head_hash == second.head_hash == ledger.head_hash()
    assert len(first.state) == 50  # 50 distinct goals, each at its last stage
    verify_against_head(ledger, GoalStages(), first)  # fresh projection verifies


# ---- verify_against_head: stale + poisoned (T7) ---------------------------


def test_fresh_projection_verifies() -> None:
    ledger = _ledger_with()
    verify_against_head(ledger, GoalStages(), replay(ledger, GoalStages()))  # no raise


def test_stale_projection_is_detected() -> None:
    ledger = _ledger_with()
    proj = replay(ledger, GoalStages())
    ledger.append(Event(1, "advance", {"goal": "g0", "stage": "stage9"}))  # ledger advances
    with pytest.raises(StaleProjection):
        verify_against_head(ledger, GoalStages(), proj)


def test_poisoned_state_is_detected() -> None:
    ledger = _ledger_with()
    proj = replay(ledger, GoalStages())
    poisoned = replace(proj, state={**proj.state, "g0": "TAMPERED"})
    with pytest.raises(PoisonedProjection):
        verify_against_head(ledger, GoalStages(), poisoned)


def test_poison_hidden_behind_a_matching_digest_field_is_still_caught() -> None:
    # An attacker tampers the state AND updates the cached digest field to match. verify recomputes
    # the digest from the state against the ledger, so it is still caught.
    ledger = _ledger_with()
    proj = replay(ledger, GoalStages())
    bad_state = {**proj.state, "g0": "TAMPERED"}
    forged = Projection(
        state=bad_state,
        head_hash=proj.head_hash,
        state_digest=GoalStages().digest(bad_state),  # internally consistent, but not the truth
    )
    with pytest.raises(PoisonedProjection):
        verify_against_head(ledger, GoalStages(), forged)
