"""CAS boundary tests for worker evidence publication."""

from __future__ import annotations

from pathlib import Path

import pytest
from kernel.cas import CAS, InMemoryCasStore
from runtime.worker_evidence import publish_scanned_bundle, scan_and_stage_evidence


def test_publication_does_not_create_court_or_ledger_state(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    (source / "receipt.json").write_text('{"status":"clean"}')
    bundle = scan_and_stage_evidence(
        source,
        allowlist=("receipt.json",),
        staging_root=tmp_path / "staging",
        quarantine_root=tmp_path / "quarantine",
        free_bytes=536_870_912,
    )
    cas = CAS(InMemoryCasStore())

    receipt = publish_scanned_bundle(bundle, cas)

    assert receipt.cas_hashes
    assert not (tmp_path / "court").exists()
    assert not (tmp_path / "ledger").exists()


def test_cas_failure_is_not_retried_or_converted_to_a_seal(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    (source / "receipt.json").write_text('{"status":"clean"}')
    bundle = scan_and_stage_evidence(
        source,
        allowlist=("receipt.json",),
        staging_root=tmp_path / "staging",
        quarantine_root=tmp_path / "quarantine",
        free_bytes=536_870_912,
    )

    class FailingCas:
        def __init__(self) -> None:
            self.calls = 0

        def put(self, _data: bytes) -> str:
            self.calls += 1
            raise RuntimeError("synthetic CAS outage")

    cas = FailingCas()
    with pytest.raises(RuntimeError, match="synthetic CAS outage"):
        publish_scanned_bundle(bundle, cas)  # type: ignore[arg-type]
    assert cas.calls == 1
