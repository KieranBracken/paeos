"""Tests for hidden canary mutation harness (Gate F Task 2)."""

from __future__ import annotations

from kernel.ledger import Event


def _payload(manifest, tx: str, **extra: object) -> dict[str, object]:
    payload = {
        "canary_id": manifest.canary_id,
        "version": manifest.version,
        "target_hash": manifest.target_hash,
        "mutation_hash": manifest.mutation_hash,
        "installer_hash": manifest.installer_hash,
        "transaction_id": tx,
    }
    payload.update(extra)
    return payload


def test_adjudicate_canary_installed_reached_killed() -> None:
    from runtime.autonomy.canary import (
        CanaryManifest,
        CanaryResult,
        adjudicate_canary,
    )

    manifest = CanaryManifest(
        canary_id="CANARY-001",
        version="1.0",
        target_hash="a" * 64,
        mutation_hash="b" * 64,
        expected_failure_code="FENCE_EXPIRED",
        installer_hash="c" * 64,
    )

    events = [
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload=_payload(manifest, "tx-001")),
        Event(schema_ver=1, kind="CANARY_REACHED", payload=_payload(manifest, "tx-001")),
        Event(
            schema_ver=1,
            kind="CANARY_KILLED",
            payload=_payload(
                manifest,
                "tx-001",
                observed_failure_code="FENCE_EXPIRED",
                evidence_ref="evidence-001",
            ),
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
        target_hash="a" * 64,
        mutation_hash="b" * 64,
        expected_failure_code="SCOPE_ESCAPE",
        installer_hash="c" * 64,
    )

    events = [
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload=_payload(manifest, "tx-002")),
        Event(schema_ver=1, kind="CANARY_REACHED", payload=_payload(manifest, "tx-002")),
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
        target_hash="a" * 64,
        mutation_hash="b" * 64,
        expected_failure_code="FENCE_EXPIRED",
        installer_hash="c" * 64,
    )

    events = [
        Event(
            schema_ver=1,
            kind="CANARY_KILLED",
            payload=_payload(
                manifest,
                "tx-003",
                observed_failure_code="FENCE_EXPIRED",
                evidence_ref="evidence-003",
            ),
        ),
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload=_payload(manifest, "tx-003")),
        Event(schema_ver=1, kind="CANARY_REACHED", payload=_payload(manifest, "tx-003")),
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
        target_hash="a" * 64,
        mutation_hash="b" * 64,
        expected_failure_code="SCOPE_ESCAPE",
        installer_hash="c" * 64,
    )
    events = [
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload=_payload(manifest, "tx-004")),
        Event(schema_ver=1, kind="CANARY_REACHED", payload=_payload(manifest, "tx-004")),
        Event(
            schema_ver=1,
            kind="CANARY_KILLED",
            payload=_payload(
                manifest,
                "tx-004",
                observed_failure_code="SCOPE_ESCAPE",
            ),
        ),
    ]

    assert adjudicate_canary(manifest, events).killed is False


def test_canary_rejects_stale_manifest_binding() -> None:
    from runtime.autonomy.canary import CanaryManifest, adjudicate_canary

    manifest = CanaryManifest("CANARY-005", "2", "a" * 64, "b" * 64, "FENCE_EXPIRED", "c" * 64)
    stale = {
        "canary_id": "CANARY-005",
        "version": "1",
        "target_hash": manifest.target_hash,
        "mutation_hash": manifest.mutation_hash,
        "installer_hash": manifest.installer_hash,
        "transaction_id": "tx-005",
    }
    events = [
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload=stale),
        Event(schema_ver=1, kind="CANARY_REACHED", payload=stale),
        Event(
            schema_ver=1,
            kind="CANARY_KILLED",
            payload={**stale, "observed_failure_code": "FENCE_EXPIRED", "evidence_ref": "ref"},
        ),
    ]
    result = adjudicate_canary(manifest, events)
    assert result.installed is False
    assert result.reached is False
    assert result.killed is False


def test_canary_rejects_replayed_or_conflicting_transaction() -> None:
    from runtime.autonomy.canary import CanaryManifest, adjudicate_canary

    manifest = CanaryManifest("CANARY-006", "1", "a" * 64, "b" * 64, "SCOPE_ESCAPE", "c" * 64)
    events = [
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload=_payload(manifest, "tx-006")),
        Event(schema_ver=1, kind="CANARY_INSTALLED", payload=_payload(manifest, "tx-006")),
        Event(schema_ver=1, kind="CANARY_REACHED", payload=_payload(manifest, "tx-006")),
        Event(
            schema_ver=1,
            kind="CANARY_KILLED",
            payload=_payload(
                manifest,
                "tx-006",
                observed_failure_code="SCOPE_ESCAPE",
                evidence_ref="ref-006",
            ),
        ),
    ]
    assert adjudicate_canary(manifest, events).killed is False
