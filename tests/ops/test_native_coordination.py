from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest
from ops.native_coordination import (
    CoordinationCache,
    DuplicateIdentityError,
    InvalidTransitionError,
    NonAuthoritativeStateError,
)

INTENT_SHA256 = "a" * 64
RESULT_SHA256 = "b" * 64


def _record_assignment(cache_path: str, assignment_id: str, event_id: str) -> None:
    cache = CoordinationCache(Path(cache_path))
    cache.record_assignment_intent(
        assignment_id=assignment_id,
        owner_thread_id=f"owner-{assignment_id}",
        event_id=event_id,
        intent_sha256=INTENT_SHA256,
        created_at="2026-10-19T12:00:00+00:00",
    )


def test_assignment_intent_is_persisted_before_any_send(tmp_path: Path) -> None:
    cache = CoordinationCache(tmp_path / "coordination.json")

    assignment = cache.record_assignment_intent(
        assignment_id="B00-test-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-test-v1",
        intent_sha256=INTENT_SHA256,
        created_at="2026-10-19T12:00:00+00:00",
    )

    assert assignment["state"] == "PENDING_SEND"
    assert assignment["attempts"][0]["attempt_id"] == "B00-test-v1:send:1"
    assert assignment["attempts"][0]["state"] == "PENDING_SEND"
    state = cache.snapshot()
    assert state["canonical_authority"] is False
    assert state["assignments"]["B00-test-v1"] == assignment
    assert "worker_started" not in assignment


def test_stable_assignment_and_event_ids_reject_duplicates(tmp_path: Path) -> None:
    cache = CoordinationCache(tmp_path / "coordination.json")
    cache.record_assignment_intent(
        assignment_id="B00-test-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-test-v1",
        intent_sha256=INTENT_SHA256,
    )
    before = cache.snapshot()

    with pytest.raises(DuplicateIdentityError):
        cache.record_assignment_intent(
            assignment_id="B00-test-v1",
            owner_thread_id="other-owner",
            event_id="dispatch-B00-test-v2",
            intent_sha256=RESULT_SHA256,
        )
    with pytest.raises(DuplicateIdentityError):
        cache.record_assignment_intent(
            assignment_id="B00-test-v2",
            owner_thread_id="thread-owner",
            event_id="dispatch-B00-test-v1",
            intent_sha256=RESULT_SHA256,
        )

    assert cache.snapshot() == before


def test_unknown_send_survives_restart_and_blocks_retry_until_reconciled(
    tmp_path: Path,
) -> None:
    path = tmp_path / "coordination.json"
    cache = CoordinationCache(path)
    cache.record_assignment_intent(
        assignment_id="B00-unknown-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-unknown-v1",
        intent_sha256=INTENT_SHA256,
        created_at="2026-10-19T12:00:00+00:00",
    )
    cache.record_send_outcome(
        assignment_id="B00-unknown-v1",
        outcome="UNKNOWN",
        result_sha256=RESULT_SHA256,
        recorded_at="2026-10-19T12:00:01+00:00",
    )

    restarted = CoordinationCache(path)
    assert restarted.snapshot()["assignments"]["B00-unknown-v1"]["state"] == "UNKNOWN"
    assert restarted.recovery_candidates(
        now="2026-10-19T12:01:00+00:00",
        callback_grace_seconds=0,
    )["unknown_sends"] == ["B00-unknown-v1"]
    with pytest.raises(InvalidTransitionError):
        restarted.begin_retry(
            assignment_id="B00-unknown-v1",
            event_id="retry-before-reconcile-v1",
            intent_sha256=INTENT_SHA256,
        )
    with pytest.raises(InvalidTransitionError):
        restarted.reconcile_unknown_send(
            assignment_id="B00-unknown-v1",
            delivered=False,
            evidence={},
            reconciled_at="2026-10-19T12:02:00+00:00",
        )

    restarted.reconcile_unknown_send(
        assignment_id="B00-unknown-v1",
        delivered=False,
        evidence={"destination_thread_checked": "thread-owner", "turn_found": False},
        reconciled_at="2026-10-19T12:02:00+00:00",
    )
    retry = restarted.begin_retry(
        assignment_id="B00-unknown-v1",
        event_id="retry-after-not-sent-v1",
        intent_sha256=INTENT_SHA256,
        created_at="2026-10-19T12:03:00+00:00",
    )

    assert retry["attempts"][-1]["attempt_id"] == "B00-unknown-v1:send:2"
    assert retry["attempts"][-1]["state"] == "PENDING_SEND"


def test_restart_surfaces_missed_callback_candidate_without_redispatch(
    tmp_path: Path,
) -> None:
    path = tmp_path / "coordination.json"
    cache = CoordinationCache(path)
    cache.record_assignment_intent(
        assignment_id="B00-callback-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-callback-v1",
        intent_sha256=INTENT_SHA256,
        created_at="2026-10-19T12:00:00+00:00",
    )
    cache.record_send_outcome(
        assignment_id="B00-callback-v1",
        outcome="SENT",
        result_sha256=RESULT_SHA256,
        recorded_at="2026-10-19T12:00:01+00:00",
    )
    cache.record_turn_start(
        assignment_id="B00-callback-v1",
        event_id="turn-start-B00-callback-v1",
        recipient_turn_id="turn-actual-2",
        recipient_status="completed",
        evidence_sha256="c" * 64,
        observed_at="2026-10-19T12:00:02+00:00",
    )

    restarted = CoordinationCache(path)
    recovered = restarted.recovery_candidates(
        now="2026-10-19T12:20:00+00:00",
        callback_grace_seconds=900,
    )

    assert recovered["missed_callback_candidates"] == ["B00-callback-v1"]
    assert recovered["redispatch"] == []
    assert restarted.snapshot()["assignments"]["B00-callback-v1"]["state"] == "ACTIVE"


def test_callback_event_is_deduplicated_and_clears_recovery_candidate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "coordination.json"
    cache = CoordinationCache(path)
    cache.record_assignment_intent(
        assignment_id="B00-callback-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-callback-v1",
        intent_sha256=INTENT_SHA256,
        created_at="2026-10-19T12:00:00+00:00",
    )
    cache.record_send_outcome(
        assignment_id="B00-callback-v1",
        outcome="SENT",
        result_sha256=RESULT_SHA256,
        recorded_at="2026-10-19T12:00:01+00:00",
    )

    callback = {
        "event_id": "callback-B00-callback-v1",
        "assignment_id": "B00-callback-v1",
        "origin_thread": "thread-owner",
        "source_turn_id": "turn-callback-1",
        "payload_sha256": "c" * 64,
        "received_at": "2026-10-19T12:20:00+00:00",
    }
    assert cache.record_callback(**callback) is True
    assert cache.record_callback(**callback) is False

    recovered = CoordinationCache(path).recovery_candidates(
        now="2026-10-19T12:21:00+00:00",
        callback_grace_seconds=0,
    )
    assert recovered["missed_callback_candidates"] == []
    assert recovered["unknown_sends"] == []


def test_actual_turn_start_resolves_unknown_and_blocks_false_non_delivery(
    tmp_path: Path,
) -> None:
    cache = CoordinationCache(tmp_path / "coordination.json")
    cache.record_assignment_intent(
        assignment_id="B00-turn-start-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-turn-start-v1",
        intent_sha256=INTENT_SHA256,
        created_at="2026-10-19T12:00:00+00:00",
    )
    cache.record_send_outcome(
        assignment_id="B00-turn-start-v1",
        outcome="UNKNOWN",
        result_sha256=RESULT_SHA256,
        recorded_at="2026-10-19T12:00:01+00:00",
    )
    with pytest.raises(InvalidTransitionError):
        cache.record_turn_start(
            assignment_id="B00-turn-start-v1",
            event_id="queued-is-not-a-turn-start",
            recipient_turn_id="queued-receipt",
            recipient_status="queued",
            evidence_sha256="c" * 64,
        )

    active = cache.record_turn_start(
        assignment_id="B00-turn-start-v1",
        event_id="turn-start-B00-turn-start-v1",
        recipient_turn_id="turn-actual-1",
        recipient_status="inProgress",
        evidence_sha256="c" * 64,
        observed_at="2026-10-19T12:00:02+00:00",
    )

    assert active["state"] == "ACTIVE"
    assert active["actual_turn_starts"][0]["recipient_turn_id"] == "turn-actual-1"
    with pytest.raises(InvalidTransitionError):
        cache.reconcile_unknown_send(
            assignment_id="B00-turn-start-v1",
            delivered=False,
            evidence={"destination_checked": "turn-actual-1"},
        )
    assert (
        cache.recovery_candidates(
            now="2026-10-19T12:00:03+00:00",
            callback_grace_seconds=0,
        )["unknown_sends"]
        == []
    )


def test_owner_cannot_receive_competing_assignment_until_held_closeout(
    tmp_path: Path,
) -> None:
    cache = CoordinationCache(tmp_path / "coordination.json")
    cache.record_assignment_intent(
        assignment_id="B00-owner-slot-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-owner-slot-v1",
        intent_sha256=INTENT_SHA256,
    )
    cache.record_send_outcome(
        assignment_id="B00-owner-slot-v1",
        outcome="SENT",
        result_sha256=RESULT_SHA256,
    )
    cache.record_turn_start(
        assignment_id="B00-owner-slot-v1",
        event_id="turn-start-B00-owner-slot-v1",
        recipient_turn_id="turn-actual-3",
        recipient_status="inProgress",
        evidence_sha256="c" * 64,
    )

    with pytest.raises(InvalidTransitionError):
        cache.record_assignment_intent(
            assignment_id="B00-owner-slot-v2",
            owner_thread_id="thread-owner",
            event_id="dispatch-B00-owner-slot-v2",
            intent_sha256=INTENT_SHA256,
        )

    cache.record_callback(
        event_id="callback-B00-owner-slot-v1",
        assignment_id="B00-owner-slot-v1",
        origin_thread="thread-owner",
        source_turn_id="turn-actual-3",
        payload_sha256="e" * 64,
    )
    cache.record_assignment_disposition(
        assignment_id="B00-owner-slot-v1",
        disposition="HELD",
        evidence_sha256="d" * 64,
        wake_condition="exact entitlement evidence is captured",
    )
    next_assignment = cache.record_assignment_intent(
        assignment_id="B00-owner-slot-v2",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-owner-slot-v2",
        intent_sha256=INTENT_SHA256,
    )
    assert next_assignment["state"] == "PENDING_SEND"


def test_callback_before_tool_result_proves_delivery_and_survives_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "coordination.json"
    cache = CoordinationCache(path)
    cache.record_assignment_intent(
        assignment_id="B00-early-callback-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-early-callback-v1",
        intent_sha256=INTENT_SHA256,
    )

    assert cache.record_callback(
        event_id="callback-B00-early-callback-v1",
        assignment_id="B00-early-callback-v1",
        origin_thread="thread-owner",
        source_turn_id="turn-callback-early",
        payload_sha256="c" * 64,
    )
    restarted = CoordinationCache(path)
    recovered = restarted.recovery_candidates(
        now="2026-10-19T12:20:00+00:00",
        callback_grace_seconds=0,
    )
    assert recovered["unknown_sends"] == []
    assert recovered["missed_callback_candidates"] == []
    with pytest.raises(InvalidTransitionError):
        restarted.record_send_outcome(
            assignment_id="B00-early-callback-v1",
            outcome="UNKNOWN",
            result_sha256=RESULT_SHA256,
        )
    with pytest.raises(InvalidTransitionError):
        restarted.reconcile_unknown_send(
            assignment_id="B00-early-callback-v1",
            delivered=False,
            evidence={"destination_checked": "turn-callback-early"},
        )
    completed = restarted.record_send_outcome(
        assignment_id="B00-early-callback-v1",
        outcome="SENT",
        result_sha256=RESULT_SHA256,
    )
    assert completed["state"] == "ACTIVE"


def test_owner_handoff_ack_closes_old_assignment_with_evidence(
    tmp_path: Path,
) -> None:
    cache = CoordinationCache(tmp_path / "coordination.json")
    cache.record_assignment_intent(
        assignment_id="B00-handoff-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-B00-handoff-v1",
        intent_sha256=INTENT_SHA256,
    )
    cache.record_send_outcome(
        assignment_id="B00-handoff-v1",
        outcome="SENT",
        result_sha256=RESULT_SHA256,
    )
    cache.record_handoff_ack(
        assignment_id="B00-handoff-v1",
        event_id="handoff-ack-B00-handoff-v1",
        origin_thread="thread-owner",
        source_turn_id="turn-handoff-1",
        payload_sha256="c" * 64,
        handoff_summary_sha256="d" * 64,
    )
    assignment = cache.snapshot()["assignments"]["B00-handoff-v1"]
    assert assignment["state"] == "HANDED_OFF"
    assert assignment["handoff_ack"]["origin_thread"] == "thread-owner"
    assert assignment["callback_state"] == "RECEIVED"


def test_concurrent_process_updates_are_atomic_and_preserve_old_history(
    tmp_path: Path,
) -> None:
    path = tmp_path / "coordination.json"
    path.write_text(
        json.dumps(
            {
                "schema": "paeos.native-coordination-cache/1",
                "canonical_authority": False,
                "processed_events": {"old-event": {"state": "SENT"}},
                "assignments": {},
                "historical_note": "preserve",
            }
        ),
        encoding="utf-8",
    )
    context = multiprocessing.get_context("fork")
    processes = [
        context.Process(
            target=_record_assignment,
            args=(str(path), f"B00-concurrent-{index}", f"event-{index}"),
        )
        for index in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)

    assert [process.exitcode for process in processes] == [0, 0]
    state = CoordinationCache(path).snapshot()
    assert set(state["assignments"]) == {"B00-concurrent-0", "B00-concurrent-1"}
    assert state["processed_events"] == {"old-event": {"state": "SENT"}}
    assert state["historical_note"] == "preserve"
    assert state["canonical_authority"] is False


def test_canonical_runtime_state_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "canonical.json"
    path.write_text(
        json.dumps({"canonical_authority": True, "processed_events": {}}),
        encoding="utf-8",
    )

    with pytest.raises(NonAuthoritativeStateError):
        CoordinationCache(path).record_assignment_intent(
            assignment_id="B00-should-not-write",
            owner_thread_id="thread-owner",
            event_id="dispatch-should-not-write",
            intent_sha256=INTENT_SHA256,
        )


def test_unknown_cache_schema_requires_explicit_migration(tmp_path: Path) -> None:
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "schema": "legacy-coordinator-cache",
                "canonical_authority": False,
                "processed_events": {},
                "assignments": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(NonAuthoritativeStateError):
        CoordinationCache(path).record_assignment_intent(
            assignment_id="B00-no-implicit-migration",
            owner_thread_id="thread-owner",
            event_id="dispatch-no-implicit-migration",
            intent_sha256=INTENT_SHA256,
        )


def test_legacy_assignment_requires_explicit_evidence_reconciliation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "coordination.json"
    original = {
        "schema": "paeos.native-coordination-cache/1",
        "canonical_authority": False,
        "processed_events": {"old-event": {"state": "SENT"}},
        "assignments": {
            "legacy-owner-task-v1": {
                "owner_thread": "thread-owner",
                "state": "SENT",
                "historical_field": "preserve exactly",
            }
        },
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    cache = CoordinationCache(path)

    with pytest.raises(InvalidTransitionError):
        cache.record_assignment_intent(
            assignment_id="B00-after-legacy-v1",
            owner_thread_id="thread-owner",
            event_id="dispatch-after-legacy-v1",
            intent_sha256=INTENT_SHA256,
        )

    cache.reconcile_legacy_assignment(
        assignment_id="legacy-owner-task-v1",
        owner_thread_id="thread-owner",
        event_id="reconcile-legacy-owner-task-v1",
        disposition="HELD",
        evidence_sha256="c" * 64,
        wake_condition="new exact source evidence arrives",
    )
    reconciled = cache.snapshot()["assignments"]["legacy-owner-task-v1"]
    assert reconciled["state"] == "SENT"
    assert reconciled["historical_field"] == "preserve exactly"
    assert reconciled["coordinator_reconciliation"]["disposition"] == "HELD"
    next_assignment = cache.record_assignment_intent(
        assignment_id="B00-after-legacy-v1",
        owner_thread_id="thread-owner",
        event_id="dispatch-after-legacy-v1",
        intent_sha256=INTENT_SHA256,
    )
    assert next_assignment["state"] == "PENDING_SEND"


def test_callback_before_expected_owner_is_rejected(tmp_path: Path) -> None:
    cache = CoordinationCache(tmp_path / "coordination.json")
    cache.record_assignment_intent(
        assignment_id="B00-owner-v1",
        owner_thread_id="thread-expected",
        event_id="dispatch-B00-owner-v1",
        intent_sha256=INTENT_SHA256,
    )
    cache.record_send_outcome(
        assignment_id="B00-owner-v1",
        outcome="SENT",
        result_sha256=RESULT_SHA256,
    )

    with pytest.raises(InvalidTransitionError):
        cache.record_callback(
            event_id="callback-wrong-owner-v1",
            assignment_id="B00-owner-v1",
            origin_thread="thread-other",
            source_turn_id="turn-wrong-owner",
            payload_sha256="c" * 64,
        )
