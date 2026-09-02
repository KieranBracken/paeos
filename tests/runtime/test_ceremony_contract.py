"""L02 ceremony contract + Trace-A discharge evidence stubs (K1).

Implements canonical law from `operations/ENGINEERING_LIFECYCLE.md` (v1.3 L18-30) and its derived
machine form `operations/WORKFLOW_STATE_MACHINE.yaml` (ceremony_depth L56-72). Doctrine extraction:
RB-CEREMONY-DEPTH-001 D1 (PAEOS_CEREMONY_DEPTH_DOCTRINE_EXTRACTION_v1.md).

Negative coverage (RB-CEREMONY-DEPTH-001 §16 matrix, G "model misclassification ⇒ deterministic
policy wins"): an unknown/missing ceremony depth must default to full ceremony (Trace-B), never a
silent fast-path; a never-dischargeable layer must refuse discharge.
"""

from __future__ import annotations

import pytest
from kernel.types import WeightClass
from runtime.ceremony import (
    NEVER_DISCHARGEABLE,
    TRACE_A_DISCHARGE,
    Layer,
    Obligation,
    ceremony_for,
    discharged_layers_for,
)
from runtime.task_package import Budget
from runtime.triage import Trace, triage

_BUDGETS = {
    WeightClass.ROUTINE: Budget(50_000, 300, 1),
    WeightClass.SUBSTANTIAL: Budget(200_000, 900, 2),
    WeightClass.KERNEL_TOUCHING: Budget(400_000, 1800, 3),
}

_TRACE_A_DISCHARGE_LAYERS = {
    Layer.L03, Layer.L04, Layer.L05, Layer.L06, Layer.L07, Layer.L08,
    Layer.L09, Layer.L10, Layer.L11, Layer.L17, Layer.L18,
}
_TRACE_A_EXECUTE_LAYERS = {
    Layer.L01, Layer.L02, Layer.L12, Layer.L13, Layer.L14, Layer.L15, Layer.L16,
    Layer.L19,  # execute-if-triggered, never dischargeable (EL L26)
}


def test_trace_a_discharge_and_execute_sets_match_doctrine() -> None:
    c = ceremony_for("trace_a")
    # EL L24-25 / WSM L62: auto-discharge L03-L11 and L17-L18.
    assert c.dischargeable == _TRACE_A_DISCHARGE_LAYERS
    # EL L26: execute L01, L02, L12-L16 in full (L19 if triggered, never dischargeable).
    assert c.execute_full == _TRACE_A_EXECUTE_LAYERS
    assert c.dischargeable == TRACE_A_DISCHARGE
    # Covenant: the union of execute/full and discharge is exactly the 19 canonical layers,
    # i.e. no layer silently disappears and none gets both labels.
    assert c.dischargeable | c.execute_full == set(Layer)
    assert len(c.obligation_plan()) == 19


def test_trace_a_emits_exactly_one_k1_stub_per_discharged_layer() -> None:
    c = ceremony_for("trace_a")
    stubs = c.discharge_stubs()
    assert len(stubs) == 11
    layers = {s.layer for s in stubs}
    assert layers == _TRACE_A_DISCHARGE_LAYERS
    for s in stubs:
        rec = s.to_record()
        assert rec["result"] == "auto_pass"
        assert rec["reason"] == "trace_a"
        assert rec["by"] == "runtime"
        assert rec["layer"] in {layer.value for layer in _TRACE_A_DISCHARGE_LAYERS}


def test_trace_a_execute_full_layers_are_not_dischargeable() -> None:
    c = ceremony_for("trace_a")
    for layer in _TRACE_A_EXECUTE_LAYERS:
        assert c.obligation_for(layer) is Obligation.EXECUTE
        with pytest.raises(ValueError):
            c.assert_discharge_legal(layer)


def test_trace_b_executes_all_layers_and_never_discharges() -> None:
    c = ceremony_for("trace_b")
    assert c.dischargeable == frozenset()
    assert c.execute_full == set(Layer)
    assert c.discharge_stubs() == ()
    assert len(c.obligation_plan()) == 19
    for layer in Layer:
        assert c.obligation_for(layer) is Obligation.EXECUTE
        with pytest.raises(ValueError):
            c.assert_discharge_legal(layer)


def test_unknown_or_missing_depth_defaults_to_full_ceremony() -> None:
    # RB §16 G: LLM "simple" cannot under-classify; deterministic policy wins ⇒ full ceremony.
    for bad in (None, "", "trace_unknown", "TRACE_A"):
        c = ceremony_for(bad)
        assert c.trace == "trace_b"
        assert c.dischargeable == frozenset()
        assert c.discharge_stubs() == ()


def test_never_dischargeable_invariant() -> None:
    # L01/L02/L12..L16/L19 can never be auto-discharged on any trace (EL L24-26; D1 §6).
    non_dischargeable = {Layer.L01, Layer.L02, Layer.L13, Layer.L19}
    assert non_dischargeable <= NEVER_DISCHARGEABLE
    for layer in non_dischargeable:
        with pytest.raises(ValueError):
            ceremony_for("trace_a").assert_discharge_legal(layer)


def test_discharged_layers_helper() -> None:
    assert discharged_layers_for("trace_a") == _TRACE_A_DISCHARGE_LAYERS
    assert discharged_layers_for("trace_b") == frozenset()


# ---- integration with triage (L02 ceremony decision → run ceremony contract) ----


def test_routine_triage_carries_trace_a_contract_with_stubs() -> None:
    d = triage(
        changed_paths=("docs/notes.md",),
        verifiable=True,
        reversible=True,
        budget_by_class=_BUDGETS,
    )
    assert d.trace is Trace.A
    assert d.ceremony.trace == "trace_a"
    stubs = d.discharge_stubs()
    assert len(stubs) == 11
    assert all(s.reason == "trace_a" for s in stubs)


def test_substantial_and_kernel_triage_carry_trace_b_with_no_stubs() -> None:
    for paths, verifiable, reversible in [
        (("runtime/x.py",), False, True),  # SUBSTANTIAL
        (("kernel/gates.py",), True, True),  # KERNEL_TOUCHING (forced full)
    ]:
        d = triage(
            changed_paths=paths,
            verifiable=verifiable,
            reversible=reversible,
            budget_by_class=_BUDGETS,
        )
        assert d.trace is Trace.B
        assert d.ceremony.trace == "trace_b"
        assert d.discharge_stubs() == ()
        # Even a kernel-adjacent call cannot produce Trace-A stubs (T6).
        assert d.ceremony.dischargeable == frozenset()
