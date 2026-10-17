"""Acceptance tests for the canonical v1.3-derived transition oracle.

Enumerates all 21x21 StageId pairs across all 3 weight classes and checks is_legal against an
*independent* transcription of the Founder-selected lifecycle projection (so the module cannot
silently drift from the canonical prose). Also pins illegal edges and Trace-A compression.
"""

from __future__ import annotations

import itertools

from kernel.lifecycle import FORWARD_EDGES, ROUTINE_FASTPATH_EDGES, is_legal
from kernel.types import StageId, WeightClass

# Independent transcription of the canonical v1.3 forward chain plus runtime controls.
# This is the test's own copy of the spec — if kernel.lifecycle drifts, this diverges.
_RATIFIED_CHAIN = [
    "RAW", "INTAKE", "TRIAGE", "RE_DERIVE", "IDEATE", "RESEARCH", "TRADEOFF", "MITIGATION",
    "DESIGN", "CRITIQUE", "ADVERSARIAL_REVIEW", "PLAN", "IMPLEMENT", "VERIFY", "LEDGER_SYNC",
    "SEAL", "RETROSPECT", "MEMORY_UPDATE", "EVOLVE", "IMPROVE_RUNTIME", "RESTART",
]

# Expected forward edges (all weight classes): consecutive pairs + RESTART→RE_DERIVE recovery.
_EXPECTED_FORWARD = {
    (StageId[a], StageId[b]) for a, b in itertools.pairwise(_RATIFIED_CHAIN)
} | {(StageId.RESTART, StageId.RE_DERIVE)}

# ROUTINE-only compression edge for Trace-A discharge.
_EXPECTED_ROUTINE_EXTRA = {
    (StageId.TRIAGE, StageId.IMPLEMENT),
}


def _expected_legal(a: StageId, b: StageId, wc: WeightClass) -> bool:
    if (a, b) in _EXPECTED_FORWARD:
        return True
    return wc is WeightClass.ROUTINE and (a, b) in _EXPECTED_ROUTINE_EXTRA


# ---- the edge sets match the ratified table -------------------------------


def test_forward_edge_set_matches_ratified_table() -> None:
    assert FORWARD_EDGES == _EXPECTED_FORWARD
    assert len(FORWARD_EDGES) == 21  # 20 chain edges + RESTART→RE_DERIVE cycle
    assert ROUTINE_FASTPATH_EDGES == _EXPECTED_ROUTINE_EXTRA


# ---- the exhaustive 21x21 x 3 enumeration (B0.5 acceptance) ----------------


def test_all_pairs_all_weight_classes() -> None:
    stages = list(StageId)
    assert len(stages) == 21
    checked = 0
    for wc in WeightClass:
        for a, b in itertools.product(stages, stages):
            assert is_legal(a, b, wc) == _expected_legal(a, b, wc), (a, b, wc)
            checked += 1
    assert checked == 21 * 21 * 3  # 1323 combinations, every one verified


# ---- targeted properties --------------------------------------------------


def test_a_representative_illegal_edge_is_false() -> None:
    # RAW → SEAL skips the entire lifecycle: illegal for every weight class.
    for wc in WeightClass:
        assert is_legal(StageId.RAW, StageId.SEAL, wc) is False
    # self-loops are never legal
    assert is_legal(StageId.IMPLEMENT, StageId.IMPLEMENT, WeightClass.ROUTINE) is False


def test_full_forward_chain_is_legal_for_every_weight_class() -> None:
    chain = [StageId[name] for name in _RATIFIED_CHAIN]
    for wc in WeightClass:
        for a, b in itertools.pairwise(chain):
            assert is_legal(a, b, wc) is True
        assert is_legal(StageId.RESTART, StageId.RE_DERIVE, wc) is True


def test_fast_path_differs_by_weight_class() -> None:
    # ROUTINE admits the compression edge; the heavier classes do not.
    for edge in (
        (StageId.TRIAGE, StageId.IMPLEMENT),
    ):
        assert is_legal(*edge, WeightClass.ROUTINE) is True
        assert is_legal(*edge, WeightClass.SUBSTANTIAL) is False
        assert is_legal(*edge, WeightClass.KERNEL_TOUCHING) is False


def test_kernel_touching_must_traverse_intake_and_triage() -> None:
    # KERNEL_TOUCHING follows canonical L01 Intake → L02 Triage → L03 Re-Derivation.
    assert is_legal(StageId.RAW, StageId.INTAKE, WeightClass.KERNEL_TOUCHING) is True
    assert is_legal(StageId.INTAKE, StageId.TRIAGE, WeightClass.KERNEL_TOUCHING) is True
    assert is_legal(StageId.TRIAGE, StageId.RE_DERIVE, WeightClass.KERNEL_TOUCHING) is True


def test_reverse_edges_are_illegal() -> None:
    # is_legal governs forward edges only; a backward (remand-shaped) edge is not legal here
    # (remand is kernel failure-routing, PAEOS-IP-0003 Part A), so e.g. VERIFY→DESIGN is False.
    assert is_legal(StageId.VERIFY, StageId.DESIGN, WeightClass.KERNEL_TOUCHING) is False
    assert is_legal(StageId.SEAL, StageId.PLAN, WeightClass.ROUTINE) is False
