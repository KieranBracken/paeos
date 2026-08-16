"""B0.9 acceptance tests for the Seal Authority + keystore (PAEOS-7.6 §10 / FR-7).

Covers: refuse without verdict/adversary/verified-chain; signature verifies; idempotency
(same content ⇒ same seal_hash, committed once) incl. across a simulated restart; supersedes
(compensation, not mutation); persistent keystore load/create.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from kernel.keystore import load_or_create_signing_key
from kernel.ledger import Event, InMemoryLedgerStore, Ledger, tamper
from kernel.seal import SEAL_EVENT_KIND, SealAuthority, SealRefused
from nacl.signing import SigningKey

_ART = "a" * 64
_VERDICT = "v" * 64
_ADV = "d" * 64


def _authority(ledger: Ledger | None = None) -> tuple[SealAuthority, Ledger]:
    if ledger is None:
        ledger = Ledger(InMemoryLedgerStore())
    return SealAuthority(SigningKey.generate(), ledger), ledger


def _seal_count(ledger: Ledger) -> int:
    return sum(1 for row in ledger.read() if row.event.kind == SEAL_EVENT_KIND)


# ---- refusal (G-Seal preconditions) ---------------------------------------


def test_seal_refused_without_verdict() -> None:
    authority, _ = _authority()
    with pytest.raises(SealRefused):
        authority.seal(
            goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=None, adversary_ref=_ADV
        )


def test_seal_refused_without_adversary_review() -> None:
    authority, _ = _authority()
    with pytest.raises(SealRefused):
        authority.seal(
            goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=None
        )


def test_seal_refused_on_corrupted_chain() -> None:
    store = InMemoryLedgerStore()
    ledger = Ledger(store)
    ledger.append(Event(1, "noise", {"x": 1}))
    store._rows[0] = tamper(store._rows[0], row_hash="0" * 64)  # break the chain
    authority = SealAuthority(SigningKey.generate(), ledger)
    with pytest.raises(SealRefused):
        authority.seal(
            goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
        )


# ---- happy path + signature -----------------------------------------------


def test_seal_commits_and_verifies() -> None:
    authority, ledger = _authority()
    record = authority.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    assert authority.verify_seal(record) is True
    assert _seal_count(ledger) == 1
    assert record.verdict_ref == _VERDICT
    assert record.adversary_ref == _ADV


def test_tampered_seal_does_not_verify() -> None:
    authority, _ = _authority()
    record = authority.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    assert authority.verify_seal(replace(record, verdict_ref="f" * 64)) is False  # hash mismatch
    assert authority.verify_seal(replace(record, attestation="00" * 64)) is False  # bad sig


def test_seal_from_another_key_does_not_verify() -> None:
    _, ledger = _authority()
    a1 = SealAuthority(SigningKey.generate(), ledger)
    record = a1.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    other = SealAuthority(SigningKey.generate(), Ledger(InMemoryLedgerStore()))
    assert other.verify_seal(record) is False  # different kernel key


# ---- idempotency (FR-7) ----------------------------------------------------


def test_resealing_identical_content_is_idempotent() -> None:
    authority, ledger = _authority()
    first = authority.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    second = authority.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    assert first == second  # same record
    assert first.seal_hash == second.seal_hash
    assert _seal_count(ledger) == 1  # committed once


def test_idempotency_survives_restart() -> None:
    store = InMemoryLedgerStore()
    ledger = Ledger(store)
    a1 = SealAuthority(SigningKey.generate(), ledger)
    first = a1.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    # a new authority over the same ledger rebuilds its index from committed events (D1)
    a2 = SealAuthority(SigningKey.generate(), ledger)
    again = a2.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    assert again.seal_hash == first.seal_hash  # dedup rebuilt from the ledger
    assert _seal_count(ledger) == 1  # still committed once


def test_distinct_content_seals_separately() -> None:
    authority, ledger = _authority()
    authority.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    authority.seal(
        goal_id="g", run_id="r", artifact_bundle="b" * 64, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    assert _seal_count(ledger) == 2


def test_supersedes_is_a_new_seal_not_a_mutation() -> None:
    authority, ledger = _authority()
    original = authority.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    fixed = authority.seal(
        goal_id="g", run_id="r", artifact_bundle="b" * 64, verdict_ref=_VERDICT,
        adversary_ref=_ADV, supersedes=original.seal_hash,
    )
    assert fixed.supersedes == original.seal_hash
    assert authority.verify_seal(original) is True  # original remains valid + addressable (SI-7)
    assert _seal_count(ledger) == 2


# ---- persistent keystore --------------------------------------------------


def test_keystore_creates_then_loads_same_key(tmp_path: Path) -> None:
    path = tmp_path / "keys" / "kernel_ed25519.key"
    first = load_or_create_signing_key(path)
    assert path.exists()
    second = load_or_create_signing_key(path)  # reload
    assert bytes(first) == bytes(second)  # same seed → same key


def test_keystore_rejects_malformed_key_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.key"
    path.write_bytes(b"too short")
    with pytest.raises(ValueError):
        load_or_create_signing_key(path)


def test_keystore_key_signs_verifiable_seals(tmp_path: Path) -> None:
    key = load_or_create_signing_key(tmp_path / "k.key")
    authority = SealAuthority(key, Ledger(InMemoryLedgerStore()))
    record = authority.seal(
        goal_id="g", run_id="r", artifact_bundle=_ART, verdict_ref=_VERDICT, adversary_ref=_ADV
    )
    assert authority.verify_seal(record) is True
