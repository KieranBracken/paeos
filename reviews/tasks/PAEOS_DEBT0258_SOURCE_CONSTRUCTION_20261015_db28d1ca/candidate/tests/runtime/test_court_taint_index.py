"""Taint-index behavior of FileCourtEvidencePool (CRITICAL-002 remediation, Entry 140/141).

Fabricated/unbound court rows must be skipped by `evidence_for` once listed in `.tainted.json`,
while byte-different rows — even ones sharing the same claim+command (and therefore the same
Evidence hash) — must still be served. The pool files themselves are never rewritten.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.types import Role
from runtime.orchestrator import FileCourtEvidencePool


def _row(artifact_hash: str) -> Evidence:
    return Evidence(
        hash=content_hash(b"builds:pytest"),
        kind=EvidenceKind.TEST,
        claim_id="builds",
        artifact_hash=artifact_hash,
        environment_hash="e" * 64,
        reproducible_command="pytest",
        producer=EvidenceProducer(role=Role.BUILDER, session="test"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": "ok"},
        attestation="pending-kernel-sig",
    )


def _write_pool(tmp_path: Path) -> FileCourtEvidencePool:
    pool = FileCourtEvidencePool(tmp_path / "court")
    pool.submit("r-taint1", _row(artifact_hash="dummy_hash_for_now"))
    pool.submit("r-taint1", _row(artifact_hash="a" * 64))  # honest row, same claim+command
    return pool


def test_tainted_rows_are_skipped(tmp_path: Path) -> None:
    pool = _write_pool(tmp_path)
    court = tmp_path / "court"
    # before tainting: both rows served
    assert len(pool.evidence_for("r-taint1")) == 2

    lines = [ln for ln in (court / "r-taint1.jsonl").read_text().splitlines() if ln.strip()]
    fabricated = next(ln for ln in lines if json.loads(ln)["artifact_hash"] == "dummy_hash_for_now")
    (court / ".tainted.json").write_text(
        json.dumps({hashlib.sha256(fabricated.encode()).hexdigest(): "test: fabricated"}) + "\n"
    )

    served = pool.evidence_for("r-taint1")
    assert len(served) == 1  # only the honest row
    assert served[0].artifact_hash == "a" * 64


def test_pool_files_are_not_rewritten_by_taint(tmp_path: Path) -> None:
    pool = _write_pool(tmp_path)
    court = tmp_path / "court"
    before = (court / "r-taint1.jsonl").read_text()
    (court / ".tainted.json").write_text(json.dumps({"0" * 64: "unrelated"}) + "\n")
    pool.evidence_for("r-taint1")
    assert (court / "r-taint1.jsonl").read_text() == before  # forensic record intact


def test_corrupt_taint_index_serves_pool(tmp_path: Path) -> None:
    pool = _write_pool(tmp_path)
    (tmp_path / "court" / ".tainted.json").write_text("{not json")
    assert len(pool.evidence_for("r-taint1")) == 2  # treated as absent; rows still parseable
