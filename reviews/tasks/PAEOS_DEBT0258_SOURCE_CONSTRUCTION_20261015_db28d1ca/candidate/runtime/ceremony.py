"""Canonical L02 ceremony contract + Trace-A discharge evidence stubs.

Implements the **existing canonical law** — no legislation. Source: Engineering Lifecycle
(operations/ENGINEERING_LIFECYCLE.md v1.3, L18-30) and its derived machine-executable form
(operations/WORKFLOW_STATE_MACHINE.yaml, ``ceremony_depth`` L56-72). Doctrine extraction with
citations: ``backlog/research/PAEOS_RESEARCH_BACKLOGS_CEREMONY_TDD_v0.1/
PAEOS_CEREMONY_DEPTH_DOCTRINE_EXTRACTION_v1.md`` (RB-CEREMONY-DEPTH-001 D1).

What this module gives the runtime (the R4 gap labelled "L02 PARTIAL — depth assignment and
ceremony contract absent" in the Two-Axis Conformance Map):

  1. **CeremonyContract** — the per-run obligation graph derived from L02's ceremony-depth
     decision: for every canonical layer L01-L19, EXECUTE or lawful DISCHARGE.
  2. **DischargeStub** — the mandatory K1 evidence for a discharged layer, in the canonical
     WSM format ``{result: auto_pass, reason: trace_a, by: runtime}`` (WSM L70-72; EL L29-30:
     "auto-discharge is not skip — it emits the evidence stub that keeps every transition valid").
  3. **Obligation plan** — the ordered ceremony-resolved path a run must follow
     (the input to the runtime obligation-graph execution, approved sequence step 4).

Canonical sets encoded here (EL L24-28 / WSM L60-68):

  * Trace-A: executes L01, L02, L12, L13, L14, L15, L16 (and L19 if triggered) **in full**;
    auto-discharges L03-L11 and L17-L18.
  * Trace-B: all 19 layers execute in full, founder decisions at the gates.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

__all__ = [
    "TRACE_A_DISCHARGE",
    "TRACE_A_EXECUTE_FULL",
    "TRACE_B_EXECUTE_FULL",
    "CeremonyContract",
    "DischargeStub",
    "Layer",
    "Obligation",
    "assert_canonical_lifecycle_bound",
    "ceremony_for",
    "discharged_layers_for",
]

CANONICAL_LIFECYCLE_SHA256 = "0bc717cc738a27b126c48d2f9a034998ad7d4a29cca61eeff7f1e63149d8dfae"


def assert_canonical_lifecycle_bound(canonical_path: Path | None = None) -> None:
    """Fail closed if the ceremony would run against an unratified lifecycle source."""

    path = canonical_path or Path(__file__).resolve().parents[1] / "operations" / "ENGINEERING_LIFECYCLE.md"
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise RuntimeError("canonical lifecycle source is unavailable") from exc
    if hashlib.sha256(content).hexdigest() != CANONICAL_LIFECYCLE_SHA256:
        raise RuntimeError("canonical lifecycle source hash does not match Founder IP-0017")
    if b"This is **v1.3**" not in content:
        raise RuntimeError("canonical lifecycle source does not declare v1.3")


class Layer(Enum):
    """The 19 canonical lifecycle layers (EL v1.3), not runtime StageIds."""

    L01 = "L01"
    L02 = "L02"
    L03 = "L03"
    L04 = "L04"
    L05 = "L05"
    L06 = "L06"
    L07 = "L07"
    L08 = "L08"
    L09 = "L09"
    L10 = "L10"
    L11 = "L11"
    L12 = "L12"
    L13 = "L13"
    L14 = "L14"
    L15 = "L15"
    L16 = "L16"
    L17 = "L17"
    L18 = "L18"
    L19 = "L19"


class Obligation(Enum):
    """What the contract demands of a layer for this run (EL L24-28)."""

    EXECUTE = "EXECUTE"  # substantive execution (or L01/L02/TRIAGE/... never dischargeable)
    DISCHARGE = "DISCHARGE"  # lawful auto-discharge with a mandatory evidence stub


# Canonical layer sequence (EL "The 19 States", L42+).
CANONICAL_ORDER: tuple[Layer, ...] = (
    Layer.L01,
    Layer.L02,
    Layer.L03,
    Layer.L04,
    Layer.L05,
    Layer.L06,
    Layer.L07,
    Layer.L08,
    Layer.L09,
    Layer.L10,
    Layer.L11,
    Layer.L12,
    Layer.L13,
    Layer.L14,
    Layer.L15,
    Layer.L16,
    Layer.L17,
    Layer.L18,
    Layer.L19,
)

# Trace-A auto-discharge set: L03-L11 and L17-L18 (EL L24-25; WSM L62).
TRACE_A_DISCHARGE: frozenset[Layer] = frozenset(
    {
        Layer.L03,
        Layer.L04,
        Layer.L05,
        Layer.L06,
        Layer.L07,
        Layer.L08,
        Layer.L09,
        Layer.L10,
        Layer.L11,
        Layer.L17,
        Layer.L18,
    }
)
TRACE_A_EXECUTE_FULL: frozenset[Layer] = frozenset(
    {
        Layer.L01,
        Layer.L02,
        Layer.L12,
        Layer.L13,
        Layer.L14,
        Layer.L15,
        Layer.L16,
        # L19 executes only if triggered (EL L26); it is never dischargeable.
    }
)
# Trace-B: all 19 in full (EL L27-28).
TRACE_B_EXECUTE_FULL: frozenset[Layer] = frozenset(CANONICAL_ORDER)

# Layers that may NEVER be auto-discharged on any trace (EL L24-26; D1 §6).
NEVER_DISCHARGEABLE: frozenset[Layer] = TRACE_A_EXECUTE_FULL | frozenset({Layer.L19})


@dataclass(frozen=True, slots=True)
class DischargeStub:
    """A lawful-discharge evidence stub (K1) for one auto-discharged layer.

    Structured exactly per WSM L70-72 / EL L29-30, so every discharged transition still carries
    evidence. `result`/`reason`/`by` are fixed for a Trace-A auto-discharge; a Trace-B run never
    produces stubs (nothing is discharged).
    """

    layer: Layer
    result: str = "auto_pass"
    reason: str = "trace_a"
    by: str = "runtime"

    def to_record(self) -> dict[str, str]:
        """The canonical machine record (WSM format + layer tag)."""
        return {
            "layer": self.layer.value,
            "result": self.result,
            "reason": self.reason,
            "by": self.by,
        }


@dataclass(frozen=True, slots=True)
class CeremonyContract:
    """The per-run obligation graph derived from the L02 ceremony-depth decision."""

    trace: str  # "trace_a" | "trace_b"
    obligations: Mapping[Layer, Obligation]

    @property
    def dischargeable(self) -> frozenset[Layer]:
        return frozenset(
            layer for layer, obl in self.obligations.items() if obl is Obligation.DISCHARGE
        )

    @property
    def execute_full(self) -> frozenset[Layer]:
        return frozenset(
            layer for layer, obl in self.obligations.items() if obl is Obligation.EXECUTE
        )

    def obligation_for(self, layer: Layer) -> Obligation:
        try:
            return self.obligations[layer]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"layer {layer} not present in ceremony contract") from exc

    def obligation_plan(self) -> tuple[Layer, ...]:
        """Ordered canonical path (L01→L19) with discharged layers included in place.

        The runtime walks this plan; for a DISCHARGE entry it MUST record the corresponding
        DischargeStub (K1) rather than silently skip. L19 is included (execute-if-triggered) so
        the plan is complete and auditable.
        """
        return tuple(layer for layer in CANONICAL_ORDER if layer in self.obligations)

    def discharge_stubs(self) -> tuple[DischargeStub, ...]:
        """The K1 stubs the runtime MUST emit for this contract (Trace-A discharges only)."""
        if self.trace == "trace_b":
            return ()
        return tuple(
            DischargeStub(layer=layer)
            for layer in CANONICAL_ORDER
            if layer in self.obligations and self.obligations[layer] is Obligation.DISCHARGE
        )

    def assert_discharge_legal(self, layer: Layer) -> None:
        """Reject a bogus discharge of a never-dischargeable layer (fail-closed)."""
        if self.obligation_for(layer) is not Obligation.DISCHARGE:
            raise ValueError(
                f"layer {layer.value} is not dischargeable under trace {self.trace!r} "
                "(never-dischargeable or Trace-B full execution)"
            )


def ceremony_for(trace: str | None) -> CeremonyContract:
    """Build the run ceremony contract from the L02 ceremony-depth decision.

    `trace` is the ceremony value produced by triage ("trace_a"/"trace_b"). A conservative default
    of "trace_b" is used for a missing/unknown depth so an ambiguous classification can never
    silently fast-path (T6; D1 §8 de-escalation-disallowed).
    """
    assert_canonical_lifecycle_bound()
    if trace == "trace_a":
        discharge: frozenset[Layer] = TRACE_A_DISCHARGE
        execute: frozenset[Layer] = TRACE_A_EXECUTE_FULL
    else:  # trace_b, None, "" or any unrecognised value ⇒ full ceremony (never a silent fast-path)
        trace = "trace_b"
        discharge = frozenset()
        execute = TRACE_B_EXECUTE_FULL

    obligations: dict[Layer, Obligation] = {}
    for layer in CANONICAL_ORDER:
        if layer in execute or layer in discharge:
            obligations[layer] = Obligation.EXECUTE if layer in execute else Obligation.DISCHARGE
        else:
            # L01/L02/L12..L16/L19 execute-if-triggered are never dischargeable.
            obligations[layer] = Obligation.EXECUTE
    return CeremonyContract(trace=trace, obligations=obligations)


def discharged_layers_for(trace: str | None) -> frozenset[Layer]:
    """The layers lawfully discharged for `trace` (useful without building a full contract)."""
    return ceremony_for(trace).dischargeable
