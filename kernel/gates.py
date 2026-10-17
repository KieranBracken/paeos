"""Gate reference monitor — the four-tuple `propose_transition` (PAEOS-7.6 §4 / 7 §4.3-4.4).

Task B0.6 (PAEOS-8 §10). This is where the kernel actually *decides*. Every state change is a
`TransitionRequest` carrying four things — **Authority, Goal, Evidence, Validation** — and this
module composes the modules that check each into one deny-by-default gate (FR-4):

  1. **Authority** → `CapabilityBroker.verify` (B0.8): genuine, in-TTL, bound, op-allowed.
  2. **Goal**      → `is_legal` (B0.5): the requested edge is legal for the weight class.
  3. **Evidence**  → `verify_binding` + `verify_deterministic` (B0.7): every claim has evidence,
     bound to the artifact under review (SI-4), and deterministic evidence is kernel-reproduced.
  4. **Validation**→ separation of powers (SI-3): the producing session does not already hold a
     conflicting separated power for this (goal, run).

Miss any one ⇒ no transition. On failure the gate routes to the correct `Outcome` (7 §4.4):
attacks (forgery, relabel, escalation, evidence forgery, power fusion) → **QUARANTINE** (the
FR-2/FR-3 tripwire); invalid requests (expired token, illegal edge) → **REJECT**; fixable gaps
(missing / stale / unreproducible evidence) → **REMAND** to the current stage.

Scope notes:
  * `propose_transition` returns the *decision*. The ledger append (single-writer, B0.1) that
    assigns `committed_seq` is the control-plane's job (B0.12); in decision-only use it is None.
  * Step 5 (TCB-touch ⇒ require HARD-classification ⇒ route to amendment, SI-8/A-2) is a
    pluggable `classify_change` hook, default off — the classifier is B0.11.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from kernel.capability import (
    BindingMismatch,
    CapabilityBroker,
    CapabilityError,
    ExpiredToken,
    InvalidToken,
    OperationNotPermitted,
)
from kernel.evidence import (
    Determinism,
    Evidence,
    NotReproducible,
    ReproductionMismatch,
    StaleEvidence,
    verify_binding,
    verify_deterministic,
)
from kernel.lifecycle import is_legal
from kernel.types import (
    Hash,
    Outcome,
    Role,
    StageId,
    TransitionRequest,
    TransitionResult,
    Ts,
    WeightClass,
)

__all__ = ["PROPOSE_TRANSITION_OP", "SEPARATED_POWERS", "Gate"]

# The four mutually-exclusive powers (PAEOS-7 §5.1): a single session may hold at most one.
# The Critic/Planner/Doc are deliberately NOT separated powers (§5.1). "Seal" ⇒ RATIFIER.
SEPARATED_POWERS: frozenset[Role] = frozenset(
    {Role.BUILDER, Role.VERIFIER, Role.ADVERSARY, Role.RATIFIER}
)

# The kernel operation a transition request exercises (checked against the token allow-list).
PROPOSE_TRANSITION_OP = "propose_transition"

EvidenceResolver = Callable[[Hash], Evidence]
ChangeClassifier = Callable[[TransitionRequest], str]  # -> "SOFT" | "HARD"


def _deny(outcome: Outcome, reason: str, *, remand_to: StageId | None = None) -> TransitionResult:
    return TransitionResult(
        outcome=outcome,
        committed_seq=None,
        remand_to=remand_to,
        reason=reason,
        verdict_ref=None,
    )


class Gate:
    """The reference monitor. Holds the capability broker and an evidence resolver; decides each
    `TransitionRequest` deny-by-default."""

    def __init__(
        self,
        broker: CapabilityBroker,
        resolve_evidence: EvidenceResolver,
        *,
        classify_change: ChangeClassifier | None = None,
    ) -> None:
        self._broker = broker
        self._resolve = resolve_evidence
        self._classify = classify_change

    def propose_transition(
        self,
        request: TransitionRequest,
        *,
        weight_class: WeightClass,
        current_seq: Ts,
        artifact_under_review: Hash,
        powers_exercised: Mapping[str, Role] | None = None,
    ) -> TransitionResult:
        """Run the four-tuple check and return the decision. `powers_exercised` maps a session id
        to the separated power it already holds for this (goal, run)."""
        producer = request.validation.producer

        # ---- 1. Authority (SI-1, T1) ----
        try:
            self._broker.verify(
                request.authority,
                goal_id=request.goal_id,
                run_id=request.run_id,
                stage=request.from_state,
                role=producer,
                operation=PROPOSE_TRANSITION_OP,
                current_seq=current_seq,
            )
        except ExpiredToken as exc:
            return _deny(Outcome.REJECT, f"authority: {exc}")  # stale, invalid request
        except (InvalidToken, BindingMismatch, OperationNotPermitted, CapabilityError) as exc:
            # forgery / role-relabel / escalation = capability-escalation attempt (§4.4)
            return _deny(Outcome.QUARANTINE, f"authority (escalation attempt): {exc}")

        # ---- 2. Goal: legal edge for this weight class (§4.1) ----
        if not is_legal(request.from_state, request.to_state, weight_class):
            return _deny(
                Outcome.REJECT,
                f"goal: {request.from_state.name} -> {request.to_state.name} "
                f"is not a legal edge for {weight_class.name}",
            )

        # ---- 3. Evidence: bound + deterministic-reproduced (T2, SI-4) ----
        if request.validation.produced_against != artifact_under_review:
            return _deny(
                Outcome.REMAND,
                "validation is not bound to the artifact under review (SI-4)",
                remand_to=request.from_state,
            )
        for claim in request.validation.claims:
            if not claim.evidence_refs:
                return _deny(
                    Outcome.REMAND,
                    f"claim {claim.id!r} has no evidence (deny-by-default, FR-4)",
                    remand_to=request.from_state,
                )
            for ref in claim.evidence_refs:
                evidence = self._resolve(ref)
                try:
                    verify_binding(evidence, artifact_under_review)
                except StaleEvidence as exc:
                    return _deny(Outcome.REMAND, f"evidence: {exc}", remand_to=request.from_state)
                if evidence.determinism is Determinism.DETERMINISTIC:
                    try:
                        verify_deterministic(evidence, artifact_under_review)
                    except ReproductionMismatch as exc:
                        # forged result caught by kernel re-run = attack (§4.4)
                        return _deny(Outcome.QUARANTINE, f"evidence forgery: {exc}")
                    except NotReproducible as exc:
                        return _deny(
                            Outcome.REMAND, f"evidence: {exc}", remand_to=request.from_state
                        )

        # ---- 4. Validation: separation of powers (SI-3, §5.1) ----
        session = request.authority.bound_to.session
        held = (powers_exercised or {}).get(session)
        if (
            producer in SEPARATED_POWERS
            and held is not None
            and held != producer
            and held in SEPARATED_POWERS
        ):
            return _deny(
                Outcome.QUARANTINE,
                f"separation of powers: session {session!r} already holds {held.name}, "
                f"cannot also act as {producer.name} (SI-3)",
            )

        # ---- 5. TCB touch ⇒ HARD ⇒ route to amendment (SI-8, A-2; classifier = B0.11) ----
        if self._classify is not None and self._classify(request) == "HARD":
            return _deny(
                Outcome.REJECT,
                "change is HARD (TCB-touching): route to the amendment path (G-Amend), refuse here",
            )

        # ---- 6. Pass. committed_seq is assigned by the ledger append (B0.1), not here. ----
        return TransitionResult(
            outcome=Outcome.COMMITTED,
            committed_seq=None,
            remand_to=None,
            reason="",
            verdict_ref=None,
        )
