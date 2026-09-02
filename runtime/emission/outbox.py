"""PAEOS post-seal outbox writer (L15/L16).

The outbox is deliberately PAEOS-side: it stores a small, append-only journal of sealed
bundle *references* and never imports the SAKG graph store.  A caller may invoke
``write_after_seal`` after L15/L16 has established both an integrated goal state and a
strictly-after-seal event order.  Non-integrated goals are a true no-op: validation,
filesystem creation, and timestamps are all skipped.

Each record is a canonical JSON line.  The file is opened with O_APPEND, flushed and
fsynced before the parent directory is synced.  A process lock protects the read/append
sequence allocation.  Existing records are never rewritten or removed; identical replay
is idempotent while a conflicting bundle identity fails closed.
"""

from __future__ import annotations

import datetime as _datetime
import fcntl
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "OutboxCorruptionError",
    "OutboxError",
    "OutboxOrderingError",
    "OutboxValidationError",
    "OutboxWriter",
    "PostSealOutbox",
]

_HASH = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_RECORD_VERSION = 1
_REQUIRED_BUNDLE_FIELDS = frozenset(
    {"bundle_id", "goal_id", "namespace", "artifact_bundle_hash", "evidence_refs"}
)
_FORBIDDEN_INLINE_FIELDS = frozenset({"evidence", "payload", "content", "inline_evidence"})


class OutboxError(Exception):
    """Base class for fail-closed outbox errors."""


class OutboxValidationError(OutboxError, ValueError):
    """A bundle reference or lifecycle boundary is malformed."""


class OutboxOrderingError(OutboxValidationError):
    """L16 emission was not proven to occur strictly after the seal event."""


class OutboxCorruptionError(OutboxError):
    """The append-only journal contains an invalid or truncated record."""


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    """One durable post-seal reference record; no evidence bytes are embedded."""

    sequence: int
    bundle_id: str
    goal_id: str
    namespace: str
    artifact_bundle_hash: str
    evidence_refs: tuple[str, ...]
    seal_sequence: int
    l16_sequence: int
    emitted_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_bundle_hash": self.artifact_bundle_hash,
            "bundle_id": self.bundle_id,
            "evidence_refs": list(self.evidence_refs),
            "emitted_at": self.emitted_at,
            "goal_id": self.goal_id,
            "goal_state": "integrated",
            "l16_sequence": self.l16_sequence,
            "namespace": self.namespace,
            "seal_sequence": self.seal_sequence,
            "sequence": self.sequence,
            "version": _RECORD_VERSION,
        }


def _canonical(value: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as exc:
        raise OutboxValidationError("record is not JSON serializable") from exc


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise OutboxValidationError(f"{field} must be a non-empty single-line string")
    return value


def _identifier(value: object, field: str) -> str:
    text = _text(value, field)
    if _IDENTIFIER.fullmatch(text) is None:
        raise OutboxValidationError(f"{field} has an invalid identifier")
    return text


def _hash(value: object, field: str) -> str:
    text = _text(value, field)
    if _HASH.fullmatch(text) is None:
        raise OutboxValidationError(f"{field} must be a lowercase SHA-256 reference")
    return text


def _sequence(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OutboxValidationError(f"{field} must be a non-negative integer")
    return value


def _record_from_dict(value: object, line_no: int) -> OutboxRecord:
    if not isinstance(value, Mapping):
        raise OutboxCorruptionError(f"journal line {line_no} is not an object")
    expected = {
        "artifact_bundle_hash",
        "bundle_id",
        "evidence_refs",
        "emitted_at",
        "goal_id",
        "goal_state",
        "l16_sequence",
        "namespace",
        "seal_sequence",
        "sequence",
        "version",
    }
    if set(value) != expected:
        raise OutboxCorruptionError(f"journal line {line_no} has an unexpected schema")
    try:
        if value["version"] != _RECORD_VERSION or value["goal_state"] != "integrated":
            raise OutboxCorruptionError(f"journal line {line_no} has an unsupported state/version")
        refs = value["evidence_refs"]
        if not isinstance(refs, list) or not refs:
            raise OutboxCorruptionError(f"journal line {line_no} has no evidence references")
        record = OutboxRecord(
            sequence=_sequence(value["sequence"], "sequence"),
            bundle_id=_identifier(value["bundle_id"], "bundle_id"),
            goal_id=_identifier(value["goal_id"], "goal_id"),
            namespace=_identifier(value["namespace"], "namespace"),
            artifact_bundle_hash=_hash(value["artifact_bundle_hash"], "artifact_bundle_hash"),
            evidence_refs=tuple(_hash(ref, "evidence_refs[]") for ref in refs),
            seal_sequence=_sequence(value["seal_sequence"], "seal_sequence"),
            l16_sequence=_sequence(value["l16_sequence"], "l16_sequence"),
            emitted_at=_text(value["emitted_at"], "emitted_at"),
        )
    except OutboxValidationError as exc:
        raise OutboxCorruptionError(f"journal line {line_no} is invalid: {exc}") from exc
    if record.l16_sequence <= record.seal_sequence:
        raise OutboxCorruptionError(f"journal line {line_no} violates post-seal ordering")
    return record


def _record_key(record: OutboxRecord) -> tuple[object, ...]:
    return (
        record.bundle_id,
        record.goal_id,
        record.namespace,
        record.artifact_bundle_hash,
        record.evidence_refs,
        record.seal_sequence,
        record.l16_sequence,
    )


class PostSealOutbox:
    """Crash-safe append-only outbox for L15/L16 integrated goals."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def records(self) -> tuple[OutboxRecord, ...]:
        """Read and validate all records without modifying the journal."""
        if not self._path.exists():
            return ()
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise OutboxCorruptionError(f"cannot read outbox: {exc}") from exc
        records: list[OutboxRecord] = []
        expected_sequence = 1
        for line_no, line in enumerate(lines, start=1):
            if not line.strip():
                raise OutboxCorruptionError(f"journal line {line_no} is empty")
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OutboxCorruptionError(f"journal line {line_no} is not valid JSON") from exc
            record = _record_from_dict(payload, line_no)
            if record.sequence != expected_sequence:
                raise OutboxCorruptionError(f"journal sequence gap at line {line_no}")
            records.append(record)
            expected_sequence += 1
        return tuple(records)

    def write_after_seal(
        self,
        bundle: Mapping[str, object],
        *,
        goal_state: str,
        seal_sequence: int | None,
        l16_sequence: int | None,
        emitted_at: str | None = None,
    ) -> OutboxRecord | None:
        """Append one integrated bundle reference after a verified seal.

        Any state other than ``integrated`` returns ``None`` without touching the filesystem.
        Integrated writes require a non-negative seal sequence and an L16 sequence strictly
        greater than it.  ``bundle`` is metadata plus SHA-256 references only; inline evidence
        or payload fields are rejected.
        """
        if goal_state != "integrated":
            return None
        if seal_sequence is None or l16_sequence is None:
            raise OutboxOrderingError("integrated emission requires seal and L16 sequence")
        seal = _sequence(seal_sequence, "seal_sequence")
        l16 = _sequence(l16_sequence, "l16_sequence")
        if l16 <= seal:
            raise OutboxOrderingError("L16 emission must occur strictly after the seal")
        if not isinstance(bundle, Mapping):
            raise OutboxValidationError("bundle must be an object")
        keys = set(bundle)
        forbidden = keys & _FORBIDDEN_INLINE_FIELDS
        if forbidden:
            raise OutboxValidationError(
                f"inline evidence/payload fields are forbidden: {sorted(forbidden)}"
            )
        if keys != _REQUIRED_BUNDLE_FIELDS:
            raise OutboxValidationError("bundle must contain exactly metadata and CAS references")
        refs_value = bundle["evidence_refs"]
        if isinstance(refs_value, (str, bytes, bytearray)) or not isinstance(refs_value, Sequence):
            raise OutboxValidationError("evidence_refs must be a non-empty sequence of hashes")
        refs = tuple(_hash(ref, "evidence_refs[]") for ref in refs_value)
        if not refs:
            raise OutboxValidationError("evidence_refs must not be empty")
        emitted = _text(
            emitted_at
            if emitted_at is not None
            else _datetime.datetime.now(_datetime.__dict__["UTC"])
            .isoformat()
            .replace("+00:00", "Z"),
            "emitted_at",
        )
        candidate = OutboxRecord(
            sequence=0,
            bundle_id=_identifier(bundle["bundle_id"], "bundle_id"),
            goal_id=_identifier(bundle["goal_id"], "goal_id"),
            namespace=_identifier(bundle["namespace"], "namespace"),
            artifact_bundle_hash=_hash(bundle["artifact_bundle_hash"], "artifact_bundle_hash"),
            evidence_refs=refs,
            seal_sequence=seal,
            l16_sequence=l16,
            emitted_at=emitted,
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_CREAT | os.O_APPEND | os.O_RDWR, 0o600)
        try:
            with os.fdopen(fd, "a+", encoding="utf-8") as handle:
                fd = -1
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                handle.seek(0)
                existing = self._records_from_handle(handle)
                for prior in existing:
                    if prior.bundle_id == candidate.bundle_id:
                        if _record_key(prior) != _record_key(candidate):
                            raise OutboxError(
                                f"bundle_id {candidate.bundle_id!r} conflicts with history"
                            )
                        return prior
                record = OutboxRecord(
                    sequence=len(existing) + 1,
                    bundle_id=candidate.bundle_id,
                    goal_id=candidate.goal_id,
                    namespace=candidate.namespace,
                    artifact_bundle_hash=candidate.artifact_bundle_hash,
                    evidence_refs=candidate.evidence_refs,
                    seal_sequence=candidate.seal_sequence,
                    l16_sequence=candidate.l16_sequence,
                    emitted_at=candidate.emitted_at,
                )
                handle.seek(0, os.SEEK_END)
                encoded = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            if fd != -1:
                os.close(fd)
        try:
            directory_fd = os.open(self._path.parent, os.O_RDONLY)
        except OSError as exc:
            raise OutboxError(
                f"outbox committed but parent directory could not be synced: {exc}"
            ) from exc
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return record

    def _records_from_handle(self, handle: Any) -> tuple[OutboxRecord, ...]:
        handle.seek(0)
        records: list[OutboxRecord] = []
        expected = 1
        for line_no, line in enumerate(handle.read().splitlines(), start=1):
            if not line.strip():
                raise OutboxCorruptionError(f"journal line {line_no} is empty")
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OutboxCorruptionError(f"journal line {line_no} is not valid JSON") from exc
            record = _record_from_dict(payload, line_no)
            if record.sequence != expected:
                raise OutboxCorruptionError(f"journal sequence gap at line {line_no}")
            records.append(record)
            expected += 1
        return tuple(records)


OutboxWriter = PostSealOutbox
