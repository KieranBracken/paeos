"""Append-only, hash-chained, single-writer ledger — the PAEOS source of truth (FR-5).

Task B0.1 (PAEOS-8 §10). The ledger is the *only* authority in the system: every state
change is an event appended here, and every projection (goals, seals, …) is derived by
replaying it (B0.10). Three invariants make it trustworthy:

  1. Append-only   — rows are never mutated or deleted; this module exposes no update or
                     delete operation. The only mutating call is ``append``.
  2. Hash-chained  — each row commits to its predecessor's hash, so any tamper to any
                     historical row breaks the chain and is caught by ``verify_chain``.
  3. Single-writer — exactly one writer may append at a time (FR-5). A second writer is
                     refused (``SingleWriterViolation``) and a fork — two rows at one seq —
                     is refused (``ForkRejected``), so the chain is a total order. Together
                     these defeat the T7 fork attack.

Storage sits behind ``LedgerStore`` (K9 narrow waist): the hash-chain algebra lives here
in the TCB and is storage-agnostic. ``InMemoryLedgerStore`` is the reference backend the
property tests drive; the §3-locked Postgres backend implements the same Protocol behind
this waist (deferred: it is forced by B0.10's cross-restart replay test and needs a DB
service, but the algebra it stores is exactly the algebra proven here).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

__all__ = [
    "GENESIS_HASH",
    "ChainCorruption",
    "Event",
    "ForkRejected",
    "InMemoryLedgerStore",
    "JsonValue",
    "Ledger",
    "LedgerError",
    "LedgerRow",
    "LedgerStore",
    "SingleWriterViolation",
    "compute_row_hash",
]

# A JSON value: the payload universe. Recursive alias (PEP 695, py3.12+). Constrained to
# JSON so canonicalisation is total and hashing is deterministic across processes.
type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

# Chain anchor. The genesis row's predecessor. A constant so an empty ledger has a
# well-defined head hash and the first real row is bound to it.
GENESIS_HASH: str = hashlib.sha256(b"PAEOS-LEDGER-GENESIS/v1").hexdigest()


# ---- errors ---------------------------------------------------------------


class LedgerError(Exception):
    """Base for every ledger fault. Callers may catch this to catch all of them."""


class SingleWriterViolation(LedgerError):
    """A second writer tried to attach to a ledger already owned by another (FR-5)."""


class ForkRejected(LedgerError):
    """An append would create a second row at an existing seq — a fork (T7). Refused."""


class ChainCorruption(LedgerError):
    """``verify_chain`` found a broken link: a tampered row, gap, or reordering."""


# ---- value types (immutable) ---------------------------------------------


def _empty_payload() -> dict[str, JsonValue]:
    return {}


@dataclass(frozen=True, slots=True)
class Event:
    """One thing that happened. The unit of append.

    ``schema_ver`` versions the payload shape so projections can migrate (PAEOS-8 §10
    standing caution). ``kind`` is the event discriminator; ``payload`` is JSON.
    """

    schema_ver: int
    kind: str
    payload: dict[str, JsonValue] = field(default_factory=_empty_payload)


@dataclass(frozen=True, slots=True)
class LedgerRow:
    """A committed, hash-chained row. Frozen: rows never change once appended."""

    seq: int  # 1-based, strictly monotonic, dense (no gaps)
    timestamp: str  # ISO-8601 UTC, stored so replay recomputes hashes deterministically
    event: Event
    prev_hash: str  # row_hash of seq-1 (GENESIS_HASH for seq 1)
    row_hash: str  # sha256 over (prev_hash, seq, timestamp, event) — see compute_row_hash


# ---- hashing --------------------------------------------------------------


def _canonical(obj: JsonValue) -> bytes:
    """Deterministic JSON encoding: sorted keys, no whitespace, no NaN/Inf, ASCII-safe."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def compute_row_hash(prev_hash: str, seq: int, timestamp: str, event: Event) -> str:
    """The row's content hash: binds it to its predecessor and its own fields.

    Any change to prev_hash, seq, timestamp, or any event field changes this hash, so
    ``verify_chain`` detects it. Recomputable from stored fields alone (deterministic).
    """
    body: dict[str, JsonValue] = {
        "prev_hash": prev_hash,
        "seq": seq,
        "timestamp": timestamp,
        "schema_ver": event.schema_ver,
        "kind": event.kind,
        "payload": dict(event.payload),
    }
    return hashlib.sha256(_canonical(body)).hexdigest()


# ---- storage seam (K9 narrow waist) --------------------------------------


@runtime_checkable
class LedgerStore(Protocol):
    """The append-only storage contract. Deliberately tiny; no update/delete exists.

    ``append_row`` must be atomic and must reject a seq that already exists (fork guard);
    ``acquire_writer`` must reject a second distinct owner (single-writer guard). A real
    backend (Postgres) satisfies both with a serialisable transaction + unique(seq) and a
    session advisory lock; the in-memory backend satisfies them directly.
    """

    def acquire_writer(self, owner: str) -> None:
        """Claim exclusive write ownership. Raise SingleWriterViolation if held by another."""
        ...

    def release_writer(self, owner: str) -> None:
        """Release ownership if ``owner`` holds it; a no-op otherwise."""
        ...

    def head(self) -> LedgerRow | None:
        """The last row, or None when empty."""
        ...

    def append_row(self, row: LedgerRow) -> None:
        """Append atomically. Raise ForkRejected if ``row.seq`` is not exactly head.seq+1."""
        ...

    def read(self, start: int, end: int | None) -> list[LedgerRow]:
        """Rows with seq in [start, end); end=None means through head. Ascending by seq."""
        ...

    def count(self) -> int:
        """Number of rows appended."""
        ...


class InMemoryLedgerStore:
    """Reference backend: a list guarded by a single-writer token. No durability.

    Used by the property tests and any in-process caller. Enforces the same invariants as
    the production backend: strict dense seq, single writer, atomic fork rejection.
    """

    def __init__(self) -> None:
        self._rows: list[LedgerRow] = []
        self._writer: str | None = None

    def acquire_writer(self, owner: str) -> None:
        if self._writer is not None and self._writer != owner:
            raise SingleWriterViolation(
                f"ledger already owned by writer {self._writer!r}; {owner!r} refused"
            )
        self._writer = owner

    def release_writer(self, owner: str) -> None:
        if self._writer == owner:
            self._writer = None

    def head(self) -> LedgerRow | None:
        return self._rows[-1] if self._rows else None

    def append_row(self, row: LedgerRow) -> None:
        expected = len(self._rows) + 1
        if row.seq != expected:
            raise ForkRejected(
                f"expected seq {expected} (head+1); got {row.seq} — fork refused"
            )
        self._rows.append(row)

    def read(self, start: int, end: int | None) -> list[LedgerRow]:
        if start < 1:
            raise ValueError(f"start must be >= 1, got {start}")
        if end is not None and end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
        hi = len(self._rows) + 1 if end is None else end
        return [r for r in self._rows if start <= r.seq < hi]

    def count(self) -> int:
        return len(self._rows)


# ---- the ledger -----------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class Ledger:
    """The single-writer, append-only, hash-chained log.

    Constructing a Ledger claims the store's writer token, so a second Ledger over the
    same store is refused until the first is closed. Use as a context manager, or call
    ``close()`` to release.
    """

    def __init__(self, store: LedgerStore, *, writer_id: str = "paeos-writer") -> None:
        self._store = store
        self._writer_id = writer_id
        self._closed = False
        store.acquire_writer(writer_id)  # FR-5: refuses a competing writer here

    def append(self, event: Event) -> int:
        """Append ``event``; return its 1-based seq. Never mutates an existing row."""
        self._ensure_open()
        prev = self._store.head()
        prev_hash = prev.row_hash if prev is not None else GENESIS_HASH
        seq = (prev.seq if prev is not None else 0) + 1
        timestamp = _utcnow_iso()
        row_hash = compute_row_hash(prev_hash, seq, timestamp, event)
        row = LedgerRow(
            seq=seq,
            timestamp=timestamp,
            event=event,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
        self._store.append_row(row)  # atomic; ForkRejected if a racer took this seq
        return seq

    def read(self, start: int = 1, end: int | None = None) -> list[LedgerRow]:
        """Rows with seq in [start, end); end=None reads through the head."""
        return self._store.read(start, end)

    def head(self) -> LedgerRow | None:
        """The most recent row, or None when the ledger is empty."""
        return self._store.head()

    def head_hash(self) -> str:
        """The head row's hash, or GENESIS_HASH when empty. The chain's current tip."""
        h = self._store.head()
        return h.row_hash if h is not None else GENESIS_HASH

    def verify_chain(self) -> str:
        """Walk the whole chain; raise ChainCorruption on any break. Return the head hash.

        Detects: a tampered field (recomputed hash mismatch), a rewritten link (prev_hash
        mismatch), and a gap or reorder (seq not dense from 1).
        """
        prev_hash = GENESIS_HASH
        expected_seq = 1
        for row in self._store.read(1, None):
            if row.seq != expected_seq:
                raise ChainCorruption(
                    f"seq gap/reorder: expected {expected_seq}, found {row.seq}"
                )
            if row.prev_hash != prev_hash:
                raise ChainCorruption(
                    f"broken link at seq {row.seq}: prev_hash does not match seq {row.seq - 1}"
                )
            recomputed = compute_row_hash(row.prev_hash, row.seq, row.timestamp, row.event)
            if recomputed != row.row_hash:
                raise ChainCorruption(
                    f"tampered row at seq {row.seq}: content hash mismatch"
                )
            prev_hash = row.row_hash
            expected_seq += 1
        return prev_hash

    def close(self) -> None:
        """Release the writer token. Idempotent."""
        if not self._closed:
            self._store.release_writer(self._writer_id)
            self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise LedgerError("ledger is closed; its writer token was released")

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def tamper(row: LedgerRow, **changes: object) -> LedgerRow:
    """Test helper: return a copy of ``row`` with fields replaced (to forge a bad chain).

    Lives beside the ledger so the tamper-detection tests can construct corrupted rows
    without reaching into a store's internals. Not used by production paths.
    """
    return replace(row, **changes)  # type: ignore[arg-type]
