"""Provider-free behavior checks for the restored vendor-neutral boundary."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def test_missing_boundary_exports_runtime_checkable_protocol(tmp_path):
    try:
        boundary = importlib.import_module("runtime.transport")
    except ModuleNotFoundError as error:
        if error.name != "runtime.transport":
            raise
        pytest.fail("vendor-neutral runtime.transport boundary is absent")
    transport = boundary.FileWorkerTransport(tmp_path / "pool")
    assert isinstance(transport, boundary.WorkerTransport)


@pytest.fixture
def boundary():
    module = importlib.import_module("runtime.transport")
    assert Path(module.__file__).resolve() == (
        Path(__file__).resolve().parents[2] / "runtime/transport.py"
    )
    return module


def _synthetic_evidence(claim):
    from kernel.cas import content_hash
    from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
    from kernel.types import Role

    return Evidence(
        hash=content_hash(claim.encode()),
        kind=EvidenceKind.TEST,
        claim_id=claim,
        artifact_hash=content_hash(b"synthetic-artifact"),
        environment_hash=content_hash(b"synthetic-environment"),
        reproducible_command="synthetic-only-not-executed",
        producer=EvidenceProducer(role=Role.BUILDER, session="synthetic-session"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": "synthetic observation"},
        attestation="synthetic-unverified",
    )


@pytest.mark.parametrize("run_id", ["r-1", "R_2:alpha.beta", "r" * 128])
def test_submit_status_receive_and_reopen_preserve_evidence(boundary, tmp_path, run_id):
    from runtime.orchestrator import FileCourtEvidencePool

    pool_path = tmp_path / "pool"
    transport = boundary.FileWorkerTransport(pool_path)
    evidence = _synthetic_evidence("synthetic-claim")
    assert transport.status(run_id) == f"0 evidence submitted for run {run_id}"
    assert transport.receive(run_id) == ()
    transport.submit(run_id, evidence)
    assert transport.status(run_id) == f"1 evidence submitted for run {run_id}"
    assert transport.receive(run_id) == (evidence,)
    assert transport.evidence_for(run_id) == (evidence,)
    assert FileCourtEvidencePool(pool_path).evidence_for(run_id) == (evidence,)
    assert boundary.FileWorkerTransport(pool_path).receive(run_id) == (evidence,)
    assert transport.receive("different-run") == ()


def test_current_pool_taint_filter_remains_effective(boundary, tmp_path):
    pool_path = tmp_path / "pool"
    transport = boundary.FileWorkerTransport(pool_path)
    tainted = _synthetic_evidence("tainted-synthetic")
    retained = _synthetic_evidence("retained-synthetic")
    transport.submit("r-1", tainted)
    transport.submit("r-1", retained)
    original_rows = (pool_path / "r-1.jsonl").read_bytes()
    first_line = original_rows.splitlines()[0]
    (pool_path / ".tainted.json").write_text(
        json.dumps({hashlib.sha256(first_line).hexdigest(): "synthetic denial"})
    )
    assert transport.receive("r-1") == (retained,)
    assert transport.evidence_for("r-1") == (retained,)
    assert transport.status("r-1") == "1 evidence submitted for run r-1"
    assert (pool_path / "r-1.jsonl").read_bytes() == original_rows


class _UntrustedLabel(str):
    pass


@pytest.mark.parametrize("method", ["submit", "status", "receive", "evidence_for"])
@pytest.mark.parametrize(
    "run_id",
    [
        "",
        ".",
        "..",
        "../outside",
        "/outside",
        "r/../outside",
        "r/child",
        "r\\child",
        "r\n",
        "r\r",
        "r\x00",
        "r\x7f",
        "r child",
        "r\tchild",
        "ré",
        "r" * 129,
        None,
        True,
        1,
        b"r-1",
        [],
        _UntrustedLabel("r-1"),
    ],
)
def test_invalid_run_identity_denied_before_pool_access(
    boundary, tmp_path, monkeypatch, method, run_id
):
    pool_path = tmp_path / "pool"
    transport = boundary.FileWorkerTransport(pool_path)
    sentinel = tmp_path / "outside.jsonl"
    sentinel.write_bytes(b"synthetic-outside-sentinel\n")
    evidence = _synthetic_evidence("synthetic-claim")

    def forbidden(*args, **kwargs):
        pytest.fail("invalid run identity reached the path-bearing pool")

    monkeypatch.setattr(transport._pool, "submit", forbidden)
    monkeypatch.setattr(transport._pool, "evidence_for", forbidden)
    args = (run_id, evidence) if method == "submit" else (run_id,)
    with pytest.raises(ValueError):
        getattr(transport, method)(*args)
    assert sentinel.read_bytes() == b"synthetic-outside-sentinel\n"
    assert tuple(pool_path.iterdir()) == ()


def test_traversal_cannot_write_outside_real_pool(boundary, tmp_path):
    transport = boundary.FileWorkerTransport(tmp_path / "pool")
    sentinel = tmp_path / "outside.jsonl"
    sentinel.write_bytes(b"synthetic-outside-sentinel\n")
    with pytest.raises(ValueError):
        transport.submit("../outside", _synthetic_evidence("synthetic-claim"))
    assert sentinel.read_bytes() == b"synthetic-outside-sentinel\n"


def test_import_does_not_create_pool_or_start_provider(boundary, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("boundary import attempted an external effect")

    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    before = set(sys.modules)
    spec = importlib.util.spec_from_file_location("synthetic_inert_transport", boundary.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "WorkerTransport")
    assert not any(
        name.split(".")[0] in {"anthropic", "openai", "litellm", "mcp"}
        for name in set(sys.modules) - before
    )
