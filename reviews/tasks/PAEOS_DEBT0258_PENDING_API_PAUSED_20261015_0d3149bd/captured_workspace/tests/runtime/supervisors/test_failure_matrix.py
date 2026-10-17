"""Quota, ambiguity, injection, and drift recovery matrix."""

import pytest
from runtime.supervisors.coordinator import RecoveryAction, SupervisorRecoveryCoordinator


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        ("NEW", RecoveryAction.RETRY_NEW_ATTEMPT),
        ("PREPARED", RecoveryAction.RETRY_NEW_ATTEMPT),
        ("CLAIMED", RecoveryAction.RETRY_NEW_ATTEMPT),
        ("RESPONDED", RecoveryAction.HALT),
        ("CONSUMED", RecoveryAction.HALT),
    ],
)
def test_quota_loss_only_allows_one_preacceptance_retry(phase, expected) -> None:
    coordinator = SupervisorRecoveryCoordinator()
    first = coordinator.decide("tx-1", phase=phase, failure="quota exhausted")
    assert first.action is expected
    second = coordinator.decide("tx-1", phase=phase, failure="quota exhausted")
    if phase in {"NEW", "PREPARED", "CLAIMED"}:
        assert second.action is RecoveryAction.HALT
        assert second.reason_code == "NO_SAFE_RETRY"


def test_accepted_or_ambiguous_side_effect_never_retries() -> None:
    coordinator = SupervisorRecoveryCoordinator()
    for phase in ("NEW", "PREPARED", "CLAIMED", "RESPONDED"):
        decision = coordinator.decide(
            f"tx-{phase}",
            phase=phase,
            failure="connection lost",
            side_effect_accepted=True,
        )
        assert decision.action is RecoveryAction.RECONCILIATION_REQUIRED
        ambiguous = coordinator.decide(
            f"tx-{phase}-ambiguous",
            phase=phase,
            failure="partial stream",
            side_effect_ambiguous=True,
        )
        assert ambiguous.action is RecoveryAction.RECONCILIATION_REQUIRED


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"prompt_injection": True}, "PROMPT_INJECTION"),
        ({"receipt_conflict": True}, "RECEIPT_CONFLICT"),
        ({"policy_expired": True}, "POLICY_EXPIRED"),
        ({"response_valid": False}, "INVALID_RESPONSE"),
        ({"stale_checkpoint": True}, "STALE_CHECKPOINT"),
    ],
)
def test_invalid_or_drifted_supervisor_state_quarantines_or_halts(kwargs, reason) -> None:
    coordinator = SupervisorRecoveryCoordinator()
    decision = coordinator.decide(
        "tx-1",
        phase="NEW",
        failure="raw failure bytes",
        **kwargs,
    )
    assert decision.reason_code == reason
    if reason == "STALE_CHECKPOINT":
        assert decision.action is RecoveryAction.HALT
    else:
        assert decision.action is RecoveryAction.QUARANTINE
    assert len(decision.raw_failure_hash) == 64


def test_recovery_has_no_sleep_or_adapter_dispatch_side_effects() -> None:
    coordinator = SupervisorRecoveryCoordinator(max_preacceptance_retries=2)
    decisions = [
        coordinator.decide("tx-1", phase="NEW", failure="quota"),
        coordinator.decide("tx-1", phase="NEW", failure="quota"),
        coordinator.decide("tx-1", phase="NEW", failure="quota"),
    ]
    assert [item.action for item in decisions] == [
        RecoveryAction.RETRY_NEW_ATTEMPT,
        RecoveryAction.RETRY_NEW_ATTEMPT,
        RecoveryAction.HALT,
    ]
