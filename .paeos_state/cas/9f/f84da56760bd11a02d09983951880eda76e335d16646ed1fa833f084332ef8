"""B1.E acceptance tests for the Verification Court (PAEOS-8 §10 / 7 §4.3).

The court reproduces every claim; an unmet claim ⇒ REMAND; a forged result (T2 reward-hack) and a
planted canary (B0.14, CANARY-0001) are caught. Reproduction runs in the DEBT-0005 sandbox.
"""

from __future__ import annotations

from pathlib import Path

from kernel.canary import load_canaries, run_canary
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.types import Claim, Role
from runtime.court import Court, VerdictOutcome

_ART = "a" * 64
_CANARY_DIR = Path(__file__).resolve().parents[2] / "constitution" / "canaries"


def _evidence(*, command: str, result: object, ev_hash: str = "e" * 64) -> Evidence:
    return Evidence(
        hash=ev_hash, kind=EvidenceKind.TEST, claim_id="c", artifact_hash=_ART,
        environment_hash="v" * 64, reproducible_command=command,
        producer=EvidenceProducer(role=Role.BUILDER, session="s"),
        determinism=Determinism.DETERMINISTIC, result=result, attestation="sig",  # type: ignore[arg-type]
    )


def _claim(evidence: Evidence) -> Claim:
    return Claim(id="c", statement="works", evidence_refs=(evidence.hash,))


# ---- adjudication ---------------------------------------------------------


def test_passes_when_every_claim_reproduces() -> None:
    court = Court()
    ev = _evidence(command="echo real", result={"exit_code": 0, "stdout": "real\n"})
    court.submit_evidence(ev)
    verdict = court.adjudicate(_ART, [_claim(ev)])
    assert verdict.outcome is VerdictOutcome.PASS
    assert court.get_verdict(_ART) == verdict


def test_forged_result_is_caught_and_remanded() -> None:
    # T2 reward-hack: the agent claims a passing result the command does not produce.
    court = Court()
    forged = _evidence(command="echo real", result={"exit_code": 0, "stdout": "FORGED\n"})
    court.submit_evidence(forged)
    verdict = court.adjudicate(_ART, [_claim(forged)])
    assert verdict.outcome is VerdictOutcome.REMAND
    assert verdict.unmet_claims == ("c",)


def test_claim_without_submitted_evidence_is_remanded() -> None:
    court = Court()
    ev = _evidence(command="echo real", result={"exit_code": 0, "stdout": "real\n"})
    # not submitted → the court has nothing to reproduce
    verdict = court.adjudicate(_ART, [_claim(ev)])
    assert verdict.outcome is VerdictOutcome.REMAND


def test_claim_with_no_evidence_is_remanded() -> None:
    court = Court()
    empty = Claim(id="c", statement="unbacked", evidence_refs=())
    assert court.adjudicate(_ART, [empty]).outcome is VerdictOutcome.REMAND


def test_submit_is_inert_until_adjudicate() -> None:
    court = Court()
    ev = _evidence(command="echo real", result={"exit_code": 0, "stdout": "real\n"})
    court.submit_evidence(ev)
    assert court.get_verdict(_ART) is None  # no verdict until adjudicate runs


# ---- canary caught (wires B0.14 to the real court) ------------------------


def test_seed_canary_is_caught_by_the_court() -> None:
    court = Court()

    def _court_detector(canary: object) -> bool:
        # rebuild the forged-evidence artifact and submit it to the court; caught iff REMAND
        art = load_canaries(_CANARY_DIR)[0].artifact
        command = art["reproducible_command"]
        claimed = art["claimed_result"]
        assert isinstance(command, str)
        ev = _evidence(command=command, result=claimed)
        court.submit_evidence(ev)
        return court.adjudicate(_ART, [_claim(ev)]).outcome is VerdictOutcome.REMAND

    seed = load_canaries(_CANARY_DIR)[0]
    result = run_canary(seed, _court_detector)
    assert result.caught is True
    assert result.passed is True  # a correct court catches the canary
