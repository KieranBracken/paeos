"""Standing canary calibration — a live FR-2/FR-3 tripwire (PAEOS-7 §5.3, PAEOS-8 §12 Phase 2).

B0.14 built the canary *scaffold* (`kernel/canary.py`): the format, the loader, and a harness that
submits a canary to an injected detector. B1.E wired the seed canary to the real Court **in the test
suite only**. This module makes calibration **standing**: it wires the canaries in
`constitution/canaries/` to the **live Court** and reports catch/miss, so a detector regression is
an alarm outside of CI.

A **canary** is a deliberately-planted known-bad artifact; a correct detector must catch it. A
**miss** (a `CAUGHT`-expected canary the detector does not catch) means the detector is
miscalibrated — the FR-2/FR-3 tripwire: no sealing may proceed until a human clears it (§5.3). The
`self-host` driver runs calibration **before** any backlog work; a miss **quarantines** — it refuses
to run and exits non-zero, so a blunted Court can never seal.

Only the `forged-evidence` category is exercised (the sole planted category, CANARY-0001). Any other
category returns *not caught* → a MISS → an alarm, which is fail-safe: a planted canary the harness
cannot exercise is itself a miscalibration, forcing `court_detector` to be extended before it lands.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kernel.canary import Canary, CanaryResult, load_canaries, run_calibration
from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.ledger import JsonValue
from kernel.types import Claim, Role

from runtime.court import Court, VerdictOutcome

__all__ = [
    "CANARY_DIR_DEFAULT",
    "CalibrationReport",
    "calibrate",
    "court_detector",
]

CANARY_DIR_DEFAULT = Path("constitution/canaries")
_FORGED_EVIDENCE = "forged-evidence"
# A placeholder artifact hash: the Court reproduces the canary's *command*, not any artifact bytes.
_CANARY_ART = "a" * 64


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """The outcome of a standing calibration run over a canary set."""

    results: tuple[CanaryResult, ...]

    @property
    def passed(self) -> bool:
        """All canaries behaved correctly AND at least one canary ran (an empty tripwire is an
        alarm: a standing tripwire must never be silently disabled)."""
        return len(self.results) > 0 and all(r.passed for r in self.results)

    @property
    def misses(self) -> tuple[CanaryResult, ...]:
        """The canaries the detector mishandled — the alarms."""
        return tuple(r for r in self.results if not r.passed)


def court_detector(canary: Canary) -> bool:
    """A live detector: reconstruct the canary's known-bad artifact and run it through a real
    `Court` (which re-runs the command in the DEBT-0005 sandbox). Caught iff the court REMANDS."""
    if canary.category != _FORGED_EVIDENCE:
        return False  # fail-safe: an un-exercisable planted canary is a miss (alarm)
    command = canary.artifact.get("reproducible_command")
    claimed = canary.artifact.get("claimed_result")
    if not isinstance(command, str) or not isinstance(claimed, Mapping):
        return False
    court = Court()
    evidence = _forged_evidence(command, {str(k): v for k, v in claimed.items()})
    court.submit_evidence(evidence)
    claim = Claim(id="c", statement="works", evidence_refs=(evidence.hash,))
    return court.adjudicate(_CANARY_ART, [claim]).outcome is VerdictOutcome.REMAND


def calibrate(canary_dir: str | Path = CANARY_DIR_DEFAULT) -> CalibrationReport:
    """Run the standing calibration: every canary in `canary_dir` against the live Court."""
    canaries = load_canaries(canary_dir)
    results = run_calibration(canaries, court_detector)
    return CalibrationReport(tuple(results))


def _forged_evidence(command: str, result: dict[str, JsonValue]) -> Evidence:
    """Rebuild the canary's forged deterministic evidence (the artifact the Court must reject)."""
    return Evidence(
        hash=content_hash(f"canary:{command}".encode()),
        kind=EvidenceKind.TEST,
        claim_id="c",
        artifact_hash=_CANARY_ART,
        environment_hash="v" * 64,
        reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session="canary"),
        determinism=Determinism.DETERMINISTIC,
        result=result,
        attestation="canary",
    )
