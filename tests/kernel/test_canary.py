"""B0.14 acceptance tests for the canary scaffold (PAEOS-8 §10 / PAEOS-7 §5.3).

The canary format loads; the harness submits the seed canary to a detector and records catch/miss.
A correct detector (kernel re-run) catches CANARY-0001 (forged evidence); a blind detector misses
it, and the harness records that MISS.
"""

from __future__ import annotations

from pathlib import Path

from kernel.canary import (
    Canary,
    load_canaries,
    run_calibration,
    run_canary,
)
from kernel.evidence import (
    Determinism,
    Evidence,
    EvidenceKind,
    EvidenceProducer,
    ReproductionMismatch,
    verify_deterministic,
)
from kernel.types import Role

_CANARY_DIR = Path(__file__).resolve().parents[2] / "constitution" / "canaries"
_ART = "a" * 64


def _forged_evidence_detector(canary: Canary) -> bool:
    """Phase-0 detector stub: rebuild the Evidence the canary describes and run it through the
    kernel's deterministic check. Returns True iff the forgery is caught (ReproductionMismatch)."""
    art = canary.artifact
    command = art["reproducible_command"]
    result = art["claimed_result"]
    assert isinstance(command, str)
    evidence = Evidence(
        hash="c" * 64,
        kind=EvidenceKind.TEST,
        claim_id="canary",
        artifact_hash=_ART,
        environment_hash="e" * 64,
        reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session="canary"),
        determinism=Determinism.DETERMINISTIC,
        result=result,
        attestation="sig",
    )
    try:
        verify_deterministic(evidence, _ART)
    except ReproductionMismatch:
        return True  # caught the forgery
    return False


def _blind_detector(_canary: Canary) -> bool:
    return False  # a miscalibrated detector that catches nothing


# ---- format loads ----------------------------------------------------------


def test_seed_canary_loads_with_expected_fields() -> None:
    canaries = load_canaries(_CANARY_DIR)
    assert [c.id for c in canaries] == ["CANARY-0001"]
    seed = canaries[0]
    assert seed.category == "forged-evidence"
    assert seed.expected == "CAUGHT"
    assert seed.detection_signature
    assert seed.artifact["reproducible_command"] == "echo real"


# ---- harness records catch/miss (B0.14 acceptance) ------------------------


def test_correct_detector_catches_the_seed_canary() -> None:
    seed = load_canaries(_CANARY_DIR)[0]
    result = run_canary(seed, _forged_evidence_detector)
    assert result.caught is True
    assert result.passed is True  # caught, as expected
    assert result.canary_id == "CANARY-0001"


def test_blind_detector_misses_and_harness_records_it() -> None:
    seed = load_canaries(_CANARY_DIR)[0]
    result = run_canary(seed, _blind_detector)
    assert result.caught is False
    assert result.passed is False  # a MISS — calibration alarm
    assert "MISS" in result.detail


def test_calibration_runs_over_all_canaries() -> None:
    canaries = load_canaries(_CANARY_DIR)
    results = run_calibration(canaries, _forged_evidence_detector)
    assert len(results) == len(canaries)
    assert all(r.passed for r in results)  # every seed canary is caught by the correct detector
