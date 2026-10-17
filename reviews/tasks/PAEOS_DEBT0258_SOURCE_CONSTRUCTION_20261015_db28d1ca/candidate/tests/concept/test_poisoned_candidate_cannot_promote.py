from __future__ import annotations

import ast
import importlib
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from concept.model import ScoreVector
from concept.store import ConceptStore

from tests.concept._inspiration_fixtures import uri_text
from tests.concept.test_candidate_bridge import _build, _seeded


def test_high_novelty_candidate_stays_untrusted_and_cannot_change_truth(tmp_path: Path) -> None:
    path = tmp_path / "poisoned.db"
    source, analogy, transform, candidate = _seeded(path)
    bridge = importlib.import_module("concept.bridge")
    with ConceptStore(path) as store:
        envelope = _build(store, candidate, source, analogy, transform)
        poisoned = replace(envelope, score_vectors=ScoreVector(novelty="1.000000", provenance_completeness="0.100000"))
        bridge.emit_candidate(store, poisoned)
        stored = store.get_node(uri_text(candidate.id))
    assert stored is not None
    assert stored.payload.lifecycle == "candidate"


def test_truth_status_tampering_is_rejected_without_an_outbox_row(tmp_path: Path) -> None:
    path = tmp_path / "tampered.db"
    source, analogy, transform, candidate = _seeded(path)
    bridge = importlib.import_module("concept.bridge")
    with ConceptStore(path) as store:
        envelope = _build(store, candidate, source, analogy, transform)
        with pytest.raises(bridge.TruthBearingStatusForbiddenError):
            bridge.emit_candidate(store, replace(envelope, proposal_kind="accepted"))
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT uri FROM candidate_outbox WHERE hypothesis_uri = ?",
            (uri_text(candidate.id),),
        ).fetchall()
    finally:
        connection.close()
    assert rows == []


def test_bridge_has_no_execution_or_external_authority_call_sites() -> None:
    bridge = importlib.import_module("concept.bridge")
    bridge_file = bridge.__file__
    assert bridge_file is not None
    tree = ast.parse(Path(bridge_file).read_text(encoding="utf-8"))
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert calls.isdisjoint({"execute", "executemany", "promote", "broker", "publish"})
