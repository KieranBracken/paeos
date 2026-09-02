"""Durable SQLite institutional scar store.

The in-memory :class:`runtime.memory.ScarStore` remains the small, deterministic test
implementation.  This adapter provides the same scar semantics with a state-directory-owned
SQLite database so lessons survive process restarts without becoming repository-relative state.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path

from kernel.types import StageId

from runtime.memory import (
    INJECTION_STAGES,
    MIN_SIGNATURE_TAGS,
    Scar,
    ScarDraft,
    ScarQuarantined,
    ScarStore,
    parse_signature,
)

__all__ = ["SqliteScarStore"]


class SqliteScarStore(ScarStore):
    """Append-only, cross-process durable implementation of the scar-store contract.

    The database is always colocated at ``<state_dir>/scars.db``.  A transaction obtains the
    next SQLite sequence before assigning the stable ``scar-NNNN`` identifier, so independent
    processes cannot overwrite one another's records.  Existing rows are never updated or
    deleted; reopening the store reconstructs the exact same :class:`Scar` values.
    """

    def __init__(self, state_dir: str | Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "scars.db"
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.db_path, timeout=30.0, check_same_thread=False
        )
        self._connection.execute("PRAGMA busy_timeout=30000")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scars (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                signature TEXT NOT NULL,
                lesson TEXT NOT NULL,
                detection TEXT NOT NULL,
                severity TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    @staticmethod
    def _validate(draft: ScarDraft) -> None:
        if len(draft.signature) < MIN_SIGNATURE_TAGS:
            raise ScarQuarantined(
                f"scar signature {set(draft.signature)} has < {MIN_SIGNATURE_TAGS} conditions; "
                "too broad to inject — quarantined (T3)"
            )

    @staticmethod
    def _encode_signature(signature: frozenset[str]) -> str:
        return json.dumps(sorted(signature), ensure_ascii=True, separators=(",", ":"))

    @staticmethod
    def _decode(row: tuple[object, ...]) -> Scar:
        raw_signature = row[2]
        if not isinstance(raw_signature, str):
            raise TypeError("scar signature column is not text")
        decoded = json.loads(raw_signature)
        if not isinstance(decoded, list) or not all(isinstance(tag, str) for tag in decoded):
            raise ValueError("scar signature column is malformed")
        values = row[1:]
        if not all(isinstance(value, str) for value in values if value is not None):
            raise TypeError("scar column contains a non-text value")
        return Scar(
            id=str(row[1]),
            signature=frozenset(decoded),
            lesson=str(row[3]),
            detection=str(row[4]),
            severity=str(row[5]),
        )

    def record_scar(self, draft: ScarDraft) -> Scar:
        """Validate and append a scar, returning its durable stable identifier."""
        self._validate(draft)
        with self._lock:
            pending_id = "pending-" + uuid.uuid4().hex
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                cursor = self._connection.execute(
                    """
                    INSERT INTO scars(id, signature, lesson, detection, severity)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        pending_id,
                        self._encode_signature(draft.signature),
                        draft.lesson,
                        draft.detection,
                        draft.severity,
                    ),
                )
                sequence = cursor.lastrowid
                if sequence is None:
                    raise RuntimeError("SQLite did not return a scar sequence")
                identifier = f"scar-{int(sequence):04d}"
                self._connection.execute(
                    "UPDATE scars SET id = ? WHERE seq = ?", (identifier, sequence)
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return Scar(
            id=identifier,
            signature=draft.signature,
            lesson=draft.lesson,
            detection=draft.detection,
            severity=draft.severity,
        )

    # ScarStore's historical write name is retained for callers in EvolutionLayer.
    def propose_scar(self, draft: ScarDraft) -> Scar:
        return self.record_scar(draft)

    def all_scars(self) -> list[Scar]:
        """Return every scar in append/sequence order."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT seq, id, signature, lesson, detection, severity FROM scars ORDER BY seq"
            ).fetchall()
        return [self._decode(row) for row in rows]

    def match_scars(self, signature: str) -> list[Scar]:
        """Return scars whose condition tags are a subset of the goal signature."""
        goal_tags = parse_signature(signature)
        return sorted(
            (scar for scar in self.all_scars() if scar.signature <= goal_tags),
            key=lambda scar: scar.id,
        )

    def get_precedent(self, precedent_id: str) -> Scar | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT seq, id, signature, lesson, detection, severity "
                "FROM scars WHERE id = ?",
                (precedent_id,),
            ).fetchone()
        return self._decode(row) if row is not None else None

    def injected_scars(self, *, signature: str, stage: StageId) -> list[Scar]:
        if stage not in INJECTION_STAGES:
            return []
        return self.match_scars(signature)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SqliteScarStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
