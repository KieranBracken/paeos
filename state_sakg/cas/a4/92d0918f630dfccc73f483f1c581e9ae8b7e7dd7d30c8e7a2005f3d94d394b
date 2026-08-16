"""B1.F acceptance tests for the scar store (PAEOS-8 §10 / FR-6 / §7.1).

A written scar is auto-injected on a matching goal at the injection stages; a broad-signature scar
is quarantined (Adversary T3 poison).
"""

from __future__ import annotations

import pytest
from kernel.types import StageId
from runtime.memory import ScarDraft, ScarQuarantined, ScarStore


def _draft(*tags: str, lesson: str = "do not repeat") -> ScarDraft:
    return ScarDraft(signature=frozenset(tags), lesson=lesson, detection="sig")


# ---- propose + match ------------------------------------------------------


def test_written_scar_is_injected_on_a_matching_goal() -> None:
    store = ScarStore()
    scar = store.propose_scar(_draft("stage:DESIGN", "domain:kernel"))
    # a goal whose signature is a superset of the scar's conditions matches
    matched = store.match_scars("stage:DESIGN,domain:kernel,goal:g1")
    assert [s.id for s in matched] == [scar.id]
    assert store.get_precedent(scar.id) == scar


def test_scar_does_not_match_a_goal_missing_a_condition() -> None:
    store = ScarStore()
    store.propose_scar(_draft("stage:DESIGN", "domain:kernel"))
    assert store.match_scars("stage:DESIGN,domain:runtime") == []  # domain:kernel not present


def test_injection_only_at_injection_stages() -> None:
    store = ScarStore()
    store.propose_scar(_draft("stage:VERIFY", "kind:flaky"))
    sig = "stage:VERIFY,kind:flaky,goal:g"
    assert len(store.injected_scars(signature=sig, stage=StageId.VERIFY)) == 1  # 11 = injection
    assert store.injected_scars(signature=sig, stage=StageId.SEAL) == []  # not an injection stage
    assert len(store.injected_scars(signature=sig, stage=StageId.RE_DERIVE)) == 1  # 0 = injection
    assert len(store.injected_scars(signature=sig, stage=StageId.DESIGN)) == 1  # 7
    assert len(store.injected_scars(signature=sig, stage=StageId.CRITIQUE)) == 1  # 8


# ---- Adversary T3: broad-signature poison quarantined ---------------------


def test_empty_signature_scar_is_quarantined() -> None:
    store = ScarStore()
    with pytest.raises(ScarQuarantined):
        store.propose_scar(_draft())  # matches every goal → poison


def test_single_condition_scar_is_quarantined() -> None:
    store = ScarStore()
    with pytest.raises(ScarQuarantined):
        store.propose_scar(_draft("stage:DESIGN"))  # too broad (< 2 conditions)


def test_quarantined_scar_is_never_stored_or_injected() -> None:
    store = ScarStore()
    with pytest.raises(ScarQuarantined):
        store.propose_scar(_draft("common"))
    # nothing was stored, so nothing injects broadly
    assert store.injected_scars(signature="common,anything", stage=StageId.DESIGN) == []


def test_specific_scars_coexist_and_match_precisely() -> None:
    store = ScarStore()
    a = store.propose_scar(_draft("stage:VERIFY", "kind:forged-evidence"))
    b = store.propose_scar(_draft("stage:DESIGN", "domain:kernel"))
    assert {s.id for s in store.match_scars("stage:VERIFY,kind:forged-evidence,x:1")} == {a.id}
    assert {s.id for s in store.match_scars("stage:DESIGN,domain:kernel,x:1")} == {b.id}
    assert store.match_scars("stage:PLAN,domain:docs") == []  # neither applies
