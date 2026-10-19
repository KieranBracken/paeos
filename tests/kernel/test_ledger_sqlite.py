"""DEBT-0003 tests — the durable SQLite ledger backend satisfies the LedgerStore contract and
persists across restart (PAEOS-8 §10 / FR-5)."""

from __future__ import annotations

import threading
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


def test_compare_and_append_serializes_revocation_across_connections(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    store_a = SqliteLedgerStore(db)
    ledger_a = Ledger(store_a, writer_id="b00-test")
    store_b = SqliteLedgerStore(db)
    ledger_b = Ledger(store_b, writer_id="b00-test")
    expected_head = ledger_a.head_hash()

    ledger_a.append(Event(1, "admission_revoked", {"admission_ref": "fixture"}))
    with pytest.raises(ForkRejected):
        ledger_b.append_if_head(
            Event(1, "send_claimed", {"logical_job_id": "fixture-job"}),
            expected_head_hash=expected_head,
            domain_tag="TEST",
        )

    assert [row.event.kind for row in ledger_b.read()] == ["admission_revoked"]
    assert ledger_b.verify_chain() == ledger_b.head_hash()
    ledger_a.close()
    store_a.close()
    ledger_b.close()
    store_b.close()


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


def test_concurrent_appends_produce_one_dense_unforked_chain(tmp_path: Path) -> None:
    # K8 integration under M2 concurrency: many threads append to ONE ledger at once. The serialized
    # compose-and-commit (Ledger._append_lock) + the store's connection lock must yield a dense,
    # gap-free, hash-verified chain with every event present exactly once — no fork, no lost write.
    ledger = Ledger(SqliteLedgerStore(tmp_path / "ledger.db"))
    n_threads, per_thread = 8, 25
    barrier = threading.Barrier(n_threads)  # release all threads at once to maximise contention

    def worker(t: int) -> None:
        barrier.wait()
        for i in range(per_thread):
            ledger.append(Event(1, "e", {"t": t, "i": i}))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    rows = ledger.read()
    assert [r.seq for r in rows] == list(range(1, n_threads * per_thread + 1))  # dense, no gaps
    assert ledger.verify_chain() == ledger.head_hash()  # chain intact (no fork/tamper)
    submitted = {(t, i) for t in range(n_threads) for i in range(per_thread)}
    assert {(r.event.payload["t"], r.event.payload["i"]) for r in rows} == submitted  # none lost


def test_concurrent_independent_connections_retry_stale_append(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    store_a = SqliteLedgerStore(db)
    store_b = SqliteLedgerStore(db)
    ledger_a = Ledger(store_a, writer_id="b00-test")
    ledger_b = Ledger(store_b, writer_id="b00-test")
    barrier = threading.Barrier(2)

    def delay_first_head_read(store: SqliteLedgerStore) -> None:
        original_head = store.head
        first = True

        def delayed_head():
            nonlocal first
            row = original_head()
            if first:
                first = False
                barrier.wait(timeout=5)
            return row

        store.head = delayed_head  # type: ignore[method-assign]

    for store in (store_a, store_b):
        delay_first_head_read(store)

    failures: list[BaseException] = []

    def append(ledger: Ledger, kind: str) -> None:
        try:
            ledger.append(Event(1, kind, {"writer": kind}))
        except BaseException as exc:  # captured so thread failures reach the test
            failures.append(exc)

    threads = [
        threading.Thread(target=append, args=(ledger_a, "writer-a")),
        threading.Thread(target=append, args=(ledger_b, "writer-b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    rows = ledger_a.read()
    assert not any(thread.is_alive() for thread in threads)
    assert failures == []
    assert [row.seq for row in rows] == [1, 2]
    assert {row.event.kind for row in rows} == {"writer-a", "writer-b"}
    assert ledger_a.verify_chain() == ledger_a.head_hash()
    ledger_a.close()
    store_a.close()
    ledger_b.close()
    store_b.close()
