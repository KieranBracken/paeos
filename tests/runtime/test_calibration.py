"""B2.D tests for standing canary calibration (PAEOS-7 §5.3, PAEOS-8 §12 Phase 2).

The live Court catches the planted forged-evidence canary; an un-exercisable canary MISSES
(fail-safe alarm); an empty canary set is itself an alarm (the tripwire must never be silent).
`paeos calibrate` exits 0 when calibrated. Reproduction runs in the DEBT-0005 sandbox.
"""

from __future__ import annotations

from pathlib import Path

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
