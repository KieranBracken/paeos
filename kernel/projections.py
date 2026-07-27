"""Projections + replay — derived state rebuilt from the ledger (PAEOS-8 §10 B0.10 / §6).

Task B0.10. The ledger (B0.1) is the source of truth; a *projection* is a read-model folded
from it (goal state, seal index, …). Two properties make projections safe to use:

  * **Deterministic replay** — folding the same event sequence always yields byte-identical
    state and the same head hash. Two independent replays of a corpus agree exactly (D1, §6).
  * **Verifiable against the head** — a projection is a *cache*, never an authority. `replay`
    binds a projection to the ledger head it was built at and to a digest of its state;
    `verify_against_head` re-derives from the ledger and rejects a **stale** projection (head
    moved) or a **poisoned** one (cached state does not match the truth) *before* it is used
    (T7).

The engine is generic over the state type `S`; a caller supplies a `Projector` (initial state,
fold, and a canonical digest). No domain schema is baked in here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from kernel.ledger import Ledger, LedgerRow

__all__ = [
    "PoisonedProjection",
    "Projection",
    "ProjectionError",
    "Projector",
    "StaleProjection",
    "replay",
    "verify_against_head",
]

class ProjectionError(Exception):
    """Base for projection faults."""


class StaleProjection(ProjectionError):
    """The projection was built against an earlier ledger head; the ledger has advanced."""


class PoisonedProjection(ProjectionError):
    """The projection's cached state does not match a fresh replay of the ledger (T7 tamper)."""


class Projector[S](Protocol):
    """How to fold the ledger into a read-model of type `S`. Must be deterministic and pure."""

    def initial(self) -> S:
        """The empty state before any event."""
        ...

    def fold(self, state: S, row: LedgerRow) -> S:
        """Apply one committed row to the state, returning the next state."""
        ...

    def digest(self, state: S) -> str:
        """A canonical content hash of `state` — identical states ⇒ identical digest."""
        ...


@dataclass(frozen=True, slots=True)
class Projection[S]:
    """A read-model plus the two bindings that make it verifiable: the ledger head it was built
    at, and a digest of its state."""

    state: S
    head_hash: str
    state_digest: str


def replay[S](ledger: Ledger, projector: Projector[S]) -> Projection[S]:
    """Fold the whole ledger (in seq order) into a fresh projection bound to the current head."""
    state = projector.initial()
    for row in ledger.read():
        state = projector.fold(state, row)
    return Projection(
        state=state,
        head_hash=ledger.head_hash(),
        state_digest=projector.digest(state),
    )


def verify_against_head[S](
    ledger: Ledger, projector: Projector[S], projection: Projection[S]
) -> None:
    """Reject a stale or poisoned projection before use. Re-derives from the authoritative ledger
    and compares. Raises `StaleProjection` (head moved) or `PoisonedProjection` (state tampered);
    returns None if the projection faithfully reflects the current ledger."""
    rebuilt = replay(ledger, projector)
    if projection.head_hash != rebuilt.head_hash:
        raise StaleProjection(
            f"projection built at {projection.head_hash[:12]}…, "
            f"ledger head is {rebuilt.head_hash[:12]}…"
        )
    # digest the projection's *state* directly (do not trust its cached state_digest field), so a
    # tampered state is caught even if its digest field was updated to match.
    if projector.digest(projection.state) != rebuilt.state_digest:
        raise PoisonedProjection(
            f"projection state does not match the ledger head {rebuilt.head_hash[:12]}…"
        )
