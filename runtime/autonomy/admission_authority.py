"""Offline-capable authenticated records on the existing canonical Ledger.

Trust is supplied by the composition owner as frozen, independently enrolled public
identities and root-signed exact grants. This module never discovers/enrolls keys,
reads credentials, opens a provider connection, or supplies production trust.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from kernel.ledger import GENESIS_HASH, Event, ForkRejected, Ledger

BINDINGS = (
    "goal_id",
    "task_id",
    "run_id",
    "session_id",
    "stage",
    "role",
    "workspace_id",
    "contract_digest",
    "scope_digest",
    "route_id",
    "route_digest",
    "root_allocation_id",
)
CURRENT = {
    "ADMISSION_CURRENT": ("admission_ref", "epoch", "ADMISSION_REVOKED"),
    "DISCLOSURE_POLICY_CURRENT": ("policy_id", "revision", "DISCLOSURE_POLICY_REVOKED"),
}
HASH = re.compile(r"[0-9a-f]{64}\Z")


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class EnrolledIdentity:
    identity_id: str
    public_key: bytes

    def __post_init__(self):
        if (
            type(self.identity_id) is not str
            or not self.identity_id
            or type(self.public_key) is not bytes
            or len(self.public_key) != 32
        ):
            raise ValueError("invalid enrolled identity")


@dataclass(frozen=True, slots=True)
class FrozenTrust:
    roots: tuple[EnrolledIdentity, ...] = ()
    identities: tuple[EnrolledIdentity, ...] = ()
    grants: tuple[bytes, ...] = ()

    def __post_init__(self):
        if any(type(v) is not tuple for v in (self.roots, self.identities, self.grants)):
            raise ValueError("trust inputs must be immutable tuples")
        people = self.roots + self.identities
        if any(not isinstance(x, EnrolledIdentity) for x in people) or any(
            type(x) is not bytes for x in self.grants
        ):
            raise ValueError("invalid frozen trust")
        if len({x.identity_id for x in people}) != len(people):
            raise ValueError("ambiguous enrolled identity")


class AdmissionAuthority:
    """Concrete verifier and CAS producer; no default enrolled root or authority.

    ``issue`` accepts an external signer but trusts only independently enrolled keys
    and root grants. Signed bytes are verified again immediately before append.
    Revocation is terminal for a record identity; renewal uses a new identity and
    still consumes the same root allocation.
    """

    requires_authenticated_settlement = True

    def __init__(self, ledger: Ledger, *, trust: FrozenTrust, domain_tag="PRODUCTION", now=None):
        if not isinstance(ledger, Ledger) or not isinstance(trust, FrozenTrust):
            raise TypeError("canonical ledger and frozen enrolled trust required")
        self.ledger, self.trust = ledger, trust
        self.domain_tag = domain_tag
        self.now = now or (lambda: datetime.now(UTC))

    def validate_context(self, ledger: Ledger, domain_tag: str) -> None:
        """A verifier cannot carry authority into another canonical store or domain."""
        if ledger is not self.ledger or domain_tag != self.domain_tag:
            raise ValueError("authority ledger/domain binding mismatch")

    def _time(self, value):
        if type(value) is not str:
            raise ValueError("timestamp must be ISO-8601 text")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timezone required")
        return parsed

    def _signature(self, record, identities):
        if (
            record.get("schema") != 1
            or type(record.get("schema")) is not int
            or record.get("domain_tag") != self.domain_tag
        ):
            raise ValueError("wrong signature context")
        key = next((x for x in identities if x.identity_id == record.get("issuer_id")), None)
        if key is None:
            raise ValueError("issuer not enrolled")
        signature_text = record.get("signature")
        if type(signature_text) is not str or not re.fullmatch(r"[0-9a-f]{128}", signature_text):
            raise ValueError("invalid signature encoding")
        signature = bytes.fromhex(signature_text)
        try:
            Ed25519PublicKey.from_public_bytes(key.public_key).verify(
                signature, canonical({k: v for k, v in record.items() if k != "signature"})
            )
        except InvalidSignature as exc:
            raise ValueError("invalid authority signature") from exc
        if not self.now() < self._time(record["expires_at"]):
            raise ValueError("expired proof")

    def _grant(self, grant_id):
        matches = [
            json.loads(x) for x in self.trust.grants if json.loads(x).get("grant_id") == grant_id
        ]
        if len(matches) != 1:
            raise ValueError("missing or ambiguous root grant")
        grant = matches[0]
        self._signature(grant, self.trust.roots)
        if grant.get("record_kind") != "ROOT_GRANT":
            raise ValueError("wrong root proof")
        for field in BINDINGS:
            value = grant.get(field)
            if type(value) is not str or not value or len(value) > 512 or "\x00" in value:
                raise ValueError("invalid root binding")
            if field.endswith("digest") and not HASH.fullmatch(value):
                raise ValueError("invalid root digest")
        if type(grant.get("max_frames")) is not int or not 0 < grant["max_frames"] <= 100000:
            raise ValueError("invalid root allocation")
        return grant

    def _validate(self, record, kind):
        if record.get("record_kind") != kind:
            raise ValueError("wrong record kind")
        grant = self._grant(record.get("grant_id"))
        if kind != "SEND_EVIDENCE" and record.get("root_grant_digest") != digest(grant):
            raise ValueError("root grant changed since issuance")
        root_revoke = kind == "AUTHORITY_GRANT_REVOKED"
        self._signature(record, self.trust.roots if root_revoke else self.trust.identities)
        if root_revoke:
            if record["issuer_id"] != grant["issuer_id"]:
                raise ValueError("wrong root revoker")
            return grant
        expected = grant["reconciler_id"] if kind == "SEND_EVIDENCE" else grant["delegate_id"]
        if record["issuer_id"] != expected:
            raise ValueError("issuer lacks delegated authority")
        if self._time(record["expires_at"]) > self._time(grant["expires_at"]):
            raise ValueError("proof exceeds root expiry")
        if kind != "SEND_EVIDENCE" and any(record.get(k) != grant[k] for k in BINDINGS):
            raise ValueError("scope exceeds root grant")
        if kind == "DISCLOSURE_POLICY_CURRENT":
            frames = record.get("frame_digests")
            if (
                type(frames) is not list
                or not frames
                or any(type(x) is not str or not HASH.fullmatch(x) for x in frames)
            ):
                raise ValueError("exact frame allowlist required")
            body = {k: v for k, v in record.items() if k not in {"signature", "digest"}}
            if record.get("digest") != digest(body):
                raise ValueError("policy digest mismatch")
        current_kind = (
            kind if kind in CURRENT else next((k for k, v in CURRENT.items() if v[2] == kind), None)
        )
        if current_kind is not None:
            identity, version, _ = CURRENT[current_kind]
            if (
                type(record.get(identity)) is not str
                or not record[identity]
                or type(record.get(version)) is not int
                or record[version] < 1
            ):
                raise ValueError("invalid record identity/version")
        if kind == "ADMISSION_CURRENT" and (
            any(
                type(record.get(k)) is not str or not record[k]
                for k in ("logical_job_id", "policy_id")
            )
            or type(record.get("policy_revision")) is not int
            or record["policy_revision"] < 1
            or not HASH.fullmatch(str(record.get("policy_digest")))
        ):
            raise ValueError("invalid admission policy binding")
        return grant

    def _verified(self, payload, kind):
        try:
            self._validate(payload, kind)
            return True
        except Exception:
            return False

    def verify_admission(self, payload: Mapping[str, object]) -> bool:
        """Verify signed scope/expiry; only the fence's CAS claim permits a send."""
        return self._verified(payload, "ADMISSION_CURRENT")

    def verify_policy(self, payload: Mapping[str, object]) -> bool:
        """Verify signed policy bytes; canonical currentness is checked by the fence."""
        return self._verified(payload, "DISCLOSURE_POLICY_CURRENT")

    def authorize_frame(self, admission, policy, *, frame_digest, route_digest):
        """Check exact frame membership. Never use this proof check as a send lease."""
        return (
            self.verify_admission(admission)
            and self.verify_policy(policy)
            and all(admission.get(k) == policy.get(k) for k in (*BINDINGS, "grant_id"))
            and admission["policy_id"] == policy["policy_id"]
            and admission["policy_revision"] == policy["revision"]
            and admission["policy_digest"] == policy["digest"]
            and route_digest == policy["route_digest"]
            and frame_digest in policy["frame_digests"]
        )

    def validate_current(self, rows, admission, policy):
        if not self._allocation_current(rows, admission):
            return False
        for kind, record in (
            ("ADMISSION_CURRENT", admission),
            ("DISCLOSURE_POLICY_CURRENT", policy),
        ):
            identity, version, _ = CURRENT[kind]
            previous_version = 0
            for row in rows:
                if (
                    row.domain_tag != self.domain_tag
                    or row.event.kind != kind
                    or row.event.payload.get(identity) != record[identity]
                ):
                    continue
                current_version = row.event.payload.get(version)
                if type(current_version) is not int or current_version <= previous_version:
                    return False
                previous_version = current_version
        for row in rows:
            if row.domain_tag != self.domain_tag:
                continue
            p = row.event.payload
            # Even malformed canonical revocations conservatively deny; they cannot grant.
            if (
                row.event.kind == "ADMISSION_REVOKED"
                and p.get("admission_ref") == admission["admission_ref"]
            ) or (
                row.event.kind == "DISCLOSURE_POLICY_REVOKED"
                and p.get("policy_id") == policy["policy_id"]
            ):
                return False
            if row.event.kind == "AUTHORITY_GRANT_REVOKED" and p.get("grant_id") in {
                admission["grant_id"],
                policy["grant_id"],
            }:
                return False
        return True

    def _allocation_current(self, rows, record):
        """The first canonical root binding fixes this allocation across restarts.

        Reissuing admissions/policies or replacing the frozen grant cannot enlarge
        the allowance. A new grant for an existing allocation is not a budget reset.
        """
        for row in rows:
            if row.domain_tag != self.domain_tag or row.event.kind not in {
                *CURRENT,
                "ADMISSION_SEND_CLAIMED",
            }:
                continue
            previous = row.event.payload
            if previous.get("root_allocation_id") == record.get(
                "root_allocation_id"
            ) and previous.get("root_grant_digest") != record.get("root_grant_digest"):
                return False
        return True

    def validate_operation(self, operation, admission, rows):
        grant = self._grant(admission["grant_id"])
        if operation.operation_kind not in {"WORKER_LAUNCH", "PROVIDER_FRAME"}:
            return False
        if any(getattr(operation, k) != grant[k] for k in BINDINGS):
            return False
        cap = 1 if operation.operation_kind == "WORKER_LAUNCH" else grant["max_frames"]
        if type(operation.frame_ordinal) is not int or not 0 <= operation.frame_ordinal < cap:
            return False
        claims = [
            r
            for r in rows
            if r.domain_tag == self.domain_tag
            and r.event.kind == "ADMISSION_SEND_CLAIMED"
            and r.event.payload.get("root_allocation_id") == grant["root_allocation_id"]
            and r.event.payload.get("operation_kind") == operation.operation_kind
        ]
        return len(claims) < cap

    def issue(
        self,
        kind: str,
        fields: Mapping[str, object],
        *,
        issuer_id: str,
        signer: Callable[[bytes], bytes],
    ):
        body = dict(fields)
        body.update(schema=1, record_kind=kind, issuer_id=issuer_id, domain_tag=self.domain_tag)
        body["root_grant_digest"] = digest(self._grant(body.get("grant_id")))
        body.pop("signature", None)
        if kind == "DISCLOSURE_POLICY_CURRENT":
            body.pop("digest", None)
            body["digest"] = digest(body)
        body["signature"] = signer(canonical(body)).hex()
        self.append_signed(body)
        return body

    def append_signed(self, payload):
        try:
            record = json.loads(canonical(dict(payload)))  # isolate caller mutations
        except (TypeError, ValueError) as exc:
            raise ValueError("authority envelope must be a JSON mapping") from exc
        kind = record.get("record_kind")
        if type(kind) is not str or kind not in {
            *CURRENT,
            "ADMISSION_REVOKED",
            "DISCLOSURE_POLICY_REVOKED",
            "AUTHORITY_GRANT_REVOKED",
        }:
            raise ValueError("unsupported authority event")
        for _ in range(16):
            self._validate(record, kind)
            rows = self.ledger.read()
            head = rows[-1].row_hash if rows else GENESIS_HASH
            if self.ledger.verify_chain() != head:
                continue
            scoped = [r for r in rows if r.domain_tag == self.domain_tag]
            if kind in CURRENT and not self._allocation_current(scoped, record):
                raise ValueError("canonical root allocation cannot be rebound")
            if any(
                r.event.kind == "AUTHORITY_GRANT_REVOKED"
                and r.event.payload.get("grant_id") == record["grant_id"]
                for r in scoped
            ):
                raise ValueError("root grant revoked")
            current_kind = (
                kind
                if kind in CURRENT
                else next((k for k, v in CURRENT.items() if v[2] == kind), None)
            )
            if current_kind:
                identity, version, revoked = CURRENT[current_kind]
                if identity not in record or version not in record:
                    raise ValueError("missing revocation target")
                previous = [
                    r
                    for r in scoped
                    if r.event.kind in {current_kind, revoked}
                    and r.event.payload.get(identity) == record[identity]
                ]
                if any(r.event.kind == revoked for r in previous):
                    raise ValueError("identity revoked")
                if previous:
                    old = previous[-1].event.payload
                    if old.get("grant_id") != record["grant_id"]:
                        raise ValueError("record owner substitution")
                    if kind == revoked:
                        if record[version] != old.get(version):
                            raise ValueError("stale revocation")
                    elif record[version] <= old.get(version, 0):
                        raise ValueError("stale version")
                elif kind == revoked:
                    raise ValueError("revocation target absent")
            if kind == "ADMISSION_CURRENT":
                policies = [
                    r
                    for r in scoped
                    if r.event.kind in {"DISCLOSURE_POLICY_CURRENT", "DISCLOSURE_POLICY_REVOKED"}
                    and r.event.payload.get("policy_id") == record["policy_id"]
                ]
                if not policies or policies[-1].event.kind != "DISCLOSURE_POLICY_CURRENT":
                    raise ValueError("policy unavailable")
                policy = policies[-1].event.payload
                if (
                    not self.verify_policy(policy)
                    or any(record.get(k) != policy.get(k) for k in (*BINDINGS, "grant_id"))
                    or record["policy_revision"] != policy["revision"]
                    or record["policy_digest"] != policy["digest"]
                ):
                    raise ValueError("policy not current or parent mismatch")
            try:
                return self.ledger.append_if_head(
                    Event(1, kind, record), expected_head_hash=head, domain_tag=self.domain_tag
                )
            except ForkRejected:
                continue
        raise ValueError("canonical authority state remained contended")

    def verify_settlement_record(self, evidence, claim):
        """Authenticate receipt metadata; this alone cannot reconcile return bytes."""
        try:
            grant = self._validate(evidence, "SEND_EVIDENCE")
            if (
                evidence["grant_id"] != claim["grant_id"]
                or claim.get("root_grant_digest") != digest(grant)
                or evidence["lease_id"] != claim["lease_id"]
                or evidence["claim_digest"] != digest(claim)
            ):
                return False
            if evidence["outcome"] == "UNKNOWN":
                return evidence.get("outcome_ref") is None
            return (
                evidence["outcome"] == "RETURNED"
                and type(evidence.get("outcome_ref")) is str
                and HASH.fullmatch(evidence["outcome_ref"]) is not None
            )
        except Exception:
            return False

    def verify_settlement(self, evidence, claim, outcome_bytes):
        if not self.verify_settlement_record(evidence, claim):
            return False
        if evidence["outcome"] == "UNKNOWN":
            return outcome_bytes is None
        return (
            type(outcome_bytes) is bytes
            and evidence["outcome_ref"] == hashlib.sha256(outcome_bytes).hexdigest()
        )
