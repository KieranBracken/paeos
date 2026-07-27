"""B0.4 acceptance tests for core runtime types (PAEOS-7.6 §3-4).

Verifies the enums match 7.6 §3 exactly (all constants, no extras), illegal enum values are
rejected, and the §4 value contracts are frozen and correctly shaped. Also pins the
deliberate omission of `TransitionRequest` (blocked on PAEOS-IP-0002 / undefined EvidenceRef).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import kernel.types as types_module
import pytest
from kernel.types import (
    ArtifactRef,
    Claim,
    Outcome,
    Role,
    StageId,
    TransitionResult,
    ValidationClaim,
    WeightClass,
)

# ---- StageId: the 21 constants, verbatim from 7.6 §3 ----------------------

# Transcribed directly from PAEOS-7.6 §3, in spec order. This literal is the test's own
# independent copy of the spec — if the module drifts from 7.6, this diverges and fails.
_EXPECTED_STAGES = (
    "RAW", "RE_DERIVE", "INTAKE", "TRIAGE", "IDEATE", "RESEARCH",
    "TRADEOFF", "MITIGATION", "DESIGN", "CRITIQUE", "PLAN", "IMPLEMENT",
    "VERIFY", "ADVERSARIAL_REVIEW", "LEDGER_SYNC", "SEAL",
    "RETROSPECT", "EVOLVE", "MEMORY_UPDATE", "IMPROVE_RUNTIME", "RESTART",
)


def test_stageid_has_exactly_21_constants() -> None:
    assert len(StageId) == 21
    assert len(_EXPECTED_STAGES) == 21


def test_stageid_names_match_spec_exactly() -> None:
    assert tuple(s.name for s in StageId) == _EXPECTED_STAGES
    # value == name so the ledger/wire representation is the constant itself
    assert all(s.value == s.name for s in StageId)


def test_stageid_illegal_value_is_rejected() -> None:
    with pytest.raises(ValueError):
        StageId("NOT_A_STAGE")
    with pytest.raises(KeyError):
        StageId["NOT_A_STAGE"]


def test_stageid_lookup_round_trips() -> None:
    assert StageId("IMPLEMENT") is StageId.IMPLEMENT
    assert StageId["SEAL"] is StageId.SEAL


# ---- the other §3 enums ---------------------------------------------------


def test_role_matches_spec() -> None:
    assert tuple(r.name for r in Role) == (
        "PLANNER", "BUILDER", "CRITIC", "VERIFIER", "ADVERSARY", "DOC", "RATIFIER",
    )
    with pytest.raises(ValueError):
        Role("KERNEL")


def test_weightclass_matches_spec() -> None:
    assert tuple(w.name for w in WeightClass) == ("ROUTINE", "SUBSTANTIAL", "KERNEL_TOUCHING")


def test_outcome_matches_spec() -> None:
    assert tuple(o.name for o in Outcome) == (
        "COMMITTED", "REMAND", "REJECT", "QUARANTINE", "ABORT",
    )


# ---- §3-4 value contracts: shape + immutability ---------------------------


def test_artifact_ref_shape_and_frozen() -> None:
    ref = ArtifactRef(hash="a" * 64, type="plan")
    assert ref.hash == "a" * 64
    assert ref.type == "plan"
    with pytest.raises(FrozenInstanceError):
        ref.type = "design"  # type: ignore[misc]


def test_claim_shape_and_frozen() -> None:
    claim = Claim(id="builds", statement="exit 0", evidence_refs=("h1", "h2"))
    assert claim.id == "builds"
    assert claim.evidence_refs == ("h1", "h2")
    with pytest.raises(FrozenInstanceError):
        claim.statement = "changed"  # type: ignore[misc]


def test_validation_claim_composes_claims() -> None:
    claim = Claim(id="c", statement="s", evidence_refs=())
    vc = ValidationClaim(
        gate_id="G-Court",
        claims=(claim,),
        producer=Role.VERIFIER,
        produced_against="artifacthash",
    )
    assert vc.producer is Role.VERIFIER
    assert vc.claims[0] is claim
    with pytest.raises(FrozenInstanceError):
        vc.gate_id = "G-Other"  # type: ignore[misc]


def test_transition_result_committed_and_non_committed() -> None:
    committed = TransitionResult(
        outcome=Outcome.COMMITTED,
        committed_seq=42,
        remand_to=None,
        reason="",
        verdict_ref="v" * 64,
    )
    assert committed.outcome is Outcome.COMMITTED
    assert committed.committed_seq == 42

    remanded = TransitionResult(
        outcome=Outcome.REMAND,
        committed_seq=None,
        remand_to=StageId.PLAN,
        reason="missing evidence",
        verdict_ref=None,
    )
    assert remanded.remand_to is StageId.PLAN
    assert remanded.committed_seq is None
    with pytest.raises(FrozenInstanceError):
        remanded.reason = "x"  # type: ignore[misc]


# ---- deliberate omission: TransitionRequest (PAEOS-IP-0002) ----------------


def test_transition_request_is_deliberately_absent() -> None:
    # B0.4 halts TransitionRequest: its `evidence: EvidenceRef[]` field references a type
    # 7.6 uses but never defines. Held pending founder ratification of PAEOS-IP-0002 rather
    # than inventing EvidenceRef's shape (constitutional preamble / CER-6). This test makes
    # the omission explicit and intentional, not an oversight.
    assert not hasattr(types_module, "TransitionRequest")
    assert "TransitionRequest" not in types_module.__all__
