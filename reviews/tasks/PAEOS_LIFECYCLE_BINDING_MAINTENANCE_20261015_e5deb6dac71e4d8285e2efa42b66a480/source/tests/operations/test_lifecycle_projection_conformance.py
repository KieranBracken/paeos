"""Deterministic conformance checks for lifecycle projections under IP-0017."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PATH = REPO_ROOT / "operations" / "ENGINEERING_LIFECYCLE.md"
PROJECTION_PATH = REPO_ROOT / "operations" / "WORKFLOW_STATE_MACHINE.yaml"
CANONICAL_SHA256 = "0bc717cc738a27b126c48d2f9a034998ad7d4a29cca61eeff7f1e63149d8dfae"
EXPECTED_NAMES = (
    "Intake",
    "Triage",
    "First-Principles Re-Derivation",
    "Ambitious Ideation",
    "Frontier Research",
    "Trade-off Analysis",
    "Trade-off Mitigation",
    "System Design",
    "Multi-Perspective Critique",
    "Adversarial Review",
    "Formal Planning",
    "Branch Implementation",
    "Verification",
    "Independent Audit",
    "Documentation & Ledger",
    "Promotion Decision",
    "Retrospective + Constitutional Review",
    "Knowledge Extraction",
    "Constitutional Evolution",
)


def _projection() -> dict[str, object]:
    loaded = yaml.safe_load(PROJECTION_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_canonical_lifecycle_bytes_remain_founder_ratified_v13() -> None:
    assert hashlib.sha256(CANONICAL_PATH.read_bytes()).hexdigest() == CANONICAL_SHA256
    assert "This is **v1.3**" in CANONICAL_PATH.read_text(encoding="utf-8")


def test_executable_projection_declares_derived_authority_binding() -> None:
    projection = _projection()
    assert projection["version"] == "1.3"
    assert projection["authority"] == {
        "classification": "DERIVED_EXECUTABLE_PROJECTION",
        "canonical_path": "operations/ENGINEERING_LIFECYCLE.md",
        "canonical_version": "1.3",
        "canonical_sha256": CANONICAL_SHA256,
        "precedence": "canonical_prose_controls_unless_lawfully_amended",
        "founder_disposition": "PAEOS-IP-0017",
    }


def test_executable_projection_has_exact_l01_l19_order_and_names() -> None:
    states = _projection()["states"]
    assert isinstance(states, dict)
    assert tuple(states) == tuple(f"L{number:02d}" for number in range(1, 20))
    assert tuple(state["name"] for state in states.values()) == EXPECTED_NAMES


def test_executable_projection_preserves_v13_separation_of_powers() -> None:
    states = _projection()["states"]
    assert isinstance(states, dict)
    assert states["L12"]["role"] == "builder"
    assert states["L13"]["role"] == ["auditor", "runtime", "adversary"]
    assert states["L14"]["role"] == "auditor"
    assert states["L15"]["role"] == ["runtime", "builder"]
    assert states["L16"]["role"] == ["integrator", "founder"]


def test_trace_a_discharge_is_recorded_and_never_claimed_as_skip() -> None:
    trace_a = _projection()["ceremony_depth"]["levels"]["trace_a"]
    assert trace_a["auto_discharge"] == [
        "L03",
        "L04",
        "L05",
        "L06",
        "L07",
        "L08",
        "L09",
        "L10",
        "L11",
        "L17",
        "L18",
    ]
    assert trace_a["execute_full"] == ["L01", "L02", "L12", "L13", "L14", "L15", "L16"]
    assert "auto_discharge != skip" in _projection()["ceremony_depth"]["rule"]


def test_runtime_stage_bindings_cover_each_layer_without_synthetic_layers() -> None:
    from kernel.types import StageId
    from runtime.ceremony import CANONICAL_ORDER, Layer
    from runtime.lifecycle_projection import (
        CANONICAL_LAYER_STAGE_MAP,
        NON_LIFECYCLE_CONTROL_STAGES,
        assert_lifecycle_projection_conformant,
    )

    assert_lifecycle_projection_conformant()
    assert tuple(CANONICAL_LAYER_STAGE_MAP) == CANONICAL_ORDER
    assert CANONICAL_LAYER_STAGE_MAP[Layer.L10] is StageId.ADVERSARIAL_REVIEW
    assert CANONICAL_LAYER_STAGE_MAP[Layer.L13] is StageId.VERIFY
    assert CANONICAL_LAYER_STAGE_MAP[Layer.L14] is None
    assert CANONICAL_LAYER_STAGE_MAP[Layer.L15] is StageId.LEDGER_SYNC
    assert CANONICAL_LAYER_STAGE_MAP[Layer.L16] is StageId.SEAL
    assert frozenset(
        {StageId.RAW, StageId.IMPROVE_RUNTIME, StageId.RESTART}
    ) == NON_LIFECYCLE_CONTROL_STAGES
    mapped = {stage for stage in CANONICAL_LAYER_STAGE_MAP.values() if stage is not None}
    assert mapped | NON_LIFECYCLE_CONTROL_STAGES == set(StageId)
    assert mapped & NON_LIFECYCLE_CONTROL_STAGES == set()


def test_orchestrator_uses_authoritative_projection_slices() -> None:
    from runtime.lifecycle_projection import FRONTEND_PLANNER_STAGES, POST_PROMOTION_STAGES
    from runtime.orchestrator import FRONTEND_PLANNER_STAGES as ORCHESTRATOR_FRONTEND
    from runtime.orchestrator import POST_SEAL_EVOLUTION_STAGES as ORCHESTRATOR_POST_SEAL

    assert ORCHESTRATOR_FRONTEND == FRONTEND_PLANNER_STAGES
    assert ORCHESTRATOR_POST_SEAL == POST_PROMOTION_STAGES


def test_runtime_guard_accepts_exact_approved_lifecycle() -> None:
    from runtime.ceremony import assert_canonical_lifecycle_bound

    assert hashlib.sha256(CANONICAL_PATH.read_bytes()).hexdigest() == CANONICAL_SHA256
    assert_canonical_lifecycle_bound(CANONICAL_PATH)
    assert_canonical_lifecycle_bound()


def test_runtime_guard_rejects_one_byte_change_preserving_version(tmp_path: Path) -> None:
    from runtime.ceremony import assert_canonical_lifecycle_bound

    approved = CANONICAL_PATH.read_bytes()
    assert approved.startswith(b"# PAEOS")
    modified = b"!" + approved[1:]
    assert b"This is **v1.3**" in modified
    altered = tmp_path / "one-byte-lifecycle.md"
    altered.write_bytes(modified)
    with pytest.raises(RuntimeError, match="source hash does not match"):
        assert_canonical_lifecycle_bound(altered)


def test_runtime_guard_rejects_wrong_prose_with_valid_version(tmp_path: Path) -> None:
    from runtime.ceremony import assert_canonical_lifecycle_bound

    wrong = tmp_path / "wrong-lifecycle.md"
    wrong.write_bytes(b"This is **v1.3**\nUnapproved lifecycle content.\n")
    with pytest.raises(RuntimeError, match="source hash does not match"):
        assert_canonical_lifecycle_bound(wrong)


def test_runtime_guard_rejects_unavailable_lifecycle(tmp_path: Path) -> None:
    from runtime.ceremony import assert_canonical_lifecycle_bound

    with pytest.raises(RuntimeError, match="source is unavailable"):
        assert_canonical_lifecycle_bound(tmp_path / "absent-lifecycle.md")
