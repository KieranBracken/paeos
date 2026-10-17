from __future__ import annotations

from types import SimpleNamespace

import pytest
from kernel.cas import CAS, InMemoryCasStore
from kernel.lifecycle import is_legal
from kernel.types import Outcome, StageId, WeightClass
from runtime.agents import role_spec
from runtime.retrospective import (
    CER_RETROSPECTIVE_QUESTIONS,
    RetrospectiveEngine,
    RetrospectiveTransitionRejected,
)


def _outcome(status: str = "REMANDED") -> object:
    return SimpleNamespace(
        status=SimpleNamespace(value=status),
        goal_id="g-1",
        detail="court rejected evidence",
    )


def test_failure_report_answers_all_cer_questions_and_drafts_narrow_scar() -> None:
    report = RetrospectiveEngine(CAS(InMemoryCasStore())).build_report(
        _outcome(), run_id="r-1", objective="exercise", goal_signature="domain:runtime"
    )
    assert len(report.answers) == 6 == len(CER_RETROSPECTIVE_QUESTIONS)
    assert all(answer for answer in report.answers)
    assert len(report.scar_drafts) == 1
    assert len(report.scar_drafts[0].signature) >= 2
    assert report.scar_drafts[0].severity == "high"


def test_sealed_report_emits_cas_artifact_without_scar() -> None:
    cas = CAS(InMemoryCasStore())
    report = RetrospectiveEngine(cas).build_report(_outcome("SEALED"), run_id="r-1", objective="ok")
    artifact = RetrospectiveEngine(cas).emit_report(report)
    assert cas.get(artifact) == report.canonical_bytes()
    assert report.scar_drafts == ()


def test_retrospective_auditor_scope_is_exact() -> None:
    spec = role_spec(StageId.RETROSPECT)
    assert spec.write_scopes == ("retrospective/",)
    assert "retrospective" in spec.objective.lower()


def test_frozen_kernel_requires_canonical_evolve_hop() -> None:
    for weight in WeightClass:
        assert is_legal(StageId.SEAL, StageId.RETROSPECT, weight)
        assert is_legal(StageId.RETROSPECT, StageId.MEMORY_UPDATE, weight)
        assert is_legal(StageId.MEMORY_UPDATE, StageId.EVOLVE, weight)
        assert not is_legal(StageId.RETROSPECT, StageId.EVOLVE, weight)


def test_rejected_gate_is_not_silently_accepted() -> None:
    class RejectingGate:
        def propose_transition(self, *_args: object, **_kwargs: object) -> object:
            return SimpleNamespace(outcome=Outcome.REJECT, reason="denied")

    cas = CAS(InMemoryCasStore())
    report = RetrospectiveEngine(cas).build_report(_outcome("SEALED"), run_id="r-1", objective="ok")
    evidence_hash = cas.put(report.canonical_bytes())
    request = SimpleNamespace()
    with pytest.raises(RetrospectiveTransitionRejected, match="denied"):
        RetrospectiveEngine(cas).route_transition(
            RejectingGate(),
            request,
            weight_class=WeightClass.ROUTINE,
            current_seq=1,
            artifact_hash=evidence_hash,
        )
