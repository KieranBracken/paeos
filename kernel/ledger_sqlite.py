"""Durable ledger backend — SQLite `LedgerStore` (DEBT-0003 / FR-5).

Repays DEBT-0003: a **durable, append-only, single-writer** persistence backend behind the
`LedgerStore` narrow waist (kernel/ledger.py), so events survive process restart and multi-session
runs share one ledger. SQLite is single-writer *by nature* (exactly FR-5), append-only here by
construction (INSERT only; `seq` is the primary key so a fork/duplicate seq fails atomically), and
needs no service — the roadmap's Postgres remains the production-scale target and drops in behind
the same Protocol (PAEOS-IP-0003 note; the debt tracks the *capability*, not the engine).

The hash-chain algebra is unchanged — this backend only stores and returns `LedgerRow`s; the
`Ledger` in `ledger.py` computes and verifies the chain over it exactly as over the in-memory store.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from kernel.ledger import Event, ForkRejected, JsonValue, LedgerRow, SingleWriterViolation

__all__ = ["SqliteLedgerStore"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_rows (
    seq        INTEGER PRIMARY KEY,   -- dense, 1-based; PK ⇒ duplicate seq (fork) fails atomically
    timestamp  TEXT    NOT NULL,
    prev_hash  TEXT    NOT NULL,
    row_hash   TEXT    NOT NULL,
    schema_ver INTEGER NOT NULL,
    kind       TEXT    NOT NULL,
    payload    TEXT    NOT NULL        -- canonical JSON of the event payload
);
CREATE TABLE IF NOT EXISTS ledger_writer (
    id     INTEGER PRIMARY KEY CHECK (id = 1),
    owner  TEXT
);
INSERT OR IGNORE INTO ledger_writer (id, owner) VALUES (1, NULL);
"""


class SqliteLedgerStore:
    """A durable `LedgerStore` over a SQLite file. Satisfies the same contract as
    `InMemoryLedgerStore`: strict dense seq, single writer, atomic fork rejection."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self._path), isolation_level=None)  # autocommit
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(_SCHEMA)

    def acquire_writer(self, owner: str) -> None:
        row = self._db.execute("SELECT owner FROM ledger_writer WHERE id = 1").fetchone()
        current: str | None = row[0] if row is not None else None
        if current is not None and current != owner:
            raise SingleWriterViolation(
                f"ledger already owned by writer {current!r}; {owner!r} refused"
            )
        self._db.execute("UPDATE ledger_writer SET owner = ? WHERE id = 1", (owner,))

    def release_writer(self, owner: str) -> None:
        self._db.execute(
            "UPDATE ledger_writer SET owner = NULL WHERE id = 1 AND owner = ?", (owner,)
        )

    def head(self) -> LedgerRow | None:
        row = self._db.execute(
            "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload "
            "FROM ledger_rows ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return _to_row(row) if row is not None else None

    def append_row(self, row: LedgerRow) -> None:
        expected = self.count() + 1
        if row.seq != expected:
            raise ForkRejected(
                f"expected seq {expected} (head+1); got {row.seq} — fork refused"
            )
        try:
            self._db.execute(
                "INSERT INTO ledger_rows "
                "(seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row.seq,
                    row.timestamp,
                    row.prev_hash,
                    row.row_hash,
                    row.event.schema_ver,
                    row.event.kind,
                    json.dumps(dict(row.event.payload), sort_keys=True, separators=(",", ":")),
                ),
            )
        except sqlite3.IntegrityError as exc:  # duplicate seq PK ⇒ a racing fork
            raise ForkRejected(f"seq {row.seq} already present — fork refused") from exc

    def read(self, start: int, end: int | None) -> list[LedgerRow]:
        if start < 1:
            raise ValueError(f"start must be >= 1, got {start}")
        if end is None:
            rows = self._db.execute(
                "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload "
                "FROM ledger_rows WHERE seq >= ? ORDER BY seq",
                (start,),
            ).fetchall()
        else:
            if end < start:
                raise ValueError(f"end ({end}) must be >= start ({start})")
            rows = self._db.execute(
                "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload "
                "FROM ledger_rows WHERE seq >= ? AND seq < ? ORDER BY seq",
                (start, end),
            ).fetchall()
        return [_to_row(r) for r in rows]

    def count(self) -> int:
        row = self._db.execute("SELECT COUNT(*) FROM ledger_rows").fetchone()
        return int(row[0]) if row is not None else 0

    def close(self) -> None:
        self._db.close()


def _to_row(record: tuple[object, ...]) -> LedgerRow:
    seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload = record
    assert isinstance(seq, int)
    assert isinstance(timestamp, str)
    assert isinstance(prev_hash, str)
    assert isinstance(row_hash, str)
    assert isinstance(schema_ver, int)
    assert isinstance(kind, str)
    assert isinstance(payload, str)
    parsed: JsonValue = json.loads(payload)
    assert isinstance(parsed, dict)
    return LedgerRow(
        seq=seq,
        timestamp=timestamp,
        event=Event(schema_ver=schema_ver, kind=kind, payload=parsed),
        prev_hash=prev_hash,
        row_hash=row_hash,
    )
