"""TDD contract for secret-blind authenticated Cline profile leases."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from runtime.worker_adapter import AdapterFailureKind
from runtime.worker_profile import (
    AuthenticatedProfileHandle,
    ProfileLease,
    ProfileLeaseError,
    public_profile_payload,
    validate_profile_handle,
)

PROFILE_UUID = UUID("6f05f1b8-297d-46cf-8e4c-5af5fc0c31da")


def _private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True)
    path.chmod(0o700)
    return path


def _handle(tmp_path: Path) -> AuthenticatedProfileHandle:
    return AuthenticatedProfileHandle(
        root=_private_dir(tmp_path / "cline-profile"),
        profile_uuid=PROFILE_UUID,
        auth_epoch=3,
    )


def _acquire(tmp_path: Path) -> ProfileLease:
    handle = _handle(tmp_path)
    lease_root = _private_dir(tmp_path / "profile-leases")
    return ProfileLease.acquire(
        handle,
        invocation_id="probe-003",
        lease_root=lease_root,
        forbidden_roots=(tmp_path / "forbidden",),
        process_start_token="pid:123:start:456",
        boot_id="boot-test-001",
        monotonic_ns=lambda: 123_456_789,
    )


def test_public_handle_serializes_only_root_uuid_and_auth_epoch(tmp_path: Path) -> None:
    payload = public_profile_payload(_handle(tmp_path))

    assert payload == {
        "auth_epoch": 3,
        "profile_root": str(tmp_path / "cline-profile"),
        "profile_uuid": str(PROFILE_UUID),
    }


def test_auth_epoch_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="auth_epoch"):
        AuthenticatedProfileHandle(
            root=_private_dir(tmp_path / "cline-profile"),
            profile_uuid=PROFILE_UUID,
            auth_epoch=0,
        )


def test_profile_root_must_be_absolute_private_and_outside_forbidden_roots(
    tmp_path: Path,
) -> None:
    relative = AuthenticatedProfileHandle(Path("relative"), PROFILE_UUID, 1)
    with pytest.raises(ProfileLeaseError) as relative_error:
        validate_profile_handle(relative, forbidden_roots=())
    assert relative_error.value.kind is AdapterFailureKind.PROFILE_LOCK_FAILED

    forbidden = _private_dir(tmp_path / "repository" / "profile")
    handle = AuthenticatedProfileHandle(forbidden, PROFILE_UUID, 1)
    with pytest.raises(ProfileLeaseError):
        validate_profile_handle(handle, forbidden_roots=(tmp_path / "repository",))


def test_profile_rejects_symlink_component_before_traversal(tmp_path: Path) -> None:
    real_parent = _private_dir(tmp_path / "real-parent")
    profile = _private_dir(real_parent / "profile")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    handle = AuthenticatedProfileHandle(linked_parent / profile.name, PROFILE_UUID, 1)

    with pytest.raises(ProfileLeaseError) as exc:
        validate_profile_handle(handle, forbidden_roots=())

    assert exc.value.kind is AdapterFailureKind.PROFILE_LOCK_FAILED


def test_profile_rejects_wrong_owner_or_group_world_permissions(tmp_path: Path) -> None:
    handle = _handle(tmp_path)
    handle.root.chmod(0o750)
    with pytest.raises(ProfileLeaseError):
        validate_profile_handle(handle, forbidden_roots=())

    handle.root.chmod(0o700)
    with pytest.raises(ProfileLeaseError):
        validate_profile_handle(handle, forbidden_roots=(), expected_uid=os.getuid() + 1)


def test_second_process_cannot_acquire_same_profile_lock(tmp_path: Path) -> None:
    lease = _acquire(tmp_path)
    code = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit(23)
raise SystemExit(0)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(lease.lock_path)], check=False, timeout=5
    )

    assert result.returncode == 23
    terminal = tmp_path / "terminal.json"
    terminal.write_text("{}\n", encoding="utf-8")
    lease.release(terminal)


def test_active_record_without_held_lock_requires_manual_recovery(tmp_path: Path) -> None:
    lease = _acquire(tmp_path)
    active_path = lease.active_record_path
    terminal = tmp_path / "terminal.json"
    terminal.write_text("{}\n", encoding="utf-8")
    lease.release(terminal)
    released = next(lease.lease_root.glob("*.released.json"))
    active_path.write_bytes(released.read_bytes())
    active_path.chmod(0o600)

    with pytest.raises(ProfileLeaseError) as exc:
        ProfileLease.acquire(
            lease.handle,
            invocation_id="probe-004",
            lease_root=lease.lease_root,
            forbidden_roots=(),
            process_start_token="pid:124:start:999",
            boot_id="boot-test-001",
        )

    assert exc.value.kind is AdapterFailureKind.PROFILE_LOCK_FAILED
    assert active_path.exists()


def test_ambiguous_release_retains_active_record_and_blocks_reuse(tmp_path: Path) -> None:
    lease = _acquire(tmp_path)

    with pytest.raises(ProfileLeaseError) as exc:
        lease.release(tmp_path / "missing-terminal.json")

    assert exc.value.kind is AdapterFailureKind.SIDE_EFFECT_UNCERTAIN
    assert lease.active_record_path.exists()
    assert not tuple(lease.lease_root.glob("*.released.json"))


def test_normal_release_preserves_history_and_permits_fresh_invocation(tmp_path: Path) -> None:
    lease = _acquire(tmp_path)
    terminal = tmp_path / "terminal.json"
    terminal.write_text('{"status":"terminal"}\n', encoding="utf-8")

    released_path = lease.release(terminal)

    assert released_path.exists()
    assert not lease.active_record_path.exists()
    record = json.loads(released_path.read_text(encoding="utf-8"))
    assert record["invocation_id"] == "probe-003"
    assert record["profile_uuid"] == str(PROFILE_UUID)
    assert len(released_path.name.split(".")[-3]) == 64

    second = ProfileLease.acquire(
        lease.handle,
        invocation_id="probe-004",
        lease_root=lease.lease_root,
        forbidden_roots=(),
        process_start_token="pid:124:start:999",
        boot_id="boot-test-001",
    )
    second_terminal = tmp_path / "terminal-2.json"
    second_terminal.write_text("{}\n", encoding="utf-8")
    second.release(second_terminal)
    assert len(tuple(lease.lease_root.glob("*.released.json"))) == 2


def test_profile_validation_never_lists_reads_or_hashes_profile_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handle = _handle(tmp_path)
    credential = handle.root / "provider-token.json"
    credential.write_text("synthetic-secret-that-must-not-be-read", encoding="utf-8")
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path.is_relative_to(handle.root):
            raise AssertionError("profile content read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(
        Path,
        "iterdir",
        lambda path: (_ for _ in ()).throw(AssertionError("profile content listed")),
    )

    validate_profile_handle(handle, forbidden_roots=())


def test_lease_record_is_private_and_content_free(tmp_path: Path) -> None:
    lease = _acquire(tmp_path)
    record_text = lease.active_record_path.read_text(encoding="utf-8")

    assert lease.active_record_path.stat().st_mode & 0o777 == 0o600
    assert "credential" not in record_text.lower()
    assert "api_key" not in record_text.lower()
    assert "synthetic-secret" not in record_text
    assert fcntl.LOCK_NB
    terminal = tmp_path / "terminal.json"
    terminal.write_text("{}\n", encoding="utf-8")
    lease.release(terminal)
