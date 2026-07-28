"""DEBT-0003 tests — the durable SQLite ledger backend satisfies the LedgerStore contract and
persists across restart (PAEOS-8 §10 / FR-5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from kernel.ledger import (
    ChainCorruption,
    Event,
    ForkRejected,
    Ledger,
    SingleWriterViolation,
    tamper,
)
from kernel.ledger_sqlite import SqliteLedgerStore


def test_ledger_over_sqlite_appends_and_verifies(tmp_path: Path) -> None:
    ledger = Ledger(SqliteLedgerStore(tmp_path / "ledger.db"))
    for i in range(5):
        assert ledger.append(Event(1, "e", {"i": i})) == i + 1
    assert [r.seq for r in ledger.read()] == [1, 2, 3, 4, 5]
    assert ledger.verify_chain() == ledger.head_hash()


def test_persists_across_restart(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    store = SqliteLedgerStore(db)
    ledger = Ledger(store)
    ledger.append(Event(1, "durable", {"note": "survives"}))
    head_before = ledger.head_hash()
    store.close()  # simulate process exit

    reopened = SqliteLedgerStore(db)
    ledger2 = Ledger(reopened, writer_id="paeos-writer")
    assert reopened.count() == 1
    assert ledger2.head_hash() == head_before  # same chain head after restart
    assert ledger2.verify_chain() == head_before
    assert ledger2.read()[0].event.payload == {"note": "survives"}


def test_single_writer_refused_on_sqlite(tmp_path: Path) -> None:
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    Ledger(store, writer_id="alpha")
    with pytest.raises(SingleWriterViolation):
        Ledger(store, writer_id="beta")


def test_fork_refused_on_sqlite(tmp_path: Path) -> None:
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    ledger = Ledger(store)
    ledger.append(Event(1, "a"))
    forged = tamper(ledger.read(1, 2)[0], seq=3)  # non-dense seq
    with pytest.raises(ForkRejected):
        store.append_row(forged)


def test_tamper_detected_on_reopened_ledger(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    store = SqliteLedgerStore(db)
    ledger = Ledger(store)
    ledger.append(Event(1, "a", {"x": 1}))
    ledger.append(Event(1, "b", {"x": 2}))
    # tamper a row directly in the database, then reopen and verify the chain catches it
    store._db.execute("UPDATE ledger_rows SET payload = '{\"x\": 999}' WHERE seq = 1")
    store.close()
    ledger2 = Ledger(SqliteLedgerStore(db))
    with pytest.raises(ChainCorruption):
        ledger2.verify_chain()
