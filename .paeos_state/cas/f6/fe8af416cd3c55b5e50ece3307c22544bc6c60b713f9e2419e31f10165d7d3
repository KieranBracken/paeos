"""Seal Authority — the idempotent finalization (PAEOS-7.6 §10 / 7 §4.3 G-Seal / FR-7).

Task B0.9 (PAEOS-8 §10). Sealing is what makes an artifact *canonical*. The Seal Authority:

  * **Refuses without the G-Seal preconditions** (§10 invariant): a passing verdict, a resolved
    adversary review, AND a verified ledger chain. Miss any ⇒ `SealRefused` (deny-by-default).
  * **Signs** the seal with the kernel Ed25519 key (A-5; from `kernel/keystore.py`), so a seal is
    verifiable and unforgeable.
  * **Is idempotent** (FR-7): sealing the same content twice yields the same `SealRecord`,
    committed to the ledger exactly once. The idempotency index is rebuilt from the ledger on
    construction (crash-only, D1).
  * **Never mutates** a seal: a later defect produces a *new* seal with `supersedes` set
    (compensation, PAEOS-7 §4.5 / SI-7).

`seal_hash = sha256(artifact_bundle + verdict_ref + adversary_ref + ledger_head)`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from kernel.ledger import ChainCorruption, Event, JsonValue, Ledger
from kernel.types import GoalId, Hash, RunId, Sig, Ts

__all__ = [
    "SEAL_EVENT_KIND",
    "SealAuthority",
    "SealError",
    "SealRecord",
    "SealRefused",
    "compute_seal_hash",
]

SEAL_EVENT_KIND = "SealCommitted"


class SealError(Exception):
    """Base for seal faults."""


class SealRefused(SealError):
    """The G-Seal preconditions are not met (no verdict / no adversary / unverified chain)."""


@dataclass(frozen=True, slots=True)
class SealRecord:
    """The canonical, kernel-signed finalization of an artifact (PAEOS-7.6 §10)."""

    seal_hash: Hash
    goal_id: GoalId
    run_id: RunId
    artifact_bundle: Hash
    verdict_ref: Hash
    adversary_ref: Hash
    ledger_head: Ts
    attestation: Sig
    promote_to: str | None = None
    supersedes: Hash | None = None


def compute_seal_hash(
    artifact_bundle: Hash, verdict_ref: Hash, adversary_ref: Hash, ledger_head: Ts
) -> str:
    """The seal's content hash (§10 formula), over a canonical JSON of the four bound fields."""
    body = json.dumps(
        {
            "artifact_bundle": artifact_bundle,
            "verdict_ref": verdict_ref,
            "adversary_ref": adversary_ref,
            "ledger_head": ledger_head,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(body.encode("ascii")).hexdigest()


def _idempotency_key(
    goal_id: GoalId, run_id: RunId, artifact_bundle: Hash, verdict_ref: Hash, adversary_ref: Hash
) -> str:
    """Identifies "the same content" for idempotency — everything except the ledger position."""
    body = json.dumps(
        [goal_id, run_id, artifact_bundle, verdict_ref, adversary_ref],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(body.encode("ascii")).hexdigest()


class SealAuthority:
    """Mints and verifies seals over a single-writer ledger. Holds the kernel signing key (A-5)."""

    def __init__(self, signing_key: SigningKey, ledger: Ledger) -> None:
        self._signing_key = signing_key
        self._verify_key: VerifyKey = signing_key.verify_key
        self._ledger = ledger
        self._index: dict[str, SealRecord] = {}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Reconstruct the idempotency index from committed seal events (crash-only, D1)."""
        for row in self._ledger.read():
            if row.event.kind != SEAL_EVENT_KIND:
                continue
            record = _record_from_payload(row.event.payload)
            self._index[_idempotency_key(
                record.goal_id, record.run_id, record.artifact_bundle,
                record.verdict_ref, record.adversary_ref,
            )] = record

    def seal(
        self,
        *,
        goal_id: GoalId,
        run_id: RunId,
        artifact_bundle: Hash,
        verdict_ref: Hash | None,
        adversary_ref: Hash | None,
        promote_to: str | None = None,
        supersedes: Hash | None = None,
    ) -> SealRecord:
        """Seal `artifact_bundle`. Idempotent: the same content returns the same record, committed
        once. Raises `SealRefused` unless a passing verdict, a resolved adversary review, and a
        verified ledger chain are all present (G-Seal)."""
        # --- refuse without the G-Seal preconditions (§10 invariant) ---
        if not verdict_ref:
            raise SealRefused("no passing G-Court verdict")
        if not adversary_ref:
            raise SealRefused("no resolved G-Adversary review")
        try:
            self._ledger.verify_chain()  # G-Seal requires a verified chain
        except ChainCorruption as exc:
            raise SealRefused(f"ledger chain does not verify: {exc}") from exc

        key = _idempotency_key(goal_id, run_id, artifact_bundle, verdict_ref, adversary_ref)
        existing = self._index.get(key)
        if existing is not None:
            return existing  # idempotent: same record, no second commit

        head = self._ledger.head()
        ledger_head = head.seq if head is not None else 0
        seal_hash = compute_seal_hash(artifact_bundle, verdict_ref, adversary_ref, ledger_head)
        attestation = self._signing_key.sign(seal_hash.encode("ascii")).signature.hex()
        record = SealRecord(
            seal_hash=seal_hash,
            goal_id=goal_id,
            run_id=run_id,
            artifact_bundle=artifact_bundle,
            verdict_ref=verdict_ref,
            adversary_ref=adversary_ref,
            ledger_head=ledger_head,
            attestation=attestation,
            promote_to=promote_to,
            supersedes=supersedes,
        )
        self._ledger.append(Event(schema_ver=1, kind=SEAL_EVENT_KIND, payload=_payload(record)))
        self._index[key] = record
        return record

    def verify_seal(self, record: SealRecord) -> bool:
        """True iff the seal's hash recomputes and its attestation verifies under the kernel key."""
        expected = compute_seal_hash(
            record.artifact_bundle, record.verdict_ref, record.adversary_ref, record.ledger_head
        )
        if expected != record.seal_hash:
            return False
        try:
            self._verify_key.verify(
                record.seal_hash.encode("ascii"), bytes.fromhex(record.attestation)
            )
        except (BadSignatureError, ValueError):
            return False
        return True


def _payload(record: SealRecord) -> dict[str, JsonValue]:
    return {
        "seal_hash": record.seal_hash,
        "goal_id": record.goal_id,
        "run_id": record.run_id,
        "artifact_bundle": record.artifact_bundle,
        "verdict_ref": record.verdict_ref,
        "adversary_ref": record.adversary_ref,
        "ledger_head": record.ledger_head,
        "attestation": record.attestation,
        "promote_to": record.promote_to,
        "supersedes": record.supersedes,
    }


def _record_from_payload(payload: Mapping[str, JsonValue]) -> SealRecord:
    return SealRecord(
        seal_hash=_s(payload["seal_hash"]),
        goal_id=_s(payload["goal_id"]),
        run_id=_s(payload["run_id"]),
        artifact_bundle=_s(payload["artifact_bundle"]),
        verdict_ref=_s(payload["verdict_ref"]),
        adversary_ref=_s(payload["adversary_ref"]),
        ledger_head=_i(payload["ledger_head"]),
        attestation=_s(payload["attestation"]),
        promote_to=_opt_s(payload.get("promote_to")),
        supersedes=_opt_s(payload.get("supersedes")),
    )


def _s(value: JsonValue) -> str:
    assert isinstance(value, str)
    return value


def _i(value: JsonValue) -> int:
    assert isinstance(value, int)
    return value


def _opt_s(value: JsonValue | None) -> str | None:
    assert value is None or isinstance(value, str)
    return value
