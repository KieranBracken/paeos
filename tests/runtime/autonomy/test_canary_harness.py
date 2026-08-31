"""Tests for hidden canary mutation harness (Gate F Task 2)."""

from __future__ import annotations

from kernel.ledger import Event


def test_adjudicate_canary_installed_reached_killed() -> None:
    from runtime.autonomy.canary import (
        CanaryManifest,
        CanaryResult,
        adjudicate_canary,
    )

    manifest = CanaryManifest(
        canary_id="CANARY-001",
        version="1.0",
        target_hash="t" * 64,
        mutation_hash="m" * 64,
        expected_failure_code="FENCE_EXPIRED",
        installer_hash="i" * 64,
    )

    events = [
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload={"canary_id": "CANARY-001"}),
        Event(schema_ver=1, kind="CANARY_REACHED", payload={"canary_id": "CANARY-001"}),
        Event(
            schema_ver=1,
            kind="CANARY_KILLED",
            payload={
                "canary_id": "CANARY-001",
                "observed_failure_code": "FENCE_EXPIRED",
                "evidence_ref": "evidence-001",
            },
        ),
    ]

    result = adjudicate_canary(manifest, events)
    assert isinstance(result, CanaryResult)
    assert result.canary_id == "CANARY-001"
    assert result.installed is True
    assert result.reached is True
    assert result.killed is True
    assert result.observed_failure_code == "FENCE_EXPIRED"


def test_adjudicate_canary_survived_when_missing_kill() -> None:
    from runtime.autonomy.canary import (
        CanaryManifest,
        adjudicate_canary,
    )

    manifest = CanaryManifest(
        canary_id="CANARY-002",
        version="1.0",
        target_hash="t" * 64,
        mutation_hash="m" * 64,
        expected_failure_code="SCOPE_ESCAPE",
        installer_hash="i" * 64,
    )

    events = [
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload={"canary_id": "CANARY-002"}),
        Event(schema_ver=1, kind="CANARY_REACHED", payload={"canary_id": "CANARY-002"}),
    ]

    result = adjudicate_canary(manifest, events)
    assert result.installed is True
    assert result.reached is True
    assert result.killed is False


def test_canary_kill_without_ordered_install_and_reach_is_not_admissible() -> None:
    from runtime.autonomy.canary import CanaryManifest, adjudicate_canary

    manifest = CanaryManifest(
        canary_id="CANARY-003",
        version="1.0",
        target_hash="t" * 64,
        mutation_hash="m" * 64,
        expected_failure_code="FENCE_EXPIRED",
        installer_hash="i" * 64,
    )

    events = [
        Event(
            schema_ver=1,
            kind="CANARY_KILLED",
            payload={
                "canary_id": "CANARY-003",
                "observed_failure_code": "FENCE_EXPIRED",
                "evidence_ref": "evidence-003",
            },
        ),
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload={"canary_id": "CANARY-003"}),
        Event(schema_ver=1, kind="CANARY_REACHED", payload={"canary_id": "CANARY-003"}),
    ]

    result = adjudicate_canary(manifest, events)

    assert result.installed is True
    assert result.reached is True
    assert result.killed is False


def test_canary_requires_nonempty_evidence_reference() -> None:
    from runtime.autonomy.canary import CanaryManifest, adjudicate_canary

    manifest = CanaryManifest(
        canary_id="CANARY-004",
        version="1.0",
        target_hash="t" * 64,
        mutation_hash="m" * 64,
        expected_failure_code="SCOPE_ESCAPE",
        installer_hash="i" * 64,
    )
    events = [
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload={"canary_id": "CANARY-004"}),
        Event(schema_ver=1, kind="CANARY_REACHED", payload={"canary_id": "CANARY-004"}),
        Event(
            schema_ver=1,
            kind="CANARY_KILLED",
            payload={"canary_id": "CANARY-004", "observed_failure_code": "SCOPE_ESCAPE"},
        ),
    ]

    assert adjudicate_canary(manifest, events).killed is False
