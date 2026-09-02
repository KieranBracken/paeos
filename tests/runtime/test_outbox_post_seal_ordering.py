"""L15/L16 ordering and restart invariants."""

import pytest

from runtime.emission.outbox import OutboxCorruptionError, OutboxOrderingError, OutboxWriter


from hashlib import sha256


def bundle(bundle_id: str = "bundle-1") -> dict[str, object]:
    return {
        "bundle_id": bundle_id,
        "goal_id": "goal-outbox-1",
        "namespace": "sakg-demo",
        "artifact_bundle_hash": sha256(b"artifact-bundle").hexdigest(),
        "evidence_refs": [sha256(b"evidence-a").hexdigest(), sha256(b"evidence-b").hexdigest()],
    }



def test_l16_must_follow_seal_and_records_are_monotonic(tmp_path) -> None:
    path = tmp_path / "outbox.jsonl"
    writer = OutboxWriter(path)
    with pytest.raises(OutboxOrderingError):
        writer.write_after_seal(bundle(), goal_state="integrated", seal_sequence=8, l16_sequence=8)
    first = writer.write_after_seal(bundle(), goal_state="integrated", seal_sequence=8, l16_sequence=9)
    second_bundle = bundle("bundle-2")
    second = writer.write_after_seal(second_bundle, goal_state="integrated", seal_sequence=20, l16_sequence=21)
    assert first is not None and second is not None
    assert (first.sequence, second.sequence) == (1, 2)
    assert [item.sequence for item in writer.records()] == [1, 2]


def test_restart_reads_the_same_append_only_history(tmp_path) -> None:
    path = tmp_path / "outbox.jsonl"
    writer = OutboxWriter(path)
    original = writer.write_after_seal(bundle(), goal_state="integrated", seal_sequence=2, l16_sequence=3,
                                       emitted_at="2026-09-02T12:00:00Z")
    reopened = OutboxWriter(path)
    assert reopened.records() == (original,)


def test_tampered_or_truncated_line_fails_closed_without_repair(tmp_path) -> None:
    path = tmp_path / "outbox.jsonl"
    writer = OutboxWriter(path)
    writer.write_after_seal(bundle(), goal_state="integrated", seal_sequence=1, l16_sequence=2,
                            emitted_at="2026-09-02T12:00:00Z")
    before = path.read_bytes()
    with path.open("ab") as handle:
        handle.write(b'{"truncated":')
    with pytest.raises(OutboxCorruptionError):
        writer.write_after_seal(bundle("bundle-2"), goal_state="integrated", seal_sequence=3, l16_sequence=4)
    assert path.read_bytes() != before
