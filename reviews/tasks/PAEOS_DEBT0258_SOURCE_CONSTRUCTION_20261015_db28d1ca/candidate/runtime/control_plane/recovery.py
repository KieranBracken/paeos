"""Compare-before-commit application of watchdog recovery proposals."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from kernel.ledger import Ledger

from runtime.control_plane.coordinator import StaleComparison, TransactionCoordinator
from runtime.control_plane.events import (
    SideEffectCertainty,
    TransactionCommand,
    side_effect_retry_eligible,
)
from runtime.control_plane.projection import ProjectedTransaction
from runtime.control_plane.sqlite_projection import SqliteControlPlaneProjection
from runtime.control_plane.watchdog import RecoveryAction, WatchdogDecision
from runtime.integrations.bridge_protocol import TransactionEvent, TransactionState


@dataclass(frozen=True, slots=True)
class RecoveryReceipt:
    decision_hash: str
    action: RecoveryAction
    ledger_seq: int | None
    ledger_head: str
    resulting_state: TransactionState
    new_fencing_token: int | None


class RecoveryController:
    """Apply only still-current, side-effect-safe watchdog decisions."""

    def __init__(
        self,
        coordinator: TransactionCoordinator,
        ledger: Ledger,
        projection: SqliteControlPlaneProjection,
    ) -> None:
        self._coordinator = coordinator
        self._ledger = ledger
        self._projection = projection

    def apply(self, decision: WatchdogDecision) -> RecoveryReceipt:
        if not isinstance(decision, WatchdogDecision):
            raise TypeError("decision must be a WatchdogDecision")
        current_head = self._ledger.verify_chain()
        if not decision.observed_ledger_head:
            raise StaleComparison("decision has no observed ledger head")
        if decision.observed_ledger_head != current_head:
            raise StaleComparison("decision observed ledger head is stale")
        try:
            current = (
                self._projection.get(
                    decision.request_id,
                    verified_ledger_head=current_head,
                )
                if decision.request_id
                else self._projection.find_by_transaction_key(
                    decision.transaction_key,
                    verified_ledger_head=current_head,
                )
            )
        except KeyError as exc:
            raise StaleComparison("decision transaction is not projected") from exc
        self._assert_identity(decision, current)
        if current.fencing_token != decision.fencing_token:
            raise StaleComparison("decision fencing token is stale")

        if decision.action in {
            RecoveryAction.NONE,
            RecoveryAction.DIAGNOSE,
            RecoveryAction.RESTART_STATELESS_ADAPTER,
            RecoveryAction.ROTATE_PROVIDER,
            RecoveryAction.HALT_SHARED_CONTROL_PLANE,
        }:
            return self._receipt_without_commit(decision, current, current_head)
        if decision.action is RecoveryAction.EXPIRE_PRE_SIDE_EFFECT_LEASE:
            return self._expire_lease(decision, current, current_head)
        if decision.action is RecoveryAction.REQUIRE_RECONCILIATION:
            return self._reconcile(decision, current, current_head)
        raise ValueError(f"unsupported recovery action: {decision.action.value}")

    @staticmethod
    def _assert_identity(decision: WatchdogDecision, current: ProjectedTransaction) -> None:
        if decision.transaction_key != current.record.transaction_key:
            raise StaleComparison("decision transaction key does not match projection")
        if decision.request_id and decision.request_id != current.record.request_id:
            raise StaleComparison("decision request id does not match projection")

    @staticmethod
    def _decision_hash(decision: WatchdogDecision) -> str:
        from runtime.integrations.bridge_protocol import canonical_json

        return hashlib.sha256(canonical_json(decision).encode("utf-8")).hexdigest()

    def _receipt_without_commit(
        self,
        decision: WatchdogDecision,
        current: ProjectedTransaction,
        current_head: str,
    ) -> RecoveryReceipt:
        return RecoveryReceipt(
            decision_hash=self._decision_hash(decision),
            action=decision.action,
            ledger_seq=current.ledger_seq,
            ledger_head=current_head,
            resulting_state=current.record.state,
            new_fencing_token=None,
        )

    def _expire_lease(
        self,
        decision: WatchdogDecision,
        current: ProjectedTransaction,
        current_head: str,
    ) -> RecoveryReceipt:
        if not side_effect_retry_eligible(decision.side_effect_certainty):
            raise ValueError("lease expiry requires proven pre-side-effect certainty")
        if current.record.state is not TransactionState.CLAIMED:
            raise StaleComparison("lease expiry requires a CLAIMED transaction")
        command = TransactionCommand(
            request_id=current.record.request_id,
            transaction_key=current.record.transaction_key,
            run_id=current.record.run_id,
            stage_id=current.record.stage_id,
            payload_hash=current.record.payload_hash,
            event=TransactionEvent.EXPIRE_LEASE,
            actor="overseer-recovery",
            at=datetime.now(UTC).isoformat(),
            expected_prior_digest=current.digest,
            fencing_token=current.fencing_token + 1,
        )
        committed = self._coordinator.apply(command, expected_ledger_head=current_head)
        projected = self._projection.get(
            current.record.request_id,
            verified_ledger_head=committed.ledger_head,
        )
        return RecoveryReceipt(
            decision_hash=self._decision_hash(decision),
            action=decision.action,
            ledger_seq=committed.ledger_seq,
            ledger_head=committed.ledger_head,
            resulting_state=projected.record.state,
            new_fencing_token=committed.fencing_token,
        )

    def _reconcile(
        self,
        decision: WatchdogDecision,
        current: ProjectedTransaction,
        current_head: str,
    ) -> RecoveryReceipt:
        if decision.side_effect_certainty not in {
            SideEffectCertainty.ACCEPTED,
            SideEffectCertainty.UNCERTAIN,
        }:
            raise ValueError("reconciliation requires accepted or uncertain certainty")
        if decision.idempotency_key is None:
            raise ValueError("reconciliation requires an idempotency key")
        evidence = decision.dispatch_evidence
        if evidence is None or not evidence.attempted:
            raise ValueError("reconciliation requires dispatch attempt evidence")
        command = TransactionCommand(
            request_id=current.record.request_id,
            transaction_key=current.record.transaction_key,
            run_id=current.record.run_id,
            stage_id=current.record.stage_id,
            payload_hash=current.record.payload_hash,
            event=TransactionEvent.SIDE_EFFECT_UNCERTAIN,
            actor="overseer-recovery",
            at=datetime.now(UTC).isoformat(),
            expected_prior_digest=current.digest,
            fencing_token=current.fencing_token + 1,
            last_side_effect=decision.idempotency_key,
            side_effect_certainty=decision.side_effect_certainty,
            idempotency_key=decision.idempotency_key,
            dispatch_evidence=evidence,
        )
        committed = self._coordinator.apply(command, expected_ledger_head=current_head)
        projected = self._projection.get(
            current.record.request_id,
            verified_ledger_head=committed.ledger_head,
        )
        return RecoveryReceipt(
            decision_hash=self._decision_hash(decision),
            action=decision.action,
            ledger_seq=committed.ledger_seq,
            ledger_head=committed.ledger_head,
            resulting_state=projected.record.state,
            new_fencing_token=committed.fencing_token,
        )


__all__ = ["RecoveryController", "RecoveryReceipt"]
