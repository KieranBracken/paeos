"""Protocol-level tests for the paeos-bridge-v2 immutable envelopes.

Approved contract:
docs/superpowers/plans/2026-08-25-paeos-control-plane-recovery-subproject-1.md
"""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from runtime.integrations.bridge_protocol import (
    SCHEMA_VERSION,
    BridgePaths,
    CircuitBreaker,
    Disposition,
    ProtocolViolation,
    RequestEnvelope,
    ResponseEnvelope,
    TransactionEvent,
    TransactionRecord,
    TransactionState,
    TransactionStore,
    canonical_json,
    content_hash,
    correlate_response,
    incident_from_violation,
    load_json,
    migrate_legacy_transaction,
    reduce_transaction,
    transaction_key,
    validate_request,
    validate_response,
    write_once_bytes,
    write_once_json,
)


def valid_request(**changes: object) -> RequestEnvelope:
    values: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "request_id": "req-001",
        "transaction_key": transaction_key(
            request_id="req-001",
            run_id="run-001",
            stage_id="L14",
            semantic_hash="a" * 64,
            evidence_manifest_hash="b" * 64,
            payload_hash="c" * 64,
        ),
        "created_at": "2026-08-25T10:00:00+00:00",
        "expires_at": "2026-08-25T10:10:00+00:00",
        "goal_id": "goal-001",
        "run_id": "run-001",
        "stage_id": "L14",
        "role": "BUILDER_OUTPUT_REVIEW",
        "workspace_root": "/private/tmp/paeos-control-plane-recovery-s1",
        "worker_transport_id": "cline:paeos-code",
        "worker_session_id": "session-001",
        "worker_pid": 4242,
        "worker_tty": "/dev/ttys001",
        "worker_model_provider": "openai",
        "worker_model_id": "implementation-model",
        "worker_model_family": "implementation-family",
        "semantic_hash": "a" * 64,
        "evidence_manifest_hash": "b" * 64,
        "payload_hash": "c" * 64,
        "allowed_dispositions": (
            Disposition.CONTINUE,
            Disposition.REMAND,
            Disposition.HALT,
            Disposition.NEEDS_FOUNDER,
        ),
    }
    values.update(changes)
    return RequestEnvelope(**values)


def valid_response(request: RequestEnvelope, **changes: object) -> ResponseEnvelope:
    text = "Evidence is incomplete; remand."
    values: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request.request_id,
        "transaction_key": request.transaction_key,
        "run_id": request.run_id,
        "stage_id": request.stage_id,
        "payload_hash": request.payload_hash,
        "lease_owner": "codex-overseer",
        "overseer_model_provider": "openai",
        "overseer_model_id": "gpt-5.6-sol",
        "overseer_model_family": "gpt-5.6",
        "disposition": Disposition.REMAND,
        "response_text": text,
        "response_hash": content_hash(text),
        "source_task_id": "codex-task-001",
        "completed_at": "2026-08-25T10:02:00+00:00",
    }
    values.update(changes)
    return ResponseEnvelope(**values)


def test_bridge_paths_are_contained_by_injected_root(tmp_path: Path) -> None:
    paths = BridgePaths(state_root=tmp_path / "state")
    bridge_root = paths.bridge_root
    assert bridge_root.is_relative_to(paths.state_root)
    for directory in (
        paths.requests,
        paths.responses,
        paths.quarantine,
        paths.transactions,
    ):
        assert directory.is_relative_to(bridge_root)
    assert bridge_root == (tmp_path / "state" / "bridge").resolve()


def test_canonical_hash_is_order_independent() -> None:
    ordered = {"alpha": 1, "beta": {"gamma": [True, 2], "delta": "x"}}
    shuffled = {"beta": {"delta": "x", "gamma": [True, 2]}, "alpha": 1}
    assert canonical_json(ordered) == canonical_json(shuffled)
    assert content_hash(ordered) == content_hash(shuffled)


def test_distinct_event_identity_changes_transaction_key() -> None:
    identity: dict[str, str] = {
        "request_id": "req-001",
        "run_id": "run-001",
        "stage_id": "L14",
        "semantic_hash": "a" * 64,
        "evidence_manifest_hash": "b" * 64,
        "payload_hash": "c" * 64,
    }
    baseline = transaction_key(**identity)
    assert baseline == transaction_key(**dict(identity))
    assert baseline != transaction_key(**{**identity, "request_id": "req-002"})


def test_request_rejects_missing_or_unknown_worker_identity() -> None:
    validate_request(valid_request())
    for field in ("worker_model_provider", "worker_model_id", "worker_model_family"):
        for bad in ("", "   ", "unknown", "None", "null", "UNAVAILABLE"):
            with pytest.raises(ProtocolViolation):
                validate_request(valid_request(**{field: bad}))


def test_request_allows_null_tty_only_for_declared_headless_transport() -> None:
    with pytest.raises(ProtocolViolation):
        validate_request(valid_request(worker_tty=None))

    headless = valid_request(
        worker_transport_id="headless:cline-paeos-code",
        worker_tty=None,
    )
    validate_request(headless)

    with pytest.raises(ProtocolViolation):
        validate_request(
            valid_request(
                worker_transport_id="headless:cline-paeos-code",
                worker_tty=None,
                worker_session_id="",
            )
        )
    with pytest.raises(ProtocolViolation):
        validate_request(
            valid_request(
                worker_transport_id="headless:cline-paeos-code",
                worker_tty=None,
                worker_pid=0,
            )
        )


def test_response_disposition_has_no_ratify_member() -> None:
    assert [member.value for member in Disposition] == [
        "CONTINUE",
        "REMAND",
        "HALT",
        "NEEDS_FOUNDER",
    ]
    assert not hasattr(Disposition, "RATIFY")

    request = valid_request()
    response = valid_response(request)
    validate_response(response)
    assert response.request_id == request.request_id
    assert response.transaction_key == request.transaction_key
    assert response.payload_hash == request.payload_hash
    assert response.disposition is Disposition.REMAND


def test_write_once_json_refuses_overwrite(tmp_path: Path) -> None:
    paths = BridgePaths(state_root=tmp_path / "state")
    paths.ensure()
    target = paths.transactions / "tx-001.json"
    first = {"schema_version": SCHEMA_VERSION, "state": "NEW", "sequence": 1}
    write_once_json(target, first)
    original = target.read_bytes()

    second = {
        "schema_version": SCHEMA_VERSION,
        "state": "RESPONDED",
        "sequence": 2,
    }
    with pytest.raises(FileExistsError):
        write_once_json(target, second)

    assert target.read_bytes() == original
    assert load_json(target) == first


def test_load_json_rejects_malformed_input(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed_bytes = b'{"state": "NEW", "sequence": '
    malformed.write_bytes(malformed_bytes)
    with pytest.raises(ProtocolViolation):
        load_json(malformed)
    assert malformed.read_bytes() == malformed_bytes

    non_object = tmp_path / "array.json"
    non_object_bytes = b'["NEW", "PREPARED"]'
    non_object.write_bytes(non_object_bytes)
    with pytest.raises(ProtocolViolation):
        load_json(non_object)
    assert non_object.read_bytes() == non_object_bytes

    invalid_utf8 = tmp_path / "binary.json"
    invalid_utf8_bytes = b"\xff\xfe\x00corrupted"
    invalid_utf8.write_bytes(invalid_utf8_bytes)
    with pytest.raises(ProtocolViolation):
        load_json(invalid_utf8)
    assert invalid_utf8.read_bytes() == invalid_utf8_bytes


def valid_record(
    request: RequestEnvelope | None = None,
    **changes: object,
) -> TransactionRecord:
    request = valid_request() if request is None else request
    values: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request.request_id,
        "transaction_key": request.transaction_key,
        "run_id": request.run_id,
        "stage_id": request.stage_id,
        "payload_hash": request.payload_hash,
    }
    values.update(changes)
    return TransactionRecord(**values)


def test_reducer_accepts_the_single_happy_path() -> None:
    record = valid_record()
    prepared = reduce_transaction(
        record,
        TransactionEvent.PREPARE,
        actor="builder",
        at="2026-08-25T10:00:00+00:00",
    )
    claimed = reduce_transaction(
        prepared,
        TransactionEvent.CLAIM,
        actor="overseer",
        at="2026-08-25T10:01:00+00:00",
        lease_owner="codex-overseer",
        lease_expires_at="2026-08-25T10:10:00+00:00",
    )
    responded = reduce_transaction(
        claimed,
        TransactionEvent.RESPOND,
        actor="codex-overseer",
        at="2026-08-25T10:02:00+00:00",
    )
    consumed = reduce_transaction(
        responded,
        TransactionEvent.CONSUME,
        actor="paeos-runtime",
        at="2026-08-25T10:03:00+00:00",
    )

    assert record.state is TransactionState.NEW
    assert consumed.state is TransactionState.CONSUMED
    assert tuple(entry.event for entry in consumed.transitions) == (
        TransactionEvent.PREPARE,
        TransactionEvent.CLAIM,
        TransactionEvent.RESPOND,
        TransactionEvent.CONSUME,
    )
    assert tuple(entry.to_state for entry in consumed.transitions) == (
        TransactionState.PREPARED,
        TransactionState.CLAIMED,
        TransactionState.RESPONDED,
        TransactionState.CONSUMED,
    )


def test_claim_requires_a_lease_owner() -> None:
    prepared = reduce_transaction(
        valid_record(),
        TransactionEvent.PREPARE,
        actor="builder",
        at="2026-08-25T10:00:00+00:00",
    )
    for lease_owner, lease_expires_at in (
        (None, "2026-08-25T10:10:00+00:00"),
        ("", "2026-08-25T10:10:00+00:00"),
        ("codex-overseer", None),
        ("codex-overseer", "2026-08-25T10:01:00+00:00"),
    ):
        with pytest.raises(ProtocolViolation):
            reduce_transaction(
                prepared,
                TransactionEvent.CLAIM,
                actor="overseer",
                at="2026-08-25T10:01:00+00:00",
                lease_owner=lease_owner,
                lease_expires_at=lease_expires_at,
            )
        assert prepared.state is TransactionState.PREPARED


def test_uncertain_side_effect_requires_reconciliation() -> None:
    prepared = reduce_transaction(
        valid_record(),
        TransactionEvent.PREPARE,
        actor="builder",
        at="2026-08-25T10:00:00+00:00",
    )
    reconciled = reduce_transaction(
        prepared,
        TransactionEvent.SIDE_EFFECT_UNCERTAIN,
        actor="paeos-runtime",
        at="2026-08-25T10:01:00+00:00",
        last_side_effect="prompt write completion unknown",
    )

    assert prepared.state is TransactionState.PREPARED
    assert reconciled.state is TransactionState.RECONCILIATION_REQUIRED
    assert reconciled.last_side_effect == "prompt write completion unknown"


def test_circuit_breakers_are_exact_and_timeout_has_no_retry_transition() -> None:
    expected = (
        "NONEXISTENT_OR_UNAUTHORIZED_SUBAGENT_INVOCATION",
        "UNREQUESTED_REVIEW_OR_SKILL_ROUTING",
        "PASTED_GOVERNANCE_TEXT_INTERPRETED_AS_TOOL_ARGUMENTS",
        "COMMAND_EXPANSION_BEYOND_THE_AUTHORIZED_COMMAND",
        "SHELL_COMMAND_MUTATED_MATERIALLY_FROM_DIRECTIVE",
        "REPEATED_IDENTICAL_FAILED_TOOL_CALL_WITHOUT_NEW_RATIONALE",
        "REPEATED_IDENTICAL_COMMAND_AFTER_SAME_RESULT_WITHOUT_EXPLICIT_RERUN_AUTHORITY",
        "WRITE_ATTEMPT_OUTSIDE_CURRENT_ALLOWLIST",
        "TRUNK_OR_MAIN_PROMOTION_ATTEMPT",
        "UNAUTHORIZED_LIFECYCLE_ADVANCEMENT",
        "SELF_RATIFICATION_ATTEMPT",
    )
    assert tuple(item.value for item in CircuitBreaker) == expected
    assert "RETRY" not in TransactionEvent.__members__
    assert "RESEND" not in TransactionEvent.__members__

    record = valid_record()
    for breaker in CircuitBreaker:
        violation = ProtocolViolation(breaker, f"raw failure for {breaker.value}")
        incident = incident_from_violation(
            violation,
            record=record,
            occurred_at="2026-08-25T10:00:00+00:00",
            request_envelope_hash="f" * 64,
        )
        assert incident.breaker is breaker
        assert incident.raw_exception == f"raw failure for {breaker.value}"


def test_reconciliation_is_terminal_for_automation() -> None:
    reconciled = reduce_transaction(
        valid_record(),
        TransactionEvent.SIDE_EFFECT_UNCERTAIN,
        actor="paeos-runtime",
        at="2026-08-25T10:00:00+00:00",
    )
    for event in (
        TransactionEvent.PREPARE,
        TransactionEvent.CLAIM,
        TransactionEvent.RESPOND,
        TransactionEvent.CONSUME,
        TransactionEvent.QUARANTINE,
    ):
        with pytest.raises(ProtocolViolation):
            reduce_transaction(
                reconciled,
                event,
                actor="automation",
                at="2026-08-25T10:01:00+00:00",
                lease_owner="automation",
                lease_expires_at="2026-08-25T10:10:00+00:00",
            )
        assert reconciled.state is TransactionState.RECONCILIATION_REQUIRED


def test_founder_or_overseer_recovery_may_quarantine_reconciliation() -> None:
    reconciled = reduce_transaction(
        valid_record(),
        TransactionEvent.SIDE_EFFECT_UNCERTAIN,
        actor="paeos-runtime",
        at="2026-08-25T10:00:00+00:00",
    )
    for actor in ("founder", "overseer-recovery"):
        quarantined = reduce_transaction(
            reconciled,
            TransactionEvent.QUARANTINE,
            actor=actor,
            at="2026-08-25T10:01:00+00:00",
        )
        assert quarantined.state is TransactionState.QUARANTINED
        assert quarantined.transitions[-1].actor == actor


def test_response_correlation_accepts_exact_binding() -> None:
    request = valid_request()
    prepared = reduce_transaction(
        valid_record(request),
        TransactionEvent.PREPARE,
        actor="builder",
        at="2026-08-25T10:00:00+00:00",
    )
    claimed = reduce_transaction(
        prepared,
        TransactionEvent.CLAIM,
        actor="overseer",
        at="2026-08-25T10:01:00+00:00",
        lease_owner="codex-overseer",
        lease_expires_at="2026-08-25T10:10:00+00:00",
    )
    response = valid_response(request)

    assert (
        correlate_response(
            request,
            response,
            record=claimed,
            now="2026-08-25T10:02:00+00:00",
        )
        is None
    )
    assert claimed.state is TransactionState.CLAIMED


def test_mismatched_response_is_quarantined_and_not_consumed(
    tmp_path: Path,
) -> None:
    request = valid_request(allowed_dispositions=(Disposition.REMAND,))
    prepared = reduce_transaction(
        valid_record(request),
        TransactionEvent.PREPARE,
        actor="builder",
        at="2026-08-25T10:00:00+00:00",
    )
    claimed = reduce_transaction(
        prepared,
        TransactionEvent.CLAIM,
        actor="overseer",
        at="2026-08-25T10:01:00+00:00",
        lease_owner="codex-overseer",
        lease_expires_at="2026-08-25T10:10:00+00:00",
    )
    mutations: tuple[tuple[str, object], ...] = (
        ("request_id", "req-other"),
        ("transaction_key", "d" * 64),
        ("run_id", "run-other"),
        ("stage_id", "L15"),
        ("payload_hash", "e" * 64),
        ("lease_owner", "other-overseer"),
        ("disposition", Disposition.CONTINUE),
    )

    for index, (field_name, value) in enumerate(mutations):
        paths = BridgePaths(tmp_path / f"case-{index}")
        paths.ensure()
        store = TransactionStore(paths)
        store.create(claimed)
        response = valid_response(request, **{field_name: value})
        response_path = paths.responses / f"{request.request_id}.json"
        write_once_json(response_path, response)
        original = response_path.read_bytes()

        with pytest.raises(ProtocolViolation):
            store.accept_response(
                request,
                record=claimed,
                now="2026-08-25T10:02:00+00:00",
            )

        assert store.load(request.request_id).state is TransactionState.CLAIMED
        assert response_path.read_bytes() == original
        quarantine_payloads = tuple(
            path.read_bytes() for path in paths.quarantine.glob("*.raw") if path.is_file()
        )
        assert original in quarantine_payloads


def test_legacy_sequence_81_migrates_to_reconciliation() -> None:
    legacy: dict[str, object] = {
        "state": "SUBMITTED",
        "dispatch_seq": 81,
        "request_id": "legacy-seq-81",
        "transaction_key": "d" * 64,
        "run_id": "legacy-run",
        "stage_id": "legacy-stage",
        "payload_hash": "e" * 64,
    }

    migrated = migrate_legacy_transaction(
        legacy,
        at="2026-08-25T10:00:00+00:00",
    )

    assert migrated.state is TransactionState.RECONCILIATION_REQUIRED
    assert migrated.legacy_state == "SUBMITTED"
    assert migrated.legacy_dispatch_seq == 81
    assert migrated.legacy_raw_hash == content_hash(canonical_json(legacy))


def test_malformed_stored_record_is_quarantined(tmp_path: Path) -> None:
    paths = BridgePaths(tmp_path / "state")
    paths.ensure()
    store = TransactionStore(paths)
    transaction_path = paths.transactions / "req-broken.json"
    malformed = b"{not-json\xff"
    write_once_bytes(transaction_path, malformed)

    with pytest.raises(ProtocolViolation):
        store.load_or_quarantine("req-broken")

    assert transaction_path.read_bytes() == malformed
    raw_payloads = tuple(path.read_bytes() for path in paths.quarantine.glob("*.raw"))
    reason_documents = tuple(paths.quarantine.glob("*.reason.json"))
    assert raw_payloads == (malformed,)
    assert len(reason_documents) == 1


def test_duplicate_transaction_key_cannot_create_second_active_request(
    tmp_path: Path,
) -> None:
    paths = BridgePaths(tmp_path / "state")
    paths.ensure()
    store = TransactionStore(paths)
    first = valid_record()
    second = replace(first, request_id="req-002")

    first_path = store.create(first)
    with pytest.raises(ProtocolViolation) as raised:
        store.create(second)

    assert raised.value.breaker is (
        CircuitBreaker.REPEATED_IDENTICAL_COMMAND_AFTER_SAME_RESULT_WITHOUT_EXPLICIT_RERUN_AUTHORITY
    )
    assert first_path.read_bytes()
    assert not (paths.transactions / "req-002.json").exists()
