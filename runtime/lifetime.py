"""Constitutional Knowledge Lifetime Ontology — L0-L5 (PAEOS-IP-0006, ratified 2026-07-30).

IP-0006 adds a second classification axis (Purpose x **Lifetime**) and requires (§5) that every
information artifact *declare* its `lifetime_class`. Following the founder's own precedent
(`ExecutionContext` declares L1 by its type identity, not a mutated field), this module is the
**single runtime-side declaration**: a registry mapping each artifact *type* to its class, plus
the owner / persistence facts (IP-0006 §2) and the promotion rule (§5).

Declaring the classes centrally — rather than stamping a `lifetime_class` field onto every dataclass
— keeps the **kernel** L5/L4 types (`Evidence`, `Event`, `SealRecord`, constitution) **untouched**:
adding fields there would be an F2 HARD-LOOP change routed through the amendment path (B2.E), not a
unilateral edit. Extending kernel types with a literal field is deferred to that channel.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from kernel.types import StageId

__all__ = [
    "ONTOLOGY",
    "LifetimeClass",
    "LifetimeInfo",
    "classify_type",
    "may_promote",
]


class LifetimeClass(Enum):
    """The six constitutional lifetime classes (IP-0006 §2)."""

    L0 = "L0"  # Scratch
    L1 = "L1"  # Ephemeral Execution Context
    L2 = "L2"  # Runtime Projection
    L3 = "L3"  # Institutional Memory
    L4 = "L4"  # Constitutional Knowledge
    L5 = "L5"  # Historical Truth


@dataclass(frozen=True, slots=True)
class LifetimeInfo:
    """The invariant facts of a lifetime class (IP-0006 §2 table)."""

    name: str
    owner: str  # Worker / Runtime / Evolution / Founder / Kernel
    lifetime: str
    persisted: str  # Never / No / Cache / Durable / Immutable
    rebuildable: bool


ONTOLOGY: dict[LifetimeClass, LifetimeInfo] = {
    LifetimeClass.L0: LifetimeInfo("Scratch", "Worker", "Step / Function", "Never", False),
    LifetimeClass.L1: LifetimeInfo("Ephemeral Execution Context", "Runtime", "run_id", "No", False),
    LifetimeClass.L2: LifetimeInfo("Runtime Projection", "Runtime", "Session", "Cache", True),
    LifetimeClass.L3: LifetimeInfo(
        "Institutional Memory", "Evolution", "Cross-Run", "Durable", False
    ),
    LifetimeClass.L4: LifetimeInfo(
        "Constitutional Knowledge", "Founder", "Until Amended", "Durable", False
    ),
    LifetimeClass.L5: LifetimeInfo("Historical Truth", "Kernel", "Forever", "Immutable", False),
}

# The falsification mapping (IP-0006 §4): each artifact *type name* → its lifetime class.
_REGISTRY: dict[str, LifetimeClass] = {
    # L5 — Historical Truth (kernel-owned, immutable)
    "Evidence": LifetimeClass.L5,
    "Event": LifetimeClass.L5,
    "LedgerEvent": LifetimeClass.L5,
    "LedgerRow": LifetimeClass.L5,
    "SealRecord": LifetimeClass.L5,
    "GenesisRecord": LifetimeClass.L5,
    # L4 — Constitutional Knowledge (founder-owned, until amended)
    "Constitution": LifetimeClass.L4,
    "Clause": LifetimeClass.L4,
    "KernelSpec": LifetimeClass.L4,
    "AmendmentProposal": LifetimeClass.L4,  # a proposed amendment (IP-); ratified content is L4
    # L3 — Institutional Memory (Evolution-owned, cross-run)
    "Scar": LifetimeClass.L3,
    "ScarDraft": LifetimeClass.L3,
    "Lesson": LifetimeClass.L3,
    # L2 — Runtime Projection (runtime-owned cache; 100% derived from L4/L5)
    "TaskPackage": LifetimeClass.L2,
    "CompiledContext": LifetimeClass.L2,
    "Projection": LifetimeClass.L2,
    # L1 — Ephemeral Execution Context (runtime-owned, run-scoped)
    "ExecutionContext": LifetimeClass.L1,
    "RemandNote": LifetimeClass.L1,
    "RetryHint": LifetimeClass.L1,
    # L0 — Scratch (worker-owned, step-scoped)
    "ScratchFile": LifetimeClass.L0,
}


def classify_type(type_name: str) -> LifetimeClass:
    """The lifetime class of an artifact by its type name (IP-0006 §4). Raises KeyError if unknown —
    an unregistered artifact type is a conformance gap to be closed, not silently defaulted."""
    try:
        return _REGISTRY[type_name]
    except KeyError:
        raise KeyError(
            f"artifact type {type_name!r} has no declared lifetime_class (IP-0006 §5)"
        ) from None


# Promotions permitted between lifetime classes, each keyed to the verified transition that allows
# it (IP-0006 §5: "Promotion between lifetime classes may ONLY occur through explicit, verified
# constitutional transitions, e.g. L1 -> L3 Scar via Stage 17 Evolution").
_PROMOTIONS: dict[tuple[LifetimeClass, LifetimeClass], StageId] = {
    (LifetimeClass.L1, LifetimeClass.L3): StageId.MEMORY_UPDATE,  # ephemeral -> institutional
    # B2.Q audit (the live R4 Adversary flagged this): a former (L5 -> L3) entry was REMOVED. A scar
    # is *authored from* the run's L1 context at Stage 17 (the L5 ledger evidence is a referenced
    # input, immutable and unpromoted) — so the only promotion is L1 -> L3. Framing "derive a scar
    # from immutable evidence" as an L5 -> L3 *promotion* was a category confusion (IP-0006 §5).
}


def may_promote(src: LifetimeClass, dst: LifetimeClass, *, via_stage: StageId) -> bool:
    """True iff promoting `src` → `dst` is a permitted, verified transition at `via_stage` (§5).

    Deny-by-default: any promotion not explicitly permitted (or attempted at the wrong stage) is
    refused — e.g. the SoftLoop cannot promote an L1 note to an L3 scar outside Stage 17."""
    required = _PROMOTIONS.get((src, dst))
    return required is not None and required is via_stage
