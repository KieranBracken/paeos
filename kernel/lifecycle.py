"""Lifecycle legal-edge oracle — PAEOS-7 §4.1, as pinned by PAEOS-IP-0003 (ratified).

Task B0.5 (PAEOS-8 §10). `is_legal(from_stage, to_stage, weight_class)` is the reference
monitor's second check (PAEOS-7.6 §4 `propose_transition` step 2): given a *requested* forward
transition, is that edge legal for this goal's weight class? Deny-by-default (FR-4): anything
not explicitly legal is illegal. The edge table is a derived projection of
`operations/ENGINEERING_LIFECYCLE.md` v1.3; it is not a second lifecycle authority.

Scope (PAEOS-IP-0003 Part A, ratified): this oracle governs **requester-initiated forward
edges only**. Failure outcomes — `REMAND`, `REJECT`, `QUARANTINE`, `ABORT` — are the kernel
reactor's failure-routing (`TransitionResult.remand_to`), not edges a requester may ask for,
and are deliberately absent here.

Weight-class topology:
  * `KERNEL_TOUCHING` / `SUBSTANTIAL` (Trace-B): canonical L01 → L19 order, with runtime
    control state `RAW` before L01 and `IMPROVE_RUNTIME`/`RESTART` after L19, plus the
    re-execution cycle `RESTART → RE_DERIVE`.
  * `ROUTINE` (Trace-A): the same order plus the lawful compression edge `TRIAGE → IMPLEMENT`;
    L03–L11 remain represented by ceremony discharge evidence, never an omitted layer.

The edge set is *derived from the ratified ordered chain* below rather than hand-listed, so it
cannot silently drift from the spec.
"""

from __future__ import annotations

import itertools

from kernel.types import StageId, WeightClass

__all__ = ["FORWARD_EDGES", "ROUTINE_FASTPATH_EDGES", "is_legal"]

# Canonical L01-L19 projection with non-layer runtime controls. `ADVERSARIAL_REVIEW` is L10 and
# therefore precedes `PLAN`/L11, while `VERIFY` is L13 and follows `IMPLEMENT`/L12.
_MAIN_CHAIN: tuple[StageId, ...] = (
    StageId.RAW,
    StageId.INTAKE,
    StageId.TRIAGE,
    StageId.RE_DERIVE,
    StageId.IDEATE,
    StageId.RESEARCH,
    StageId.TRADEOFF,
    StageId.MITIGATION,
    StageId.DESIGN,
    StageId.CRITIQUE,
    StageId.ADVERSARIAL_REVIEW,
    StageId.PLAN,
    StageId.IMPLEMENT,
    StageId.VERIFY,
    StageId.LEDGER_SYNC,
    StageId.SEAL,
    StageId.RETROSPECT,
    StageId.MEMORY_UPDATE,
    StageId.EVOLVE,
    StageId.IMPROVE_RUNTIME,
    StageId.RESTART,
)

# Forward edges legal for EVERY weight class: consecutive pairs of the chain + the
# RESTART → RE_DERIVE re-execution cycle (stage 19, PAEOS-7 §4.1 "RE-EXECUTE").
FORWARD_EDGES: frozenset[tuple[StageId, StageId]] = frozenset(
    set(itertools.pairwise(_MAIN_CHAIN)) | {(StageId.RESTART, StageId.RE_DERIVE)}
)

# Additional edges legal ONLY for ROUTINE (Trace-A): L03-L11 auto-discharge compression.
ROUTINE_FASTPATH_EDGES: frozenset[tuple[StageId, StageId]] = frozenset(
    {
        (StageId.TRIAGE, StageId.IMPLEMENT),  # auto-discharge L03..L11
    }
)


def is_legal(from_stage: StageId, to_stage: StageId, weight_class: WeightClass) -> bool:
    """True iff a requested transition `from_stage → to_stage` is a legal forward edge for
    `weight_class`. Deny-by-default: any edge not explicitly legal returns False."""
    edge = (from_stage, to_stage)
    return edge in FORWARD_EDGES or (
        weight_class is WeightClass.ROUTINE and edge in ROUTINE_FASTPATH_EDGES
    )
