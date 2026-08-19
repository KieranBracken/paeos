"""Verification Court — deterministic re-run + adjudication (PAEOS-8 §10 B1.E / 7 §4.3 G-Court).

The court is where evidence stops being a claim and becomes a verdict. It **reproduces every
claim**: for each, it re-runs the deterministic evidence (via the DEBT-0005 **sandbox** by default),
checks the re-run reproduces the claimed result. If any claim is unmet, the goal is **remanded**
(§4.4). A forged result the agent could not actually produce (T2) — or a planted **canary** — is
caught here, because the court, not the agent, decides what happened.

`submit_evidence` is **inert** until `adjudicate` runs (SI-2): submission only pools the evidence;
the kernel-style re-run is what renders the verdict. Implements the `CourtBackend` Protocol (B1.A).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from kernel.evidence import (
    Evidence,
    NotReproducible,
    ReproductionMismatch,
    StaleEvidence,
    verify_deterministic,
)
from kernel.evidence import Runner as EvidenceRunner
from kernel.sandbox import sandbox_runner
from kernel.types import Claim, Hash

__all__ = ["Court", "Verdict", "VerdictOutcome"]


class VerdictOutcome(Enum):
    PASS = "PASS"
    REMAND = "REMAND"


@dataclass(frozen=True, slots=True)
class Verdict:
    """The court's adjudication of an artifact's claims."""

    outcome: VerdictOutcome
    artifact_hash: Hash
    unmet_claims: tuple[str, ...] = ()
    detail: str = ""


class Court:
    """Pools submitted evidence and adjudicates claims by kernel re-run (sandboxed by default)."""

    def __init__(self, *, runner: EvidenceRunner | None = None) -> None:
        # Untrusted agent commands are re-run in the resource-limited sandbox (DEBT-0005).
        self._runner: EvidenceRunner = runner if runner is not None else sandbox_runner()
        self._evidence: dict[Hash, Evidence] = {}
        self._verdicts: dict[Hash, Verdict] = {}

    def submit_evidence(self, evidence: Evidence) -> object:
        """Pool evidence for later adjudication. Inert until `adjudicate` (SI-2)."""
        self._evidence[evidence.hash] = evidence
        return {"submitted": evidence.hash}

    def adjudicate(self, artifact_under_review: Hash, claims: Sequence[Claim]) -> Verdict:
        """Reproduce every claim; PASS iff all met, else REMAND (with the unmet claim ids)."""
        unmet: list[str] = []
        for claim in claims:
            if not self._claim_holds(claim, artifact_under_review):
                unmet.append(claim.id)
        if unmet:
            verdict = Verdict(
                outcome=VerdictOutcome.REMAND,
                artifact_hash=artifact_under_review,
                unmet_claims=tuple(unmet),
                detail=f"{len(unmet)} claim(s) not reproduced by the kernel re-run",
            )
        else:
            verdict = Verdict(
                outcome=VerdictOutcome.PASS,
                artifact_hash=artifact_under_review,
                detail="every claim reproduced",
            )
        self._verdicts[artifact_under_review] = verdict
        return verdict

    def get_verdict(self, artifact_hash: Hash) -> object:
        """The recorded verdict for an artifact, or None if not yet adjudicated."""
        return self._verdicts.get(artifact_hash)

    def _claim_holds(self, claim: Claim, artifact_under_review: Hash) -> bool:
        if not claim.evidence_refs:
            return False  # deny-by-default: a claim with no evidence never holds
        for ref in claim.evidence_refs:
            evidence = self._evidence.get(ref)
            if evidence is None:
                return False  # evidence was never submitted
            try:
                verify_deterministic(evidence, artifact_under_review, runner=self._runner)
            except (ReproductionMismatch, StaleEvidence, NotReproducible):
                return False  # forgery / stale / unreproducible ⇒ claim unmet (T2)
        return True
