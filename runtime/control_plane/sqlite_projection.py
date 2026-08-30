"""Replaceable, ledger-head-bound SQLite materialization for control-plane projections."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from kernel.ledger import GENESIS_HASH, Event, JsonValue, LedgerRow

from runtime.control_plane.events import CONTROL_PLANE_TRANSACTION
from runtime.control_plane.projection import (
    ProjectedTransaction,
    ProjectionError,
    _command_from_event,
    _digest,
    _verify_row,
    project_row,
    rebuild_projection,
)
from runtime.integrations.bridge_protocol import _record_from_mapping, canonical_json


class ProjectionCorruption(ProjectionError):
    """Stored projection bytes do not match their recorded integrity metadata."""


class ProjectionHeadMismatch(ProjectionError):
    """The caller's verified ledger head differs from the stored projection head."""


class SqliteControlPlaneProjection:
    """A replaceable cache whose only trusted input is a verified ledger replay."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS control_plane_projection_meta (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    ledger_seq INTEGER NOT NULL,
                    ledger_head TEXT NOT NULL,
                    row_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS control_plane_projection (
                    request_id TEXT PRIMARY KEY,
                    transaction_key TEXT NOT NULL UNIQUE,
                    ledger_seq INTEGER NOT NULL,
                    ledger_head TEXT NOT NULL,
                    row_hash TEXT NOT NULL,
                    row_timestamp TEXT NOT NULL,
                    row_prev_hash TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def replace_from_verified_ledger(
        self,
        rows: Sequence[LedgerRow],
        head_hash: str,
    ) -> None:
        """Atomically replace the cache from a complete, verified ledger prefix."""

        rows_list = list(rows)
        try:
            projections = rebuild_projection(rows_list)
        except ProjectionError:
            raise
        actual_head = rows_list[-1].row_hash if rows_list else GENESIS_HASH
        if head_hash != actual_head:
            raise ProjectionHeadMismatch("verified ledger head does not match ledger rows")
        rows_by_seq = {
            row.seq: row for row in rows_list if row.event.kind == CONTROL_PLANE_TRANSACTION
        }
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM control_plane_projection")
            for projected in projections.values():
                source = rows_by_seq.get(projected.ledger_seq)
                if source is None:
                    raise ProjectionCorruption("projected source row is missing")
                self._insert(connection, projected, source, ledger_head=head_hash)
            ledger_seq = rows_list[-1].seq if rows_list else 0
            connection.execute("DELETE FROM control_plane_projection_meta")
            connection.execute(
                "INSERT INTO control_plane_projection_meta "
                "(singleton, ledger_seq, ledger_head, row_count) VALUES (1, ?, ?, ?)",
                (ledger_seq, head_hash, len(projections)),
            )

    def apply_committed(self, row: LedgerRow, verified_prior_head: str) -> None:
        """Apply one row after its ledger append, refusing a stale projection head."""

        _verify_row(row)
        if row.event.kind != CONTROL_PLANE_TRANSACTION:
            raise ProjectionError("only control-plane transaction rows may be applied")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            meta = self._read_meta(connection)
            prior_head = meta[1] if meta is not None else GENESIS_HASH
            prior_seq = meta[0] if meta is not None else 0
            if verified_prior_head != prior_head:
                raise ProjectionHeadMismatch("verified prior head does not match projection")
            if row.prev_hash != verified_prior_head or row.seq != prior_seq + 1:
                raise ProjectionHeadMismatch("committed row is not the next ledger row")
            projections = self._load_projections(connection, meta)
            existing = projections.get(_command_from_event(row.event).request_id)
            projected = project_row(existing, row)
            for request_id, candidate in projections.items():
                if (
                    candidate.record.transaction_key == projected.record.transaction_key
                    and request_id != projected.record.request_id
                ):
                    raise ProjectionCorruption("duplicate transaction_key")
            connection.execute(
                "UPDATE control_plane_projection SET ledger_head = ?",
                (row.row_hash,),
            )
            source = row
            self._upsert(connection, projected, source, ledger_head=row.row_hash)
            connection.execute("DELETE FROM control_plane_projection_meta")
            connection.execute(
                "INSERT INTO control_plane_projection_meta "
                "(singleton, ledger_seq, ledger_head, row_count) VALUES (1, ?, ?, ?)",
                (row.seq, row.row_hash, len(projections) + (1 if existing is None else 0)),
            )

    def get(self, request_id: str, *, verified_ledger_head: str) -> ProjectedTransaction:
        projections = self._checked_snapshot(verified_ledger_head)
        try:
            return projections[request_id]
        except KeyError as exc:
            raise KeyError(request_id) from exc

    def find_by_transaction_key(
        self,
        transaction_key: str,
        *,
        verified_ledger_head: str,
    ) -> ProjectedTransaction:
        """Return the projection bound to ``transaction_key`` from a verified snapshot."""

        for projected in self._checked_snapshot(verified_ledger_head).values():
            if projected.record.transaction_key == transaction_key:
                return projected
        raise KeyError(transaction_key)

    def claimable(self, *, verified_ledger_head: str) -> tuple[ProjectedTransaction, ...]:
        projections = self._checked_snapshot(verified_ledger_head)
        return tuple(
            sorted(
                (
                    projected
                    for projected in projections.values()
                    if projected.record.state.value == "PREPARED"
                ),
                key=lambda projected: (projected.ledger_seq, projected.record.request_id),
            )
        )

    def recorded_head(self) -> tuple[int, str] | None:
        with self._connect() as connection:
            meta = self._read_meta(connection)
            if meta is None:
                return None
            self._load_projections(connection, meta)
            return meta[0], meta[1]

    def _checked_snapshot(
        self,
        verified_ledger_head: str,
    ) -> dict[str, ProjectedTransaction]:
        with self._connect() as connection:
            meta = self._read_meta(connection)
            if meta is None:
                if verified_ledger_head != GENESIS_HASH:
                    raise ProjectionHeadMismatch("projection has no recorded ledger head")
                return {}
            if meta[1] != verified_ledger_head:
                raise ProjectionHeadMismatch("verified ledger head differs from projection head")
            return self._load_projections(connection, meta)

    def _read_meta(self, connection: sqlite3.Connection) -> tuple[int, str, int] | None:
        try:
            raw = connection.execute(
                "SELECT ledger_seq, ledger_head, row_count "
                "FROM control_plane_projection_meta WHERE singleton = 1"
            ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise ProjectionCorruption("projection metadata cannot be read") from exc
        if raw is None:
            return None
        seq, head, row_count = raw
        if (
            isinstance(seq, bool)
            or not isinstance(seq, int)
            or seq < 0
            or not isinstance(head, str)
            or len(head) != 64
            or any(character not in "0123456789abcdef" for character in head)
            or isinstance(row_count, bool)
            or not isinstance(row_count, int)
            or row_count < 0
        ):
            raise ProjectionCorruption("projection metadata is malformed")
        if seq == 0 and head != GENESIS_HASH:
            raise ProjectionCorruption("empty projection has a non-genesis head")
        return seq, head, row_count

    def _load_projections(
        self,
        connection: sqlite3.Connection,
        meta: tuple[int, str, int] | None,
    ) -> dict[str, ProjectedTransaction]:
        if meta is None:
            return {}
        ledger_seq, ledger_head, expected_count = meta
        try:
            rows = connection.execute(
                "SELECT request_id, transaction_key, ledger_seq, ledger_head, row_hash, "
                "row_timestamp, row_prev_hash, event_json, record_json, digest, fencing_token "
                "FROM control_plane_projection ORDER BY ledger_seq, request_id"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ProjectionCorruption("projection rows cannot be read") from exc
        if len(rows) != expected_count:
            raise ProjectionCorruption("projection row count does not match metadata")
        projections: dict[str, ProjectedTransaction] = {}
        transaction_keys: set[str] = set()
        for raw in rows:
            projected = self._decode_row(raw, ledger_head=ledger_head)
            if projected.ledger_seq > ledger_seq:
                raise ProjectionCorruption("projection row is ahead of ledger head")
            if projected.record.request_id in projections:
                raise ProjectionCorruption("duplicate request_id")
            if projected.record.transaction_key in transaction_keys:
                raise ProjectionCorruption("duplicate transaction_key")
            projections[projected.record.request_id] = projected
            transaction_keys.add(projected.record.transaction_key)
        return projections

    def _decode_row(
        self,
        raw: tuple[Any, ...],
        *,
        ledger_head: str,
    ) -> ProjectedTransaction:
        (
            request_id,
            transaction_key,
            ledger_seq,
            stored_head,
            row_hash,
            row_timestamp,
            row_prev_hash,
            event_json,
            record_json,
            digest,
            fencing_token,
        ) = raw
        if not all(isinstance(value, str) for value in raw[:2] + raw[3:10]):
            raise ProjectionCorruption("projection row contains a non-text field")
        if stored_head != ledger_head or not isinstance(ledger_seq, int) or ledger_seq < 1:
            raise ProjectionCorruption("projection row head or sequence is invalid")
        if (
            isinstance(fencing_token, bool)
            or not isinstance(fencing_token, int)
            or fencing_token < 1
        ):
            raise ProjectionCorruption("projection row fence is invalid")
        try:
            event_raw = json.loads(cast(str, event_json))
            record_raw = json.loads(cast(str, record_json))
            if not isinstance(event_raw, dict) or not isinstance(record_raw, dict):
                raise ValueError("objects required")
            payload = event_raw.get("payload")
            schema_ver = event_raw.get("schema_ver")
            kind = event_raw.get("kind")
            if (
                isinstance(schema_ver, bool)
                or not isinstance(schema_ver, int)
                or not isinstance(kind, str)
                or not isinstance(payload, dict)
            ):
                raise ValueError("invalid event object")
            event = Event(
                schema_ver=schema_ver,
                kind=kind,
                payload=cast(dict[str, JsonValue], payload),
            )
            row = LedgerRow(
                seq=ledger_seq,
                timestamp=cast(str, row_timestamp),
                event=event,
                prev_hash=cast(str, row_prev_hash),
                row_hash=cast(str, row_hash),
            )
            _verify_row(row)
            record = _record_from_mapping(cast(dict[str, object], record_raw))
        except (ValueError, TypeError, ProjectionError) as exc:
            raise ProjectionCorruption("projection row encoding is invalid") from exc
        except Exception as exc:
            raise ProjectionCorruption("projection row record is invalid") from exc
        if (
            record.request_id != request_id
            or record.transaction_key != transaction_key
            or digest != _digest(record, fencing_token, ledger_seq)
        ):
            raise ProjectionCorruption("projection row digest or identity is invalid")
        return ProjectedTransaction(
            record=record,
            digest=digest,
            fencing_token=fencing_token,
            ledger_seq=ledger_seq,
            ledger_head=ledger_head,
        )

    def _insert(
        self,
        connection: sqlite3.Connection,
        projected: ProjectedTransaction,
        source: LedgerRow,
        *,
        ledger_head: str,
    ) -> None:
        connection.execute(
            "INSERT INTO control_plane_projection "
            "(request_id, transaction_key, ledger_seq, ledger_head, row_hash, row_timestamp, "
            "row_prev_hash, event_json, record_json, digest, fencing_token) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                projected.record.request_id,
                projected.record.transaction_key,
                projected.ledger_seq,
                ledger_head,
                source.row_hash,
                source.timestamp,
                source.prev_hash,
                canonical_json(source.event),
                canonical_json(projected.record),
                projected.digest,
                projected.fencing_token,
            ),
        )

    def _upsert(
        self,
        connection: sqlite3.Connection,
        projected: ProjectedTransaction,
        source: LedgerRow,
        *,
        ledger_head: str,
    ) -> None:
        connection.execute(
            "DELETE FROM control_plane_projection WHERE request_id = ?",
            (projected.record.request_id,),
        )
        self._insert(connection, projected, source, ledger_head=ledger_head)
