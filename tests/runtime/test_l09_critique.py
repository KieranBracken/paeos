"""Verification test suite for Canonical Layer L09 Multi-Perspective Critique."""

from __future__ import annotations

import pytest

from runtime.critique import CritiqueStance, MultiPerspectiveCritiqueEngine


def test_critique_evaluates_all_eight_stances() -> None:
    engine = MultiPerspectiveCritiqueEngine()
    proposal = {"title": "L09 Multi-Perspective Critique Integration", "changes": ["runtime/critique.py"]}
    report = engine.evaluate(proposal)

    assert len(report.evaluations) == 8
    assert report.passed_all is True
    assert "Critique passed" in report.summary

    stances_evaluated = {e.stance for e in report.evaluations}
    assert len(stances_evaluated) == 8
    for stance in CritiqueStance:
        assert stance in stances_evaluated


def test_critique_report_serialization() -> None:
    engine = MultiPerspectiveCritiqueEngine()
    proposal = {"title": "Test Proposal"}
    report = engine.evaluate(proposal)
    report_dict = report.to_dict()

    assert report_dict["passed_all"] is True
    assert len(report_dict["evaluations"]) == 8
    assert report_dict["evaluations"][0]["stance"] == "SECURITY"
