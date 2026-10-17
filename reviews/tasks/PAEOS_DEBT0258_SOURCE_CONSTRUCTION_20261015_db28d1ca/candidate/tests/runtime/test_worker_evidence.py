"""TDD tests for secret-blind worker evidence capture and staging."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from kernel.cas import CAS, InMemoryCasStore
from runtime.worker_evidence import (
    MIN_FREE_BYTES_BEFORE_CAPTURE,
    EvidencePublishError,
    ScannedEvidenceBundle,
    SecretCategory,
    publish_scanned_bundle,
    scan_and_stage_evidence,
)


def _scan(
    tmp_path: Path, data: bytes, *, free_bytes: int = MIN_FREE_BYTES_BEFORE_CAPTURE
) -> ScannedEvidenceBundle:
    source = tmp_path / "source"
    staging = tmp_path / "staging"
    quarantine = tmp_path / "quarantine"
    source.mkdir(mode=0o700, parents=True)
    (source / "stdout.raw").write_bytes(data)
    return scan_and_stage_evidence(
        source,
        allowlist=("stdout.raw",),
        staging_root=staging,
        quarantine_root=quarantine,
        free_bytes=free_bytes,
    )


@pytest.mark.parametrize(
    ("category", "payload"),
    [
        (
            SecretCategory.PRIVATE_KEY,
            b"-----BEGIN PRIVATE KEY-----\nsynthetic\n-----END PRIVATE KEY-----",
        ),
        (SecretCategory.AUTHORIZATION_HEADER, b"Authorization: Bearer synthetic-bearer-value"),
        (SecretCategory.JWT_SHAPE, b"eyJsynthetic.eyJpayload.synthetic-signature"),
        (SecretCategory.COOKIE, b"Cookie: session=synthetic-cookie-value"),
        (SecretCategory.TOKEN_ASSIGNMENT, b"TOKEN=synthetic-assigned-token-value"),
        (SecretCategory.PROVIDER_KEY_PREFIX, b"key=sk-synthetic-provider-key-value"),
    ],
)
def test_secret_categories_are_reported_without_echoing_secret_bytes(
    tmp_path: Path,
    category: SecretCategory,
    payload: bytes,
) -> None:
    bundle = _scan(tmp_path, payload)
    serialized = repr(bundle)

    assert any(finding.category is category for finding in bundle.findings)
    assert payload.decode() not in serialized
    assert all(finding.byte_length > 0 for finding in bundle.findings)
    assert all(finding.scanner_rule_version for finding in bundle.findings)
    assert all(len(finding.redacted_artifact_sha256) == 64 for finding in bundle.findings)


def test_clean_bundle_is_canonical_and_publishes_once(tmp_path: Path) -> None:
    bundle = _scan(tmp_path, b"content-free structured evidence")
    cas = CAS(InMemoryCasStore())

    receipt = publish_scanned_bundle(bundle, cas)

    assert receipt.bundle_sha256 == hashlib.sha256(bundle.canonical_bytes).hexdigest()
    assert receipt.cas_hashes == (receipt.bundle_sha256,)
    assert cas.get(receipt.bundle_sha256) == bundle.canonical_bytes


def test_secret_bundle_cannot_publish_to_cas(tmp_path: Path) -> None:
    bundle = _scan(tmp_path, b"Authorization: Bearer synthetic-no-echo-value")
    cas = CAS(InMemoryCasStore())

    with pytest.raises(EvidencePublishError):
        publish_scanned_bundle(bundle, cas)

    assert list(cas._store.iter_keys()) == []  # type: ignore[attr-defined]


def test_secret_finding_hash_is_independent_of_secret_value(tmp_path: Path) -> None:
    first = _scan(tmp_path / "first", b"TOKEN=first-secret-value-123\ncontext")
    second = _scan(tmp_path / "second", b"TOKEN=other-secret-value-999\ncontext")

    assert first.findings[0].redacted_artifact_sha256 == second.findings[0].redacted_artifact_sha256


def test_exact_size_limit_is_accepted_and_one_byte_more_is_quarantined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("runtime.worker_evidence._write_staged", lambda *_args: None)
    monkeypatch.setattr("runtime.worker_evidence.MAX_EVIDENCE_BUNDLE_BYTES", 2)
    accepted = _scan(tmp_path / "accepted", b"aa")
    assert accepted.quarantine_reason is None
    shutil.rmtree(tmp_path / "accepted")

    rejected = _scan(tmp_path / "rejected", b"aaa")
    assert rejected.quarantine_reason == "EVIDENCE_TOO_LARGE"
    assert rejected.canonical_bytes == b""


def test_free_space_boundary_is_fail_closed(tmp_path: Path) -> None:
    accepted = _scan(tmp_path / "accepted", b"ok", free_bytes=MIN_FREE_BYTES_BEFORE_CAPTURE)
    assert accepted.quarantine_reason is None

    rejected = _scan(
        tmp_path / "rejected",
        b"ok",
        free_bytes=MIN_FREE_BYTES_BEFORE_CAPTURE - 1,
    )
    assert rejected.quarantine_reason == "INSUFFICIENT_FREE_SPACE"


def test_unallowlisted_file_and_symlink_are_quarantined_without_reading_target(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    (source / "stdout.raw").write_bytes(b"safe")
    (source / "unexpected.txt").write_bytes(b"unexpected")
    outside = tmp_path / "outside-secret"
    outside.write_bytes(b"synthetic-target-secret")
    (source / "link.raw").symlink_to(outside)

    bundle = scan_and_stage_evidence(
        source,
        allowlist=("stdout.raw",),
        staging_root=tmp_path / "staging",
        quarantine_root=tmp_path / "quarantine",
        free_bytes=MIN_FREE_BYTES_BEFORE_CAPTURE,
    )

    assert bundle.quarantine_reason == "UNALLOWLISTED_FILE"
    assert b"synthetic-target-secret" not in bundle.quarantine_receipt.read_bytes()  # type: ignore[union-attr]


def test_quarantine_receipt_is_private_and_content_free(tmp_path: Path) -> None:
    bundle = _scan(tmp_path, b"TOKEN=synthetic-quarantine-secret-value")
    receipt = bundle.quarantine_receipt
    assert receipt is not None
    assert receipt.stat().st_mode & 0o777 == 0o600
    assert b"synthetic-quarantine-secret-value" not in receipt.read_bytes()
    assert "TOKEN" not in receipt.read_text()
