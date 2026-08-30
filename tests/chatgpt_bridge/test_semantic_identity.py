"""Protocol-level tests for the paeos-bridge-v2 immutable envelopes.

Approved contract:
docs/superpowers/plans/2026-08-25-paeos-control-plane-recovery-subproject-1.md
"""

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from paeos.model_router.types import ModelFamily
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
    bind_request_to_admitted_worker,
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
    worker_evidence_manifest,
    write_once_bytes,
    write_once_json,
)
from runtime.worker_admission import (
    AdmissionError,
    PhysicalModelReceipt,
    ProbeContract,
    RawWorkerRun,
    ToolDecisionRecord,
    VerificationReceipt,
    WorkerBinding,
    admitted_worker_binding,
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


def test_claim_requires_a_lease_owner(tmp_path: Path) -> None:
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

    store = TransactionStore(BridgePaths(tmp_path / "state"))
    invalid_claimed = replace(
        valid_record(),
        state=TransactionState.CLAIMED,
    )
    with pytest.raises(ProtocolViolation):
        store.create(invalid_claimed)


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

    with pytest.raises(ProtocolViolation):
        store.save(replace(first, state=TransactionState.PREPARED))

    prepared_for_save = reduce_transaction(
        first,
        TransactionEvent.PREPARE,
        actor="builder",
        at="2026-08-25T10:00:00+00:00",
    )
    with pytest.raises(ProtocolViolation):
        store.save(
            replace(prepared_for_save, transaction_key="e" * 64, run_id="run-drift")
        )

    assert store.load(first.request_id) == first


def test_transaction_save_rejects_stale_prior_digest_and_preserves_winner(
    tmp_path: Path,
) -> None:
    paths = BridgePaths(tmp_path / "state")
    store = TransactionStore(paths)
    first = valid_record()
    store.create(first)
    prepared = reduce_transaction(
        first,
        TransactionEvent.PREPARE,
        actor="builder",
        at="2026-08-25T10:00:00+00:00",
    )
    prior_digest = store.digest(first.request_id)
    store.save(prepared, expected_prior_digest=prior_digest)

    claimed = reduce_transaction(
        prepared,
        TransactionEvent.CLAIM,
        actor="codex-overseer",
        at="2026-08-25T10:00:30+00:00",
        lease_owner="codex-overseer",
        lease_expires_at="2026-08-25T10:05:00+00:00",
    )
    with pytest.raises(ProtocolViolation, match="changed concurrently"):
        store.save(claimed, expected_prior_digest=prior_digest)

    assert store.load(first.request_id) == prepared


def test_transaction_lock_serializes_competing_processes(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    first_marker = tmp_path / "first.marker"
    second_marker = tmp_path / "second.marker"
    child = """
import sys
import time
from pathlib import Path
from runtime.integrations.bridge_protocol import BridgePaths, TransactionStore

state_root = Path(sys.argv[1])
marker = Path(sys.argv[2])
with TransactionStore(BridgePaths(state_root))._transaction_lock():
    marker.write_text("acquired", encoding="utf-8")
    time.sleep(0.25)
    marker.write_text("released", encoding="utf-8")
"""
    first = subprocess.Popen([sys.executable, "-c", child, str(state_root), str(first_marker)])
    try:
        deadline = time.monotonic() + 3.0
        while not first_marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert first_marker.read_text(encoding="utf-8") == "acquired"
        second = subprocess.Popen(
            [sys.executable, "-c", child, str(state_root), str(second_marker)]
        )
        try:
            time.sleep(0.05)
            assert not second_marker.exists()
            assert first.wait(timeout=3) == 0
            assert second.wait(timeout=3) == 0
            assert second_marker.read_text(encoding="utf-8") == "released"
        finally:
            if second.poll() is None:
                second.kill()
                second.wait(timeout=3)
    finally:
        if first.poll() is None:
            first.kill()
            first.wait(timeout=3)


# ---------------------------------------------------------------------------
# Task 5: bind admitted worker receipts into bridge requests
# ---------------------------------------------------------------------------


def evidence_pair(
    provider: str = "cline-pass",
    model: str = "cline-pass/qwen3.8-max",
    family: ModelFamily = ModelFamily.QWEN,
    session: str = "session-001",
    pid: int = 4242,
    transport: str = "headless:cline-cli-3.0.56",
    stdout_hash: str = "b" * 64,
) -> tuple[ProbeContract, RawWorkerRun]:
    """Valid (contract, run) evidence that passes admission assessment."""
    contract = ProbeContract(
        probe_id="probe-001",
        sandbox=Path("/probe/sandbox"),
        provider_id=provider,
        model_id=model,
        expected_family=family,
        artifact_name="artifact.txt",
        initial_bytes=b"old\n",
        expected_bytes=b"new\n",
        verification_command="python3 verify_probe.py",
    )
    receipt = PhysicalModelReceipt(
        transport_id=transport,
        session_id=session,
        pid=pid,
        configured_provider_id=provider,
        configured_model_id=model,
        actual_provider_id=provider,
        actual_model_id=model,
        actual_family=family,
        manifest_provider_id=provider,
        manifest_model_id=model,
        message_models=(model,),
        argv_hash="a" * 64,
        stdout_hash=stdout_hash,
        stderr_hash="c" * 64,
        manifest_hash="d" * 64,
        messages_hash="e" * 64,
    )
    argv = ("python3", "verify_probe.py")
    artifact_hash = hashlib.sha256(b"new\n").hexdigest()
    run = RawWorkerRun(
        probe_id=contract.probe_id,
        receipt=receipt,
        tool_decisions=(
            ToolDecisionRecord(tool_name="editor", approved=True, reason_code=""),
            ToolDecisionRecord(
                tool_name="run_commands", approved=True, reason_code=""
            ),
        ),
        artifact_name="artifact.txt",
        artifact_hash=artifact_hash,
        artifact_size=4,
        verification=VerificationReceipt(
            argv=argv,
            argv_hash=hashlib.sha256(
                json.dumps(argv, separators=(",", ":")).encode()
            ).hexdigest(),
            baseline_artifact_hash=hashlib.sha256(b"old\n").hexdigest(),
            baseline_exit_code=1,
            baseline_stdout_hash="1" * 64,
            baseline_stderr_hash="2" * 64,
            candidate_artifact_hash=artifact_hash,
            candidate_exit_code=0,
            candidate_stdout_hash="3" * 64,
            candidate_stderr_hash="4" * 64,
            mutation_hash=hashlib.sha256(b"seeded-mutation\n").hexdigest(),
            mutation_exit_code=1,
            mutation_stdout_hash="5" * 64,
            mutation_stderr_hash="6" * 64,
            artifact_restored_hash=artifact_hash,
            restored_exit_code=0,
            restored_stdout_hash="8" * 64,
            restored_stderr_hash="9" * 64,
        ),
    )
    return contract, run


def admitted_binding(**overrides: object) -> WorkerBinding:
    """An authoritative binding built only through admitted probe evidence."""
    return WorkerBinding(*evidence_pair(**overrides))


def receipt_bound_request(binding: WorkerBinding, **changes: object) -> RequestEnvelope:
    """A protocol-valid request whose canonical manifest is unbound (no receipt hash)."""
    request = valid_request(
        worker_transport_id=binding.transport,
        worker_session_id=binding.session,
        worker_pid=binding.pid,
        worker_tty=binding.tty,
        worker_model_provider=binding.provider,
        worker_model_id=binding.model,
        worker_model_family=binding.family.value,
    )
    unbound_hash = content_hash(worker_evidence_manifest(request))
    request = replace(request, evidence_manifest_hash=unbound_hash)
    request = replace(
        request,
        transaction_key=transaction_key(
            request_id=request.request_id,
            run_id=request.run_id,
            stage_id=request.stage_id,
            semantic_hash=request.semantic_hash,
            evidence_manifest_hash=unbound_hash,
            payload_hash=request.payload_hash,
        ),
    )
    if changes:
        request = replace(request, **changes)
    return request


def test_worker_receipt_hash_is_bound_into_the_evidence_manifest() -> None:
    binding = admitted_binding()
    request = receipt_bound_request(binding)
    result = bind_request_to_admitted_worker(request, binding)
    bound = result.request

    manifest = worker_evidence_manifest(bound, worker_receipt_hash=binding.receipt_hash)
    assert manifest["worker_receipt_hash"] == binding.receipt_hash
    assert bound.evidence_manifest_hash == content_hash(manifest)
    assert bound.evidence_manifest_hash != request.evidence_manifest_hash
    assert bound.transaction_key != request.transaction_key
    assert bound.transaction_key == transaction_key(
        request_id=bound.request_id,
        run_id=bound.run_id,
        stage_id=bound.stage_id,
        semantic_hash=bound.semantic_hash,
        evidence_manifest_hash=bound.evidence_manifest_hash,
        payload_hash=bound.payload_hash,
    )
    validate_request(bound)


def test_binding_is_idempotent_for_an_already_bound_request() -> None:
    binding = admitted_binding()
    first = bind_request_to_admitted_worker(receipt_bound_request(binding), binding)
    again = bind_request_to_admitted_worker(first.request, binding)
    assert again.request == first.request


def test_binding_rejects_conflicting_existing_worker_identity() -> None:
    binding = admitted_binding()
    request = receipt_bound_request(binding, worker_model_provider="other-provider")
    with pytest.raises(ProtocolViolation, match="worker identity"):
        bind_request_to_admitted_worker(request, binding)


def test_binding_rejects_conflicting_existing_manifest_hash() -> None:
    binding = admitted_binding()
    request = receipt_bound_request(binding, evidence_manifest_hash="e" * 64)
    with pytest.raises(ProtocolViolation, match="manifest"):
        bind_request_to_admitted_worker(request, binding)


def test_binding_rejects_conflicting_existing_transaction_binding() -> None:
    binding = admitted_binding()
    request = receipt_bound_request(binding, transaction_key="e" * 64)
    with pytest.raises(ProtocolViolation, match="transaction binding"):
        bind_request_to_admitted_worker(request, binding)


def test_unvalidated_receipt_cannot_produce_a_binding_or_bound_request() -> None:
    binding = admitted_binding()
    # Identity fields are not constructor inputs, so a receipt hash cannot be
    # injected into a binding — and no binding can be manufactured without
    # admitted probe evidence.
    with pytest.raises(TypeError):
        WorkerBinding(
            transport=binding.transport, session=binding.session, pid=binding.pid,
            tty=None, provider=binding.provider, model=binding.model,
            family=ModelFamily.QWEN, receipt_hash="not-a-hex-receipt")


def test_rejected_admission_cannot_bind_any_request(tmp_path: Path) -> None:
    contract = ProbeContract(
        probe_id="probe-001",
        sandbox=tmp_path / "sandbox",
        provider_id="cline-pass",
        model_id="cline-pass/qwen3.8-max",
        expected_family=ModelFamily.QWEN,
        artifact_name="artifact.txt",
        initial_bytes=b"old\n",
        expected_bytes=b"new\n",
        verification_command="python3 verify_probe.py",
    )
    receipt = PhysicalModelReceipt(
        transport_id="headless:cline-cli-3.0.56",
        session_id="session-001",
        pid=4242,
        configured_provider_id="cline-pass",
        configured_model_id="cline-pass/qwen3.8-max",
        actual_provider_id="cline-pass",
        actual_model_id="cline-pass/qwen3.8-max",
        actual_family=ModelFamily.QWEN,
        manifest_provider_id="cline-pass",
        manifest_model_id="cline-pass/qwen3.8-max",
        message_models=("cline-pass/qwen3.8-max",),
        argv_hash="a" * 64,
        stdout_hash="b" * 64,
        stderr_hash="c" * 64,
        manifest_hash="d" * 64,
        messages_hash="e" * 64,
    )
    rejected_run = RawWorkerRun(
        probe_id="probe-001",
        receipt=receipt,
        tool_decisions=(),
        artifact_name="artifact.txt",
        artifact_hash="0" * 64,
        artifact_size=4,
        verification=VerificationReceipt(
            argv=("python3", "verify_probe.py"),
            argv_hash="a" * 64,
            baseline_artifact_hash="b" * 64,
            baseline_exit_code=1,
            baseline_stdout_hash="1" * 64,
            baseline_stderr_hash="2" * 64,
            candidate_artifact_hash="0" * 64,
            candidate_exit_code=0,
            candidate_stdout_hash="3" * 64,
            candidate_stderr_hash="4" * 64,
            mutation_hash="5" * 64,
            mutation_exit_code=1,
            mutation_stdout_hash="6" * 64,
            mutation_stderr_hash="7" * 64,
            artifact_restored_hash="0" * 64,
            restored_exit_code=0,
            restored_stdout_hash="8" * 64,
            restored_stderr_hash="9" * 64,
        ),
    )
    with pytest.raises(AdmissionError, match="worker not admitted"):
        admitted_worker_binding(contract, rejected_run)


def test_bound_result_manifest_bytes_are_exact_evidence() -> None:
    binding = admitted_binding()
    result = bind_request_to_admitted_worker(receipt_bound_request(binding), binding)
    manifest_bytes = result.evidence_manifest_bytes
    assert (
        hashlib.sha256(manifest_bytes).hexdigest()
        == result.request.evidence_manifest_hash
    )
    parsed = json.loads(manifest_bytes)
    assert parsed["worker_receipt_hash"] == binding.receipt_hash
    assert not manifest_bytes.endswith(b"\n")


def test_changing_the_receipt_changes_manifest_hash_and_transaction_key() -> None:
    first = admitted_binding(stdout_hash="b" * 64)
    second = admitted_binding(stdout_hash="f" * 64)
    assert first.receipt_hash != second.receipt_hash
    result_a = bind_request_to_admitted_worker(receipt_bound_request(first), first)
    result_b = bind_request_to_admitted_worker(receipt_bound_request(first), second)
    assert (
        result_a.request.evidence_manifest_hash
        != result_b.request.evidence_manifest_hash
    )
    assert result_a.request.transaction_key != result_b.request.transaction_key
    assert (
        json.loads(result_a.evidence_manifest_bytes)["worker_receipt_hash"]
        == first.receipt_hash
    )
    assert (
        json.loads(result_b.evidence_manifest_bytes)["worker_receipt_hash"]
        == second.receipt_hash
    )


def test_already_bound_request_returns_identical_manifest_bytes() -> None:
    binding = admitted_binding()
    first = bind_request_to_admitted_worker(receipt_bound_request(binding), binding)
    again = bind_request_to_admitted_worker(first.request, binding)
    assert again.request == first.request
    assert again.evidence_manifest_bytes == first.evidence_manifest_bytes


def test_binder_cannot_operate_without_a_valid_admission() -> None:
    # Cross-probe replay: the evidence constructor re-assesses probe identity.
    contract, run = evidence_pair()
    with pytest.raises(AdmissionError, match="probe ID mismatch"):
        WorkerBinding(replace(contract, probe_id="probe-002"), run)

    # Tampered evidence cannot survive re-assessment on any construction path.
    with pytest.raises(AdmissionError, match="worker not admitted"):
        WorkerBinding(contract, replace(run, artifact_hash="f" * 64))
