"""Lifecycle legal-edge oracle — PAEOS-7 §4.1, as pinned by PAEOS-IP-0003 (ratified).

Task B0.5 (PAEOS-8 §10). `is_legal(from_stage, to_stage, weight_class)` is the reference
monitor's second check (PAEOS-7.6 §4 `propose_transition` step 2): given a *requested* forward
transition, is that edge legal for this goal's weight class? Deny-by-default (FR-4): anything
not explicitly legal is illegal.

Scope (PAEOS-IP-0003 Part A, ratified): this oracle governs **requester-initiated forward
edges only**. Failure outcomes — `REMAND`, `REJECT`, `QUARANTINE`, `ABORT` — are the kernel
reactor's failure-routing (`TransitionResult.remand_to`), not edges a requester may ask for,
and are deliberately absent here.

Weight-class topology (PAEOS-IP-0003 Part B, ratified):
  * `KERNEL_TOUCHING` / `SUBSTANTIAL` (Trace-B): the full forward chain, RAW → … → RESTART,
    plus the re-execution cycle RESTART → RE_DERIVE.
  * `ROUTINE` (Trace-A): the same chain PLUS the compression edges `TRIAGE → IMPLEMENT` and
    `RAW → INTAKE`. Auto-discharge stubs keep the ledger fully replayable (PAEOS-9 §2.3); the
    cheaper *edge* is what makes the fast path the primary economic control.

The edge set is *derived from the ratified ordered chain* below rather than hand-listed, so it
cannot silently drift from the spec.
"""

from __future__ import annotations

import itertools

from kernel.types import StageId, WeightClass

__all__ = ["FORWARD_EDGES", "ROUTINE_FASTPATH_EDGES", "is_legal"]

# The canonical forward chain (PAEOS-7 §4.1, ratified IP-0003). Ordered exactly as the founder
# ratified it: RAW through RESTART, then the re-execution cycle back to RE_DERIVE.
_MAIN_CHAIN: tuple[StageId, ...] = (
    StageId.RAW,
    StageId.RE_DERIVE,
    StageId.INTAKE,
    StageId.TRIAGE,
    StageId.IDEATE,
    StageId.RESEARCH,
    StageId.TRADEOFF,
    StageId.MITIGATION,
    StageId.DESIGN,
    StageId.CRITIQUE,
    StageId.PLAN,
    StageId.IMPLEMENT,
    StageId.VERIFY,
    StageId.ADVERSARIAL_REVIEW,
    StageId.LEDGER_SYNC,
    StageId.SEAL,
    StageId.RETROSPECT,
    StageId.EVOLVE,
    StageId.MEMORY_UPDATE,
    StageId.IMPROVE_RUNTIME,
    StageId.RESTART,
)

# Forward edges legal for EVERY weight class: consecutive pairs of the chain + the
# RESTART → RE_DERIVE re-execution cycle (stage 19, PAEOS-7 §4.1 "RE-EXECUTE").
FORWARD_EDGES: frozenset[tuple[StageId, StageId]] = frozenset(
    set(itertools.pairwise(_MAIN_CHAIN)) | {(StageId.RESTART, StageId.RE_DERIVE)}
)

# Additional edges legal ONLY for ROUTINE (Trace-A): the ratified compression edges.
ROUTINE_FASTPATH_EDGES: frozenset[tuple[StageId, StageId]] = frozenset(
    {
        (StageId.TRIAGE, StageId.IMPLEMENT),  # auto-discharge IDEATE..PLAN (YAML L02→L12)
        (StageId.RAW, StageId.INTAKE),  # RE_DERIVE is Trace-B only (§0.4)
    }
)


def is_legal(from_stage: StageId, to_stage: StageId, weight_class: WeightClass) -> bool:
    """True iff a requested transition `from_stage → to_stage` is a legal forward edge for
    `weight_class`. Deny-by-default: any edge not explicitly legal returns False."""
    edge = (from_stage, to_stage)
    return edge in FORWARD_EDGES or (
        weight_class is WeightClass.ROUTINE and edge in ROUTINE_FASTPATH_EDGES
    )
