"""Core runtime types — PAEOS-7.6 §3-4, transcribed, not invented.

Task B0.4 (PAEOS-8 §10). These are the machine constants and value contracts that every
other kernel module speaks in: stage identities, roles, weight classes, outcomes, and the
claim/validation/result shapes of the four-tuple transition contract. This module is pure
data — no behaviour. The kernel operations that consume these types (`propose_transition`,
`open_stage`, …) are implemented by their own tasks (B0.5 lifecycle, B0.6 gates, B0.8
capability broker); B0.4 only pins the vocabulary.

Fidelity discipline (CER-6, constitutional preamble): every name, field, and enum member
below is a verbatim transcription of PAEOS-7.6 §3-4. Nothing is added. Field names that
shadow builtins (`id`, `type`) are kept exactly as the spec writes them.

**Deliberate omission — `TransitionRequest` (PAEOS-7.6 §4).** Its `evidence: EvidenceRef[]`
field references a type, `EvidenceRef`, that PAEOS-7.6 *uses* (§4, §5) but never *defines* —
and the spec's precedent (`ArtifactRef = {hash, type}`, a struct rather than a bare `Hash`)
makes its shape genuinely ambiguous. Per the preamble ("default to derivation, not
invention; if invention is genuinely required, HALT and produce an Improvement Proposal")
`TransitionRequest` is held back pending founder ratification of **PAEOS-IP-0002**. It lands
in a B0.4 follow-up the moment `EvidenceRef` is pinned. Everything else in §3-4 is here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "ArtifactRef",
    "Claim",
    "GoalId",
    "Hash",
    "Outcome",
    "Role",
    "RunId",
    "Sig",
    "StageId",
    "TransitionResult",
    "Ts",
    "ValidationClaim",
    "WeightClass",
]

# ---- primitive aliases (PAEOS-7.6 §1 notation, §3) ------------------------
# `Hash` = content address (sha256 hex). `Sig` = kernel-produced signature.
# `Ts` = logical sequence number (ledger seq), never wall-clock (PAEOS-7 §3.5).
type GoalId = str
type RunId = str
type Hash = str
type Sig = str
type Ts = int


# ---- enums (PAEOS-7.6 §3) -------------------------------------------------
# String-valued so the wire/ledger representation is the constant's own name. No integer
# ordering is assigned here: the "0→19 + RAW" numbering is descriptive, and the legal-edge
# ordering is B0.5's lifecycle table, not this module's to invent.


class StageId(Enum):
    """The 21 canonical stage constants — the single source of truth for state identity
    across Kernel, Runtime, ledger, and traces (PAEOS-7.6 §3). Order of definition follows
    the spec's list verbatim."""

    RAW = "RAW"
    RE_DERIVE = "RE_DERIVE"
    INTAKE = "INTAKE"
    TRIAGE = "TRIAGE"
    IDEATE = "IDEATE"
    RESEARCH = "RESEARCH"
    TRADEOFF = "TRADEOFF"
    MITIGATION = "MITIGATION"
    DESIGN = "DESIGN"
    CRITIQUE = "CRITIQUE"
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    VERIFY = "VERIFY"
    ADVERSARIAL_REVIEW = "ADVERSARIAL_REVIEW"
    LEDGER_SYNC = "LEDGER_SYNC"
    SEAL = "SEAL"
    RETROSPECT = "RETROSPECT"
    EVOLVE = "EVOLVE"
    MEMORY_UPDATE = "MEMORY_UPDATE"
    IMPROVE_RUNTIME = "IMPROVE_RUNTIME"
    RESTART = "RESTART"


class Role(Enum):
    """The seven producer roles (PAEOS-7.6 §3)."""

    PLANNER = "PLANNER"
    BUILDER = "BUILDER"
    CRITIC = "CRITIC"
    VERIFIER = "VERIFIER"
    ADVERSARY = "ADVERSARY"
    DOC = "DOC"
    RATIFIER = "RATIFIER"


class WeightClass(Enum):
    """Blast-radius class, set at TRIAGE (PAEOS-7.6 §3)."""

    ROUTINE = "ROUTINE"
    SUBSTANTIAL = "SUBSTANTIAL"
    KERNEL_TOUCHING = "KERNEL_TOUCHING"


class Outcome(Enum):
    """The five terminal outcomes of a transition (PAEOS-7.6 §3)."""

    COMMITTED = "COMMITTED"
    REMAND = "REMAND"
    REJECT = "REJECT"
    QUARANTINE = "QUARANTINE"
    ABORT = "ABORT"


# ---- value contracts (PAEOS-7.6 §3-4) -------------------------------------
# All frozen: these are immutable data. Field names and types are verbatim from the spec.


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A reference to a stored artifact by content address (PAEOS-7.6 §3)."""

    hash: Hash
    type: str


@dataclass(frozen=True, slots=True)
class Claim:
    """One assertion in a validation, mapped to its supporting evidence (PAEOS-7.6 §4).
    `evidence_refs` are content-address hashes of the evidence backing the claim."""

    id: str
    statement: str
    evidence_refs: tuple[Hash, ...]


@dataclass(frozen=True, slots=True)
class ValidationClaim:
    """The assertion a transition makes, to be checked by the gate (PAEOS-7.6 §4).
    `produced_against` binds every claim to the exact artifact under review (SI-4)."""

    gate_id: str
    claims: tuple[Claim, ...]
    producer: Role
    produced_against: Hash


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """The outcome of `propose_transition` (PAEOS-7.6 §4). `reason` is required for any
    non-COMMITTED outcome; `committed_seq` is the ledger seq iff COMMITTED."""

    outcome: Outcome
    committed_seq: Ts | None
    remand_to: StageId | None
    reason: str
    verdict_ref: Hash | None
