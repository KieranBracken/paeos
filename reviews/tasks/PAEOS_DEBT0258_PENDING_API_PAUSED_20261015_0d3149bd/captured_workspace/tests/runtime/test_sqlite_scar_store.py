"""Tests for SqliteScarStore module export (backlog/intakes/durable_scar_store.json)."""

from __future__ import annotations

from pathlib import Path

from runtime.memory import ScarDraft
from runtime.memory.sqlite_store import SqliteScarStore


def test_sqlite_scar_store_persistence_and_match(tmp_path: Path) -> None:
    store1 = SqliteScarStore(tmp_path)
    draft = ScarDraft(
        signature=frozenset({"domain:sakg", "failure:timeout"}),
        lesson="persist the institutional lesson",
        detection="assert the lesson is injected",
        severity="high",
    )
    scar1 = store1.record_scar(draft)
    assert scar1 is not None
    store1.close()

    # Open a fresh instance on the same directory
    store2 = SqliteScarStore(tmp_path)
    matched = store2.match_scars("domain:sakg,failure:timeout,extra:tag")
    assert len(matched) == 1
    assert matched[0].id == scar1.id
    assert matched[0].lesson == "persist the institutional lesson"
    store2.close()
