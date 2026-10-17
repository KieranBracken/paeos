from __future__ import annotations

import importlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from concept.store import ConceptStore

from tests.concept._inspiration_fixtures import uri_text
from tests.concept.test_candidate_bridge import _build, _seeded


def _rows(path: Path, hypothesis_uri: str) -> list[dict[str, Any]]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return [
            {"uri": row[0], "event_type": row[1], "candidate": json.loads(row[2])["candidate"]}
            for row in connection.execute(
                "SELECT uri, event_type, canonical_json FROM candidate_outbox WHERE hypothesis_uri = ?",
                (hypothesis_uri,),
            ).fetchall()
        ]
    finally:
        connection.close()


def test_repeated_emissions_are_idempotent_and_append_only(tmp_path: Path) -> None:
    path = tmp_path / "idempotent.db"
    source, analogy, transform, candidate = _seeded(path)
    bridge = importlib.import_module("concept.bridge")
    with ConceptStore(path) as store:
        envelope = _build(store, candidate, source, analogy, transform)
        first, second = bridge.emit_candidate(store, envelope), bridge.emit_candidate(store, envelope)
    rows = _rows(path, uri_text(candidate.id))
    assert first == second == rows[0]["uri"]
    assert len(rows) == 1
    assert rows[0]["event_type"] == "EMITTED"
    assert rows[0]["candidate"]["envelope_id"] == uri_text(envelope.envelope_id)
