"""Evolution Layer — stages 15-18, the self-improvement loop (PAEOS-7 §7 / §8 Ph2, PAEOS-8 §12).

"The reason PAEOS exists" (§7): a run that fails must make the *next* run less likely to fail. This
layer runs *after* a soft-loop run and turns its outcome into durable learning:

  * **RETROSPECT (15)** — extract findings from the `RunOutcome`: what failed, at which stage, and
    which paths the change implicated (classified by the *kernel*, not a claim — A-2).
  * **EVOLVE (16)** — draft the guards: a soft **scar** (a lesson + detection signature, FR-6) for
    every failure; and, for a **TCB-implicated recurrence** (a failure whose guard already existed
    yet did not hold), a hard **IMPROVE_RUNTIME proposal** (§7.4 / A-3 cumulative-drift).
  * **MEMORY_UPDATE (17)** — write the scar drafts into the shared `ScarStore` (a gated transition;
    an over-broad signature is *quarantined*, not written — T3).
  * **IMPROVE_RUNTIME (18)** — emit the `AmendmentProposal`s. The layer only **proposes** — it never
    routes to the amendment path itself and never applies anything (CER-5). The caller feeds a
    proposal to `runtime/amendment.py` (B2.E), which halts at the human gate.

A clean **SEALED** run yields no scar and no proposal — learning is from failure (§7.1). Nothing
here writes the TCB; the layer's only side effect is proposing scars into the injected store.
"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.classifier import Classification, classify_paths

from runtime.amendment import AmendmentProposal
from runtime.memory import Scar, ScarDraft, ScarQuarantined, ScarStore, parse_signature
from runtime.orchestrator import RunOutcome, RunStatus

__all__ = ["EvolutionLayer", "EvolutionResult", "Retrospective"]


@dataclass(frozen=True, slots=True)
class Retrospective:
    """The findings of a single run — the raw material for guards (stage 15)."""

    goal_id: str
    status: RunStatus
    goal_signature: str
    failed_stage: str  # "VERIFY" (court remand), "BUDGET" (halt), or "" (clean seal)
    findings: tuple[str, ...]  # human-readable lessons
    implicated_paths: tuple[str, ...]  # the changed paths the run touched
    classification: Classification  # kernel blast-radius of the implicated paths (A-2)
    failure_tags: frozenset[str]  # the failure's own signature tags


@dataclass(frozen=True, slots=True)
class EvolutionResult:
    """What one turn of the loop produced (stages 16-18). The layer applies none of it."""

    retrospective: Retrospective
    scars_written: tuple[Scar, ...]  # MEMORY_UPDATE — written to the shared store (FR-6)
    scars_quarantined: tuple[frozenset[str], ...]  # signatures too broad to write (T3) — surfaced
    proposals: tuple[AmendmentProposal, ...]  # IMPROVE_RUNTIME — candidates for the B2.E gate


class EvolutionLayer:
    """Runs stages 15-18 over a completed run and writes the durable learning."""

    def __init__(self, *, scar_store: ScarStore) -> None:
        self._scars = scar_store

    def run(
        self,
        outcome: RunOutcome,
        *,
        goal_signature: str,
        changed_paths: tuple[str, ...],
    ) -> EvolutionResult:
        """RETROSPECT → EVOLVE → MEMORY_UPDATE → IMPROVE_RUNTIME for one run."""
        retro = self._retrospect(outcome, goal_signature, changed_paths)
        if retro.status is RunStatus.SEALED:
            return EvolutionResult(retro, (), (), ())  # a clean seal needs no guard (§7.1)

        signature_tags = parse_signature(goal_signature) | retro.failure_tags
        # A-3 recurrence check MUST precede the write, else the new scar always "already exists".
        recurred = bool(self._scars.match_scars(",".join(sorted(signature_tags))))

        proposals = self._improve_runtime(retro, recurred)
        written, quarantined = self._memory_update(retro, signature_tags)
        return EvolutionResult(retro, written, quarantined, proposals)

    # ---- stage 15 ----------------------------------------------------------

    def _retrospect(
        self, outcome: RunOutcome, goal_signature: str, changed_paths: tuple[str, ...]
    ) -> Retrospective:
        classification = classify_paths(changed_paths)
        if outcome.status is RunStatus.REMANDED:
            unmet = outcome.verdict.unmet_claims if outcome.verdict is not None else ()
            findings = (
                f"court remanded: claim(s) {unmet} did not reproduce"
                if unmet
                else f"court remanded: {outcome.detail}",
            )
            failed_stage, failure_tags = "VERIFY", frozenset({"stage:VERIFY", "kind:court-remand"})
        elif outcome.status is RunStatus.HALTED:
            findings = (f"halted (budget breach): {outcome.detail}",)
            failed_stage = "BUDGET"
            failure_tags = frozenset({"stage:BUDGET", "kind:budget-breach"})
        else:  # SEALED
            findings, failed_stage, failure_tags = (), "", frozenset()
        return Retrospective(
            goal_id=outcome.goal_id,
            status=outcome.status,
            goal_signature=goal_signature,
            failed_stage=failed_stage,
            findings=findings,
            implicated_paths=changed_paths,
            classification=classification,
            failure_tags=failure_tags,
        )

    # ---- stage 17 ----------------------------------------------------------

    def _memory_update(
        self, retro: Retrospective, signature_tags: frozenset[str]
    ) -> tuple[tuple[Scar, ...], tuple[frozenset[str], ...]]:
        draft = ScarDraft(
            signature=signature_tags,
            lesson="; ".join(retro.findings),
            detection=f"a {retro.failed_stage}-stage failure recurs on a goal "
            f"matching {sorted(signature_tags)}",
            severity="high" if retro.failed_stage == "VERIFY" else "medium",
        )
        try:
            return (self._scars.propose_scar(draft),), ()
        except ScarQuarantined:
            return (), (signature_tags,)  # too broad to inject safely — surfaced, not written (T3)

    # ---- stage 18 ----------------------------------------------------------

    def _improve_runtime(
        self, retro: Retrospective, recurred: bool
    ) -> tuple[AmendmentProposal, ...]:
        # Emit a hard proposal only for a TCB-implicated *recurrence*: the soft guard existed yet
        # the failure repeated, so the system itself is implicated (§7.4 mistakes / A-3 drift).
        if not (recurred and retro.classification == "HARD"):
            return ()
        return (
            AmendmentProposal(
                proposal_id=f"IP-EVO-{retro.goal_id}",
                title=f"Recurring TCB-implicated {retro.failed_stage} failure",
                target_paths=retro.implicated_paths,
                safety_invariants=(),  # authored during the amendment's own lifecycle (§7.4)
                diff=(
                    "PROPOSAL (not a finished diff): a guarded failure recurred on a TCB-touching "
                    f"change. Findings: {'; '.join(retro.findings)}. Review whether the kernel/"
                    "constitution itself must change; author the diff in the amendment lifecycle."
                ),
                rationale=f"Evolution Layer stage-18: recurrence for goal {retro.goal_id}",
            ),
        )
