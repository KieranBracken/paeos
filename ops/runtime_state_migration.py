"""Runtime state migration for PAEOS (DEBT-0057, Task 2).

Task 2 scope: immutable manifests and manifest digesting; freezing
historical runtime state into create-only tamper-evident archives;
initializing a fresh trust domain bound to the frozen archive; and a
one-shot CLI (``main``) that resolves the source repository commit,
freezes ``--source-state`` into ``--archive-root`` under ``--archive-id``,
reinitializes ``--new-state-root``, and prints a compact sorted JSON
summary containing only public, non-secret fields. This module is
deliberately side-effect-free except for the private create-only JSON
writer, the freeze/initialize procedures, and the CLI entry point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kernel.keystore import load_or_create_signing_key
from kernel.ledger import GENESIS_HASH, Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from nacl.signing import SigningKey

__all__ = [
    "FrozenArchive",
    "ManifestEntry",
    "MigrationError",
    "TrustDomain",
    "fingerprint_signing_key",
    "freeze_historical_state",
    "initialize_fresh_state",
    "main",
    "manifest_digest",
    "manifest_tree",
]

_COMMIT_RE = re.compile(r"[0-9a-f]{40}")

_CHUNK_SIZE = 1 << 16

_ARCHIVE_ID_RE = re.compile(r"[A-Za-z0-9._-]+")

_HEX64_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """One regular file in a manifested tree."""

    path: str
    size: int
    mode: int
    sha256: str


@dataclass(frozen=True, slots=True)
class FrozenArchive:
    """Pointer record for a frozen historical-state archive."""

    archive_root: Path
    state_root: Path
    metadata_path: Path
    manifest_hash: str
    file_count: int


@dataclass(frozen=True, slots=True)
class TrustDomain:
    """Fingerprints binding an old trust domain to its frozen archive."""

    state_root: Path
    old_public_fingerprint: str
    new_public_fingerprint: str
    archive_manifest_hash: str


class MigrationError(RuntimeError):
    """Raised when a runtime state migration invariant is violated."""


def manifest_tree(root: Path) -> tuple[ManifestEntry, ...]:
    """Walk ``root`` and return a sorted manifest of regular files.

    Resolves ``root`` exactly once, rejects missing/non-directory roots,
    symlinked directories/files, and non-regular files. Paths are POSIX
    relative strings sorted lexicographically; each entry hashes the file's
    bytes (never returned) and retains ``stat.S_IMODE`` permissions.
    """
    root = Path(root)
    try:
        st = root.lstat()
    except OSError as exc:
        raise MigrationError(f"manifest root is missing: {root}") from exc
    if stat.S_ISLNK(st.st_mode):
        raise MigrationError(f"symlinked manifest root rejected: {root}")
    if not stat.S_ISDIR(st.st_mode):
        raise MigrationError(f"manifest root is not a directory: {root}")
    root = root.resolve(strict=True)
    entries: list[ManifestEntry] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        for name in sorted(dirnames):
            child = current / name
            if child.is_symlink():
                raise MigrationError(f"symlinked directory rejected: {child}")
        for name in filenames:
            path = current / name
            if path.is_symlink():
                raise MigrationError(f"symlinked file rejected: {path}")
            fst = path.lstat()
            if not stat.S_ISREG(fst.st_mode):
                raise MigrationError(f"non-regular file rejected: {path}")
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    digest.update(chunk)
            entries.append(
                ManifestEntry(
                    path=path.relative_to(root).as_posix(),
                    size=fst.st_size,
                    mode=stat.S_IMODE(fst.st_mode),
                    sha256=digest.hexdigest(),
                )
            )
    return tuple(sorted(entries, key=lambda entry: entry.path))


def manifest_digest(entries: tuple[ManifestEntry, ...]) -> str:
    """Return SHA-256 over sorted compact JSON of the manifest.

    Canonicalizes only ``path``, ``size``, ``mode``, and ``sha256`` fields.
    """
    payload = [
        {
            "path": entry.path,
            "size": entry.size,
            "mode": entry.mode,
            "sha256": entry.sha256,
        }
        for entry in entries
    ]
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _write_json_create_only(path: Path, payload: object) -> None:
    """Write compact JSON to ``path`` using an O_CREAT|O_EXCL descriptor."""
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def freeze_historical_state(
    *,
    source_root: Path,
    archive_root: Path,
    archive_id: str,
    source_commit: str,
) -> FrozenArchive:
    """Freeze ``source_root`` into a create-only archive under ``archive_root``.

    Takes exactly three manifests: the initial source tree, the copied
    archive tree, and a second source tree taken after the copy to prove
    the source did not change during archival. Any partial archive created
    before an exception is deliberately preserved on disk for inspection.
    """
    if not isinstance(archive_id, str) or not _ARCHIVE_ID_RE.fullmatch(archive_id):
        raise MigrationError(f"invalid archive id: {archive_id!r}")

    archive_dir = Path(archive_root) / archive_id
    try:
        archive_dir.parent.mkdir(parents=True, exist_ok=True)
        os.mkdir(archive_dir, 0o700)
    except FileExistsError as exc:
        raise MigrationError(f"archive already exists: {archive_dir}") from exc

    state_root = archive_dir / "state"
    os.mkdir(state_root, 0o700)

    initial = manifest_tree(source_root)

    for entry in initial:
        destination = state_root / entry.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            source_root / entry.path, destination, follow_symlinks=False
        )

    copied = manifest_tree(state_root)
    if manifest_digest(copied) != manifest_digest(initial):
        raise MigrationError(
            "archive copy does not match initial source manifest"
        )

    second = manifest_tree(source_root)
    if manifest_digest(second) != manifest_digest(initial):
        raise MigrationError(
            "source changed during archival: "
            f"{Path(source_root)} was modified while being frozen"
        )

    manifest_hash = manifest_digest(initial)
    manifest_payload = [
        {
            "path": entry.path,
            "size": entry.size,
            "mode": entry.mode,
            "sha256": entry.sha256,
        }
        for entry in initial
    ]
    _write_json_create_only(archive_dir / "manifest.json", manifest_payload)

    metadata_path = archive_dir / "metadata.json"
    _write_json_create_only(
        metadata_path,
        {
            "source_commit": source_commit,
            "manifest_hash": manifest_hash,
            "file_count": len(initial),
            "created_at": datetime.now(UTC).isoformat(),
        },
    )

    return FrozenArchive(
        archive_root=archive_dir,
        state_root=state_root,
        metadata_path=metadata_path,
        manifest_hash=manifest_hash,
        file_count=len(initial),
    )


def fingerprint_signing_key(path: Path) -> str:
    """Return the SHA-256 hex fingerprint of the Ed25519 key at ``path``.

    The fingerprint is taken over the 32-byte verify (public) key bytes, so
    it is safe to record in plaintext metadata while never disclosing the
    seed. A key file that is not exactly a 32-byte seed is refused.
    """
    path = Path(path)
    seed = path.read_bytes()
    if len(seed) != 32:
        raise MigrationError(
            f"signing key at {path} is {len(seed)} bytes, expected 32"
        )
    signing_key = SigningKey(seed)
    return hashlib.sha256(bytes(signing_key.verify_key)).hexdigest()


def initialize_fresh_state(
    *,
    new_state_root: Path,
    historical_key_path: Path,
    archive_manifest_hash: str,
) -> TrustDomain:
    """Initialize a fresh trust domain under ``new_state_root``.

    Creates the state directory (0700, create-only), a new kernel signing
    key, an empty genesis-anchored SQLite ledger, and a create-only
    ``trust-domain.json`` binding the historical (frozen) domain's key
    fingerprint to the new domain's. Partial state created before an
    exception is deliberately preserved on disk for inspection.
    """
    state = Path(new_state_root)
    if not isinstance(archive_manifest_hash, str) or not _HEX64_RE.fullmatch(
        archive_manifest_hash
    ):
        raise MigrationError(
            f"archive manifest hash must be 64 lowercase hex chars: "
            f"{archive_manifest_hash!r}"
        )

    try:
        os.mkdir(state, 0o700)
    except FileExistsError as exc:
        raise MigrationError(
            f"new state root already exists: {state}"
        ) from exc

    old_public_fingerprint = fingerprint_signing_key(
        Path(historical_key_path)
    )

    new_signing_key = load_or_create_signing_key(state / "seal.key")
    new_public_fingerprint = hashlib.sha256(
        bytes(new_signing_key.verify_key)
    ).hexdigest()

    if old_public_fingerprint == new_public_fingerprint:
        raise MigrationError(
            "refusing to initialize: new signing key fingerprint equals the "
            "historical trust-domain fingerprint"
        )

    ledger: Ledger | None = None
    store: SqliteLedgerStore | None = None
    try:
        store = SqliteLedgerStore(state / "ledger.db")
        ledger = Ledger(store)
        if ledger.head() is not None:
            raise MigrationError(
                "refusing to initialize: fresh ledger is not empty"
            )
        tip = ledger.verify_chain()
        if tip != GENESIS_HASH:
            raise MigrationError(
                "refusing to initialize: fresh ledger chain tip is not the "
                "genesis hash"
            )
    finally:
        if ledger is not None:
            ledger.close()
        if store is not None:
            store.close()

    record = TrustDomain(
        state_root=state,
        old_public_fingerprint=old_public_fingerprint,
        new_public_fingerprint=new_public_fingerprint,
        archive_manifest_hash=archive_manifest_hash,
    )

    _write_json_create_only(
        state / "trust-domain.json",
        {
            "schema_version": 1,
            "status": "active",
            "historical_status": "forensic-only",
            "archive_manifest_hash": archive_manifest_hash,
            "old_public_fingerprint": old_public_fingerprint,
            "new_public_fingerprint": new_public_fingerprint,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )

    return record


def main(argv: list[str] | None = None) -> int:
    """Run the one-shot runtime state migration CLI and return exit status."""
    parser = argparse.ArgumentParser(
        prog="runtime_state_migration",
        description=(
            "Freeze historical runtime state into a create-only archive and "
            "initialize a fresh trust domain."
        ),
    )
    parser.add_argument(
        "--source-repo", required=True, type=Path,
        help="Git repository whose HEAD commit identifies the source state",
    )
    parser.add_argument(
        "--source-state", required=True, type=Path,
        help="Historical runtime state directory to freeze",
    )
    parser.add_argument(
        "--archive-root", required=True, type=Path,
        help="Root directory under which the archive is created",
    )
    parser.add_argument(
        "--archive-id", required=True,
        help="Identifier for the archive directory",
    )
    parser.add_argument(
        "--new-state-root", required=True, type=Path,
        help="Directory in which the fresh trust domain is initialized",
    )
    args = parser.parse_args(argv)

    result = subprocess.run(
        ["git", "-C", str(args.source_repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    source_commit = result.stdout.strip()
    if not _COMMIT_RE.fullmatch(source_commit):
        raise MigrationError(
            f"source commit must be 40 lowercase hex chars: "
            f"{source_commit!r}"
        )

    frozen = freeze_historical_state(
        source_root=args.source_state,
        archive_root=args.archive_root,
        archive_id=args.archive_id,
        source_commit=source_commit,
    )

    domain = initialize_fresh_state(
        new_state_root=args.new_state_root,
        historical_key_path=frozen.state_root / "seal.key",
        archive_manifest_hash=frozen.manifest_hash,
    )

    summary = {
        "archive_path": str(frozen.archive_root),
        "new_state_path": str(domain.state_root),
        "source_commit": source_commit,
        "file_count": frozen.file_count,
        "manifest_hash": frozen.manifest_hash,
        "old_public_fingerprint": domain.old_public_fingerprint,
        "new_public_fingerprint": domain.new_public_fingerprint,
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
