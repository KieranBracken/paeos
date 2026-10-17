"""Checkpoint integrity and adapter-rotation fencing tests."""

import hashlib
from pathlib import Path

import pytest
from kernel.cas import CAS, InMemoryCasStore
from kernel.ledger import InMemoryLedgerStore, Ledger
from runtime.integrations.bridge_protocol import ProtocolViolation
from runtime.supervisors.checkpoint import (
    SCHEMA_VERSION,
    SupervisorCheckpoint,
    SupervisorCoordinator,
    SupervisorRotationError,
    verify_checkpoint,
)


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text(_hash("head"), encoding="utf-8")
    (repo / "tracked.txt").write_text("stable\n", encoding="utf-8")
    return repo


def _coordinator(tmp_path: Path):
    repo = _repo(tmp_path)
    ledger = Ledger(InMemoryLedgerStore())
    cas = CAS(InMemoryCasStore())
    return repo, ledger, cas, SupervisorCoordinator(
        ledger=ledger,
        cas=cas,
        repo=repo,
        policy_hash=_hash("policy"),
    )


def test_checkpoint_is_canonical_content_addressed_and_verifiable(tmp_path: Path) -> None:
    repo, ledger, cas, coordinator = _coordinator(tmp_path)
    reference = coordinator.checkpoint(expected_ledger_head=ledger.head_hash())
    raw = cas.get(reference.hash)
    checkpoint = SupervisorCheckpoint.from_bytes(raw)
    assert checkpoint.schema_version == SCHEMA_VERSION
    assert reference.hash == _hash(raw.decode())
    verify_checkpoint(checkpoint, ledger=ledger, repo=repo)


def test_checkpoint_refuses_stale_ledger_or_repository(tmp_path: Path) -> None:
    repo, ledger, cas, coordinator = _coordinator(tmp_path)
    reference = coordinator.checkpoint(expected_ledger_head=ledger.head_hash())
    with pytest.raises(ProtocolViolation, match="repository digest"):
        repo.joinpath("tracked.txt").write_text("mutated\n", encoding="utf-8")
        checkpoint = SupervisorCheckpoint.from_bytes(cas.get(reference.hash))
        verify_checkpoint(checkpoint, ledger=ledger, repo=repo)


def test_clean_rotation_requires_no_active_or_ambiguous_claim(tmp_path: Path) -> None:
    _, ledger, _, coordinator = _coordinator(tmp_path)
    reference = coordinator.checkpoint(expected_ledger_head=ledger.head_hash())
    coordinator.rotate(from_profile="codex", to_profile="antigravity", checkpoint_ref=reference)

    coordinator.mark_claim(active=True)
    with pytest.raises(SupervisorRotationError, match="active or ambiguous"):
        coordinator.rotate(from_profile="antigravity", to_profile="codex", checkpoint_ref=reference)

    coordinator.mark_claim(active=False, ambiguous=True)
    with pytest.raises(SupervisorRotationError, match="active or ambiguous"):
        coordinator.rotate(from_profile="antigravity", to_profile="codex", checkpoint_ref=reference)


def test_old_adapter_is_fenced_after_rotation(tmp_path: Path) -> None:
    _, ledger, _, coordinator = _coordinator(tmp_path)
    reference = coordinator.checkpoint(expected_ledger_head=ledger.head_hash())
    coordinator.rotate(from_profile="codex", to_profile="antigravity", checkpoint_ref=reference)
    with pytest.raises(SupervisorRotationError, match="source profile is stale"):
        coordinator.rotate(from_profile="codex", to_profile="future", checkpoint_ref=reference)


def test_broken_checkpoint_chain_or_bytes_are_rejected(tmp_path: Path) -> None:
    _, ledger, cas, coordinator = _coordinator(tmp_path)
    reference = coordinator.checkpoint(expected_ledger_head=ledger.head_hash())
    broken = cas.put(cas.get(reference.hash) + b"tamper")
    with pytest.raises(ProtocolViolation):
        SupervisorCheckpoint.from_bytes(cas.get(broken))
