"""Append-only, durable, and idempotent outbox behavior."""

import json
from hashlib import sha256

import pytest
from runtime.emission.outbox import OutboxError, OutboxWriter


def bundle(bundle_id: str = "bundle-1") -> dict[str, object]:
    return {
        "bundle_id": bundle_id,
        "goal_id": "goal-outbox-1",
        "namespace": "sakg-demo",
        "artifact_bundle_hash": sha256(b"artifact-bundle").hexdigest(),
        "evidence_refs": [sha256(b"evidence-a").hexdigest(), sha256(b"evidence-b").hexdigest()],
    }


def test_integrated_write_is_fsynced_and_contains_only_cas_references(tmp_path) -> None:
    path = tmp_path / "outbox.jsonl"
    writer = OutboxWriter(path)
    record = writer.write_after_seal(
        bundle(),
        goal_state="integrated",
        seal_sequence=10,
        l16_sequence=11,
        emitted_at="2026-09-02T12:00:00Z",
    )
    assert record is not None
    assert path.stat().st_mode & 0o777 == 0o600
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["goal_state"] == "integrated"
    assert payload["evidence_refs"] == bundle()["evidence_refs"]
    assert "evidence" not in payload and "payload" not in payload and "content" not in payload
    assert writer.records() == (record,)


def test_identical_replay_does_not_rewrite_and_conflict_is_rejected(tmp_path) -> None:
    path = tmp_path / "outbox.jsonl"
    writer = OutboxWriter(path)
    first = writer.write_after_seal(
        bundle(),
        goal_state="integrated",
        seal_sequence=1,
        l16_sequence=2,
        emitted_at="2026-09-02T12:00:00Z",
    )
    before = path.read_bytes()
    replay = writer.write_after_seal(
        bundle(),
        goal_state="integrated",
        seal_sequence=1,
        l16_sequence=2,
        emitted_at="2026-09-02T12:01:00Z",
    )
    assert replay == first
    assert path.read_bytes() == before
    changed = bundle()
    changed["artifact_bundle_hash"] = "f" * 64
    with pytest.raises(OutboxError):
        writer.write_after_seal(changed, goal_state="integrated", seal_sequence=1, l16_sequence=2)
    assert path.read_bytes() == before
