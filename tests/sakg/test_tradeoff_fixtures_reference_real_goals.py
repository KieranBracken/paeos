"""Ensure tradeoff fixtures bind to the archaeological corpus and real sealed goals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/sakg/fixtures/tradeoff"
CATALOG = ROOT / "ops/sakg/SAKG_TRADEOFF_AXIS_CATALOG.json"
AST = ROOT / "ops/sakg/SAKG_AST_INVENTORY.json"
GOAL_FIXTURES = ROOT / "tests/sakg/fixtures/extract"


def _entries() -> dict[str, Any]:
    data = json.loads(AST.read_text())
    return {entry["path"]: entry for entry in data["entries"]}


def test_axis_catalog_binds_to_ast_inventory_and_source_anchors() -> None:
    catalog = json.loads(CATALOG.read_text())
    assert catalog["schema"] == "paeos.sakg.tradeoff-axis-catalog/v1"
    assert catalog["ast_inventory_sha256"] == hashlib.sha256(AST.read_bytes()).hexdigest()
    entries = _entries()
    assert len(catalog["axes"]) >= 10
    axes = {item["axis"] for item in catalog["axes"]}
    assert {"latency", "accuracy", "cost", "reliability", "complexity", "security", "safety"} <= axes
    for item in catalog["axes"]:
        entry = entries[item["source_path"]]
        assert entry["sha256"] == item["source_sha256"]
        assert item["heading"] in entry["document"]["headings"]
        assert item["excerpt"]


def test_fixtures_reference_catalog_axes_and_sealed_goal_decisions() -> None:
    catalog = json.loads(CATALOG.read_text())
    axis_map: dict[str, list[Any]] = {}
    for item in catalog["axes"]:
        axis_map.setdefault(item["axis"], []).append(item)
    goals = {item["goal_id"]: item for item in catalog["goals"]}
    assert len(goals) == 3
    for path in sorted(FIXTURES.glob("*.json")):
        fixture = json.loads(path.read_text())
        assert all(axis in axis_map for axis in fixture["query"]["axes"])
        source = fixture["source"]
        assert source["inventory_sha256"] == catalog["ast_inventory_sha256"]
        assert all(any(item["source_path"] == source["path"] for item in axis_map[axis]) for axis in fixture["query"]["axes"])
        goal = goals[fixture["query"]["goal_id"]]
        bundle_path = ROOT / goal["bundle_path"]
        assert hashlib.sha256(bundle_path.read_bytes()).hexdigest() == goal["bundle_sha256"]
        bundle = json.loads(bundle_path.read_text())
        decision_ids = {node["id"] for node in bundle["nodes"] if node["type"] == "Decision"}
        assert goal["decision_id"] in decision_ids
        assert all(result["decision_id"] == goal["decision_id"] for result in fixture["expected"]["results"])
