"""Content-addressable store (CAS) — immutable blobs keyed by their own hash.

Task B0.2 (PAEOS-8 §10). The CAS holds the *bytes* the ledger and artifacts refer to. It
is the second half of the source of truth: the ledger orders events; the CAS stores the
content those events point at. Its guarantees:

  1. Content-addressed — ``put(data)`` returns ``sha256(data)`` hex; the address *is* the
     content's fingerprint, so identical bytes always land at one entry (dedup) and a
     retrieved blob can be re-verified against the address it was asked for.
  2. Immutable — there is no operation that changes a stored blob. ``put`` on existing
     content is a no-op; the only removal path is GC, and GC never touches referenced
     content.
  3. Durable — the filesystem backend survives process restart (blobs are files named by
     hash), so a ``get`` after a restart returns the same bytes.
  4. Referential-integrity-safe — ``gc(reachable)`` sweeps only unreachable blobs; a hash
     in the reachable set is never collected.

Storage sits behind ``CasStore`` (K9 narrow waist): the addressing/verification/GC logic
lives here in the TCB and is storage-agnostic. ``InMemoryCasStore`` is the fast reference
backend; ``FilesystemCasStore`` is the durable one that satisfies the restart test (and,
being content-addressed files, needs no database — distinct from the ledger's DEBT-0003).
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Collection, Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = [
    "CAS",
    "CasCorruption",
    "CasError",
    "CasMiss",
    "CasStore",
    "FilesystemCasStore",
    "InMemoryCasStore",
    "content_hash",
    "is_valid_hash",
]

_HASH_HEX_LEN = 64  # sha256 → 32 bytes → 64 hex chars
_HEX_DIGITS = frozenset("0123456789abcdef")


# ---- errors ---------------------------------------------------------------


class CasError(Exception):
    """Base for every CAS fault."""


class CasMiss(CasError):
    """``get`` was asked for a hash the store does not hold."""


class CasCorruption(CasError):
    """A retrieved blob does not hash to the address it was stored under (bit-rot/tamper)."""


# ---- hashing --------------------------------------------------------------


def content_hash(data: bytes) -> str:
    """The canonical address of ``data``: lowercase hex sha256."""
    return hashlib.sha256(data).hexdigest()


def is_valid_hash(candidate: str) -> bool:
    """True iff ``candidate`` is a well-formed lowercase sha256 hex address."""
    return len(candidate) == _HASH_HEX_LEN and all(c in _HEX_DIGITS for c in candidate)


def _require_hash(candidate: str) -> None:
    if not is_valid_hash(candidate):
        raise ValueError(f"not a valid sha256 hex address: {candidate!r}")


# ---- storage seam (K9 narrow waist) --------------------------------------


@runtime_checkable
class CasStore(Protocol):
    """The blob storage contract. Deliberately tiny.

    ``write`` must be idempotent and atomic (a reader never sees a partial blob). ``delete``
    exists solely for GC; no method mutates an existing blob in place.
    """

    def write(self, key: str, data: bytes) -> None:
        """Store ``data`` under ``key`` atomically. No-op if ``key`` already present."""
        ...

    def read(self, key: str) -> bytes:
        """Return the bytes at ``key``. Raise CasMiss if absent."""
        ...

    def exists(self, key: str) -> bool:
        """True iff ``key`` is present."""
        ...

    def delete(self, key: str) -> None:
        """Remove ``key`` if present (GC only). No-op if absent."""
        ...

    def iter_keys(self) -> Iterator[str]:
        """Yield every stored key. Order unspecified."""
        ...


class InMemoryCasStore:
    """Reference backend: a dict. No durability; fast. Enforces the same CAS contract."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def write(self, key: str, data: bytes) -> None:
        self._blobs.setdefault(key, data)  # idempotent; never overwrites existing content

    def read(self, key: str) -> bytes:
        try:
            return self._blobs[key]
        except KeyError:
            raise CasMiss(f"no blob at {key}") from None

    def exists(self, key: str) -> bool:
        return key in self._blobs

    def delete(self, key: str) -> None:
        self._blobs.pop(key, None)

    def iter_keys(self) -> Iterator[str]:
        yield from list(self._blobs.keys())


class FilesystemCasStore:
    """Durable backend: blobs as files named by hash (git-style two-char sharding).

    Layout: ``<root>/<key[:2]>/<key[2:]>``. Writes are atomic (temp file + ``os.replace``),
    so a crash mid-write never leaves a partial blob visible under its final name. Survives
    process restart, which is what the B0.2 restart test requires.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._root / key[:2] / key[2:]

    def write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        if path.exists():
            return  # idempotent; content is immutable, never rewritten
        path.parent.mkdir(parents=True, exist_ok=True)
        # write to a unique temp file in the same dir, fsync, then atomically rename in
        tmp = path.parent / f".{key[2:]}.{os.getpid()}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)  # atomic within a filesystem

    def read(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            raise CasMiss(f"no blob at {key}") from None

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def iter_keys(self) -> Iterator[str]:
        for shard in self._root.iterdir():
            if not shard.is_dir() or len(shard.name) != 2:
                continue
            for blob in shard.iterdir():
                key = shard.name + blob.name
                # only well-formed addresses; skips crash-orphaned .tmp write files
                if blob.is_file() and is_valid_hash(key):
                    yield key


# ---- the CAS --------------------------------------------------------------


class CAS:
    """Immutable, content-addressed, referential-integrity-safe blob store.

    Thin logic over a ``CasStore``: computes addresses, verifies content on read, and runs
    a mark-and-sweep GC that cannot collect a referenced hash.
    """

    def __init__(self, store: CasStore, *, verify_on_read: bool = True) -> None:
        self._store = store
        self._verify_on_read = verify_on_read

    def put(self, data: bytes) -> str:
        """Store ``data``; return its address. Idempotent: same bytes ⇒ same address ⇒ one entry."""
        key = content_hash(data)
        if not self._store.exists(key):
            self._store.write(key, data)
        return key

    def get(self, key: str) -> bytes:
        """Return the bytes at ``key``. Raise CasMiss if absent, CasCorruption if it no longer
        hashes to ``key`` (bit-rot/tamper detection — the address is the checksum)."""
        _require_hash(key)
        data = self._store.read(key)
        if self._verify_on_read:
            actual = content_hash(data)
            if actual != key:
                raise CasCorruption(f"blob at {key} hashes to {actual} — corrupted")
        return data

    def has(self, key: str) -> bool:
        """True iff ``key`` is stored. Malformed addresses are simply absent."""
        return is_valid_hash(key) and self._store.exists(key)

    def gc(self, reachable: Collection[str]) -> list[str]:
        """Sweep every blob whose address is not in ``reachable``; return collected addresses.

        Referential integrity: a hash in ``reachable`` is never collected. Reachable hashes
        that are absent from the store are ignored (a dangling reference is the caller's
        concern, not something GC repairs). Deterministic: collected list is sorted.
        """
        keep = set(reachable)
        collected = [key for key in self._store.iter_keys() if key not in keep]
        for key in collected:
            self._store.delete(key)
        return sorted(collected)
