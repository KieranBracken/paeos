"""Append-only, hash-chained, single-writer ledger — the PAEOS source of truth (FR-5).

Task B0.1 (PAEOS-8 §10). The ledger is the *only* authority in the system: every state
change is an event appended here, and every projection (goals, seals, …) is derived by
replaying it (B0.10). Three invariants make it trustworthy:

  1. Append-only   — rows are never mutated or deleted; this module exposes no update or
                     delete operation. ``append`` adds an ordinary event and ``append_once``
                     adds or recovers one identity-bound compare-and-transition.
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
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol, cast, runtime_checkable

from kernel.types import DomainTag

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
    "StaleAuthorityState",
    "StaleHead",
    "TransitionConflict",
    "compute_authority_transition_digest",
    "compute_row_hash",
    "compute_transition_digest",
    "verify_ledger_rows",
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


class TransitionConflict(LedgerError):
    """A transition identity was replayed with a different exact request digest."""


class StaleHead(LedgerError):
    """A compare-and-transition was based on a head that is no longer current."""


class StaleAuthorityState(LedgerError):
    """An authority transition was based on an obsolete authority predecessor."""


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
    domain_tag: str = "PRODUCTION"  # ELH-10 state segregation (PRODUCTION, TEST, REPLAY, etc.)
    transition_id: str | None = None
    transition_digest: str | None = None
    authority_predecessor_hash: str | None = None


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


def snapshot_event(event: Event) -> Event:
    """Return a detached JSON snapshot before policy, digest, or storage decisions."""
    payload_value = json.loads(_canonical(dict(event.payload)))
    if not isinstance(payload_value, dict):
        raise ValueError("event payload must be a JSON object")
    return Event(event.schema_ver, event.kind, cast(dict[str, JsonValue], payload_value))


def compute_row_hash(
    prev_hash: str,
    seq: int,
    timestamp: str,
    event: Event,
    domain_tag: str | None = "PRODUCTION",
    transition_id: str | None = None,
    transition_digest: str | None = None,
    authority_predecessor_hash: str | None = None,
) -> str:
    """The row's content hash: binds it to its predecessor and its own fields.

    Any change to prev_hash, seq, timestamp, domain_tag (when specified), transition
    identity/digest (when present), or any event field changes this hash, so
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
    if (transition_id is None) != (transition_digest is None):
        raise ValueError("transition_id and transition_digest must be both set or both absent")
    if authority_predecessor_hash is not None and transition_id is None:
        raise ValueError("authority predecessor metadata requires a transition identity")
    if transition_id is not None:
        body["transition_id"] = transition_id
        body["transition_digest"] = transition_digest
    if authority_predecessor_hash is not None:
        body["authority_predecessor_hash"] = authority_predecessor_hash
    if domain_tag is not None:
        body["domain_tag"] = domain_tag
    return hashlib.sha256(_canonical(body)).hexdigest()


def compute_transition_digest(
    event: Event,
    *,
    transition_id: str,
    expected_head_hash: str,
    domain_tag: str,
) -> str:
    """Digest the exact compare-and-transition request independently of its timestamp."""
    body: dict[str, JsonValue] = {
        "transition_id": transition_id,
        "expected_head_hash": expected_head_hash,
        "domain_tag": domain_tag,
        "schema_ver": event.schema_ver,
        "kind": event.kind,
        "payload": dict(event.payload),
    }
    return hashlib.sha256(_canonical(body)).hexdigest()


def compute_authority_transition_digest(
    event: Event,
    *,
    transition_id: str,
    expected_authority_state_hash: str,
    domain_tag: str,
) -> str:
    """Digest an authority transition without binding it to incidental ledger-tail rows."""
    body: dict[str, JsonValue] = {
        "transition_mode": "AUTHORITY_STATE/v1",
        "transition_id": transition_id,
        "expected_authority_state_hash": expected_authority_state_hash,
        "domain_tag": domain_tag,
        "schema_ver": event.schema_ver,
        "kind": event.kind,
        "payload": dict(event.payload),
    }
    return hashlib.sha256(b"PAEOS-AUTHORITY-TRANSITION/v1\0" + _canonical(body)).hexdigest()


def verify_ledger_rows(rows: Sequence[LedgerRow]) -> tuple[str, dict[str, str]]:
    """Verify one ledger snapshot; return its physical head and per-domain authority heads.

    Storage backends call this while holding their own serialization boundary before
    accepting an authority transition. That prevents a valid-looking append from
    extending a corrupted historical chain.
    """
    prev_hash = GENESIS_HASH
    authority_heads: dict[str, str] = {}
    expected_seq = 1
    for row in rows:
        if row.seq != expected_seq:
            raise ChainCorruption(
                f"seq gap/reorder: expected {expected_seq}, found {row.seq}"
            )
        if row.prev_hash != prev_hash:
            raise ChainCorruption(
                f"broken link at seq {row.seq}: prev_hash does not match seq {row.seq - 1}"
            )
        domain = getattr(row, "domain_tag", None)
        try:
            recomputed = compute_row_hash(
                row.prev_hash,
                row.seq,
                row.timestamp,
                row.event,
                domain_tag=domain or "PRODUCTION",
                transition_id=getattr(row, "transition_id", None),
                transition_digest=getattr(row, "transition_digest", None),
                authority_predecessor_hash=getattr(row, "authority_predecessor_hash", None),
            )
        except ValueError as exc:
            raise ChainCorruption(f"invalid transition metadata at seq {row.seq}") from exc
        if row.transition_id is not None:
            if row.authority_predecessor_hash is not None:
                authority_domain = domain or "PRODUCTION"
                if row.authority_predecessor_hash != authority_heads.get(
                    authority_domain, GENESIS_HASH
                ):
                    raise ChainCorruption(
                        f"authority predecessor chain is broken at seq {row.seq}"
                    )
                expected_transition_digest = compute_authority_transition_digest(
                    row.event,
                    transition_id=row.transition_id,
                    expected_authority_state_hash=row.authority_predecessor_hash,
                    domain_tag=domain or "PRODUCTION",
                )
            else:
                expected_transition_digest = compute_transition_digest(
                    row.event,
                    transition_id=row.transition_id,
                    expected_head_hash=row.prev_hash,
                    domain_tag=domain or "PRODUCTION",
                )
            if expected_transition_digest != row.transition_digest:
                raise ChainCorruption(f"tampered transition digest at seq {row.seq}")
        elif row.authority_predecessor_hash is not None:
            raise ChainCorruption(f"authority marker lacks transition identity at seq {row.seq}")
        if (
            recomputed != row.row_hash
            and row.transition_id is None
            and row.transition_digest is None
            and (domain is None or domain == "PRODUCTION")
        ):
            # Historical P1 rows predate domain_tag being bound into their hash.
            legacy_hash = compute_row_hash(
                row.prev_hash,
                row.seq,
                row.timestamp,
                row.event,
                domain_tag=None,
            )
            if legacy_hash == row.row_hash:
                recomputed = legacy_hash
        if recomputed != row.row_hash:
            raise ChainCorruption(f"tampered row at seq {row.seq}: content hash mismatch")
        if row.authority_predecessor_hash is not None:
            authority_heads[domain or "PRODUCTION"] = row.row_hash
        prev_hash = row.row_hash
        expected_seq += 1
    return prev_hash, authority_heads


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
        """Atomically compare the head and append-or-return one idempotent transition.

        When ``fail_on_replay`` is true, an identical existing transition is reported as a
        conflict instead of being returned. This lets single-use callers distinguish the
        process that durably created a claim from callers that are only replaying it.
        """
        ...

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
        """Compare this domain's authority predecessor and append at the physical chain tip."""
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
        self._lock = threading.RLock()

    def acquire_writer(self, owner: str) -> None:
        with self._lock:
            if self._writer is not None and self._writer != owner:
                raise SingleWriterViolation(
                    f"ledger already owned by writer {self._writer!r}; {owner!r} refused"
                )
            self._writer = owner

    def release_writer(self, owner: str) -> None:
        with self._lock:
            if self._writer == owner:
                self._writer = None

    def head(self) -> LedgerRow | None:
        with self._lock:
            return self._rows[-1] if self._rows else None

    def append_row(self, row: LedgerRow) -> None:
        with self._lock:
            if row.authority_predecessor_hash is not None:
                raise TransitionConflict("authority rows require the compare-and-transition path")
            expected = len(self._rows) + 1
            if row.seq != expected:
                raise ForkRejected(
                    f"expected seq {expected} (head+1); got {row.seq} — fork refused"
                )
            self._rows.append(row)

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
        with self._lock:
            if writer_id is None or self._writer != writer_id:
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
            existing = next((r for r in self._rows if r.transition_id == transition_id), None)
            if existing is not None:
                stored_digest = (
                    compute_authority_transition_digest(
                        existing.event,
                        transition_id=transition_id,
                        expected_authority_state_hash=existing.authority_predecessor_hash,
                        domain_tag=existing.domain_tag,
                    )
                    if existing.authority_predecessor_hash is not None
                    else compute_transition_digest(
                        existing.event,
                        transition_id=transition_id,
                        expected_head_hash=existing.prev_hash,
                        domain_tag=existing.domain_tag,
                    )
                )
                stored_hash = compute_row_hash(
                    existing.prev_hash,
                    existing.seq,
                    existing.timestamp,
                    existing.event,
                    domain_tag=existing.domain_tag,
                    transition_id=existing.transition_id,
                    transition_digest=existing.transition_digest,
                    authority_predecessor_hash=existing.authority_predecessor_hash,
                )
                if stored_digest != existing.transition_digest or stored_hash != existing.row_hash:
                    raise ChainCorruption(f"stored transition {transition_id!r} failed integrity verification")
                if existing.transition_digest != transition_digest:
                    raise TransitionConflict(
                        f"transition {transition_id!r} already committed with a different digest"
                    )
                if fail_on_replay:
                    raise TransitionConflict(
                        f"transition {transition_id!r} is already committed; replay refused"
                    )
                return existing
            previous = self._rows[-1] if self._rows else None
            actual_head_hash = previous.row_hash if previous is not None else GENESIS_HASH
            if actual_head_hash != expected_head_hash:
                raise StaleHead(
                    f"expected ledger head {expected_head_hash}; current head is {actual_head_hash}"
                )
            seq = (previous.seq if previous is not None else 0) + 1
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
            self._rows.append(row)
            return row

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
        with self._lock:
            if writer_id is None or self._writer != writer_id:
                raise SingleWriterViolation(
                    f"authority transition requires the active writer identity; {writer_id!r} refused"
                )
            _, authority_heads = verify_ledger_rows(self._rows)
            authority_head_hash = authority_heads.get(domain_tag, GENESIS_HASH)
            if (
                len(expected_authority_state_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in expected_authority_state_hash)
            ):
                raise ValueError("expected_authority_state_hash must be a lowercase SHA-256 digest")
            stable_event = snapshot_event(event)
            request_digest = compute_authority_transition_digest(
                stable_event,
                transition_id=transition_id,
                expected_authority_state_hash=expected_authority_state_hash,
                domain_tag=domain_tag,
            )
            if request_digest != transition_digest:
                raise TransitionConflict("authority transition digest does not match the exact request")
            existing = next((row for row in self._rows if row.transition_id == transition_id), None)
            if existing is not None:
                stored_digest = (
                    compute_authority_transition_digest(
                        existing.event,
                        transition_id=transition_id,
                        expected_authority_state_hash=existing.authority_predecessor_hash,
                        domain_tag=existing.domain_tag,
                    )
                    if existing.authority_predecessor_hash is not None
                    else compute_transition_digest(
                        existing.event,
                        transition_id=transition_id,
                        expected_head_hash=existing.prev_hash,
                        domain_tag=existing.domain_tag,
                    )
                )
                stored_hash = compute_row_hash(
                    existing.prev_hash,
                    existing.seq,
                    existing.timestamp,
                    existing.event,
                    domain_tag=existing.domain_tag,
                    transition_id=existing.transition_id,
                    transition_digest=existing.transition_digest,
                    authority_predecessor_hash=existing.authority_predecessor_hash,
                )
                if stored_digest != existing.transition_digest or stored_hash != existing.row_hash:
                    raise ChainCorruption(
                        f"stored transition {transition_id!r} failed integrity verification"
                    )
                if existing.transition_digest != transition_digest:
                    raise TransitionConflict(
                        f"transition {transition_id!r} already committed with a different digest"
                    )
                return existing

            if authority_head_hash != expected_authority_state_hash:
                raise StaleAuthorityState(
                    f"expected authority state {expected_authority_state_hash}; "
                    f"current authority state is {authority_head_hash}"
                )

            previous = self._rows[-1] if self._rows else None
            previous_hash = previous.row_hash if previous is not None else GENESIS_HASH
            seq = (previous.seq if previous is not None else 0) + 1
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
            self._rows.append(row)
            return row

    def read(self, start: int, end: int | None) -> list[LedgerRow]:
        if start < 1:
            raise ValueError(f"start must be >= 1, got {start}")
        if end is not None and end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
        with self._lock:
            hi = len(self._rows) + 1 if end is None else end
            return [r for r in self._rows if start <= r.seq < hi]

    def count(self) -> int:
        with self._lock:
            return len(self._rows)


# ---- the ledger -----------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class Ledger:
    """The single-writer, append-only, hash-chained log.

    Constructing a Ledger claims the store's logical writer identity. A distinct owner
    is refused; reattaching with the same identity is permitted for recovery and is not
    a process/session fencing guarantee. Cross-process authority updates rely on the
    storage compare-and-transition primitive; session fencing is a separate control.
    Use as a context manager, or call ``close()`` to release the owner record.
    """

    def __init__(self, store: LedgerStore, *, writer_id: str = "paeos-writer") -> None:
        self._store = store
        self._writer_id = writer_id
        self._closed = False
        # Serializes the compose-and-commit critical section of `append` (read head → derive seq +
        # chain hash → append_row) so concurrent callers each take the NEXT seq in turn instead of
        # racing to the same one. This is the single-writer *integration* point (K8): parallel
        # generation feeds it, but institutional commit is strictly serialized (M2 concurrency).
        self._append_lock = threading.Lock()
        store.acquire_writer(writer_id)  # FR-5: refuses a competing writer here

    def append(self, event: Event, *, domain_tag: str | None = None) -> int:
        """Append ``event``; return its 1-based seq. Never mutates an existing row.

        Thread-safe: the whole read-head→derive-seq→commit sequence runs under `_append_lock`, so
        parallel goals (ConcurrentScheduler) integrate serially onto one dense, unforked chain."""
        with self._append_lock:
            self._ensure_open()
            prev = self._store.head()
            prev_hash = prev.row_hash if prev is not None else GENESIS_HASH
            seq = (prev.seq if prev is not None else 0) + 1
            timestamp = _utcnow_iso()
            if domain_tag is None and "domain_tag" in event.payload:
                domain_tag = str(event.payload["domain_tag"])
            tag = (domain_tag or "PRODUCTION").strip().upper()
            valid_domains = {d.value for d in DomainTag}
            if tag not in valid_domains:
                raise ValueError(f"Invalid domain_tag {tag!r}; must be one of {sorted(valid_domains)}")
            if tag == "PRODUCTION":
                payload_str = json.dumps(event.payload).lower()
                if any(kw in payload_str for kw in ("synthetic", "mock_id", "test_fixture", "fake_evidence", "synthetic_mock")):
                    raise ValueError(
                        "SYNTHETIC_STATE_CONTAMINATION_REJECTED: Event with synthetic/mock payload markers cannot be appended under PRODUCTION domain_tag"
                    )
            row_hash = compute_row_hash(prev_hash, seq, timestamp, event, domain_tag=tag)
            row = LedgerRow(
                seq=seq,
                timestamp=timestamp,
                event=event,
                prev_hash=prev_hash,
                row_hash=row_hash,
                domain_tag=tag,
            )
            self._store.append_row(row)  # atomic; ForkRejected if a racer took this seq
            return seq

    def append_once(
        self,
        event: Event,
        *,
        transition_id: str,
        expected_head_hash: str,
        domain_tag: str | None = None,
    ) -> LedgerRow:
        """Compare-and-append one durable transition, or return its original row on retry.

        The canonical SQLite store performs the decisive read/compare/insert under one
        cross-process transaction. The transition identity and digest live in the
        hash-chained row, so a secondary lookup structure is not an authority source.
        """
        with self._append_lock:
            self._ensure_open()
            if not transition_id.strip():
                raise ValueError("transition_id must be a non-empty string")
            if (
                len(expected_head_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in expected_head_hash)
            ):
                raise ValueError("expected_head_hash must be a lowercase SHA-256 digest")

            # Snapshot mutable caller input before deriving policy decisions. The same
            # detached value is guarded, digested, and handed to the storage boundary.
            stable_event = snapshot_event(event)

            if domain_tag is None and "domain_tag" in stable_event.payload:
                domain_tag = str(stable_event.payload["domain_tag"])
            tag = (domain_tag or "PRODUCTION").strip().upper()
            valid_domains = {d.value for d in DomainTag}
            if tag not in valid_domains:
                raise ValueError(f"Invalid domain_tag {tag!r}; must be one of {sorted(valid_domains)}")
            if tag == "PRODUCTION":
                payload_str = json.dumps(stable_event.payload).lower()
                if any(kw in payload_str for kw in ("synthetic", "mock_id", "test_fixture", "fake_evidence", "synthetic_mock")):
                    raise ValueError(
                        "SYNTHETIC_STATE_CONTAMINATION_REJECTED: Event with synthetic/mock payload markers cannot be appended under PRODUCTION domain_tag"
                    )

            transition_digest = compute_transition_digest(
                stable_event,
                transition_id=transition_id,
                expected_head_hash=expected_head_hash,
                domain_tag=tag,
            )
            return self._store.append_transition(
                stable_event,
                writer_id=self._writer_id,
                transition_id=transition_id,
                transition_digest=transition_digest,
                expected_head_hash=expected_head_hash,
                timestamp=_utcnow_iso(),
                domain_tag=tag,
            )

    def append_once_if_new(
        self,
        event: Event,
        *,
        transition_id: str,
        expected_head_hash: str,
        domain_tag: str | None = None,
    ) -> LedgerRow:
        """Append one new transition and reject even an identical replay atomically."""
        with self._append_lock:
            self._ensure_open()
            if not transition_id.strip():
                raise ValueError("transition_id must be a non-empty string")
            if (
                len(expected_head_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in expected_head_hash)
            ):
                raise ValueError("expected_head_hash must be a lowercase SHA-256 digest")

            stable_event = snapshot_event(event)
            if domain_tag is None and "domain_tag" in stable_event.payload:
                domain_tag = str(stable_event.payload["domain_tag"])
            tag = (domain_tag or "PRODUCTION").strip().upper()
            valid_domains = {d.value for d in DomainTag}
            if tag not in valid_domains:
                raise ValueError(f"Invalid domain_tag {tag!r}; must be one of {sorted(valid_domains)}")
            if tag == "PRODUCTION":
                payload_str = json.dumps(stable_event.payload).lower()
                if any(kw in payload_str for kw in ("synthetic", "mock_id", "test_fixture", "fake_evidence", "synthetic_mock")):
                    raise ValueError(
                        "SYNTHETIC_STATE_CONTAMINATION_REJECTED: Event with synthetic/mock payload markers cannot be appended under PRODUCTION domain_tag"
                    )

            transition_digest = compute_transition_digest(
                stable_event,
                transition_id=transition_id,
                expected_head_hash=expected_head_hash,
                domain_tag=tag,
            )
            return self._store.append_transition(
                stable_event,
                writer_id=self._writer_id,
                transition_id=transition_id,
                transition_digest=transition_digest,
                expected_head_hash=expected_head_hash,
                timestamp=_utcnow_iso(),
                domain_tag=tag,
                fail_on_replay=True,
            )

    def compare_and_transition_once(
        self,
        event: Event,
        *,
        transition_id: str,
        expected_authority_state_hash: str,
        domain_tag: str | None = None,
    ) -> LedgerRow:
        """Append one authority transition against ledger-derived authority state.

        The expected authority predecessor is independent of the physical ledger tail:
        ordinary audit events may interleave, while a competing authority transition
        invalidates this request. The storage backend serializes the comparison, replay
        lookup, and append in one cross-process transaction.
        """
        with self._append_lock:
            self._ensure_open()
            if not transition_id.strip():
                raise ValueError("transition_id must be a non-empty string")
            if (
                len(expected_authority_state_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in expected_authority_state_hash)
            ):
                raise ValueError("expected_authority_state_hash must be a lowercase SHA-256 digest")

            stable_event = snapshot_event(event)
            if domain_tag is None and "domain_tag" in stable_event.payload:
                domain_tag = str(stable_event.payload["domain_tag"])
            tag = (domain_tag or "PRODUCTION").strip().upper()
            valid_domains = {d.value for d in DomainTag}
            if tag not in valid_domains:
                raise ValueError(f"Invalid domain_tag {tag!r}; must be one of {sorted(valid_domains)}")
            if tag == "PRODUCTION":
                payload_str = json.dumps(stable_event.payload).lower()
                if any(
                    marker in payload_str
                    for marker in ("synthetic", "mock_id", "test_fixture", "fake_evidence", "synthetic_mock")
                ):
                    raise ValueError(
                        "SYNTHETIC_STATE_CONTAMINATION_REJECTED: Event with synthetic/mock payload markers cannot be appended under PRODUCTION domain_tag"
                    )

            transition_digest = compute_authority_transition_digest(
                stable_event,
                transition_id=transition_id,
                expected_authority_state_hash=expected_authority_state_hash,
                domain_tag=tag,
            )
            return self._store.append_authority_transition(
                stable_event,
                writer_id=self._writer_id,
                transition_id=transition_id,
                transition_digest=transition_digest,
                expected_authority_state_hash=expected_authority_state_hash,
                timestamp=_utcnow_iso(),
                domain_tag=tag,
            )

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
        """Walk every committed row from seq 1 to head; assert link and hash invariants.

        Catches any historical tampering: modifying a past payload breaks that row's
        ``row_hash``; changing a ``row_hash`` breaks the next row's ``prev_hash``; deleting a
        row leaves a seq gap. Returns the head hash on success.

        Read-only; safe to run while other readers are attached (no lock).
        """
        physical_head_hash, _ = verify_ledger_rows(self._store.read(1, None))
        return physical_head_hash

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
