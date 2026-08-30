"""Serialized ledger commit seam for control-plane transaction commands."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from kernel.ledger import ForkRejected, Ledger, LedgerRow, compute_row_hash

from runtime.control_plane.events import (
    INITIAL_TRANSACTION_DIGEST,
    TransactionCommand,
    transaction_event,
)
from runtime.control_plane.projection import ProjectionError, project_row, rebuild_projection
from runtime.control_plane.sqlite_projection import SqliteControlPlaneProjection
from runtime.integrations.bridge_protocol import (
    TransactionEvent,
    TransactionRecord,
    TransactionState,
)


class StaleComparison(RuntimeError):
    """The caller's expected ledger or projected transaction value is stale."""


class StaleFence(RuntimeError):
    """The caller's fencing token is not newer than the committed token."""


@dataclass(frozen=True, slots=True)
class CommitReceipt:
    request_id: str
    transaction_key: str
    ledger_seq: int
    ledger_head: str
    projected_digest: str
    fencing_token: int


class TransactionCoordinator:
    """The only application seam allowed to append control-plane transaction events."""

    def __init__(self, ledger: Ledger, projection: SqliteControlPlaneProjection) -> None:
        self._ledger = ledger
        self._projection = projection
        self._commit_lock = threading.Lock()

    def prepare(
        self,
        record: TransactionRecord,
        *,
        expected_ledger_head: str,
    ) -> CommitReceipt:
        if record.state is not TransactionState.NEW:
            raise StaleComparison("prepare requires a NEW transaction record")
        command = TransactionCommand(
            request_id=record.request_id,
            transaction_key=record.transaction_key,
            run_id=record.run_id,
            stage_id=record.stage_id,
            payload_hash=record.payload_hash,
            event=TransactionEvent.PREPARE,
            actor="execution-layer",
            at=datetime.now(UTC).isoformat(),
            expected_prior_digest=INITIAL_TRANSACTION_DIGEST,
            fencing_token=1,
        )
        return self.apply(command, expected_ledger_head=expected_ledger_head)

    def apply(
        self,
        command: TransactionCommand,
        *,
        expected_ledger_head: str,
    ) -> CommitReceipt:
        with self._commit_lock:
            return self._apply_locked(command, expected_ledger_head=expected_ledger_head)

    def recover_projection(self) -> str:
        with self._commit_lock:
            head = self._ledger.verify_chain()
            rows = self._ledger.read()
            self._projection.replace_from_verified_ledger(rows, head)
            return head

    def _apply_locked(
        self,
        command: TransactionCommand,
        *,
        expected_ledger_head: str,
    ) -> CommitReceipt:
        actual_head = self._ledger.verify_chain()
        if actual_head != expected_ledger_head:
            raise StaleComparison("expected ledger head does not match committed ledger")
        rows = self._ledger.read()
        projections = rebuild_projection(rows)
        current = projections.get(command.request_id)
        if current is not None:
            if command.fencing_token <= current.fencing_token:
                raise StaleFence("fencing token is reused or stale")
            if command.expected_prior_digest != current.digest:
                raise StaleComparison("expected transaction digest is stale")
        else:
            if command.event is not TransactionEvent.PREPARE:
                raise StaleComparison("transaction must be prepared before this event")
            if command.expected_prior_digest != INITIAL_TRANSACTION_DIGEST:
                raise StaleComparison("new transaction has a non-empty expected digest")
            if command.fencing_token != 1:
                raise StaleFence("first transaction fence must be 1")

        next_seq = rows[-1].seq + 1 if rows else 1
        planned_timestamp = command.at
        planned_event = transaction_event(command)
        planned_row = LedgerRow(
            seq=next_seq,
            timestamp=planned_timestamp,
            event=planned_event,
            prev_hash=actual_head,
            row_hash=compute_row_hash(actual_head, next_seq, planned_timestamp, planned_event),
        )
        try:
            planned = project_row(current, planned_row)
        except ProjectionError as exc:
            if "fencing_token" in str(exc):
                raise StaleFence(str(exc)) from exc
            raise StaleComparison(str(exc)) from exc

        try:
            committed_seq = self._ledger.append(planned_event)
        except ForkRejected as exc:
            raise StaleComparison("ledger head advanced before append") from exc
        committed_row = self._ledger.read(committed_seq, committed_seq + 1)[0]
        committed_head = self._ledger.head_hash()
        try:
            self._projection.apply_committed(
                committed_row,
                verified_prior_head=actual_head,
            )
            committed = self._projection.get(
                command.request_id,
                verified_ledger_head=committed_head,
            )
        except ProjectionError:
            # The append is durable; rebuild the replaceable cache exactly once rather than
            # appending a second event or replaying the external side effect.
            self._projection.replace_from_verified_ledger(
                self._ledger.read(),
                committed_head,
            )
            committed = rebuild_projection(self._ledger.read())[command.request_id]
        if committed.record != planned.record:
            raise ProjectionError("committed projection differs from validated command")
        return CommitReceipt(
            request_id=committed.record.request_id,
            transaction_key=committed.record.transaction_key,
            ledger_seq=committed.ledger_seq,
            ledger_head=committed_head,
            projected_digest=committed.digest,
            fencing_token=committed.fencing_token,
        )
