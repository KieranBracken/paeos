"""Read independently pinned public identity and signed policy inputs.

This dormant tooling format is NOT enrollment, a policy store or an egress permit.
Paths, pins, key ID and clock must come from independent supervisor configuration,
never worker arguments, the documents being verified, environment or defaults.
Production consumers remain disabled. Currentness, revocation, rollback protection,
signer isolation, admission and atomic attempt reservation are separate obligations.
Same-UID ownership/mode bits do not establish those facts. No private key is loaded.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from nacl.signing import VerifyKey
from paeos.model_router.disclosure_policy import (
    DisclosurePolicyError,
    DisclosurePolicyManifest,
    policy_digest,
    verify_founder_derivative_policy,
    verify_founder_policy,
)

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")
_PUBLIC_LIMIT = 4096
_POLICY_LIMIT = 1024 * 1024


class DisclosureInputError(ValueError):
    """Unusable pinned input; intentionally contains no paths or document content."""


def _parts(value: str) -> list[str]:
    if (
        type(value) is not str
        or not value
        or len(value) > 4096
        or "\\" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
        or any(p in ("", ".", "..") for p in value.split("/"))
    ):
        raise DisclosureInputError("invalid input path")
    return value.split("/")


@contextmanager
def _directory(parts: list[str], *, parent: int | None = None):
    # Never resolve then reopen a pathname. Every traversal is relative to a pinned
    # descriptor, so ancestor/leaf substitution cannot redirect a later read.
    fd = os.dup(parent) if parent is not None else os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=fd,
            )
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _read(root_fd: int, parts: list[str], limit: int) -> bytes:
    with _directory(parts[:-1], parent=root_fd) as directory:
        fd = os.open(
            parts[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=directory,
        )
        try:
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= limit:
                raise DisclosureInputError("input is not a bounded regular file")
            chunks = []
            total = 0
            while total <= limit:
                block = os.read(fd, min(65536, limit + 1 - total))
                if not block:
                    break
                chunks.append(block)
                total += len(block)
            if total > limit:
                raise DisclosureInputError("input exceeds size bound")
            return b"".join(chunks)
        finally:
            os.close(fd)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DisclosureInputError("public identity has duplicate fields")
        result[key] = value
    return result


def load_pinned_disclosure_policy(
    *,
    root: Path,
    public_key_relative_path: str,
    policy_relative_path: str,
    expected_key_id: str,
    expected_public_key_sha256: str,
    expected_policy_sha256: str,
    now: datetime,
    expected_policy_version: int = 1,
) -> DisclosurePolicyManifest:
    """Return a signature-verified snapshot only; no current-authority claim.

    Public-key pin hashes the 32 raw public bytes. Policy pin uses the existing
    canonical signed-envelope digest. Public JSON fields are exactly schema,
    key_id, algorithm and public_key_hex. No write, install or network occurs.
    The parent selects the expected version independently; document contents
    cannot upgrade the default v1 verifier or select a fallback parser.
    """
    if (
        type(expected_policy_version) is not int
        or expected_policy_version not in (1, 2)
        or type(expected_key_id) is not str
        or not _ID.fullmatch(expected_key_id)
        or any(
            type(v) is not str or not _HASH.fullmatch(v)
            for v in (
                expected_public_key_sha256,
                expected_policy_sha256,
            )
        )
        or not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
        or not isinstance(root, Path)
        or not root.is_absolute()
    ):
        raise DisclosureInputError("independent verification inputs are invalid")
    root_parts = _parts(str(root)[1:])
    public_parts = _parts(public_key_relative_path)
    policy_parts = _parts(policy_relative_path)
    try:
        with _directory(root_parts) as root_fd:
            public_bytes = _read(root_fd, public_parts, _PUBLIC_LIMIT)
            document = json.loads(public_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
            if (
                type(document) is not dict
                or set(document) != {"schema", "key_id", "algorithm", "public_key_hex"}
                or document["schema"] != "paeos.founder-public-key/1"
                or document["key_id"] != expected_key_id
                or document["algorithm"] != "Ed25519"
                or type(document["public_key_hex"]) is not str
                or not _HASH.fullmatch(document["public_key_hex"])
            ):
                raise DisclosureInputError("public identity is malformed or mismatched")
            raw_key = bytes.fromhex(document["public_key_hex"])
            if not hmac.compare_digest(
                hashlib.sha256(raw_key).hexdigest(), expected_public_key_sha256
            ):
                raise DisclosureInputError("public identity pin mismatch")
            verifier = (
                verify_founder_policy
                if expected_policy_version == 1
                else verify_founder_derivative_policy
            )
            manifest = verifier(
                _read(root_fd, policy_parts, _POLICY_LIMIT),
                VerifyKey(raw_key),
                expected_key_id,
                now=now,
            )
            if not hmac.compare_digest(policy_digest(manifest), expected_policy_sha256):
                raise DisclosureInputError("policy pin mismatch")
            return manifest
    except (OSError, ValueError, UnicodeError, RecursionError, DisclosurePolicyError):
        raise DisclosureInputError("pinned disclosure inputs did not verify") from None
