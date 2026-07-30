"""B2.H tests — the Constitutional Knowledge Lifetime Ontology L0-L5 (PAEOS-IP-0006).

The runtime-side declaration registry classifies every concrete artifact type to its L-class and
enforces the promotion rule (L1->L3 only via Stage 17). Kernel L5/L4 types are classified here
without being mutated (adding fields there is an F2 HARD-LOOP amendment, out of scope for B2.H).
"""

from __future__ import annotations

import pytest
from kernel.types import StageId
from runtime.lifetime import ONTOLOGY, LifetimeClass, classify_type, may_promote


def test_concrete_runtime_and_kernel_types_are_classified() -> None:
    assert classify_type("ExecutionContext") is LifetimeClass.L1  # runtime, run-scoped
    assert classify_type("TaskPackage") is LifetimeClass.L2  # runtime projection
    assert classify_type("Scar") is LifetimeClass.L3  # institutional memory
    assert classify_type("AmendmentProposal") is LifetimeClass.L4  # constitutional knowledge
    assert classify_type("Evidence") is LifetimeClass.L5  # historical truth (kernel)
    assert classify_type("SealRecord") is LifetimeClass.L5


def test_unknown_type_is_a_conformance_gap_not_a_silent_default() -> None:
    with pytest.raises(KeyError):
        classify_type("SomeUnregisteredArtifact")


def test_ontology_declares_all_six_classes_with_ip0006_owners() -> None:
    assert set(ONTOLOGY) == set(LifetimeClass)
    assert ONTOLOGY[LifetimeClass.L1].owner == "Runtime"
    assert ONTOLOGY[LifetimeClass.L3].owner == "Evolution"
    assert ONTOLOGY[LifetimeClass.L4].owner == "Founder"
    assert ONTOLOGY[LifetimeClass.L5].owner == "Kernel"
    # only the derived projection class is rebuildable (IP-0006 §2)
    assert ONTOLOGY[LifetimeClass.L2].rebuildable is True
    assert ONTOLOGY[LifetimeClass.L1].rebuildable is False


def test_l1_to_l3_promotion_is_permitted_only_at_stage_17() -> None:
    assert may_promote(LifetimeClass.L1, LifetimeClass.L3, via_stage=StageId.MEMORY_UPDATE) is True
    # wrong stage — the SoftLoop's own VERIFY stage may not promote an L1 note to an L3 scar
    assert may_promote(LifetimeClass.L1, LifetimeClass.L3, via_stage=StageId.VERIFY) is False
    assert may_promote(LifetimeClass.L1, LifetimeClass.L3, via_stage=StageId.IMPLEMENT) is False


def test_unsanctioned_promotions_are_denied_by_default() -> None:
    # no direct L1->L4 (execution state cannot become constitutional knowledge)
    assert may_promote(LifetimeClass.L1, LifetimeClass.L4, via_stage=StageId.MEMORY_UPDATE) is False
    # no L3->L5, no L0->L3, etc.
    assert may_promote(LifetimeClass.L3, LifetimeClass.L5, via_stage=StageId.SEAL) is False
    assert may_promote(LifetimeClass.L0, LifetimeClass.L3, via_stage=StageId.MEMORY_UPDATE) is False
