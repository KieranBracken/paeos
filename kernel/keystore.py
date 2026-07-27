"""Kernel keystore — the one Ed25519 signing key the kernel holds (A-5).

Task B0.9 (with the Seal Authority). PAEOS-7.5 A-5: signing keys are held by the *kernel*, never
by agents. This module load-or-creates that single key so it persists across process restarts —
which the seal (B0.9) requires (a seal minted before a restart must still verify) and which the
capability broker (B0.8) also uses.

The key file lives under `ops/keys/` — **gitignored and never committed** (CI gate F3 enforces
this). It is the 32-byte Ed25519 seed, written `0600`. Rotation is a founder/ops act.
"""

from __future__ import annotations

import os
from pathlib import Path

from nacl.signing import SigningKey

__all__ = ["DEFAULT_KEY_PATH", "load_or_create_signing_key"]

# Default location of the kernel signing key. Under ops/keys/ ⇒ gitignored (F3).
DEFAULT_KEY_PATH = Path("ops/keys/kernel_ed25519.key")

_SEED_LEN = 32  # Ed25519 seed length


def load_or_create_signing_key(path: str | os.PathLike[str] = DEFAULT_KEY_PATH) -> SigningKey:
    """Return the kernel `SigningKey` at `path`, creating and persisting one if absent.

    The file is the raw 32-byte seed, mode 0600. Creation is atomic-ish (write to a temp file
    then rename) so a crash never leaves a truncated key under the final name.
    """
    key_path = Path(path)
    if key_path.exists():
        seed = key_path.read_bytes()
        if len(seed) != _SEED_LEN:
            raise ValueError(f"kernel key at {key_path} is {len(seed)} bytes, expected {_SEED_LEN}")
        return SigningKey(seed)

    key_path.parent.mkdir(parents=True, exist_ok=True)
    signing_key = SigningKey.generate()
    seed = bytes(signing_key)  # the 32-byte seed
    tmp = key_path.parent / f".{key_path.name}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, seed)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, key_path)
    return signing_key
