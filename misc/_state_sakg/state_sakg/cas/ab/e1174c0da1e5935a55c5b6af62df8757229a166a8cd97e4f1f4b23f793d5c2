"""Amendment path — the hard-loop for constitutional change (PAEOS-7 §7.4, FR-2 / PAEOS-8 §12 Ph2).

Ordinary work runs the *soft loop* (`runtime/selfhost.py`). A change to the **frozen kernel or the
constitution** may not merge on Builder+Verifier alone — it must run the **hard loop** (§7.4):

  (a) the change is classified **HARD** by the *kernel* classifier, not the proposer's claim (A-2);
  (b) an **isolated Adversary attacks the safety-invariant diff specifically** (FR-2 / PAEOS-3.5);
  (c) a **human ratifier signs off** — and *nothing autonomous may substitute for that signature*.

This module wires (a) and (b) and then **halts at the human gate**. It **prepares** a
`RatificationPacket` — classification + the captured adversary review — and never applies it. The
runtime cannot write Z0; application is a founder action (sign + commit to `constitution/`), by
construction: there is no code path here that touches `kernel/` or `constitution/`. That the
runtime *proposes* and the founder *ratifies* is CER-5; the non-application is §7.4's non-negotiable
boundary and PAEOS-7.5 T4's primary defense against unsafe self-modification.

`cli/paeos.py amend` calls `prepare_amendment`; tests inject a scripted adversary runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from kernel.capability import CapabilityBroker
from kernel.cas import CAS
from kernel.classifier import Classification, classify_paths
from kernel.types import ArtifactRef, Hash
from nacl.signing import SigningKey

from runtime.claude_code import AgentDispatcher, AgentRuntime
from runtime.review import InformationBarrierManager, ReviewHarness
from runtime.task_package import Budget, TaskStatus

__all__ = [
    "AMENDMENT_BUDGET",
    "AmendmentPath",
    "AmendmentProposal",
    "AmendmentStatus",
    "RatificationPacket",
    "parse_proposal",
    "prepare_amendment",
]

# Amendments are the heaviest work: a KERNEL_TOUCHING-scale budget for the adversarial attack.
AMENDMENT_BUDGET = Budget(2_000_000, 10800, 3)


class AmendmentStatus(Enum):
    """The disposition of a prepared amendment. None of these applies the change."""

    NOT_AN_AMENDMENT = "NOT_AN_AMENDMENT"  # kernel classifier: SOFT — ordinary work, use soft loop
    ADVERSARY_INCOMPLETE = "ADVERSARY_INCOMPLETE"  # the adversary session did not complete
    AWAITING_RATIFICATION = "AWAITING_RATIFICATION"  # HARD + adversary attacked → founder gate


@dataclass(frozen=True, slots=True)
class AmendmentProposal:
    """A proposed change to the TCB (kernel/constitution). It recommends; it changes nothing."""

    proposal_id: str
    title: str
    target_paths: tuple[str, ...]  # the kernel/ or constitution/ paths the change would touch
    safety_invariants: tuple[str, ...]  # invariants the diff touches, e.g. ("K1", "FR-5")
    diff: str  # the proposed change text — the safety-invariant diff the adversary attacks
    rationale: str  # why (an Improvement Proposal reference)


@dataclass(frozen=True, slots=True)
class RatificationPacket:
    """What the founder ratifies over: the proposal, the kernel classification, and the adversary
    review. The runtime assembles it and stops — `applied` is always False."""

    proposal: AmendmentProposal
    classification: Classification
    status: AmendmentStatus
    adversary_trace_ref: Hash | None
    adversary_report_refs: tuple[ArtifactRef, ...]
    detail: str

    @property
    def applied(self) -> bool:
        """The runtime never applies an amendment. Application is a founder HARD-LOOP action
        (sign + commit to `constitution/`); this property documents the invariant (§7.4)."""
        return False


class AmendmentPath:
    """Prepares an amendment for the human ratification gate — classify, adversarially attack the
    safety-invariant diff, then halt. Never writes the TCB."""

    def __init__(
        self,
        *,
        signing_key: SigningKey,
        cas: CAS,
        adversary_runtime: AgentRuntime,
        budget: Budget = AMENDMENT_BUDGET,
    ) -> None:
        self._cas = cas
        self._budget = budget
        self._seq = 0
        broker = CapabilityBroker(signing_key)
        dispatcher = AgentDispatcher(broker, cas, adversary_runtime, clock=self._clock)
        self._ibm = InformationBarrierManager()
        self._review = ReviewHarness(self._ibm, dispatcher)

    def _clock(self) -> int:
        self._seq += 1
        return self._seq

    def prepare(self, proposal: AmendmentProposal) -> RatificationPacket:
        """Run the hard-loop's automated part; stop at the human gate. Applies nothing."""
        # (a) the KERNEL classifies blast radius, not the proposer (A-2). A non-TCB change is not an
        # amendment — it belongs in the soft loop, and cannot buy the heavyweight gate here.
        classification = classify_paths(proposal.target_paths)
        if classification == "SOFT":
            return RatificationPacket(
                proposal=proposal,
                classification=classification,
                status=AmendmentStatus.NOT_AN_AMENDMENT,
                adversary_trace_ref=None,
                adversary_report_refs=(),
                detail="target paths do not touch the TCB — run this through the soft loop",
            )

        # (b) an isolated Adversary attacks the safety-invariant diff specifically (FR-2).
        diff_ref = ArtifactRef(hash=self._cas.put(proposal.diff.encode("utf-8")), type="amendment")
        bundle = self._ibm.seal(artifact_refs=(diff_ref,), evidence_refs=())
        invariants = ", ".join(proposal.safety_invariants) or "the kernel's safety invariants"
        adversary = self._review.review(
            goal_id=proposal.proposal_id,
            run_id="amend-1",
            session="ratification-adversary",
            bundle=bundle,
            budget=self._budget,
            report_scope=f"review/{proposal.proposal_id}_ratification.md",
        )
        if adversary.status is not TaskStatus.COMPLETE:
            return RatificationPacket(
                proposal=proposal,
                classification=classification,
                status=AmendmentStatus.ADVERSARY_INCOMPLETE,
                adversary_trace_ref=adversary.trace_ref,
                adversary_report_refs=adversary.artifacts,
                detail=f"adversary session {adversary.status.value} — not ready for the human gate",
            )

        # (c) HALT at the human gate. The founder reads the adversary review and signs; the runtime
        # applies nothing.
        return RatificationPacket(
            proposal=proposal,
            classification=classification,
            status=AmendmentStatus.AWAITING_RATIFICATION,
            adversary_trace_ref=adversary.trace_ref,
            adversary_report_refs=adversary.artifacts,
            detail=(
                f"HARD change to {invariants}: adversary attacked the diff; "
                "awaiting founder signature (runtime applies nothing — §7.4)"
            ),
        )


def prepare_amendment(
    proposal: AmendmentProposal,
    *,
    signing_key: SigningKey,
    cas: CAS,
    adversary_runtime: AgentRuntime,
    budget: Budget = AMENDMENT_BUDGET,
) -> RatificationPacket:
    """Prepare one amendment for the human ratification gate. Convenience over `AmendmentPath`."""
    path = AmendmentPath(
        signing_key=signing_key, cas=cas, adversary_runtime=adversary_runtime, budget=budget
    )
    return path.prepare(proposal)


def parse_proposal(raw: object) -> AmendmentProposal:
    """Parse a JSON proposal (from `json.loads`) into an `AmendmentProposal`. ValueError if bad."""
    if not isinstance(raw, dict):
        raise ValueError("proposal must be a JSON object")
    obj = {str(k): v for k, v in raw.items()}

    def _req_str(key: str) -> str:
        value = obj.get(key)
        if not isinstance(value, str):
            raise ValueError(f"proposal field {key!r} must be a string")
        return value

    def _str_tuple(key: str) -> tuple[str, ...]:
        value = obj.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"proposal field {key!r} must be a list of strings")
        return tuple(v for v in value if isinstance(v, str))

    return AmendmentProposal(
        proposal_id=_req_str("proposal_id"),
        title=_req_str("title"),
        target_paths=_str_tuple("target_paths"),
        safety_invariants=_str_tuple("safety_invariants"),
        diff=_req_str("diff"),
        rationale=_req_str("rationale"),
    )
