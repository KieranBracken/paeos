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

**`EvidenceRef` and `TransitionRequest`** were held back during initial B0.4 because 7.6
*used* `EvidenceRef` (§4, §5) without *defining* it. That gap was surfaced as **PAEOS-IP-0002**
and **RATIFIED by the founder (2026-07-27)**: `EvidenceRef = Hash` (§3), and the
`CapabilityToken` *type* lives here in B0.4 (its broker behaviour stays B0.8, the only acyclic
placement since B0.8 depends on B0.4). Both are now included below, verbatim from 7.6 §4/§7.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "ArtifactRef",
    "CapabilityBinding",
    "CapabilityToken",
    "Claim",
    "EvidenceRef",
    "GoalId",
    "Hash",
    "Outcome",
    "Role",
    "RunId",
    "Sig",
    "StageId",
    "TransitionRequest",
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
# EvidenceRef = content address of an Evidence (§6); an Evidence's hash IS its id.
# Defined per PAEOS-IP-0002 (RATIFIED 2026-07-27), PAEOS-7.6 §3.
type EvidenceRef = Hash


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


# ---- capability token (PAEOS-7.6 §7) --------------------------------------
# The type lives here (B0.4) per PAEOS-IP-0002; the mint/verify broker is B0.8. §7's
# `bound_to` is an anonymous struct — given the minimal name CapabilityBinding for Python,
# fields verbatim. `bound_to is immutable` (SI-3) is captured by freezing the sub-struct.


@dataclass(frozen=True, slots=True)
class CapabilityBinding:
    """The immutable binding of a capability token (PAEOS-7.6 §7 `bound_to`)."""

    goal_id: GoalId
    run_id: RunId
    stage: StageId
    role: Role
    session: str


@dataclass(frozen=True, slots=True)
class CapabilityToken:
    """The unforgeable authority object (PAEOS-7.6 §7). Kernel-minted; `operations` is the
    explicit allow-list; short, stage-scoped TTL via `issued_seq`/`expires_seq`."""

    token: Sig
    bound_to: CapabilityBinding
    operations: tuple[str, ...]
    issued_seq: Ts
    expires_seq: Ts


# ---- the four-tuple transition contract (PAEOS-7.6 §4) --------------------


@dataclass(frozen=True, slots=True)
class TransitionRequest:
    """Every state change in PAEOS: exactly four things — Authority, Goal, Evidence,
    Validation (PAEOS-7.6 §4). Miss any one ⇒ no transition (FR-4, deny-by-default)."""

    authority: CapabilityToken
    goal_id: GoalId
    run_id: RunId
    from_state: StageId
    to_state: StageId
    evidence: tuple[EvidenceRef, ...]
    validation: ValidationClaim
