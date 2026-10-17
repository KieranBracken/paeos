"""Secret-blind authenticated profile handles and conservative pre-Gate-B leases."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

from runtime.worker_adapter import AdapterFailureKind

_INVOCATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ProfileLeaseError(RuntimeError):
    def __init__(self, kind: AdapterFailureKind, message: str) -> None:
        self.kind = kind
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class AuthenticatedProfileHandle:
    root: Path
    profile_uuid: UUID
    auth_epoch: int

    def __post_init__(self) -> None:
        if self.auth_epoch <= 0:
            raise ValueError("auth_epoch must be positive")


@dataclass(frozen=True, slots=True)
class ProfileLeaseRecord:
    invocation_id: str
    profile_uuid: str
    auth_epoch: int
    pid: int
    process_start_token: str
    boot_id: str
    acquired_monotonic_ns: int
    nonce: str


def public_profile_payload(handle: AuthenticatedProfileHandle) -> dict[str, object]:
    return {
        "auth_epoch": handle.auth_epoch,
        "profile_root": str(handle.root),
        "profile_uuid": str(handle.profile_uuid),
    }


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise ProfileLeaseError(
                AdapterFailureKind.PROFILE_LOCK_FAILED, "profile path unavailable"
            ) from exc
        if stat.S_ISLNK(mode):
            raise ProfileLeaseError(
                AdapterFailureKind.PROFILE_LOCK_FAILED, "profile path contains symlink"
            )


def _validate_private_directory(path: Path, expected_uid: int) -> Path:
    if not path.is_absolute():
        raise ProfileLeaseError(
            AdapterFailureKind.PROFILE_LOCK_FAILED, "profile path must be absolute"
        )
    _reject_symlink_components(path)
    metadata = path.stat()
    if not stat.S_ISDIR(metadata.st_mode):
        raise ProfileLeaseError(AdapterFailureKind.PROFILE_LOCK_FAILED, "not a directory")
    if metadata.st_uid != expected_uid or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ProfileLeaseError(
            AdapterFailureKind.PROFILE_LOCK_FAILED, "directory ownership or mode invalid"
        )
    return path.resolve(strict=True)


def validate_profile_handle(
    handle: AuthenticatedProfileHandle,
    *,
    forbidden_roots: tuple[Path, ...],
    expected_uid: int | None = None,
) -> None:
    """Validate only path metadata; never enumerate or read profile contents."""

    root = _validate_private_directory(
        handle.root, os.getuid() if expected_uid is None else expected_uid
    )
    for forbidden in forbidden_roots:
        resolved = forbidden.resolve(strict=False)
        if root == resolved or root.is_relative_to(resolved):
            raise ProfileLeaseError(
                AdapterFailureKind.PROFILE_LOCK_FAILED, "profile lies in forbidden root"
            )


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_once(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _sync_directory(path.parent)


class ProfileLease:
    def __init__(
        self,
        handle: AuthenticatedProfileHandle,
        lease_root: Path,
        lock_path: Path,
        active_record_path: Path,
        lock_fd: int,
        record: ProfileLeaseRecord,
    ) -> None:
        self.handle = handle
        self.lease_root = lease_root
        self.lock_path = lock_path
        self.active_record_path = active_record_path
        self._lock_fd = lock_fd
        self._record = record
        self._released = False

    @classmethod
    def acquire(
        cls,
        handle: AuthenticatedProfileHandle,
        *,
        invocation_id: str,
        lease_root: Path,
        forbidden_roots: tuple[Path, ...],
        process_start_token: str,
        boot_id: str,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> ProfileLease:
        validate_profile_handle(handle, forbidden_roots=forbidden_roots)
        if not _INVOCATION.fullmatch(invocation_id) or not process_start_token or not boot_id:
            raise ProfileLeaseError(
                AdapterFailureKind.PROFILE_LOCK_FAILED, "invalid lease identity"
            )
        lease_root = _validate_private_directory(lease_root, os.getuid())
        if lease_root == handle.root or lease_root.is_relative_to(handle.root):
            raise ProfileLeaseError(
                AdapterFailureKind.PROFILE_LOCK_FAILED, "lease root overlaps profile"
            )
        stem = str(handle.profile_uuid)
        lock_path = lease_root / f"{stem}.lock"
        active_path = lease_root / f"{stem}.active.json"
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(lock_fd)
            raise ProfileLeaseError(
                AdapterFailureKind.PROFILE_LOCK_FAILED, "profile lock held"
            ) from exc
        if active_path.exists():
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            raise ProfileLeaseError(
                AdapterFailureKind.PROFILE_LOCK_FAILED, "active lease requires reconciliation"
            )
        record = ProfileLeaseRecord(
            invocation_id=invocation_id,
            profile_uuid=stem,
            auth_epoch=handle.auth_epoch,
            pid=os.getpid(),
            process_start_token=process_start_token,
            boot_id=boot_id,
            acquired_monotonic_ns=monotonic_ns(),
            nonce=secrets.token_hex(16),
        )
        payload = json.dumps(asdict(record), sort_keys=True, separators=(",", ":")).encode() + b"\n"
        try:
            _write_once(active_path, payload)
        except OSError:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            raise
        return cls(handle, lease_root, lock_path, active_path, lock_fd, record)

    def release(self, terminal_evidence: Path) -> Path:
        if self._released:
            raise ProfileLeaseError(
                AdapterFailureKind.SIDE_EFFECT_UNCERTAIN, "lease already released"
            )
        try:
            if terminal_evidence.is_symlink() or not terminal_evidence.is_file():
                raise OSError
            terminal_hash = hashlib.sha256(terminal_evidence.read_bytes()).hexdigest()
            released = self.lease_root / (
                f"{self.handle.profile_uuid}.{self._record.invocation_id}."
                f"{terminal_hash}.released.json"
            )
            if released.exists():
                raise OSError
            os.rename(self.active_record_path, released)
            _sync_directory(self.lease_root)
        except OSError as exc:
            raise ProfileLeaseError(
                AdapterFailureKind.SIDE_EFFECT_UNCERTAIN, "terminal evidence or release ambiguous"
            ) from exc
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        os.close(self._lock_fd)
        self._released = True
        return released
