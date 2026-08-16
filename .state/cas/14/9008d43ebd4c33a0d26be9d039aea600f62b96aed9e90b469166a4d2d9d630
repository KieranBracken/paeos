"""Scar store + signature matching (PAEOS-8 §10 B1.F / FR-6 / §7.1).

"No rule without a scar": a failure becomes a **scar** — a lesson with a **detection signature** and
a set of *conditions* (tags) under which it applies. A scar is **auto-injected** into a matching
goal at the injection stages (`RE_DERIVE`, `DESIGN`, `CRITIQUE`, `VERIFY` — stages 0/7/8/11), so the
system does not repeat the mistake (FR-6, always on the path).

Matching is **subset containment**: a scar with conditions `{a, b}` applies to a goal whose
signature is a superset (`{a, b, …}`) — precise, never firing on unrelated goals. Proposing a scar
is a **gated transition** (T3/A-10), not a direct write: a scar whose signature is too broad (fewer
than `MIN_SIGNATURE_TAGS` conditions — it would inject *everywhere*) is **quarantined**, closing the
scar-poisoning vector (T3). This module implements the B1.A `ScarBackend`.
"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.types import StageId

__all__ = [
    "INJECTION_STAGES",
    "MIN_SIGNATURE_TAGS",
    "Scar",
    "ScarDraft",
    "ScarQuarantined",
    "ScarStore",
    "parse_signature",
]

# Scars are injected at these stages (PAEOS-8 §10: stages 0/7/8/11).
INJECTION_STAGES: frozenset[StageId] = frozenset(
    {StageId.RE_DERIVE, StageId.DESIGN, StageId.CRITIQUE, StageId.VERIFY}
)

# A scar must have at least this many conditions, else it is over-broad (T3 poison guard).
MIN_SIGNATURE_TAGS = 2


class ScarQuarantined(Exception):
    """A proposed scar's signature is too broad to inject safely — quarantined (T3)."""


@dataclass(frozen=True, slots=True)
class ScarDraft:
    """A proposed scar (a gated transition, not a direct write — T3/A-10)."""

    signature: frozenset[str]  # the conditions (tags) under which this scar applies
    lesson: str
    detection: str  # detection signature: how to catch this defect class next time (K6)
    severity: str = "medium"


@dataclass(frozen=True, slots=True)
class Scar:
    """A recorded, matchable lesson."""

    id: str
    signature: frozenset[str]
    lesson: str
    detection: str
    severity: str


def parse_signature(signature: str) -> frozenset[str]:
    """A goal/scar signature string ("a,b,c") to its tag set."""
    return frozenset(tag.strip() for tag in signature.split(",") if tag.strip())


class ScarStore:
    """Stores scars and matches them to goals by signature. Implements the B1.A `ScarBackend`."""

    def __init__(self) -> None:
        self._scars: dict[str, Scar] = {}
        self._counter = 0

    def propose_scar(self, draft: ScarDraft) -> Scar:
        """Accept a scar, or raise ScarQuarantined if its signature is too broad (T3)."""
        if len(draft.signature) < MIN_SIGNATURE_TAGS:
            raise ScarQuarantined(
                f"scar signature {set(draft.signature)} has < {MIN_SIGNATURE_TAGS} conditions; "
                "too broad to inject — quarantined (T3)"
            )
        self._counter += 1
        scar = Scar(
            id=f"scar-{self._counter:04d}",
            signature=draft.signature,
            lesson=draft.lesson,
            detection=draft.detection,
            severity=draft.severity,
        )
        self._scars[scar.id] = scar
        return scar

    def match_scars(self, signature: str) -> list[Scar]:
        """Scars whose conditions are all met by a goal with this signature (subset match)."""
        goal_tags = parse_signature(signature)
        matched = [scar for scar in self._scars.values() if scar.signature <= goal_tags]
        return sorted(matched, key=lambda s: s.id)

    def get_precedent(self, precedent_id: str) -> Scar | None:
        """A scar by id, or None."""
        return self._scars.get(precedent_id)

    def injected_scars(self, *, signature: str, stage: StageId) -> list[Scar]:
        """Matched scars to inject at this stage — empty unless `stage` is an injection stage."""
        if stage not in INJECTION_STAGES:
            return []
        return self.match_scars(signature)
