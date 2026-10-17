"""Secret-blind staging and CAS publication for worker-admission evidence."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from kernel.cas import CAS

MAX_EVIDENCE_BUNDLE_BYTES = 67_108_864
MIN_FREE_BYTES_BEFORE_CAPTURE = 536_870_912
SCANNER_RULE_VERSION = "paeos-secret-scanner/1"


class SecretCategory(StrEnum):
    PRIVATE_KEY = "PRIVATE_KEY"
    AUTHORIZATION_HEADER = "AUTHORIZATION_HEADER"
    TOKEN_ASSIGNMENT = "TOKEN_ASSIGNMENT"
    COOKIE = "COOKIE"
    JWT_SHAPE = "JWT_SHAPE"
    PROVIDER_KEY_PREFIX = "PROVIDER_KEY_PREFIX"


@dataclass(frozen=True, slots=True)
class SecretFinding:
    category: SecretCategory
    artifact_name: str
    byte_offset: int
    byte_length: int
    scanner_rule_version: str
    redacted_artifact_sha256: str


@dataclass(frozen=True, slots=True)
class ScannedEvidenceBundle:
    canonical_bytes: bytes
    artifact_names: tuple[str, ...]
    findings: tuple[SecretFinding, ...]
    quarantine_reason: str | None
    quarantine_receipt: Path | None


@dataclass(frozen=True, slots=True)
class EvidenceCasReceipt:
    bundle_sha256: str
    cas_hashes: tuple[str, ...]


class EvidencePublishError(RuntimeError):
    """A bundle is not eligible for CAS publication."""


_PATTERNS: tuple[tuple[SecretCategory, re.Pattern[bytes]], ...] = (
    (
        SecretCategory.PRIVATE_KEY,
        re.compile(
            rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    (
        SecretCategory.AUTHORIZATION_HEADER,
        re.compile(rb"(?im)\bAuthorization:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    ),
    (
        SecretCategory.COOKIE,
        re.compile(rb"(?im)\b(?:Cookie|Set-Cookie):\s*[^\r\n]+"),
    ),
    (
        SecretCategory.TOKEN_ASSIGNMENT,
        re.compile(rb"(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]{8,}"),
    ),
    (
        SecretCategory.JWT_SHAPE,
        re.compile(rb"\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    (
        SecretCategory.PROVIDER_KEY_PREFIX,
        re.compile(
            rb"\b(?:sk-[A-Za-z0-9][A-Za-z0-9_-]{11,}|AIza[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9][A-Za-z0-9_-]{11,}|xai-[A-Za-z0-9][A-Za-z0-9_-]{11,})\b"
        ),
    ),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("short evidence write")
        offset += written


def _private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    metadata = path.stat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise EvidencePublishError("evidence directory is not private")


def _quarantine(
    quarantine_root: Path,
    reason: str,
    artifact_names: tuple[str, ...],
) -> Path:
    _private_dir(quarantine_root)
    receipt = quarantine_root / f"receipt-{_sha(reason.encode())[:24]}.json"
    payload = json.dumps(
        {"artifact_count": len(artifact_names), "reason": reason, "schema": "paeos.quarantine/1"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    descriptor = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(descriptor, payload + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    descriptor = os.open(quarantine_root, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return receipt


def _scan_bytes(name: str, data: bytes) -> tuple[SecretFinding, ...]:
    matches: list[tuple[int, int, SecretCategory]] = []
    for category, pattern in _PATTERNS:
        for match in pattern.finditer(data):
            matches.append((match.start(), match.end(), category))
    matches.sort(key=lambda item: (item[0], item[1], item[2].value))
    selected: list[tuple[int, int, SecretCategory]] = []
    for match in matches:
        if any(match[0] < end and start < match[1] for start, end, _ in selected):
            continue
        selected.append(match)
    if not selected:
        return ()
    redacted = bytearray(data)
    for start, end, _ in selected:
        redacted[start:end] = b"\0" * (end - start)
    redacted_hash = _sha(bytes(redacted))
    return tuple(
        SecretFinding(category, name, start, end - start, SCANNER_RULE_VERSION, redacted_hash)
        for start, end, category in selected
    )


def _write_staged(staging_root: Path, canonical: bytes) -> None:
    _private_dir(staging_root)
    target = staging_root / "bundle.json"
    temporary = staging_root / f".bundle.{os.getpid()}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(descriptor, canonical)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.rename(temporary, target)
    descriptor = os.open(staging_root, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def scan_and_stage_evidence(
    source_root: Path,
    *,
    allowlist: tuple[str, ...],
    staging_root: Path,
    quarantine_root: Path,
    free_bytes: int | None = None,
) -> ScannedEvidenceBundle:
    """Scan an allowlisted evidence directory and stage only clean canonical bytes."""

    if not source_root.is_absolute() or not source_root.is_dir():
        receipt = _quarantine(quarantine_root, "INCOMPLETE_CAPTURE", ())
        return ScannedEvidenceBundle(b"", (), (), "INCOMPLETE_CAPTURE", receipt)
    measured_free = free_bytes if free_bytes is not None else shutil.disk_usage(source_root).free
    if measured_free < MIN_FREE_BYTES_BEFORE_CAPTURE:
        receipt = _quarantine(quarantine_root, "INSUFFICIENT_FREE_SPACE", allowlist)
        return ScannedEvidenceBundle(
            b"", tuple(sorted(allowlist)), (), "INSUFFICIENT_FREE_SPACE", receipt
        )
    expected = set(allowlist)
    discovered: dict[str, Path] = {}
    for path in source_root.rglob("*"):
        relative = path.relative_to(source_root).as_posix()
        if path.is_dir() and not path.is_symlink():
            continue
        discovered[relative] = path
    if set(discovered) - expected:
        names = tuple(sorted(discovered))
        receipt = _quarantine(quarantine_root, "UNALLOWLISTED_FILE", names)
        return ScannedEvidenceBundle(b"", names, (), "UNALLOWLISTED_FILE", receipt)
    if expected - set(discovered):
        names = tuple(sorted(expected))
        receipt = _quarantine(quarantine_root, "INCOMPLETE_CAPTURE", names)
        return ScannedEvidenceBundle(b"", names, (), "INCOMPLETE_CAPTURE", receipt)
    total_size = 0
    contents: dict[str, bytes] = {}
    for name in sorted(expected):
        path = discovered[name]
        if path.is_symlink() or not path.is_file():
            receipt = _quarantine(quarantine_root, "SYMLINK_OR_NONREGULAR", (name,))
            return ScannedEvidenceBundle(b"", (name,), (), "SYMLINK_OR_NONREGULAR", receipt)
        data = path.read_bytes()
        total_size += len(data)
        if total_size > MAX_EVIDENCE_BUNDLE_BYTES:
            receipt = _quarantine(quarantine_root, "EVIDENCE_TOO_LARGE", tuple(sorted(expected)))
            return ScannedEvidenceBundle(
                b"", tuple(sorted(expected)), (), "EVIDENCE_TOO_LARGE", receipt
            )
        contents[name] = data
    findings = tuple(
        finding for name in sorted(contents) for finding in _scan_bytes(name, contents[name])
    )
    if findings:
        receipt = _quarantine(quarantine_root, "SECRET_FOUND", tuple(sorted(contents)))
        return ScannedEvidenceBundle(
            b"", tuple(sorted(contents)), findings, "SECRET_FOUND", receipt
        )
    entries = [
        {
            "bytes_b64": base64.b64encode(contents[name]).decode("ascii"),
            "name": name,
            "sha256": _sha(contents[name]),
        }
        for name in sorted(contents)
    ]
    canonical = (
        json.dumps(
            {"artifacts": entries, "schema": "paeos.worker-evidence/1"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )
    _write_staged(staging_root, canonical)
    return ScannedEvidenceBundle(canonical, tuple(sorted(contents)), (), None, None)


def publish_scanned_bundle(bundle: ScannedEvidenceBundle, cas: CAS) -> EvidenceCasReceipt:
    """Publish one clean staged bundle; this function has no ledger or Court side effects."""

    if bundle.quarantine_reason is not None or bundle.findings:
        raise EvidencePublishError("quarantined evidence cannot enter CAS")
    if not bundle.canonical_bytes:
        raise EvidencePublishError("empty evidence bundle")
    bundle_hash = cas.put(bundle.canonical_bytes)
    return EvidenceCasReceipt(bundle_sha256=bundle_hash, cas_hashes=(bundle_hash,))
