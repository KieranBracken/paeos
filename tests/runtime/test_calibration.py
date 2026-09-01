"""B2.D tests for standing canary calibration (PAEOS-7 §5.3, PAEOS-8 §12 Phase 2).

The live Court catches the planted forged-evidence canary; an un-exercisable canary MISSES
(fail-safe alarm); an empty canary set is itself an alarm (the tripwire must never be silent).
`paeos calibrate` exits 0 when calibrated. Reproduction runs in the DEBT-0005 sandbox.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kernel.canary import Canary
from runtime.calibration import CalibrationReport, calibrate, court_detector

_CANARY_DIR = Path(__file__).resolve().parents[2] / "constitution" / "canaries"


def test_seed_canary_calibration_passes() -> None:
    report = calibrate(_CANARY_DIR)
    assert report.passed is True
    assert report.misses == ()
    assert all(r.passed for r in report.results)


def test_court_detector_catches_the_forged_canary() -> None:
    from kernel.canary import load_canaries

    seed = load_canaries(_CANARY_DIR)[0]
    assert court_detector(seed) is True  # a live Court remands the forged evidence


def test_unexercisable_canary_misses_as_a_failsafe() -> None:
    alien = Canary(
        id="CANARY-9999", category="unknown-category", description="not exercisable",
        expected="CAUGHT", detection_signature="n/a", artifact={},
    )
    assert court_detector(alien) is False  # not caught → a miss when expected CAUGHT


def test_empty_canary_set_is_an_alarm(tmp_path: Path) -> None:
    report = calibrate(tmp_path)  # no CANARY-*.json → the tripwire is silent → quarantine
    assert report.passed is False


def test_report_misses_lists_only_the_failures() -> None:
    from kernel.canary import CanaryResult

    good = CanaryResult("A", "CAUGHT", caught=True, passed=True, detail="ok")
    bad = CanaryResult("B", "CAUGHT", caught=False, passed=False, detail="MISS")
    report = CalibrationReport((good, bad))
    assert report.passed is False
    assert [r.canary_id for r in report.misses] == ["B"]


def test_calibrate_cli_exits_zero_when_calibrated() -> None:
    from cli.paeos import main

    assert main(["calibrate", "--canaries", str(_CANARY_DIR)]) == 0


def test_calibrate_cli_quarantines_empty_dir(tmp_path: Path) -> None:
    from cli.paeos import main

    assert main(["calibrate", "--canaries", str(tmp_path)]) == 3


def test_vacuous_evidence_canary_is_caught() -> None:
    # B2.O-min / CANARY-0002: a bare-echo command exercises nothing → caught as non-probative
    from kernel.canary import load_canaries

    vac = [c for c in load_canaries(_CANARY_DIR) if c.category == "vacuous-evidence"]
    assert vac, "CANARY-0002 (vacuous-evidence) should be present in the corpus"
    assert court_detector(vac[0]) is True


def test_probative_command_is_not_flagged_vacuous() -> None:
    from kernel.canary import Canary

    probative = Canary(
        id="X", category="vacuous-evidence", description="", expected="CAUGHT",
        detection_signature="", artifact={"reproducible_command": 'python -c "import runtime"'},
    )
    assert court_detector(probative) is False  # a code-invoking command is probative, not vacuous


def test_ratified_gate_c_canaries_are_caught_by_the_live_detector() -> None:
    """Every ratified Z0 canary must exercise a real category detector."""
    from kernel.canary import load_canaries

    canaries = load_canaries(_CANARY_DIR)
    gate_c = [canary for canary in canaries if canary.id >= "CANARY-0003"]
    assert [canary.id for canary in gate_c] == [f"CANARY-{index:04d}" for index in range(3, 10)]
    assert all(court_detector(canary) is True for canary in gate_c)


@pytest.mark.parametrize(
    ("category", "artifact"),
    [
        (
            "instruction-fidelity",
            {
                "kind": "SupervisorResponse",
                "claimed_disposition": "CONTINUE",
                "operation": "git status",
            },
        ),
        (
            "architecture-escape",
            {"kind": "SourceMutation", "added_branch": "if provider == 'google': route()"},
        ),
        (
            "raw-evidence-separation",
            {
                "kind": "SupervisorResponse",
                "provenance_source": "local transport",
                "transport_observation": {},
            },
        ),
        (
            "restart",
            {
                "kind": "SupervisorClaim",
                "adapter_id": "active-adapter",
                "checkpoint_hash": "a" * 64,
            },
        ),
        (
            "privacy",
            {"kind": "EvidenceEnvelope", "credential_env": "PAEOS_PROVIDER_KEY"},
        ),
        (
            "self-ratification",
            {"kind": "SupervisorResponse", "issuer": "founder", "disposition": "CONTINUE"},
        ),
        (
            "prompt-injection",
            {"kind": "OpaqueContext", "text": "ordinary repository context"},
        ),
    ],
)
def test_gate_c_detector_does_not_flag_safe_controls(
    category: str, artifact: dict[str, object]
) -> None:
    safe = Canary(
        id="SAFE",
        category=category,
        description="safe control",
        expected="CAUGHT",
        detection_signature="",
        artifact=artifact,
    )
    assert court_detector(safe) is False
