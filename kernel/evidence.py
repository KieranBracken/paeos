"""Evidence — binding, kernel reproduction, stale-replay defense (PAEOS-7.6 §6 / 7.5 T2).

Task B0.7 (PAEOS-8 §10). Evidence is the currency of every gate (FR-4); if it is forgeable,
every gate is theater (7.5 T2, the highest-impact runtime threat). This module implements the
four T2 hardenings that make forgery hard:

  1. **Binding** — every Evidence carries `(artifact_hash, claim_id, environment_hash,
     reproducible_command)`. A gate rejects evidence whose `artifact_hash` ≠ the artifact under
     review (`verify_binding`) — this kills stale-replay (SI-4).
  2. **Deterministic ⇒ always kernel-reproduced** — `reproduce` re-runs the
     `reproducible_command` itself and `verify_deterministic` rejects any claimed result that
     the re-run does not reproduce. The kernel, not the agent, decides what the result was, so a
     forged `result` is caught (T2).
  3. **Non-deterministic ⇒ two independent producers** — `verify_two_producers` requires two
     distinct producers agreeing within a declared tolerance (builder-side + court-side, 7.5 T2).
  4. **Keys held by the kernel** — `attestation` is kernel-produced; agents never sign (A-5).
     (Signature *verification* is B0.8/B0.9; this module owns binding + reproduction.)

Security note (DEBT-0005): `reproduce` executes the command with no shell and a hard timeout,
but without OS-level sandboxing (resource/filesystem/network isolation) that 7.5 §T2/EXEC
requires. That hardening is deferred and tracked; the reproduction *logic* here is complete.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum

from kernel.ledger import JsonValue
from kernel.types import Hash, Role, Sig

__all__ = [
    "Determinism",
    "Evidence",
    "EvidenceError",
    "EvidenceKind",
    "EvidenceProducer",
    "NotReproducible",
    "ReproductionMismatch",
    "StaleEvidence",
    "TwoProducerViolation",
    "reproduce",
    "verify_binding",
    "verify_deterministic",
    "verify_two_producers",
]

_DEFAULT_TIMEOUT_S = 30


# ---- errors ---------------------------------------------------------------


class EvidenceError(Exception):
    """Base for evidence faults."""


class StaleEvidence(EvidenceError):
    """Evidence's `artifact_hash` ≠ the artifact under review — stale-replay refused (SI-4)."""


class ReproductionMismatch(EvidenceError):
    """The kernel re-ran the command and got a result the evidence did not claim (T2 forgery)."""


class NotReproducible(EvidenceError):
    """Evidence cannot be kernel-reproduced (non-deterministic, no command, or run failed)."""


class TwoProducerViolation(EvidenceError):
    """Non-deterministic evidence lacks two independent producers agreeing within tolerance."""


# ---- types (PAEOS-7.6 §6) -------------------------------------------------


class EvidenceKind(Enum):
    """The evidence kinds (PAEOS-7.6 §6)."""

    BUILD = "BUILD"
    TEST = "TEST"
    BENCHMARK = "BENCHMARK"
    PROOF = "PROOF"
    CITATION = "CITATION"
    TRACE = "TRACE"
    MUTATION = "MUTATION"
    CANARY = "CANARY"


class Determinism(Enum):
    """Whether the evidence is kernel-reproducible or needs independent corroboration (§6)."""

    DETERMINISTIC = "DETERMINISTIC"
    NONDETERMINISTIC = "NONDETERMINISTIC"


@dataclass(frozen=True, slots=True)
class EvidenceProducer:
    """Who produced the evidence (PAEOS-7.6 §6 `producer`)."""

    role: Role
    session: str


@dataclass(frozen=True, slots=True)
class Evidence:
    """A content-addressed proof bound to the exact artifact + environment it is about (§6).
    `hash` IS its id (matches `EvidenceRef = Hash`, PAEOS-IP-0002)."""

    hash: Hash
    kind: EvidenceKind
    claim_id: str
    artifact_hash: Hash  # BINDING: the exact artifact under review (SI-4)
    environment_hash: Hash  # BINDING: toolchain/deps fingerprint
    reproducible_command: str | None  # required for deterministic kinds
    producer: EvidenceProducer
    determinism: Determinism
    result: JsonValue  # structured outcome; for reproducible commands: {"exit_code","stdout"}
    attestation: Sig  # kernel-produced (A-5)


# ---- binding (stale-replay defense, SI-4) ---------------------------------


def verify_binding(evidence: Evidence, artifact_under_review: Hash) -> None:
    """Raise StaleEvidence unless the evidence is bound to the artifact under review."""
    if evidence.artifact_hash != artifact_under_review:
        raise StaleEvidence(
            f"evidence {evidence.hash} is bound to {evidence.artifact_hash}, "
            f"not the artifact under review {artifact_under_review}"
        )


# ---- reproduction (T2: kernel re-runs deterministic evidence) -------------


def reproduce(evidence: Evidence, *, timeout_s: int = _DEFAULT_TIMEOUT_S) -> dict[str, JsonValue]:
    """Re-run the evidence's `reproducible_command` and return the fresh result
    `{"exit_code", "stdout"}`. The kernel — not the agent — determines what happened.

    Only for DETERMINISTIC evidence with a command. Raises NotReproducible otherwise.
    """
    if evidence.determinism is not Determinism.DETERMINISTIC:
        raise NotReproducible(f"evidence {evidence.hash} is non-deterministic; cannot re-run")
    if not evidence.reproducible_command:
        raise NotReproducible(f"evidence {evidence.hash} has no reproducible_command")
    args = shlex.split(evidence.reproducible_command)
    if not args:
        raise NotReproducible(f"evidence {evidence.hash} has an empty reproducible_command")
    try:
        # no shell; args are parsed via shlex so the command cannot inject shell syntax
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        raise NotReproducible(f"re-run of evidence {evidence.hash} failed: {exc}") from exc
    return {"exit_code": proc.returncode, "stdout": proc.stdout}


def verify_deterministic(
    evidence: Evidence, artifact_under_review: Hash, *, timeout_s: int = _DEFAULT_TIMEOUT_S
) -> None:
    """Full deterministic-evidence check: binding + kernel re-run reproduces the claimed result.
    Raises StaleEvidence, NotReproducible, or ReproductionMismatch. This is the T2 gate."""
    verify_binding(evidence, artifact_under_review)
    fresh = reproduce(evidence, timeout_s=timeout_s)
    if fresh != evidence.result:
        raise ReproductionMismatch(
            f"evidence {evidence.hash} claimed {evidence.result!r} "
            f"but the kernel re-run produced {fresh!r}"
        )


# ---- non-deterministic (T2: two independent producers) --------------------


def _within_tolerance(a: JsonValue, b: JsonValue, tolerance: float) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):  # bool is an int subclass; compare exactly
        return a == b
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(a - b) <= tolerance
    return a == b


def verify_two_producers(a: Evidence, b: Evidence, *, tolerance: float = 0.0) -> None:
    """Corroborate non-deterministic evidence: two *independent* producers for the same claim +
    artifact, whose results agree within `tolerance`. Raises TwoProducerViolation otherwise.

    Independence = distinct producer sessions (builder-side + court-side, 7.5 T2). Note: the
    schema does not carry `tolerance`, so it is supplied by the caller/gate (Observation, review).
    """
    if a.claim_id != b.claim_id or a.artifact_hash != b.artifact_hash:
        raise TwoProducerViolation("the two evidences are not about the same claim + artifact")
    if a.producer.session == b.producer.session:
        raise TwoProducerViolation(
            f"producers are not independent: both are session {a.producer.session!r}"
        )
    if not _within_tolerance(a.result, b.result, tolerance):
        raise TwoProducerViolation(
            f"producers disagree beyond tolerance {tolerance}: {a.result!r} vs {b.result!r}"
        )
