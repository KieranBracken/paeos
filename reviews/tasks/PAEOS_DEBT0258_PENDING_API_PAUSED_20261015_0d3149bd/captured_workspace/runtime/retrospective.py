"""Gate-routed L17 retrospective reports and institutional scar drafts.

The retrospective is deliberately a pure report producer: memory mutation remains owned by
the later MEMORY_UPDATE stage.  Reports are canonical JSON bytes in CAS and every scar draft
is explicit, attributable, and narrow enough for the ScarStore admission policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from kernel.cas import CAS
from kernel.types import Outcome, WeightClass

from runtime.memory import ScarDraft

CER_RETROSPECTIVE_QUESTIONS = (
    "What architectural weaknesses were exposed?",
    "Which assumptions were invalidated?",
    "Which parts of PAEOS were strengthened?",
    "What improvement proposals follow?",
    "What debt must be recorded?",
    "Does the strategy need to change?",
)


class RetrospectiveTransitionRejected(RuntimeError):
    """Raised when the kernel Gate refuses a requested L17 transition."""


@dataclass(frozen=True, slots=True)
class RetrospectiveReport:
    goal_id: str
    run_id: str
    objective: str
    status: str
    detail: str
    goal_signature: str
    changed_paths: tuple[str, ...]
    answers: tuple[str, ...]
    findings: tuple[str, ...]
    scar_drafts: tuple[ScarDraft, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "goal_id": self.goal_id,
            "run_id": self.run_id,
            "objective": self.objective,
            "status": self.status,
            "detail": self.detail,
            "goal_signature": self.goal_signature,
            "changed_paths": list(self.changed_paths),
            "questions": list(CER_RETROSPECTIVE_QUESTIONS),
            "answers": list(self.answers),
            "findings": list(self.findings),
            "scar_drafts": [
                {
                    "signature": sorted(draft.signature),
                    "lesson": draft.lesson,
                    "detection": draft.detection,
                    "severity": draft.severity,
                }
                for draft in self.scar_drafts
            ],
        }

    def canonical_bytes(self) -> bytes:
        return (json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")) + "\n").encode()


class RetrospectiveEngine:
    """Build and persist L17 reports; ask the Gate before advancing lifecycle state."""

    def __init__(self, cas: CAS) -> None:
        self._cas = cas

    def build_report(
        self,
        outcome: Any,
        *,
        run_id: str,
        objective: str,
        goal_signature: str = "",
        changed_paths: tuple[str, ...] = (),
    ) -> RetrospectiveReport:
        status = getattr(outcome.status, "value", str(outcome.status))
        detail = str(getattr(outcome, "detail", ""))
        if status == "SEALED":
            finding = "The sealed run satisfied its court and adversary obligations."
            answers = tuple(
                f"No new weakness identified for this question ({question})"
                for question in CER_RETROSPECTIVE_QUESTIONS
            )
            scars: tuple[ScarDraft, ...] = ()
        else:
            finding = f"Run ended {status}: {detail or 'failure details require remediation.'}"
            answers = tuple(
                f"Review required: {question}" for question in CER_RETROSPECTIVE_QUESTIONS
            )
            tags = frozenset({"stage:retrospect", f"status:{status.lower()}", "domain:runtime"})
            scars = (
                ScarDraft(
                    signature=tags,
                    lesson=f"Remediate {status} run: {detail}",
                    detection="L17 retrospective identified a non-sealed outcome",
                    severity="high",
                ),
            )
        return RetrospectiveReport(
            goal_id=str(getattr(outcome, "goal_id", "unknown")),
            run_id=run_id,
            objective=objective,
            status=status,
            detail=detail,
            goal_signature=goal_signature,
            changed_paths=tuple(changed_paths),
            answers=answers,
            findings=(finding,),
            scar_drafts=scars,
        )

    def emit_report(self, report: RetrospectiveReport) -> str:
        return self._cas.put(report.canonical_bytes())

    def route_transition(
        self,
        gate: Any,
        request: Any,
        *,
        weight_class: WeightClass,
        current_seq: int,
        artifact_hash: str,
    ) -> object:
        result = gate.propose_transition(
            request,
            weight_class=weight_class,
            current_seq=current_seq,
            artifact_under_review=artifact_hash,
        )
        if result.outcome is not Outcome.COMMITTED:
            raise RetrospectiveTransitionRejected(result.reason or result.outcome.value)
        return result


__all__ = [
    "CER_RETROSPECTIVE_QUESTIONS",
    "RetrospectiveEngine",
    "RetrospectiveReport",
    "RetrospectiveTransitionRejected",
]
