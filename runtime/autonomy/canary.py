"""Hidden mutation and canary fault-injection harness (Gate F Task 2)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

from kernel.cas import is_valid_hash
from kernel.ledger import Event


@dataclass(frozen=True, slots=True)
class CanaryManifest:
    canary_id: str
    version: str
    target_hash: str
    mutation_hash: str
    expected_failure_code: str
    installer_hash: str


@dataclass(frozen=True, slots=True)
class CanaryResult:
    canary_id: str
    installed: bool
    reached: bool
    killed: bool
    observed_failure_code: str | None
    evidence_refs: tuple[str, ...]


def adjudicate_canary(
    manifest: CanaryManifest, observations: Sequence[Event]
) -> CanaryResult:
    """Adjudicate one immutable canary transaction.

    Every observation must bind the complete verifier-owned manifest and one stable
    transaction id.  Combining stages from different transactions, replaying a
    stage, or changing any manifest field invalidates the triple.  The function
    intentionally returns facts (rather than trusting worker prose) and never
    treats a partial sequence as a pass.
    """

    installed = False
    reached = False
    killed = False
    invalid_sequence = False
    observed_failure_code = None
    evidence_refs: list[str] = []
    transaction_id: str | None = None
    seen_events: set[tuple[str, str, str]] = set()

    manifest_tokens = (
        manifest.canary_id,
        manifest.version,
        manifest.expected_failure_code,
        manifest.target_hash,
        manifest.mutation_hash,
        manifest.installer_hash,
    )
    if (
        any(not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value)
            for value in manifest_tokens)
        or not is_valid_hash(manifest.target_hash)
        or not is_valid_hash(manifest.mutation_hash)
        or not is_valid_hash(manifest.installer_hash)
    ):
        return CanaryResult(
            canary_id=manifest.canary_id,
            installed=False,
            reached=False,
            killed=False,
            observed_failure_code=None,
            evidence_refs=(),
        )

    manifest_values = {
        "version": manifest.version,
        "target_hash": manifest.target_hash,
        "mutation_hash": manifest.mutation_hash,
        "installer_hash": manifest.installer_hash,
    }

    def bound_transaction(payload: dict[str, object]) -> str | None:
        if payload.get("canary_id") != manifest.canary_id:
            return None
        for key, expected in manifest_values.items():
            if payload.get(key) != expected:
                return None
        value = payload.get("transaction_id")
        if not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value):
            return None
        return value

    for event in observations:
        payload = event.payload or {}
        if payload.get("canary_id") != manifest.canary_id:
            continue
        tx = bound_transaction(payload)
        if tx is None:
            invalid_sequence = True
            continue
        if transaction_id is None:
            transaction_id = tx
        elif transaction_id != tx:
            invalid_sequence = True
            continue
        if event.kind not in {"CANARY_INSTALLED", "CANARY_REACHED", "CANARY_KILLED"}:
            continue

        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "kind": event.kind,
                    "transaction_id": tx,
                    "observed_failure_code": payload.get("observed_failure_code"),
                    "evidence_ref": payload.get("evidence_ref"),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        event_key = (event.kind, tx, fingerprint)
        if any(key[0] == event.kind and key[1] == tx for key in seen_events):
            invalid_sequence = True
            continue
        seen_events.add(event_key)

        if event.kind == "CANARY_INSTALLED":
            if installed or reached or killed:
                invalid_sequence = True
            else:
                installed = True
        elif event.kind == "CANARY_REACHED":
            if not installed or reached or killed:
                invalid_sequence = True
            else:
                reached = True
        elif event.kind == "CANARY_KILLED":
            observed_code = payload.get("observed_failure_code")
            evidence_ref = payload.get("evidence_ref")
            if (
                not installed
                or not reached
                or killed
                or not isinstance(observed_code, str)
                or observed_code != manifest.expected_failure_code
                or not isinstance(evidence_ref, str)
                or not evidence_ref.strip()
            ):
                invalid_sequence = True
            else:
                killed = True
                observed_failure_code = observed_code
                if evidence_ref not in evidence_refs:
                    evidence_refs.append(evidence_ref)

    return CanaryResult(
        canary_id=manifest.canary_id,
        installed=installed,
        reached=reached,
        killed=killed and not invalid_sequence,
        observed_failure_code=observed_failure_code,
        evidence_refs=tuple(evidence_refs),
    )
