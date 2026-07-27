"""B0.7 acceptance tests for evidence binding + reproduction (PAEOS-7.6 §6 / 7.5 T2).

Covers: stale-replay rejection (artifact_hash mismatch), deterministic kernel re-run reproduces
the claimed result, the T2 forgery (a forged result is caught by the kernel re-run), and
non-deterministic two-independent-producer corroboration. Uses `echo`/`false` as portable
reproducible commands (no shell).
"""

from __future__ import annotations

import pytest
from kernel.evidence import (
    Determinism,
    Evidence,
    EvidenceKind,
    EvidenceProducer,
    NotReproducible,
    ReproductionMismatch,
    StaleEvidence,
    TwoProducerViolation,
    reproduce,
    verify_binding,
    verify_deterministic,
    verify_two_producers,
)
from kernel.ledger import JsonValue
from kernel.types import Role

_ART = "a" * 64


def _ev(
    *,
    artifact_hash: str = _ART,
    command: str | None = "echo real",
    result: JsonValue = None,
    determinism: Determinism = Determinism.DETERMINISTIC,
    session: str = "s1",
    claim_id: str = "c1",
    role: Role = Role.BUILDER,
) -> Evidence:
    if result is None:
        result = {"exit_code": 0, "stdout": "real\n"}
    return Evidence(
        hash="e" * 64,
        kind=EvidenceKind.TEST,
        claim_id=claim_id,
        artifact_hash=artifact_hash,
        environment_hash="env" + "0" * 61,
        reproducible_command=command,
        producer=EvidenceProducer(role=role, session=session),
        determinism=determinism,
        result=result,
        attestation="kernel-sig",
    )


# ---- binding / stale-replay (SI-4) ----------------------------------------


def test_binding_accepts_matching_artifact() -> None:
    verify_binding(_ev(artifact_hash=_ART), _ART)  # no raise


def test_binding_rejects_stale_evidence() -> None:
    stale = _ev(artifact_hash="b" * 64)  # bound to a different artifact
    with pytest.raises(StaleEvidence):
        verify_binding(stale, _ART)


# ---- deterministic reproduction (T2) --------------------------------------


def test_reproduce_reruns_command() -> None:
    fresh = reproduce(_ev(command="echo real"))
    assert fresh == {"exit_code": 0, "stdout": "real\n"}


def test_verify_deterministic_passes_when_result_matches() -> None:
    ev = _ev(command="echo real", result={"exit_code": 0, "stdout": "real\n"})
    verify_deterministic(ev, _ART)


def test_forged_result_is_caught_by_kernel_rerun() -> None:
    # T2: the agent claims a passing result the command does not actually produce.
    forged = _ev(command="echo real", result={"exit_code": 0, "stdout": "FORGED\n"})
    with pytest.raises(ReproductionMismatch):
        verify_deterministic(forged, _ART)


def test_forged_exit_code_is_caught() -> None:
    # `false` exits 1; claiming exit 0 is a forgery the re-run catches.
    forged = _ev(command="false", result={"exit_code": 0, "stdout": ""})
    with pytest.raises(ReproductionMismatch):
        verify_deterministic(forged, _ART)


def test_deterministic_check_still_enforces_binding_first() -> None:
    forged = _ev(artifact_hash="c" * 64, command="echo real")
    with pytest.raises(StaleEvidence):
        verify_deterministic(forged, _ART)


def test_reproduce_rejects_nondeterministic() -> None:
    with pytest.raises(NotReproducible):
        reproduce(_ev(determinism=Determinism.NONDETERMINISTIC, command="echo x"))


def test_reproduce_rejects_missing_command() -> None:
    with pytest.raises(NotReproducible):
        reproduce(_ev(command=None))


def test_reproduce_rejects_unrunnable_command() -> None:
    with pytest.raises(NotReproducible):
        reproduce(_ev(command="this_command_definitely_does_not_exist_xyz123"))


# ---- non-deterministic: two independent producers -------------------------


def test_two_independent_producers_agree() -> None:
    a = _ev(determinism=Determinism.NONDETERMINISTIC, session="builder", result=100)
    b = _ev(determinism=Determinism.NONDETERMINISTIC, session="court", result=100)
    verify_two_producers(a, b)  # no raise


def test_two_producers_within_tolerance() -> None:
    a = _ev(determinism=Determinism.NONDETERMINISTIC, session="builder", result=100.0)
    b = _ev(determinism=Determinism.NONDETERMINISTIC, session="court", result=101.0)
    verify_two_producers(a, b, tolerance=2.0)  # within tolerance
    with pytest.raises(TwoProducerViolation):
        verify_two_producers(a, b, tolerance=0.5)  # beyond tolerance


def test_same_session_is_not_independent() -> None:
    a = _ev(determinism=Determinism.NONDETERMINISTIC, session="same", result=1)
    b = _ev(determinism=Determinism.NONDETERMINISTIC, session="same", result=1)
    with pytest.raises(TwoProducerViolation):
        verify_two_producers(a, b)


def test_two_producers_must_share_claim_and_artifact() -> None:
    a = _ev(determinism=Determinism.NONDETERMINISTIC, session="b", claim_id="c1", result=1)
    b = _ev(determinism=Determinism.NONDETERMINISTIC, session="c", claim_id="c2", result=1)
    with pytest.raises(TwoProducerViolation):
        verify_two_producers(a, b)


def test_bool_results_compared_exactly_not_numerically() -> None:
    # bool is an int subclass; True/False must not be treated as 1/0 within tolerance.
    a = _ev(determinism=Determinism.NONDETERMINISTIC, session="b", result=True)
    b = _ev(determinism=Determinism.NONDETERMINISTIC, session="c", result=False)
    with pytest.raises(TwoProducerViolation):
        verify_two_producers(a, b, tolerance=5.0)
