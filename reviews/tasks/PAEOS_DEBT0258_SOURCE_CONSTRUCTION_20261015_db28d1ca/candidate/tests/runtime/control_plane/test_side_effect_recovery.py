from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from runtime.control_plane.coordinator import StaleComparison, TransactionCoordinator
from runtime.control_plane.events import (
    DispatchEvidence,
    SideEffectCertainty,
    idempotency_key,
    side_effect_retry_eligible,
)
from runtime.control_plane.sqlite_projection import SqliteControlPlaneProjection
from runtime.integrations.bridge_protocol import (
    ProtocolViolation,
    TransactionEvent,
    TransactionRecord,
    TransactionState,
    content_hash,
    persist_immutable_bytes,
)
from tests.runtime.control_plane.test_projection import command


def test_idempotency_key_is_stable_and_payload_bound() -> None:
    first = idempotency_key(transaction_key="a" * 64, operation="dispatch", payload_hash="b" * 64)
    assert first == idempotency_key(
        transaction_key="a" * 64,
        operation="dispatch",
        payload_hash="b" * 64,
    )
    assert first != idempotency_key(
        transaction_key="a" * 64,
        operation="dispatch",
        payload_hash="c" * 64,
    )


@pytest.mark.parametrize(
    ("certainty", "eligible"),
    [
        (SideEffectCertainty.NOT_ATTEMPTED, True),
        (SideEffectCertainty.REJECTED_BEFORE_ACCEPTANCE, True),
        (SideEffectCertainty.ACCEPTED, False),
        (SideEffectCertainty.UNCERTAIN, False),
    ],
)
def test_retry_policy_is_fail_closed(
    certainty: SideEffectCertainty,
    eligible: bool,
) -> None:
    assert side_effect_retry_eligible(certainty) is eligible


def test_immutable_request_bytes_are_content_addressed_and_write_once(tmp_path: Path) -> None:
    target = tmp_path / "requests" / "req-001.bin"
    target.parent.mkdir()
    payload = b"canonical request bytes"

    digest = persist_immutable_bytes(target, payload)
    assert target.read_bytes() == payload
    assert digest == content_hash(payload)
    assert persist_immutable_bytes(target, payload) == digest
    with pytest.raises(ProtocolViolation, match="different bytes"):
        persist_immutable_bytes(target, b"mutated request bytes")


@pytest.mark.parametrize(
    ("evidence", "certainty", "eligible"),
    [
        (
            DispatchEvidence(),
            SideEffectCertainty.NOT_ATTEMPTED,
            True,
        ),
        (
            DispatchEvidence(
                request_bytes_persisted=True,
                request_bytes_hash="d" * 64,
                attempted=True,
            ),
            SideEffectCertainty.REJECTED_BEFORE_ACCEPTANCE,
            True,
        ),
        (
            DispatchEvidence(
                request_bytes_persisted=True,
                request_bytes_hash="d" * 64,
                attempted=True,
                accepted=True,
            ),
            SideEffectCertainty.ACCEPTED,
            False,
        ),
        (
            DispatchEvidence(
                request_bytes_persisted=True,
                request_bytes_hash="d" * 64,
                attempted=True,
                accepted=True,
                response_bytes_persisted=True,
                response_bytes_hash="e" * 64,
                response_verified=True,
            ),
            SideEffectCertainty.ACCEPTED,
            False,
        ),
    ],
)
def test_evidence_captures_progressive_crash_boundaries(
    evidence: DispatchEvidence,
    certainty: SideEffectCertainty,
    eligible: bool,
) -> None:
    assert side_effect_retry_eligible(certainty) is eligible
    if evidence.attempted:
        assert evidence.request_bytes_persisted
    if evidence.accepted:
        assert evidence.attempted
    if evidence.response_bytes_persisted:
        assert evidence.accepted


@pytest.mark.parametrize(
    "kwargs",
    [
        {"attempted": True},
        {"accepted": True},
        {"request_bytes_persisted": True},
        {
            "request_bytes_persisted": True,
            "request_bytes_hash": "d" * 64,
            "attempted": True,
            "accepted": True,
            "response_bytes_persisted": True,
        },
    ],
)
def test_evidence_rejects_unproven_crash_boundary(kwargs: dict[str, Any]) -> None:
    with pytest.raises((TypeError, ValueError)):
        DispatchEvidence(**kwargs)


def test_accepted_but_uncorrelated_attempt_is_terminal_and_not_replayed(tmp_path: Path) -> None:
    ledger = Ledger(SqliteLedgerStore(tmp_path / "ledger.db"), writer_id="control-plane")
    projection = SqliteControlPlaneProjection(tmp_path / "projection.db")
    coordinator = TransactionCoordinator(ledger, projection)
    prepared = coordinator.prepare(
        TransactionRecord(
            schema_version="paeos-bridge-v2",
            request_id="req-001",
            transaction_key="a" * 64,
            run_id="run-001",
            stage_id="L14",
            payload_hash="b" * 64,
        ),
        expected_ledger_head=ledger.head_hash(),
    )
    key = idempotency_key(
        transaction_key="a" * 64,
        operation="dispatch",
        payload_hash="b" * 64,
    )
    uncertain = command(
        event=TransactionEvent.SIDE_EFFECT_UNCERTAIN,
        actor="execution-layer",
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=prepared.projected_digest,
        fencing_token=2,
        last_side_effect=key,
        side_effect_certainty=SideEffectCertainty.ACCEPTED,
        idempotency_key=key,
        dispatch_evidence=DispatchEvidence(
            request_bytes_persisted=True,
            request_bytes_hash="d" * 64,
            attempted=True,
            accepted=True,
        ),
    )
    receipt = coordinator.apply(uncertain, expected_ledger_head=prepared.ledger_head)
    assert (
        projection.get("req-001", verified_ledger_head=receipt.ledger_head).record.state
        is TransactionState.RECONCILIATION_REQUIRED
    )
    with pytest.raises(StaleComparison):
        coordinator.apply(uncertain, expected_ledger_head=prepared.ledger_head)
    assert len(ledger.read()) == 2


def test_idempotency_key_cannot_cross_transaction_boundaries(tmp_path: Path) -> None:
    ledger = Ledger(SqliteLedgerStore(tmp_path / "ledger.db"), writer_id="control-plane")
    projection = SqliteControlPlaneProjection(tmp_path / "projection.db")
    coordinator = TransactionCoordinator(ledger, projection)
    first = coordinator.prepare(
        TransactionRecord(
            schema_version="paeos-bridge-v2",
            request_id="req-001",
            transaction_key="a" * 64,
            run_id="run-001",
            stage_id="L14",
            payload_hash="b" * 64,
        ),
        expected_ledger_head=ledger.head_hash(),
    )
    key = idempotency_key(
        transaction_key="a" * 64,
        operation="dispatch",
        payload_hash="b" * 64,
    )
    first_uncertain = command(
        event=TransactionEvent.SIDE_EFFECT_UNCERTAIN,
        actor="execution-layer",
        at="2026-08-30T10:01:00+00:00",
        expected_prior_digest=first.projected_digest,
        fencing_token=2,
        last_side_effect=key,
        side_effect_certainty=SideEffectCertainty.ACCEPTED,
        idempotency_key=key,
        dispatch_evidence=DispatchEvidence(
            request_bytes_persisted=True,
            request_bytes_hash="d" * 64,
            attempted=True,
            accepted=True,
        ),
    )
    first_receipt = coordinator.apply(first_uncertain, expected_ledger_head=first.ledger_head)
    second = coordinator.prepare(
        TransactionRecord(
            schema_version="paeos-bridge-v2",
            request_id="req-002",
            transaction_key="c" * 64,
            run_id="run-002",
            stage_id="L14",
            payload_hash="e" * 64,
        ),
        expected_ledger_head=first_receipt.ledger_head,
    )
    second_uncertain = command(
        request_id="req-002",
        transaction_key="c" * 64,
        run_id="run-002",
        payload_hash="e" * 64,
        event=TransactionEvent.SIDE_EFFECT_UNCERTAIN,
        actor="execution-layer",
        at="2026-08-30T10:02:00+00:00",
        expected_prior_digest=second.projected_digest,
        fencing_token=2,
        last_side_effect=key,
        side_effect_certainty=SideEffectCertainty.ACCEPTED,
        idempotency_key=key,
        dispatch_evidence=DispatchEvidence(
            request_bytes_persisted=True,
            request_bytes_hash="f" * 64,
            attempted=True,
            accepted=True,
        ),
    )
    with pytest.raises(StaleComparison, match="idempotency_key was already committed"):
        coordinator.apply(second_uncertain, expected_ledger_head=second.ledger_head)
    assert len(ledger.read()) == 3
