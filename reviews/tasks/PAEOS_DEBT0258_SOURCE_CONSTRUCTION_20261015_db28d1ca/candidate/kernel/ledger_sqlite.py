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
import threading
import time
from pathlib import Path

from kernel.ledger import (
    GENESIS_HASH,
    ChainCorruption,
    Event,
    ForkRejected,
    JsonValue,
    LedgerRow,
    SingleWriterViolation,
    StaleAuthorityState,
    StaleHead,
    TransitionConflict,
    compute_authority_transition_digest,
    compute_row_hash,
    compute_transition_digest,
    snapshot_event,
    verify_ledger_rows,
)

__all__ = ["SqliteLedgerStore"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_rows (
    seq        INTEGER PRIMARY KEY,   -- dense, 1-based; PK ⇒ duplicate seq (fork) fails atomically
    timestamp  TEXT    NOT NULL,
    prev_hash  TEXT    NOT NULL,
    row_hash   TEXT    NOT NULL,
    schema_ver INTEGER NOT NULL,
    kind       TEXT    NOT NULL,
    payload    TEXT    NOT NULL,       -- canonical JSON of the event payload
    domain_tag TEXT    NOT NULL DEFAULT 'PRODUCTION' CHECK (domain_tag IN ('PRODUCTION', 'SYNTHETIC', 'RECOVERY', 'ADVERSARIAL', 'TEST', 'REPLAY', 'SHADOW', 'SIMULATION')),
    transition_id TEXT,
    transition_digest TEXT,
    authority_predecessor_hash TEXT,
    CHECK ((transition_id IS NULL AND transition_digest IS NULL) OR (transition_id IS NOT NULL AND transition_digest IS NOT NULL)),
    CHECK (authority_predecessor_hash IS NULL OR (transition_id IS NOT NULL AND transition_digest IS NOT NULL))
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
        # `check_same_thread=False` lets the connection be used from ConcurrentScheduler worker
        # threads; `_lock` (reentrant — `append_row` calls `count`) then serializes EVERY connection
        # operation, so a SQLite connection that is not itself concurrency-safe is only ever touched
        # by one thread at a time. K8 single-writer integration under parallel generation (M2).
        self._db = sqlite3.connect(
            str(self._path), isolation_level=None, check_same_thread=False, timeout=5.0
        )  # autocommit
        self._lock = threading.RLock()
        self._db.execute("PRAGMA busy_timeout=5000")
        _enable_wal_with_retry(self._db)
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(_SCHEMA)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            # Re-read schema only after acquiring SQLite's cross-process write lock.
            # This serializes legacy migrators and makes all additive DDL one unit.
            cols = {c[1] for c in self._db.execute("PRAGMA table_info(ledger_rows)").fetchall()}
            if "domain_tag" not in cols:
                self._db.execute(
                    "ALTER TABLE ledger_rows ADD COLUMN domain_tag TEXT NOT NULL DEFAULT 'PRODUCTION'"
                )
            if "transition_id" not in cols:
                self._db.execute("ALTER TABLE ledger_rows ADD COLUMN transition_id TEXT")
            if "transition_digest" not in cols:
                self._db.execute("ALTER TABLE ledger_rows ADD COLUMN transition_digest TEXT")
            if "authority_predecessor_hash" not in cols:
                self._db.execute("ALTER TABLE ledger_rows ADD COLUMN authority_predecessor_hash TEXT")
            self._db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ledger_transition_id_uq "
                "ON ledger_rows(transition_id) WHERE transition_id IS NOT NULL"
            )
            self._db.execute("COMMIT")
        except BaseException:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise

    def acquire_writer(self, owner: str) -> None:
        with self._lock:
            row = self._db.execute("SELECT owner FROM ledger_writer WHERE id = 1").fetchone()
            current: str | None = row[0] if row is not None else None
            if current is not None and current != owner:
                raise SingleWriterViolation(
                    f"ledger already owned by writer {current!r}; {owner!r} refused"
                )
            self._db.execute("UPDATE ledger_writer SET owner = ? WHERE id = 1", (owner,))

    def release_writer(self, owner: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE ledger_writer SET owner = NULL WHERE id = 1 AND owner = ?", (owner,)
            )

    def head(self) -> LedgerRow | None:
        with self._lock:
            row = self._db.execute(
                "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag, "
                "transition_id, transition_digest, authority_predecessor_hash "
                "FROM ledger_rows ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        return _to_row(row) if row is not None else None

    def append_row(self, row: LedgerRow) -> None:
        with self._lock:
            if row.authority_predecessor_hash is not None:
                raise TransitionConflict("authority rows require the compare-and-transition path")
            expected = self.count() + 1
            if row.seq != expected:
                raise ForkRejected(
                    f"expected seq {expected} (head+1); got {row.seq} — fork refused"
                )
            domain = getattr(row, "domain_tag", "PRODUCTION") or "PRODUCTION"
            try:
                self._db.execute(
                    "INSERT INTO ledger_rows "
                    "(seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag, "
                    "transition_id, transition_digest, authority_predecessor_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row.seq,
                        row.timestamp,
                        row.prev_hash,
                        row.row_hash,
                        row.event.schema_ver,
                        row.event.kind,
                        json.dumps(dict(row.event.payload), sort_keys=True, separators=(",", ":")),
                        domain,
                        row.transition_id,
                        row.transition_digest,
                        None,
                    ),
                )
            except sqlite3.IntegrityError as exc:  # duplicate seq PK ⇒ a racing fork
                raise ForkRejected(f"seq {row.seq} already present — fork refused") from exc

    def append_transition(
        self,
        event: Event,
        *,
        writer_id: str | None = None,
        transition_id: str,
        transition_digest: str,
        expected_head_hash: str,
        timestamp: str,
        domain_tag: str,
        fail_on_replay: bool = False,
    ) -> LedgerRow:
        """Cross-process compare-and-append using one SQLite write transaction.

        Transition identity and digest live in the same immutable row as the event.
        The partial unique index is rebuildable from ledger rows and is not a separate
        authority source.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                writer_row = self._db.execute(
                    "SELECT owner FROM ledger_writer WHERE id = 1"
                ).fetchone()
                active_writer = writer_row[0] if writer_row is not None else None
                if writer_id is None or active_writer != writer_id:
                    raise SingleWriterViolation(
                        f"transition append requires the active writer identity; {writer_id!r} refused"
                    )
                stable_event = snapshot_event(event)
                request_digest = compute_transition_digest(
                    stable_event,
                    transition_id=transition_id,
                    expected_head_hash=expected_head_hash,
                    domain_tag=domain_tag,
                )
                if request_digest != transition_digest:
                    raise TransitionConflict("transition digest does not match the exact request")
                prior = self._db.execute(
                    "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag, "
                    "transition_id, transition_digest, authority_predecessor_hash "
                    "FROM ledger_rows WHERE transition_id = ?",
                    (transition_id,),
                ).fetchone()
                if prior is not None:
                    prior_row = _to_row(prior)
                    stored_digest = (
                        compute_authority_transition_digest(
                            prior_row.event,
                            transition_id=transition_id,
                            expected_authority_state_hash=prior_row.authority_predecessor_hash,
                            domain_tag=prior_row.domain_tag,
                        )
                        if prior_row.authority_predecessor_hash is not None
                        else compute_transition_digest(
                            prior_row.event,
                            transition_id=transition_id,
                            expected_head_hash=prior_row.prev_hash,
                            domain_tag=prior_row.domain_tag,
                        )
                    )
                    try:
                        stored_hash = compute_row_hash(
                            prior_row.prev_hash,
                            prior_row.seq,
                            prior_row.timestamp,
                            prior_row.event,
                            domain_tag=prior_row.domain_tag,
                            transition_id=prior_row.transition_id,
                            transition_digest=prior_row.transition_digest,
                            authority_predecessor_hash=prior_row.authority_predecessor_hash,
                        )
                    except ValueError as exc:
                        raise ChainCorruption(
                            f"stored transition {transition_id!r} has incomplete metadata"
                        ) from exc
                    if stored_digest != prior_row.transition_digest or stored_hash != prior_row.row_hash:
                        raise ChainCorruption(
                            f"stored transition {transition_id!r} failed integrity verification"
                        )
                    if prior_row.transition_digest != transition_digest:
                        raise TransitionConflict(
                            f"transition {transition_id!r} already committed with a different digest"
                        )
                    if fail_on_replay:
                        raise TransitionConflict(
                            f"transition {transition_id!r} is already committed; replay refused"
                        )
                    self._db.execute("COMMIT")
                    return prior_row

                count, max_seq = self._db.execute(
                    "SELECT COUNT(*), COALESCE(MAX(seq), 0) FROM ledger_rows"
                ).fetchone()
                if count != max_seq:
                    raise ForkRejected("ledger is not dense; refusing compare-and-transition")
                head = self._db.execute(
                    "SELECT seq, row_hash FROM ledger_rows ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                actual_head_hash = str(head[1]) if head is not None else GENESIS_HASH
                if actual_head_hash != expected_head_hash:
                    raise StaleHead(
                        f"expected ledger head {expected_head_hash}; current head is {actual_head_hash}"
                    )
                seq = (int(head[0]) if head is not None else 0) + 1
                row_hash = compute_row_hash(
                    expected_head_hash,
                    seq,
                    timestamp,
                    stable_event,
                    domain_tag=domain_tag,
                    transition_id=transition_id,
                    transition_digest=transition_digest,
                )
                row = LedgerRow(
                    seq=seq,
                    timestamp=timestamp,
                    event=stable_event,
                    prev_hash=expected_head_hash,
                    row_hash=row_hash,
                    domain_tag=domain_tag,
                    transition_id=transition_id,
                    transition_digest=transition_digest,
                )
                self._db.execute(
                    "INSERT INTO ledger_rows "
                    "(seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag, "
                    "transition_id, transition_digest, authority_predecessor_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row.seq,
                        row.timestamp,
                        row.prev_hash,
                        row.row_hash,
                        row.event.schema_ver,
                        row.event.kind,
                        json.dumps(dict(row.event.payload), sort_keys=True, separators=(",", ":")),
                        row.domain_tag,
                        row.transition_id,
                        row.transition_digest,
                        None,
                    ),
                )
                self._db.execute("COMMIT")
                return row
            except BaseException:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def append_authority_transition(
        self,
        event: Event,
        *,
        writer_id: str | None = None,
        transition_id: str,
        transition_digest: str,
        expected_authority_state_hash: str,
        timestamp: str,
        domain_tag: str,
    ) -> LedgerRow:
        """Compare this domain's authority state and append at the chain tip atomically."""
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                writer_row = self._db.execute(
                    "SELECT owner FROM ledger_writer WHERE id = 1"
                ).fetchone()
                active_writer = writer_row[0] if writer_row is not None else None
                if writer_id is None or active_writer != writer_id:
                    raise SingleWriterViolation(
                        f"authority transition requires the active writer identity; {writer_id!r} refused"
                    )
                existing_rows = self._db.execute(
                    "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag, "
                    "transition_id, transition_digest, authority_predecessor_hash "
                    "FROM ledger_rows ORDER BY seq"
                ).fetchall()
                _, authority_heads = verify_ledger_rows(
                    [_to_row(record) for record in existing_rows]
                )
                authority_head_hash = authority_heads.get(domain_tag, GENESIS_HASH)
                if (
                    len(expected_authority_state_hash) != 64
                    or any(ch not in "0123456789abcdef" for ch in expected_authority_state_hash)
                ):
                    raise ValueError(
                        "expected_authority_state_hash must be a lowercase SHA-256 digest"
                    )

                stable_event = snapshot_event(event)
                request_digest = compute_authority_transition_digest(
                    stable_event,
                    transition_id=transition_id,
                    expected_authority_state_hash=expected_authority_state_hash,
                    domain_tag=domain_tag,
                )
                if request_digest != transition_digest:
                    raise TransitionConflict(
                        "authority transition digest does not match the exact request"
                    )
                prior = self._db.execute(
                    "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag, "
                    "transition_id, transition_digest, authority_predecessor_hash "
                    "FROM ledger_rows WHERE transition_id = ?",
                    (transition_id,),
                ).fetchone()
                if prior is not None:
                    prior_row = _to_row(prior)
                    stored_digest = (
                        compute_authority_transition_digest(
                            prior_row.event,
                            transition_id=transition_id,
                            expected_authority_state_hash=prior_row.authority_predecessor_hash,
                            domain_tag=prior_row.domain_tag,
                        )
                        if prior_row.authority_predecessor_hash is not None
                        else compute_transition_digest(
                            prior_row.event,
                            transition_id=transition_id,
                            expected_head_hash=prior_row.prev_hash,
                            domain_tag=prior_row.domain_tag,
                        )
                    )
                    try:
                        stored_hash = compute_row_hash(
                            prior_row.prev_hash,
                            prior_row.seq,
                            prior_row.timestamp,
                            prior_row.event,
                            domain_tag=prior_row.domain_tag,
                            transition_id=prior_row.transition_id,
                            transition_digest=prior_row.transition_digest,
                            authority_predecessor_hash=prior_row.authority_predecessor_hash,
                        )
                    except ValueError as exc:
                        raise ChainCorruption(
                            f"stored transition {transition_id!r} has incomplete metadata"
                        ) from exc
                    if stored_digest != prior_row.transition_digest or stored_hash != prior_row.row_hash:
                        raise ChainCorruption(
                            f"stored transition {transition_id!r} failed integrity verification"
                        )
                    if prior_row.transition_digest != transition_digest:
                        raise TransitionConflict(
                            f"transition {transition_id!r} already committed with a different digest"
                        )
                    self._db.execute("COMMIT")
                    return prior_row

                if authority_head_hash != expected_authority_state_hash:
                    raise StaleAuthorityState(
                        f"expected authority state {expected_authority_state_hash}; "
                        f"current authority state is {authority_head_hash}"
                    )

                count, max_seq = self._db.execute(
                    "SELECT COUNT(*), COALESCE(MAX(seq), 0) FROM ledger_rows"
                ).fetchone()
                if count != max_seq:
                    raise ForkRejected("ledger is not dense; refusing authority compare-and-transition")
                head = self._db.execute(
                    "SELECT seq, row_hash FROM ledger_rows ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                previous_hash = str(head[1]) if head is not None else GENESIS_HASH
                seq = (int(head[0]) if head is not None else 0) + 1
                row_hash = compute_row_hash(
                    previous_hash,
                    seq,
                    timestamp,
                    stable_event,
                    domain_tag=domain_tag,
                    transition_id=transition_id,
                    transition_digest=transition_digest,
                    authority_predecessor_hash=expected_authority_state_hash,
                )
                row = LedgerRow(
                    seq=seq,
                    timestamp=timestamp,
                    event=stable_event,
                    prev_hash=previous_hash,
                    row_hash=row_hash,
                    domain_tag=domain_tag,
                    transition_id=transition_id,
                    transition_digest=transition_digest,
                    authority_predecessor_hash=expected_authority_state_hash,
                )
                self._db.execute(
                    "INSERT INTO ledger_rows "
                    "(seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag, "
                    "transition_id, transition_digest, authority_predecessor_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row.seq,
                        row.timestamp,
                        row.prev_hash,
                        row.row_hash,
                        row.event.schema_ver,
                        row.event.kind,
                        json.dumps(dict(row.event.payload), sort_keys=True, separators=(",", ":")),
                        row.domain_tag,
                        row.transition_id,
                        row.transition_digest,
                        row.authority_predecessor_hash,
                    ),
                )
                self._db.execute("COMMIT")
                return row
            except BaseException:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def read(self, start: int, end: int | None) -> list[LedgerRow]:
        if start < 1:
            raise ValueError(f"start must be >= 1, got {start}")
        if end is not None and end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
        with self._lock:
            if end is None:
                rows = self._db.execute(
                    "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag, "
                    "transition_id, transition_digest, authority_predecessor_hash "
                    "FROM ledger_rows WHERE seq >= ? ORDER BY seq",
                    (start,),
                ).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag, "
                    "transition_id, transition_digest, authority_predecessor_hash "
                    "FROM ledger_rows WHERE seq >= ? AND seq < ? ORDER BY seq",
                    (start, end),
                ).fetchall()
        return [_to_row(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COUNT(*) FROM ledger_rows").fetchone()
        return int(row[0]) if row is not None else 0

    def close(self) -> None:
        with self._lock:
            self._db.close()


def _to_row(record: tuple[object, ...]) -> LedgerRow:
    transition_id = None
    transition_digest = None
    authority_predecessor_hash = None
    if len(record) >= 11:
        seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag = record[:8]
        transition_id = record[8]
        transition_digest = record[9]
        authority_predecessor_hash = record[10]
        assert isinstance(domain_tag, str)
        assert transition_id is None or isinstance(transition_id, str)
        assert transition_digest is None or isinstance(transition_digest, str)
        assert authority_predecessor_hash is None or isinstance(authority_predecessor_hash, str)
    elif len(record) >= 10:
        seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag = record[:8]
        transition_id = record[8]
        transition_digest = record[9]
        assert isinstance(domain_tag, str)
        assert transition_id is None or isinstance(transition_id, str)
        assert transition_digest is None or isinstance(transition_digest, str)
    elif len(record) >= 8:
        seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload, domain_tag = record[:8]
        assert isinstance(domain_tag, str)
    else:
        if len(record) < 7:
            raise ValueError("ledger row record has fewer than seven fields")
        seq, timestamp, prev_hash, row_hash, schema_ver, kind, payload = (
            record[0], record[1], record[2], record[3], record[4], record[5], record[6]
        )
        domain_tag = "PRODUCTION"
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
        domain_tag=domain_tag,
        transition_id=transition_id,
        transition_digest=transition_digest,
        authority_predecessor_hash=authority_predecessor_hash,
    )


def _enable_wal_with_retry(db: sqlite3.Connection) -> None:
    """Serialize SQLite's non-waiting journal-mode pragma across cold process opens.

    SQLite can report ``database is locked`` immediately for a concurrent WAL-mode
    transition even when the busy timeout is configured. WAL selection is idempotent,
    so bounded retry on that specific bootstrap operation is safe; data operations
    still rely on SQLite transactions, never on this retry or a process-local lock.
    """
    deadline = time.monotonic() + 5.0
    delay = 0.01
    while True:
        try:
            db.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if not ("locked" in message or "busy" in message) or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.25)
