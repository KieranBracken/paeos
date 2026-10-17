"""Verifier-owned fault catalog coverage for Gate F Task 2."""

from __future__ import annotations

import json
from pathlib import Path


def test_public_catalog_exposes_classes_without_expected_reasons() -> None:
    root = Path(__file__).parents[2] / "fixtures" / "autonomy"
    public = json.loads((root / "public" / "fault_classes.json").read_text(encoding="utf-8"))
    assert public["schema_version"] == 1
    assert len(public["classes"]) == 19
    assert all(isinstance(value, str) for value in public["classes"])


def test_verifier_catalog_covers_every_public_fault_class() -> None:
    root = Path(__file__).parents[2] / "fixtures" / "autonomy"
    public = json.loads((root / "public" / "fault_classes.json").read_text(encoding="utf-8"))
    hidden = json.loads((root / "z0" / "fault_catalog.json").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in hidden["entries"]}
    assert set(entries) == set(public["classes"])
    assert all(entry["expected_failure_code"] for entry in entries.values())
