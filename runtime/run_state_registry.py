"""Signed registration for externally materialized governed run roots.

The filesystem may contain residue after interruption.  Only a root with a valid supervisor/runtime
registration marker in ``REGISTERED`` state is authoritative.  Unmarked or partial roots are
classified as ``QUARANTINED`` and cannot be reused as a governed run.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey

__all__ = ["RunRegistration", "RunRegistrationError", "RunState", "RunStateRegistry"]

_SCHEMA = "paeos-run-registration/1"
_RUN_ID = re.compile(r"^r-[A-Za-z0-9_.:-]+$")


class RunRegistrationError(RuntimeError):
    """A run root cannot be classified and registered without ambiguity."""


class RunState(StrEnum):
    STAGING = "STAGING"
    REGISTERED = "REGISTERED"
    QUARANTINED = "QUARANTINED"
    RECOVERABLE = "RECOVERABLE"


@dataclass(frozen=True, slots=True)
class RunRegistration:
    run_id: str
    goal_signature: str
    root: Path
    marker_path: Path
    state: RunState


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _write_atomic(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            count = os.write(fd, payload[offset:])
            if count <= 0:
                raise OSError("registration write made no progress")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class RunStateRegistry:
    def __init__(
        self,
        roots: Path,
        signing_key: SigningKey,
        *,
        clock: Callable[[], int] | None = None,
    ) -> None:
        if not roots.is_absolute() or roots.is_symlink():
            raise ValueError("run registration root must be an absolute non-symlink path")
        self._roots = roots
        self._key = signing_key
        self._clock = clock or (lambda: int(time.time()))

    def _payload(self, run_id: str, goal_signature: str, state: RunState) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "run_id": run_id,
            "goal_signature": goal_signature,
            "state": state.value,
            "created_at": self._clock(),
        }

    def _marker(self, root: Path, payload: dict[str, object]) -> Path:
        marker = root / "registration.json"
        envelope = {
            "payload": payload,
            "signature": self._key.sign(_canonical(payload)).signature.hex(),
        }
        _write_atomic(marker, _canonical(envelope))
        marker.chmod(0o600)
        return marker

    def register(
        self,
        run_id: str,
        goal_signature: str,
        *,
        repository_root: Path | None = None,
    ) -> RunRegistration:
        if _RUN_ID.fullmatch(run_id) is None or not goal_signature:
            raise RunRegistrationError("run identity is invalid")
        roots = self._roots.resolve()
        if repository_root is not None:
            repository = repository_root.resolve()
            if roots == repository or roots.is_relative_to(repository):
                raise RunRegistrationError("run registration root is inside repository")
        roots.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(roots, 0o700)
        root = roots / run_id
        if root.exists() or root.is_symlink():
            raise RunRegistrationError("run root already exists and cannot be reused")
        try:
            root.mkdir(mode=0o700)
            staging = self._marker(root, self._payload(run_id, goal_signature, RunState.STAGING))
            (root / "quarantine").mkdir(mode=0o700)
            (root / "events").mkdir(mode=0o700)
            registered = self._marker(root, self._payload(run_id, goal_signature, RunState.REGISTERED))
            del staging
            return RunRegistration(run_id, goal_signature, root, registered, RunState.REGISTERED)
        except (OSError, ValueError) as exc:
            try:
                marker = self._marker(root, self._payload(run_id, goal_signature, RunState.QUARANTINED))
            except (OSError, ValueError) as marker_exc:
                raise RunRegistrationError("run root exists but cannot be classified") from marker_exc
            raise RunRegistrationError(f"run registration failed; root quarantined at {marker}") from exc

    def verify(self, root: Path, run_id: str) -> RunRegistration:
        if not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise RunRegistrationError("run root is unavailable")
        expected_root = self._roots.resolve() / run_id
        try:
            resolved_root = root.resolve(strict=True)
        except OSError as exc:
            raise RunRegistrationError("run root is unavailable") from exc
        if resolved_root != root or resolved_root != expected_root:
            raise RunRegistrationError("run root is outside the registration namespace")
        marker = root / "registration.json"
        try:
            document = json.loads(marker.read_text(encoding="utf-8"))
            payload = document["payload"]
            signature = document["signature"]
            self._key.verify_key.verify(_canonical(payload), bytes.fromhex(signature))
        except (OSError, KeyError, TypeError, ValueError, BadSignatureError) as exc:
            raise RunRegistrationError("run root is not registered or registration is invalid") from exc
        if not isinstance(payload, dict) or payload.get("schema") != _SCHEMA or payload.get("run_id") != run_id:
            raise RunRegistrationError("run root identity does not match")
        try:
            state = RunState(payload["state"])
        except (KeyError, ValueError) as exc:
            raise RunRegistrationError("run root state is invalid") from exc
        if state is not RunState.REGISTERED:
            raise RunRegistrationError("run root is not registered")
        return RunRegistration(run_id, str(payload.get("goal_signature", "")), root, marker, state)

    def discover(self) -> tuple[tuple[Path, RunState], ...]:
        if not self._roots.exists():
            return ()
        if self._roots.is_symlink() or not self._roots.is_dir():
            raise RunRegistrationError("run registration root is unavailable")
        found: list[tuple[Path, RunState]] = []
        for root in sorted(self._roots.iterdir()):
            if root.is_symlink():
                found.append((root, RunState.QUARANTINED))
                continue
            if not root.is_dir():
                continue
            try:
                document = json.loads((root / "registration.json").read_text(encoding="utf-8"))
                payload = document["payload"]
                self._key.verify_key.verify(_canonical(payload), bytes.fromhex(document["signature"]))
                state = RunState(payload["state"])
                if payload.get("run_id") != root.name:
                    raise ValueError("run identity mismatch")
                if state is RunState.STAGING:
                    # A valid STAGING marker means the process stopped between the two
                    # registration transitions.  It is physical residue, never authority.
                    state = RunState.QUARANTINED
            except (OSError, KeyError, TypeError, ValueError, BadSignatureError):
                state = RunState.QUARANTINED
            found.append((root, state))
        return tuple(found)
