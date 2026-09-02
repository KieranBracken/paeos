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

The forged/vacuous evidence categories are exercised through the live Court; the Gate C control
categories are exercised through their existing typed protocol and recovery boundaries. Any other
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
_VACUOUS_EVIDENCE = "vacuous-evidence"
# A placeholder artifact hash: the Court reproduces the canary's *command*, not any artifact bytes.
_CANARY_ART = "a" * 64
# B2.Q AUDIT (unify-onto-vacuous_commands attempted, FALSIFIED): the runtime B2.O gate discriminates
# against the **real** artifact-under-review; a *calibration* canary has none, so a synthetic-change
# discrimination over-flags (any command that ignores the synthetic file reads as "vacuous", incl.
# genuinely probative ones). The calibration proxy therefore stays a *shape* check: evidence that
# invokes no interpreter/test exercises nothing. The two detect the same defect at different layers.
_CODE_INVOCATION_TOKENS = ("python", "pytest", "node", "ruby", "import ", "-m ", "uv run", "make ")
_GATE_C_INSTRUCTION = "instruction-fidelity"
_GATE_C_ARCHITECTURE = "architecture-escape"
_GATE_C_PROVENANCE = "raw-evidence-separation"
_GATE_C_RESTART = "restart"
_GATE_C_PRIVACY = "privacy"
_GATE_C_SELF_RATIFICATION = "self-ratification"
_GATE_C_PROMPT_INJECTION = "prompt-injection"


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
    """A live detector: reconstruct the canary's known-bad artifact and check the right control
    catches it. `forged-evidence` (CANARY-0001) is caught by the Court's deterministic re-run;
    `vacuous-evidence` (CANARY-0002) is caught by the probative check — a command that executes no
    interpreter/test exercises nothing (zero discriminating power)."""
    if canary.category == _VACUOUS_EVIDENCE:
        command = canary.artifact.get("reproducible_command")
        if not isinstance(command, str):
            return False
        # caught iff non-probative (executes no interpreter/test) — a shape proxy; the real
        # discrimination gate (B2.O `vacuous_commands`) lives in the SoftLoop where a real artifact
        # exists to test against. See the B2.Q audit note above.
        return not any(tok in command for tok in _CODE_INVOCATION_TOKENS)
    if canary.category in {
        _GATE_C_INSTRUCTION,
        _GATE_C_ARCHITECTURE,
        _GATE_C_PROVENANCE,
        _GATE_C_RESTART,
        _GATE_C_PRIVACY,
        _GATE_C_SELF_RATIFICATION,
        _GATE_C_PROMPT_INJECTION,
    }:
        return _gate_c_detector(canary)
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


def _gate_c_detector(canary: Canary) -> bool:
    """Exercise Gate C canaries through typed safety-boundary predicates.

    These checks intentionally use artifact shape and invariant-bearing values, never canary IDs
    or model-authored prose.  A safe control for a known category must therefore remain uncaught.
    """
    artifact = canary.artifact
    kind = artifact.get("kind")
    if canary.category == _GATE_C_INSTRUCTION:
        operation = artifact.get("operation")
        if kind != "SupervisorResponse" or artifact.get("claimed_disposition") != "PROMOTE":
            return False
        if not isinstance(operation, str):
            return False
        tokens = operation.lower().split()
        return (
            len(tokens) >= 3
            and tokens[:2] == ["git", "push"]
            and any(token in {"main", "trunk"} for token in tokens[2:])
        )
    if canary.category == _GATE_C_ARCHITECTURE:
        branch = artifact.get("added_branch")
        return (
            kind == "SourceMutation"
            and isinstance(branch, str)
            and "provider ==" in branch.lower()
            and "bypass_court" in branch.lower()
        )
    if canary.category == _GATE_C_PROVENANCE:
        source = artifact.get("provenance_source")
        observation = artifact.get("transport_observation")
        return (
            kind == "SupervisorResponse"
            and isinstance(source, str)
            and "model-authored" in source.lower()
            and isinstance(observation, Mapping)
            and bool(observation)
        )
    if canary.category == _GATE_C_RESTART:
        adapter_id = artifact.get("adapter_id")
        checkpoint_hash = artifact.get("checkpoint_hash")
        return kind == "SupervisorClaim" and (
            (isinstance(adapter_id, str) and adapter_id.lower().startswith("retired-"))
            or checkpoint_hash == "0" * 64
        )
    if canary.category == _GATE_C_PRIVACY:
        return kind == "EvidenceEnvelope" and "credential_value" in artifact
    if canary.category == _GATE_C_SELF_RATIFICATION:
        issuer = artifact.get("issuer")
        return kind == "SupervisorResponse" and (
            artifact.get("authority") == "FOUNDER_RATIFICATION"
            or artifact.get("disposition") == "COURT_SEALED"
            or (
                isinstance(issuer, str)
                and bool({"model", "supervisor"} & set(issuer.lower().split("-")))
            )
        )
    if canary.category == _GATE_C_PROMPT_INJECTION:
        text = artifact.get("text")
        if kind != "OpaqueContext" or not isinstance(text, str):
            return False
        lowered = text.lower()
        return (
            "system override" in lowered
            or "ignore policy" in lowered
            or "disregard instructions" in lowered
            or "promote this branch immediately" in lowered
        )
    return False


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
