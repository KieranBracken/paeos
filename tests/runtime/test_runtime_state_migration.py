from __future__ import annotations

import json
import stat
from dataclasses import replace
from pathlib import Path

import pytest
from nacl.signing import SigningKey
from ops.runtime_state_migration import (
    ManifestEntry,
    MigrationError,
    fingerprint_signing_key,
    freeze_historical_state,
    initialize_fresh_state,
    manifest_digest,
    manifest_tree,
)


def _historical_state(root: Path) -> bytes:
    (root / "court").mkdir(parents=True)
    (root / "court" / "r-1.jsonl").write_text('{"evidence":"kept"}\n')
    (root / "ledger.db").write_bytes(b"historical-ledger")
    old_seed = bytes(SigningKey.generate())
    (root / "seal.key").write_bytes(old_seed)
    return old_seed


def test_archive_is_byte_exact_and_manifest_contains_no_secret_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    old_seed = _historical_state(source)
    frozen = freeze_historical_state(
        source_root=source,
        archive_root=tmp_path / "archives",
        archive_id="baseline",
        source_commit="a" * 40,
    )
    assert stat.S_IMODE(frozen.archive_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(frozen.state_root.stat().st_mode) == 0o700
    assert manifest_digest(manifest_tree(source)) == frozen.manifest_hash
    assert manifest_digest(manifest_tree(frozen.state_root)) == frozen.manifest_hash
    metadata = frozen.metadata_path.read_bytes()
    assert old_seed not in metadata
    assert json.loads(metadata)["source_commit"] == "a" * 40


def test_archive_refuses_existing_destination_and_source_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _historical_state(source)
    archives = tmp_path / "archives"
    freeze_historical_state(
        source_root=source,
        archive_root=archives,
        archive_id="baseline",
        source_commit="b" * 40,
    )
    with pytest.raises(MigrationError, match="already exists"):
        freeze_historical_state(
            source_root=source,
            archive_root=archives,
            archive_id="baseline",
            source_commit="b" * 40,
        )
    (source / "escape").symlink_to(tmp_path / "outside")
    with pytest.raises(MigrationError, match="symlink"):
        manifest_tree(source)


def test_new_trust_domain_never_reuses_historical_seed(tmp_path: Path) -> None:
    historical = tmp_path / "historical.key"
    old_seed = bytes(SigningKey.generate())
    historical.write_bytes(old_seed)
    trust = initialize_fresh_state(
        new_state_root=tmp_path / "runtime-v2",
        historical_key_path=historical,
        archive_manifest_hash="c" * 64,
    )
    new_seed = (trust.state_root / "seal.key").read_bytes()
    assert new_seed != old_seed
    assert trust.old_public_fingerprint == fingerprint_signing_key(historical)
    assert trust.new_public_fingerprint == fingerprint_signing_key(trust.state_root / "seal.key")
    assert stat.S_IMODE((trust.state_root / "seal.key").stat().st_mode) == 0o600
    assert old_seed not in (trust.state_root / "trust-domain.json").read_bytes()


def test_source_drift_fails_closed_and_preserves_partial_archive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import ops.runtime_state_migration as migration

    source = tmp_path / "source"
    _historical_state(source)
    real_manifest_tree = migration.manifest_tree
    calls = 0

    def drifting_manifest(root: Path) -> tuple[ManifestEntry, ...]:
        nonlocal calls
        calls += 1
        entries = real_manifest_tree(root)
        if calls == 3:
            return (replace(entries[0], sha256="0" * 64), *entries[1:])
        return entries

    monkeypatch.setattr(migration, "manifest_tree", drifting_manifest)
    archive = tmp_path / "archives" / "baseline"
    with pytest.raises(MigrationError, match="source changed during archival"):
        migration.freeze_historical_state(
            source_root=source,
            archive_root=tmp_path / "archives",
            archive_id="baseline",
            source_commit="d" * 40,
        )
    assert archive.is_dir()
    assert (archive / "state").is_dir()
