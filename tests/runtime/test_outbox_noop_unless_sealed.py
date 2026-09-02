"""Fail-closed lifecycle state and reference validation."""

from hashlib import sha256

import pytest
from runtime.emission.outbox import OutboxOrderingError, OutboxValidationError, OutboxWriter


def bundle(bundle_id: str = "bundle-1") -> dict[str, object]:
    return {
        "bundle_id": bundle_id,
        "goal_id": "goal-outbox-1",
        "namespace": "sakg-demo",
        "artifact_bundle_hash": sha256(b"artifact-bundle").hexdigest(),
        "evidence_refs": [sha256(b"evidence-a").hexdigest(), sha256(b"evidence-b").hexdigest()],
    }


def test_non_integrated_goal_is_a_true_noop(tmp_path) -> None:
    path = tmp_path / "outbox.jsonl"
    writer = OutboxWriter(path)
    malformed = {"inline_evidence": {"secret": "must never be persisted"}}
    for state in ("declared", "planned", "executed", "sealed", "remanded"):
        assert (
            writer.write_after_seal(
                malformed, goal_state=state, seal_sequence=None, l16_sequence=None
            )
            is None
        )
    assert not path.exists()


def test_integrated_goal_requires_nonempty_valid_cas_references(tmp_path) -> None:
    writer = OutboxWriter(tmp_path / "outbox.jsonl")
    invalid = bundle()
    invalid["evidence_refs"] = []
    with pytest.raises(OutboxValidationError):
        writer.write_after_seal(invalid, goal_state="integrated", seal_sequence=1, l16_sequence=2)
    invalid = bundle()
    invalid["evidence_refs"] = ["not-a-hash"]
    with pytest.raises(OutboxValidationError):
        writer.write_after_seal(invalid, goal_state="integrated", seal_sequence=1, l16_sequence=2)
    invalid = bundle()
    invalid["evidence"] = "inline"
    with pytest.raises(OutboxValidationError):
        writer.write_after_seal(invalid, goal_state="integrated", seal_sequence=1, l16_sequence=2)
    assert not writer.path.exists()


def test_integrated_goal_requires_explicit_seal_boundary(tmp_path) -> None:
    writer = OutboxWriter(tmp_path / "outbox.jsonl")
    with pytest.raises(OutboxOrderingError):
        writer.write_after_seal(
            bundle(), goal_state="integrated", seal_sequence=None, l16_sequence=2
        )
    assert not writer.path.exists()
