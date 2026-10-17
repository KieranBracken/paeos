"""Capability broker — the reference monitor (PAEOS-7.6 §7 / 7.5 T1, A-6).

Task B0.8 (PAEOS-8 §10). A `CapabilityToken` is the only authority an agent ever holds; this
module is the kernel component that **mints** them (Ed25519-signed, unforgeable) and
**verifies** them at every privileged call. The `CapabilityToken` *type* is in `kernel/types.py`
(ratified B0.4); this is its behaviour.

The reference monitor enforces the T1/A-6 invariants:
  * **Unforgeable** — the token is an Ed25519 signature over its own `bound_to`, `operations`,
    and TTL. Tampering any field breaks the signature (§3 pins Ed25519; A-5 keeps the signing
    key in the kernel — agents never hold it).
  * **Bound & immutable** — a *genuine* token is usable only for exactly the `(goal_id, run_id,
    stage, role, session)` it was minted for. A BUILDER token cannot be used for a VERIFIER
    action (SI-3, no role relabeling).
  * **TTL'd** — a token is valid only within `[issued_seq, expires_seq]`; stale-token reuse is
    denied (A-6).
  * **Least authority** — any operation not in the explicit `operations` allow-list is denied
    (deny-by-default, FR-4). No self-grant, no escalation.

Minting is kernel-only: an agent has no broker and no key, so it cannot mint or relabel.
"""

from __future__ import annotations

import json

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from kernel.types import CapabilityBinding, CapabilityToken, GoalId, Role, RunId, StageId, Ts

__all__ = [
    "BindingMismatch",
    "CapabilityBroker",
    "CapabilityError",
    "CapabilityVerifier",
    "ExpiredToken",
    "InvalidToken",
    "OperationNotPermitted",
]


# ---- errors ---------------------------------------------------------------


class CapabilityError(Exception):
    """Base for capability faults. Every one is a *denial* (deny-by-default, FR-4)."""


class InvalidToken(CapabilityError):
    """The token's signature does not verify — forged or tampered (T1)."""


class ExpiredToken(CapabilityError):
    """The token is outside its TTL window; stale-token reuse denied (A-6)."""


class BindingMismatch(CapabilityError):
    """A genuine token used outside its `bound_to` — wrong goal/run/stage/role/session (SI-3)."""


class OperationNotPermitted(CapabilityError):
    """The requested operation is not in the token's allow-list; escalation denied."""


# ---- canonical signing payload -------------------------------------------


def _payload(
    binding: CapabilityBinding,
    operations: tuple[str, ...],
    issued_seq: Ts,
    expires_seq: Ts,
) -> bytes:
    """Deterministic bytes the signature covers. Any change to any field changes these bytes,
    so a tampered token fails verification."""
    obj = {
        "goal_id": binding.goal_id,
        "run_id": binding.run_id,
        "stage": binding.stage.value,
        "role": binding.role.value,
        "session": binding.session,
        "mission_execution_digest": binding.mission_execution_digest,
        "operations": list(operations),
        "issued_seq": issued_seq,
        "expires_seq": expires_seq,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


# ---- the broker -----------------------------------------------------------


class CapabilityVerifier:
    """Verify capabilities with a public key only; this object cannot mint authority."""

    def __init__(self, verify_key: VerifyKey | bytes) -> None:
        self._verify_key = verify_key if isinstance(verify_key, VerifyKey) else VerifyKey(verify_key)

    def verify(
        self,
        token: CapabilityToken,
        *,
        goal_id: GoalId,
        run_id: RunId,
        stage: StageId,
        role: Role,
        operation: str | None,
        current_seq: Ts,
        session: str | None = None,
        mission_execution_digest: str | None = None,
    ) -> None:
        try:
            self._verify_key.verify(
                _payload(token.bound_to, token.operations, token.issued_seq, token.expires_seq),
                bytes.fromhex(token.token),
            )
        except (BadSignatureError, ValueError) as exc:
            raise InvalidToken(f"token signature does not verify: {exc}") from exc
        if not (token.issued_seq <= current_seq <= token.expires_seq):
            raise ExpiredToken(
                f"current_seq {current_seq} outside TTL "
                f"[{token.issued_seq}, {token.expires_seq}]"
            )
        binding = token.bound_to
        if (
            binding.goal_id != goal_id
            or binding.run_id != run_id
            or binding.stage is not stage
            or binding.role is not role
        ):
            raise BindingMismatch("capability identity differs from its execution request")
        if session is not None and binding.session != session:
            raise BindingMismatch("capability session differs from its execution request")
        if (
            mission_execution_digest is not None
            and binding.mission_execution_digest != mission_execution_digest
        ):
            raise BindingMismatch("capability is not bound to the current mission execution context")
        if operation is not None and operation not in token.operations:
            raise OperationNotPermitted(
                f"operation {operation!r} not in allow-list {token.operations}"
            )


class CapabilityBroker:
    """Mints and verifies capability tokens. Holds the kernel signing key (A-5); an agent has
    neither the broker nor the key, so it can neither mint nor relabel a token."""

    def __init__(self, signing_key: SigningKey | None = None) -> None:
        self._signing_key: SigningKey = (
            signing_key if signing_key is not None else SigningKey.generate()
        )
        self._verify_key: VerifyKey = self._signing_key.verify_key
        self._verifier = CapabilityVerifier(self._verify_key)

    def mint(
        self,
        *,
        goal_id: GoalId,
        run_id: RunId,
        stage: StageId,
        role: Role,
        session: str,
        operations: tuple[str, ...],
        issued_seq: Ts,
        expires_seq: Ts,
        mission_execution_digest: str | None = None,
    ) -> CapabilityToken:
        """Kernel-only: mint a signed token bound to (goal, run, stage, role, session)."""
        if expires_seq < issued_seq:
            raise ValueError(f"expires_seq ({expires_seq}) precedes issued_seq ({issued_seq})")
        binding = CapabilityBinding(
            goal_id=goal_id,
            run_id=run_id,
            stage=stage,
            role=role,
            session=session,
            mission_execution_digest=mission_execution_digest,
        )
        signature = self._signing_key.sign(_payload(binding, operations, issued_seq, expires_seq))
        return CapabilityToken(
            token=signature.signature.hex(),
            bound_to=binding,
            operations=operations,
            issued_seq=issued_seq,
            expires_seq=expires_seq,
        )

    def verify(
        self,
        token: CapabilityToken,
        *,
        goal_id: GoalId,
        run_id: RunId,
        stage: StageId,
        role: Role,
        operation: str,
        current_seq: Ts,
        session: str | None = None,
        mission_execution_digest: str | None = None,
    ) -> None:
        """Reference-monitor check. Raises the specific `CapabilityError` on any failure; returns
        None only if the token is genuine, in-TTL, bound to exactly the expected identity, and
        authorises `operation`. Order: signature → TTL → binding → allow-list."""
        self._verifier.verify(
            token,
            goal_id=goal_id,
            run_id=run_id,
            stage=stage,
            role=role,
            operation=operation,
            current_seq=current_seq,
            session=session,
            mission_execution_digest=mission_execution_digest,
        )

    def verifier(self) -> CapabilityVerifier:
        """Return the public-only verifier for independently checking issued capabilities."""
        return self._verifier

    @property
    def verify_key_hex(self) -> str:
        """The public verify key (hex). Safe to share; the signing key never leaves the broker."""
        return bytes(self._verify_key).hex()
