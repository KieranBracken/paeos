"""Tests for canonical layer L07 Trade-off Mitigation (StageId.MITIGATION)."""

from kernel.lifecycle import StageId, WeightClass, is_legal
from runtime.mitigation import (
    MitigationCatalogue,
    TradeoffHazard,
    mitigate_tradeoffs,
)


def test_l07_canonical_stage_edges() -> None:
    """Verify that TRADEOFF -> MITIGATION -> DESIGN walk edges are legal across all weight classes."""
    for wc in WeightClass:
        assert is_legal(StageId.TRADEOFF, StageId.MITIGATION, wc), f"TRADEOFF->MITIGATION illegal for {wc}"
        assert is_legal(StageId.MITIGATION, StageId.DESIGN, wc), f"MITIGATION->DESIGN illegal for {wc}"


def test_mitigate_tradeoffs_catalogue_emission() -> None:
    """Verify that mitigate_tradeoffs emits a non-empty MitigationCatalogue with bound safeguards."""
    hazards = [
        TradeoffHazard(id="H1", title="Latency spike under burst", severity="HIGH"),
        TradeoffHazard(id="H2", title="Memory growth during bulk sync", severity="MEDIUM"),
    ]
    catalogue = mitigate_tradeoffs(hazards)
    assert isinstance(catalogue, MitigationCatalogue)
    assert len(catalogue.safeguards) > 0
    assert catalogue.has_high_severity_coverage()


def test_unmitigated_high_severity_hazard_fails_guard() -> None:
    """Verify that an unmitigated HIGH severity hazard renders catalogue invalid/uncovered."""
    catalogue = MitigationCatalogue(
        safeguards=[],
        accepted_risks=[],
        hazards=[TradeoffHazard(id="H1", title="Critical data loss", severity="HIGH")],
    )
    assert not catalogue.has_high_severity_coverage()
