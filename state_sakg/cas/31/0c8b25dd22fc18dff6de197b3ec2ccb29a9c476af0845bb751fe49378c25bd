"""Information-Barrier Manager + review harness — the isolated adversary (PAEOS-8 §10 B1.D / FR-3).

Independence is *constructed, not requested* (FR-3, 7 §5.3): the adversary is a fresh session that
sees **only the sealed evidence bundle** — never builder context, scratch, or reasoning (SI-5).
This module builds that barrier:

  * `InformationBarrierManager.seal` produces a `SealedBundle` — the artifact(s) under review plus
    the evidence, content-addressed. Deliberately *nothing else*.
  * `adversary_context` yields the adversary's `context_refs` from the bundle **only**.
  * `verify_isolation` proves the adversary's context shares no ref with the builder-private set —
    a self-exfil attempt (T1/SI-5) is refused (`BarrierViolation`).

The `ReviewHarness` dispatches the adversary through the B1.B dispatcher with that bundle-only
context and a report-only write scope, so the barrier is enforced by *construction*: the adversary
is never handed builder-private refs to begin with, and the isolation check backstops it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from kernel.types import ArtifactRef, GoalId, Hash, Role, RunId, StageId

from runtime.claude_code import AgentDispatcher
from runtime.task_package import Budget, TaskResult

__all__ = [
    "AdversaryOutcome",
    "BarrierViolation",
    "InformationBarrierManager",
    "ReviewHarness",
    "SealedBundle",
    "read_adversary_verdict",
]

# The verdict line the adversary MUST end its report with (B2.K / IP-0007). A seal requires an
# explicit adversarial PASS; anything else blocks it.
VERDICT_PASS_MARKER = "VERDICT: PASS"
VERDICT_BLOCK_MARKER = "VERDICT: BLOCK"


class AdversaryOutcome(Enum):
    """The isolated adversary's machine-readable verdict on the sealed bundle (FR-3)."""

    PASS = "PASS"  # the adversary failed to break the change — a seal precondition (PAEOS-3.5)
    BLOCK = "BLOCK"  # a blocking dissent — the change may not seal


def read_adversary_verdict(report: bytes | str) -> AdversaryOutcome:
    """Parse the adversary's report for its verdict. **Fail-closed** (FR-3): BLOCK unless an
    explicit `VERDICT: PASS` is present with no `VERDICT: BLOCK` — a missing verdict never seals."""
    text = report.decode("utf-8", "replace") if isinstance(report, bytes) else report
    if VERDICT_BLOCK_MARKER in text:
        return AdversaryOutcome.BLOCK
    if VERDICT_PASS_MARKER in text:
        return AdversaryOutcome.PASS
    return AdversaryOutcome.BLOCK  # deny-by-default: no clear PASS ⇒ no seal


class BarrierViolation(Exception):
    """The adversary's context would let it see builder-private material — refused (SI-5)."""


@dataclass(frozen=True, slots=True)
class SealedBundle:
    """The ONLY thing the adversary is allowed to see: the artifact(s) under review + the evidence.
    No builder scratch, reasoning, or other-goal context is present, by construction."""

    bundle_hash: Hash
    artifact_refs: tuple[ArtifactRef, ...]
    evidence_refs: tuple[Hash, ...]


class InformationBarrierManager:
    """Seals adversary-visible bundles and proves builder context cannot leak across the barrier."""

    def seal(
        self, *, artifact_refs: tuple[ArtifactRef, ...], evidence_refs: tuple[Hash, ...]
    ) -> SealedBundle:
        canonical = json.dumps(
            {
                "artifacts": sorted([r.type, r.hash] for r in artifact_refs),
                "evidence": sorted(evidence_refs),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        bundle_hash = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        return SealedBundle(
            bundle_hash=bundle_hash,
            artifact_refs=tuple(artifact_refs),
            evidence_refs=tuple(evidence_refs),
        )

    def adversary_context(self, bundle: SealedBundle) -> tuple[ArtifactRef, ...]:
        """The adversary's `context_refs`: bundle artifacts + evidence-as-refs, nothing else."""
        evidence_as_refs = tuple(
            ArtifactRef(hash=h, type="evidence") for h in bundle.evidence_refs
        )
        return bundle.artifact_refs + evidence_as_refs

    def verify_isolation(
        self,
        adversary_context: tuple[ArtifactRef, ...],
        builder_private: tuple[ArtifactRef, ...],
    ) -> None:
        """Raise BarrierViolation if the adversary's context shares any ref with builder-private
        material (SI-5). The barrier is one-directional: the adversary sees the bundle, never the
        builder's side."""
        seen = {r.hash for r in adversary_context}
        private = {r.hash for r in builder_private}
        leaked = seen & private
        if leaked:
            raise BarrierViolation(
                f"adversary context leaks {len(leaked)} builder-private ref(s): {sorted(leaked)}"
            )


class ReviewHarness:
    """Dispatches an isolated adversary session over a sealed bundle (the review chamber, §5.3)."""

    def __init__(self, ibm: InformationBarrierManager, dispatcher: AgentDispatcher) -> None:
        self._ibm = ibm
        self._dispatcher = dispatcher

    def review(
        self,
        *,
        goal_id: GoalId,
        run_id: RunId,
        session: str,
        bundle: SealedBundle,
        budget: Budget,
        builder_private: tuple[ArtifactRef, ...] = (),
        report_scope: str = "review/adversary_report.md",
    ) -> TaskResult:
        """Dispatch the adversary with bundle-only context. Refuses (BarrierViolation) if the
        bundle-derived context would leak any builder-private ref."""
        adversary_context = self._ibm.adversary_context(bundle)
        self._ibm.verify_isolation(adversary_context, builder_private)  # barrier backstop (SI-5)
        return self._dispatcher.dispatch(
            goal_id=goal_id,
            run_id=run_id,
            stage=StageId.ADVERSARIAL_REVIEW,
            role=Role.ADVERSARY,
            session=session,
            objective=(
                "Attack the sealed evidence bundle; file blocking dissents on what fails. "
                f"End your report with exactly one line: '{VERDICT_PASS_MARKER}' if you could not "
                f"break it, or '{VERDICT_BLOCK_MARKER}' if you found a blocking defect."
            ),
            write_scopes=(report_scope,),  # the adversary may write only its report
            read_scopes=(bundle.bundle_hash,),  # and read only the sealed bundle
            mcp_servers=("constitution",),  # constitution only — NOT memory / builder context
            context_refs=adversary_context,
            budget=budget,
        )
