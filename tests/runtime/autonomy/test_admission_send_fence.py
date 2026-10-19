from __future__ import annotations

import hashlib
import multiprocessing
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kernel.ledger import Event, InMemoryLedgerStore, Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from runtime.autonomy.admission_send_fence import (
    AdmissionNotCurrent,
    AdmissionSendFence,
    DuplicateSendOperation,
    SendOperation,
    SendOutcome,
    SendSettlementError,
)

_TEST_DOMAIN = "TEST"
_ADMISSION_REF = "synthetic-admission-1"
_POLICY_ID = "synthetic-policy-1"
_POLICY_DIGEST = "a" * 64
_ROUTE_ID = "trusted-codex-worker/v1"
_ROUTE_DIGEST = hashlib.sha256(_ROUTE_ID.encode("ascii")).hexdigest()
_NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
_LATER = "2026-10-20T12:00:00+00:00"


class _SyntheticAuthority:
    """Explicit test-only verifier; no host key, provider identity or environment access."""

    def verify_policy(self, payload: Mapping[str, object]) -> bool:
        return payload.get("proof") == "synthetic-policy-proof"

    def verify_admission(self, payload: Mapping[str, object]) -> bool:
        return payload.get("proof") == "synthetic-admission-proof"

    def authorize_frame(
        self,
        admission: Mapping[str, object],
        policy: Mapping[str, object],
        *,
        frame_digest: str,
        route_digest: str,
    ) -> bool:
        return (
            admission.get("policy_id") == policy.get("policy_id")
            and route_digest == admission.get("route_digest")
            and len(frame_digest) == 64
        )


def _admission_payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "admission_ref": _ADMISSION_REF,
        "epoch": 7,
        "logical_job_id": "synthetic-logical-job-1",
        "task_id": "synthetic-task-1",
        "goal_id": "synthetic-goal-1",
        "run_id": "synthetic-run-1",
        "stage": "IMPLEMENT",
        "role": "BUILDER",
        "workspace_id": "synthetic-workspace-1",
        "route_id": _ROUTE_ID,
        "route_digest": _ROUTE_DIGEST,
        "policy_id": _POLICY_ID,
        "policy_revision": 1,
        "policy_digest": _POLICY_DIGEST,
        "expires_at": _LATER,
        "proof": "synthetic-admission-proof",
    }
    value.update(overrides)
    return value


def _seed(ledger: Ledger, **admission_overrides: object) -> None:
    ledger.append(
        Event(
            1,
            "DISCLOSURE_POLICY_CURRENT",
            {
                "policy_id": _POLICY_ID,
                "revision": 1,
                "digest": _POLICY_DIGEST,
                "expires_at": _LATER,
                "proof": "synthetic-policy-proof",
            },
        ),
        domain_tag=_TEST_DOMAIN,
    )
    ledger.append(
        Event(1, "ADMISSION_CURRENT", _admission_payload(**admission_overrides)),
        domain_tag=_TEST_DOMAIN,
    )


def _operation(
    *, request_id: str = "request-1", frame: bytes = b'{"prompt":"synthetic"}', **overrides: object
) -> SendOperation:
    value: dict[str, object] = {
        "admission_ref": _ADMISSION_REF,
        "expected_epoch": 7,
        "task_id": "synthetic-task-1",
        "goal_id": "synthetic-goal-1",
        "run_id": "synthetic-run-1",
        "stage": "IMPLEMENT",
        "role": "BUILDER",
        "workspace_id": "synthetic-workspace-1",
        "route_id": _ROUTE_ID,
        "route_digest": _ROUTE_DIGEST,
        "request_id": request_id,
        "frame": frame,
    }
    value.update(overrides)
    return SendOperation(**value)  # type: ignore[arg-type]


def _fence(ledger: Ledger) -> AdmissionSendFence:
    return AdmissionSendFence(
        ledger,
        authority=_SyntheticAuthority(),
        domain_tag=_TEST_DOMAIN,
        now=lambda: _NOW,
    )


def test_atomic_claim_is_bound_to_verified_current_admission_and_exact_frame() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _seed(ledger)

    lease = _fence(ledger).acquire_send_lease(_operation())

    claim = ledger.read()[-1]
    assert claim.event.kind == "ADMISSION_SEND_CLAIMED"
    assert claim.domain_tag == _TEST_DOMAIN
    assert claim.event.payload["lease_id"] == lease.lease_id
    assert claim.event.payload["logical_job_id"] == "synthetic-logical-job-1"
    assert claim.event.payload["request_id"] == "request-1"
    assert (
        claim.event.payload["frame_digest"] == hashlib.sha256(b'{"prompt":"synthetic"}').hexdigest()
    )
    assert claim.event.payload["policy_digest"] == _POLICY_DIGEST


@pytest.mark.parametrize(
    "overrides",
    [
        {"expected_epoch": 6},
        {"stage": "REVIEW"},
        {"run_id": "synthetic-run-stale"},
        {"workspace_id": "other-workspace"},
        {"route_id": "other-route"},
    ],
)
def test_stale_or_mismatched_admission_fails_closed(overrides: dict[str, object]) -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _seed(ledger)

    with pytest.raises(AdmissionNotCurrent):
        _fence(ledger).acquire_send_lease(_operation(**overrides))

    assert not any(row.event.kind == "ADMISSION_SEND_CLAIMED" for row in ledger.read())


def test_admission_and_policy_revocation_block_claim_before_sink() -> None:
    for revocation in (
        Event(1, "ADMISSION_REVOKED", {"admission_ref": _ADMISSION_REF, "epoch": 7}),
        Event(1, "DISCLOSURE_POLICY_REVOKED", {"policy_id": _POLICY_ID, "revision": 1}),
    ):
        ledger = Ledger(InMemoryLedgerStore())
        _seed(ledger)
        ledger.append(revocation, domain_tag=_TEST_DOMAIN)
        sink_calls: list[bytes] = []

        with pytest.raises(AdmissionNotCurrent):
            _fence(ledger).send_once(_operation(), sink_calls.append)

        assert sink_calls == []
        assert not any(row.event.kind == "ADMISSION_SEND_CLAIMED" for row in ledger.read())


def test_stale_policy_revision_and_unverified_admission_are_denied() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _seed(ledger)
    ledger.append(
        Event(
            1,
            "DISCLOSURE_POLICY_CURRENT",
            {
                "policy_id": _POLICY_ID,
                "revision": 2,
                "digest": "b" * 64,
                "expires_at": _LATER,
                "proof": "synthetic-policy-proof",
            },
        ),
        domain_tag=_TEST_DOMAIN,
    )
    with pytest.raises(AdmissionNotCurrent):
        _fence(ledger).acquire_send_lease(_operation())

    forged = Ledger(InMemoryLedgerStore())
    _seed(forged, proof="worker-asserted-admission")
    with pytest.raises(AdmissionNotCurrent):
        _fence(forged).acquire_send_lease(_operation())


def test_new_request_id_cannot_repeat_a_logical_operation() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _seed(ledger)
    fence = _fence(ledger)
    fence.acquire_send_lease(_operation())

    with pytest.raises(DuplicateSendOperation):
        fence.acquire_send_lease(
            _operation(request_id="new-request-id", frame=b'{"prompt":"synthetic","id":"new"}')
        )

    assert sum(row.event.kind == "ADMISSION_SEND_CLAIMED" for row in ledger.read()) == 1


def test_unsettled_claim_survives_restart_and_cannot_be_released(tmp_path: Path) -> None:
    database = tmp_path / "canonical-ledger.db"
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="b00-test")
    _seed(ledger)
    lease = _fence(ledger).acquire_send_lease(_operation())
    ledger.close()
    store.close()

    reopened_store = SqliteLedgerStore(database)
    reopened = Ledger(reopened_store, writer_id="b00-test")
    fence = _fence(reopened)
    assert reopened.verify_chain() == reopened.head_hash()
    with pytest.raises(DuplicateSendOperation):
        fence.acquire_send_lease(_operation(request_id="after-restart"))

    with pytest.raises(SendSettlementError):
        fence.finish_send_lease(lease, SendOutcome.UNKNOWN)
    with pytest.raises(DuplicateSendOperation):
        fence.acquire_send_lease(_operation(request_id="after-unknown"))
    assert not any(row.event.kind == "ADMISSION_SEND_SETTLED" for row in reopened.read())
    reopened.close()
    reopened_store.close()


def test_duplicate_and_conflicting_settlement_are_rejected_without_mutation() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _seed(ledger)
    fence = _fence(ledger)
    lease = fence.acquire_send_lease(_operation())
    outcome_ref = "c" * 64
    fence.finish_send_lease(lease, SendOutcome.RETURNED, outcome_ref=outcome_ref)
    count = len(ledger.read())

    with pytest.raises(SendSettlementError):
        fence.finish_send_lease(lease, SendOutcome.RETURNED, outcome_ref=outcome_ref)
    with pytest.raises(SendSettlementError):
        fence.finish_send_lease(lease, SendOutcome.UNKNOWN)

    assert len(ledger.read()) == count


def test_sink_failure_is_settled_unknown_and_never_replayed() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _seed(ledger)
    fence = _fence(ledger)
    sink_calls: list[bytes] = []

    def uncertain_sink(frame: bytes) -> bytes:
        sink_calls.append(frame)
        raise TimeoutError("synthetic sink outcome is unknown")

    with pytest.raises(TimeoutError):
        fence.send_once(_operation(), uncertain_sink)

    settled = next(row for row in ledger.read() if row.event.kind == "ADMISSION_SEND_SETTLED")
    assert settled.event.payload["outcome"] == "UNKNOWN"
    assert len(sink_calls) == 1
    with pytest.raises(DuplicateSendOperation):
        fence.send_once(_operation(request_id="retry-after-timeout"), sink_calls.append)
    assert len(sink_calls) == 1


def test_claim_committed_before_revocation_stays_settleable_and_blocks_future_claims() -> None:
    ledger = Ledger(InMemoryLedgerStore())
    _seed(ledger)
    fence = _fence(ledger)
    lease = fence.acquire_send_lease(_operation())
    ledger.append(
        Event(1, "ADMISSION_REVOKED", {"admission_ref": _ADMISSION_REF, "epoch": 7}),
        domain_tag=_TEST_DOMAIN,
    )
    rows = ledger.read()
    fence.finish_send_lease(
        lease,
        SendOutcome.RETURNED,
        outcome_ref=hashlib.sha256(b"synthetic-response").hexdigest(),
    )

    claim = next(row for row in rows if row.event.kind == "ADMISSION_SEND_CLAIMED")
    revocation = next(row for row in rows if row.event.kind == "ADMISSION_REVOKED")
    assert claim.seq < revocation.seq
    with pytest.raises(AdmissionNotCurrent):
        fence.acquire_send_lease(_operation(request_id="after-revoke"))
    assert [row.event.kind for row in ledger.read()].count("ADMISSION_SEND_CLAIMED") == 1


def _process_claim(
    database: str,
    barrier: multiprocessing.synchronize.Barrier,
    results: multiprocessing.queues.Queue,
    request_id: str,
) -> None:
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="b00-process-test")
    try:
        barrier.wait(timeout=10)
        lease = _fence(ledger).acquire_send_lease(
            _operation(request_id=request_id, frame=request_id.encode("ascii"))
        )
        results.put(("CLAIMED", lease.lease_id))
    except DuplicateSendOperation:
        results.put(("DENIED", request_id))
    except Exception as exc:  # surfaced in the parent with the exact type
        results.put(("ERROR", type(exc).__name__))
    finally:
        ledger.close()
        store.close()


class _PausingSqliteStore(SqliteLedgerStore):
    def __init__(self, database: str, claim_ready: object, continue_claim: object) -> None:
        super().__init__(database)
        self._claim_ready = claim_ready
        self._continue_claim = continue_claim

    def append_row_if_head(self, row, expected_head_hash: str) -> None:
        if row.event.kind == "ADMISSION_SEND_CLAIMED":
            self._claim_ready.set()
            if not self._continue_claim.wait(timeout=10):
                raise TimeoutError("race test did not release the send claim")
        super().append_row_if_head(row, expected_head_hash)


def _process_claim_until_compare(
    database: str,
    claim_ready: object,
    continue_claim: object,
    results: multiprocessing.queues.Queue,
) -> None:
    store = _PausingSqliteStore(database, claim_ready, continue_claim)
    ledger = Ledger(store, writer_id="b00-revocation-race")
    sink_calls: list[bytes] = []
    try:
        _fence(ledger).send_once(_operation(), lambda frame: sink_calls.append(frame))
        results.put(("SENT", len(sink_calls)))
    except AdmissionNotCurrent:
        results.put(("REVOKED", len(sink_calls)))
    except Exception as exc:
        results.put(("ERROR", type(exc).__name__, len(sink_calls)))
    finally:
        ledger.close()
        store.close()


def _process_revoke_after_claim_validation(
    database: str,
    claim_ready: object,
    continue_claim: object,
    results: multiprocessing.queues.Queue,
) -> None:
    if not claim_ready.wait(timeout=10):
        results.put(("ERROR", "claim validation did not arrive"))
        continue_claim.set()
        return
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="b00-revocation-race")
    try:
        ledger.append(
            Event(1, "ADMISSION_REVOKED", {"admission_ref": _ADMISSION_REF, "epoch": 7}),
            domain_tag=_TEST_DOMAIN,
        )
        results.put(("REVOKED",))
    except Exception as exc:
        results.put(("ERROR", type(exc).__name__))
    finally:
        ledger.close()
        store.close()
        continue_claim.set()


def test_two_processes_get_exactly_one_atomic_send_claim(tmp_path: Path) -> None:
    database = tmp_path / "canonical-ledger.db"
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="b00-process-test")
    _seed(ledger)
    ledger.close()
    store.close()

    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(
            target=_process_claim, args=(str(database), barrier, results, f"request-{i}")
        )
        for i in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
    assert all(process.exitcode == 0 for process in processes)
    outcomes = [results.get(timeout=5)[0] for _ in processes]

    reopened_store = SqliteLedgerStore(database)
    reopened = Ledger(reopened_store, writer_id="b00-process-test")
    assert outcomes.count("CLAIMED") == 1
    assert outcomes.count("DENIED") == 1
    assert sum(row.event.kind == "ADMISSION_SEND_CLAIMED" for row in reopened.read()) == 1
    assert reopened.verify_chain() == reopened.head_hash()
    reopened.close()
    reopened_store.close()


def test_revocation_committing_between_validation_and_claim_blocks_the_sink(tmp_path) -> None:
    database = tmp_path / "canonical-ledger.db"
    store = SqliteLedgerStore(database)
    ledger = Ledger(store, writer_id="b00-revocation-race")
    _seed(ledger)
    ledger.close()
    store.close()

    context = multiprocessing.get_context("spawn")
    claim_ready = context.Event()
    continue_claim = context.Event()
    results = context.Queue()
    sender = context.Process(
        target=_process_claim_until_compare,
        args=(str(database), claim_ready, continue_claim, results),
    )
    revoker = context.Process(
        target=_process_revoke_after_claim_validation,
        args=(str(database), claim_ready, continue_claim, results),
    )
    sender.start()
    revoker.start()
    sender.join(timeout=20)
    revoker.join(timeout=20)

    assert sender.exitcode == 0
    assert revoker.exitcode == 0
    outcomes = [results.get(timeout=5) for _ in range(2)]
    assert ("REVOKED",) in outcomes
    assert ("REVOKED", 0) in outcomes

    reopened_store = SqliteLedgerStore(database)
    reopened = Ledger(reopened_store, writer_id="b00-revocation-race")
    assert not any(row.event.kind == "ADMISSION_SEND_CLAIMED" for row in reopened.read())
    assert reopened.read()[-1].event.kind == "ADMISSION_REVOKED"
    assert reopened.verify_chain() == reopened.head_hash()
    reopened.close()
    reopened_store.close()
