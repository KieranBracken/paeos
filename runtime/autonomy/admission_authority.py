"""Offline-capable authenticated records on the existing canonical Ledger.

Trust is supplied by the composition owner as frozen, independently enrolled public
identities and root-signed exact grants. This module never discovers/enrolls keys,
reads credentials, opens a provider connection, or supplies production trust.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from kernel.ledger import GENESIS_HASH, Event, ForkRejected, Ledger
from nacl.signing import VerifyKey
from paeos.model_router.disclosure_policy import verify_founder_derivative_policy

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

    def __init__(
        self,
        ledger: Ledger,
        *,
        trust: FrozenTrust,
        domain_tag="PRODUCTION",
        now=None,
        tool_policy_manifests: tuple[bytes, ...] = (),
    ):
        if not isinstance(ledger, Ledger) or not isinstance(trust, FrozenTrust):
            raise TypeError("canonical ledger and frozen enrolled trust required")
        if type(tool_policy_manifests) is not tuple or any(
            type(raw) is not bytes or not 0 < len(raw) <= 1048576 for raw in tool_policy_manifests
        ):
            raise ValueError("immutable bounded tool policy bytes required")
        self._tool_policy_manifests = tool_policy_manifests
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

    def claim_parent_tool_read(self, request_bytes: bytes) -> int:
        """Commit a purpose-bound claim only; never invokes a tool."""
        return _ParentToolAuthority(self).claim(request_bytes)

    def record_parent_tool_observation(self, observation_bytes: bytes) -> int:
        """Retain a signed historical observation; never reads an artifact."""
        return _ParentToolAuthority(self).record(observation_bytes)

    def read_parent_tool_operation(self, operation_id: str) -> ParentToolReadback:
        """Read verified canonical bytes under current scope; not a permit."""
        return _ParentToolAuthority(self).read(operation_id)

    def issue_parent_tool_commit_ack(self, operation_id, phase, *, issuer_id, signer) -> bytes:
        """Protected authority API: readback precedes separately delegated signing."""
        return _ParentToolAuthority(self).ack(operation_id, phase, issuer_id, signer)

    def verify_parent_tool_commit_ack(
        self,
        ack_bytes: bytes,
        *,
        expected_request_bytes: bytes,
        expected_observation_bytes: bytes | None = None,
    ) -> ParentToolReadback:
        """Verify ACK against this Ledger, never against caller-provided rows."""
        return _ParentToolAuthority(self).verify_ack(
            ack_bytes, expected_request_bytes, expected_observation_bytes
        )


# Dedicated offline construction protocol. Legacy v1 functions above keep their semantics.
_TOOL_CONTEXT = frozenset(
    (
        "bindings",
        "base_grant_id",
        "base_grant_digest",
        "tool_grant_id",
        "tool_grant_digest",
        "admission_ref",
        "admission_epoch",
        "policy_id",
        "policy_revision",
        "policy_digest",
        "signed_v2_manifest_sha256",
        "derivative_rule_id",
    )
)
_TOOL_GRANT_FIELDS = frozenset(
    (
        "schema",
        "record_kind",
        "domain_tag",
        "issuer_id",
        "grant_id",
        "issued_at",
        "expires_at",
        "parent_grant_id",
        "parent_grant_digest",
        "bindings",
        "admission_ref",
        "admission_epoch",
        "policy_id",
        "policy_revision",
        "policy_digest",
        "policy_signer_id",
        "signed_v2_manifest_sha256",
        "derivative_rule_id",
        "parent_identity_sha256",
        "tool_name",
        "tool_envelope_sha256",
        "tool_source_sha256",
        "tool_protocol_version",
        "transformation",
        "transformation_version",
        "artifact_id",
        "expected_input_sha256",
        "max_operations",
        "max_raw_bytes",
        "max_result_bytes",
        "start_window_seconds",
        "purpose_delegations",
    )
)
_TOOL_CLAIM_FIELDS = frozenset(
    (
        "schema",
        "purpose",
        "purpose_version",
        "domain_tag",
        "issuer_id",
        "issued_at",
        "expires_at",
        "context",
        "operation_id",
        "ordinal",
        "request_id",
        "mcp_id",
        "tool_name",
        "arguments",
        "arguments_sha256",
        "artifact_id",
        "expected_input_sha256",
        "tool_envelope_sha256",
        "tool_source_sha256",
        "tool_protocol_version",
        "transformation",
        "transformation_version",
        "parent_identity_sha256",
        "parent_boot_id",
        "parent_process_id",
        "max_raw_bytes",
        "max_result_bytes",
    )
)
_TOOL_OBSERVATION_FIELDS = frozenset(
    (
        "schema",
        "purpose",
        "purpose_version",
        "domain_tag",
        "issuer_id",
        "issued_at",
        "expires_at",
        "context",
        "operation_id",
        "ordinal",
        "request_sha256",
        "claim_seq",
        "claim_row_hash",
        "parent_identity_sha256",
        "parent_boot_id",
        "parent_process_id",
        "effect_started_at",
        "observed_at",
        "outcome",
        "error_code",
        "actual_input_sha256",
        "raw_length",
        "raw_b64",
        "result_sha256",
        "result_length",
        "result_b64",
    )
)
_TOOL_ACK_FIELDS = frozenset(
    (
        "schema",
        "purpose",
        "purpose_version",
        "domain_tag",
        "issuer_id",
        "issued_at",
        "expires_at",
        "context",
        "operation_id",
        "ordinal",
        "phase",
        "request_sha256",
        "observation_sha256",
        "parent_identity_sha256",
        "parent_boot_id",
        "parent_process_id",
        "claim_seq",
        "claim_row_hash",
        "accepted_kind",
        "accepted_seq",
        "accepted_row_hash",
        "accepted_prev_hash",
        "commit_head_hash",
        "verified_head_hash",
        "raw_sha256",
        "raw_length",
        "result_sha256",
        "result_length",
        "status",
    )
)
_TOOL_CLAIM_ROW = frozenset(
    (
        "schema",
        "domain_tag",
        "operation_id",
        "ordinal",
        "request_b64",
        "request_sha256",
        "base_grant_b64",
        "tool_grant_b64",
        "authority_claimed_at",
        "start_deadline",
    )
)
_TOOL_OUTCOME_ROW = frozenset(
    (
        "schema",
        "domain_tag",
        "operation_id",
        "ordinal",
        "claim_seq",
        "claim_row_hash",
        "observation_b64",
        "observation_sha256",
    )
)

_TOOL_PURPOSES = ("PARENT_TOOL_CLAIM_REQUEST", "PARENT_TOOL_OBSERVATION", "PARENT_TOOL_COMMIT_ACK")
_TOOL_CLAIMED = "PARENT_TOOL_READ_CLAIMED"
_TOOL_RECORDED = "PARENT_TOOL_OBSERVATION_RECORDED"
_TOOL_WIRE_MAX = 196608
_TOOL_EVENT_MAX = 262144
_TOOL_RAW_MAX = 16384
_TOOL_RESULT_MAX = 131072


@dataclass(frozen=True, slots=True)
class ParentToolReadback:
    """Immutable evidence only. No read/send/launch capability is carried."""

    operation_id: str
    outcome: str
    claim_seq: int
    claim_row_hash: str
    accepted_seq: int
    accepted_row_hash: str
    request_bytes: bytes
    observation_bytes: bytes | None
    raw_bytes: bytes | None
    result_bytes: bytes | None


def _require(condition):
    if not condition:
        raise ValueError("parent-tool authority refused")


def _object(value, fields):
    _require(type(value) is dict and set(value) == set(fields))
    return value


def _text(value, limit=128):
    _require(type(value) is str and 0 < len(value.encode("utf-8")) <= limit and "\0" not in value)
    return value


def _hash(value):
    _require(type(value) is str and HASH.fullmatch(value) is not None)
    return value


def _integer(value, low, high):
    _require(type(value) is int and low <= value <= high)
    return value


def _strict(raw, limit):
    _require(type(raw) is bytes and 0 < len(raw) <= limit)

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs)
        _require(canonical(value) == raw)
    except (UnicodeError, TypeError, RecursionError, ValueError):
        raise ValueError("noncanonical parent-tool encoding") from None
    return value


def _b64(raw):
    return base64.b64encode(raw).decode("ascii")


def _unb64(text, limit):
    _require(type(text) is str and len(text) <= 4 * ((limit + 2) // 3))
    try:
        raw = base64.b64decode(text, validate=True)
    except (ValueError, UnicodeError):
        raise ValueError("invalid retained-byte encoding") from None
    _require(len(raw) <= limit and _b64(raw) == text)
    return raw


def _wire(raw, fields, purpose, domain, identities, *, version=1, limit=_TOOL_WIRE_MAX):
    envelope = _object(_strict(raw, limit), {"body", "signature"})
    body = _object(envelope["body"], fields)
    _require(type(body["schema"]) is int and body["schema"] == version)
    _require(body["domain_tag"] == domain)
    if version == 2:
        _require(body["record_kind"] == "ROOT_GRANT")
        prefix = b"PAEOS_PARENT_TOOL_GRANT/v2\0"
    else:
        _require(body["purpose"] == purpose)
        _require(type(body["purpose_version"]) is int and body["purpose_version"] == 1)
        prefix = ("PAEOS_" + purpose + "/v1\0").encode("ascii")
    _text(body["issuer_id"])
    candidates = [x for x in identities if x.identity_id == body["issuer_id"]]
    _require(len(candidates) == 1)
    signature = envelope["signature"]
    _require(type(signature) is str and re.fullmatch(r"[0-9a-f]{128}", signature) is not None)
    try:
        Ed25519PublicKey.from_public_bytes(candidates[0].public_key).verify(
            bytes.fromhex(signature), prefix + canonical(body)
        )
    except InvalidSignature:
        raise ValueError("invalid parent-tool signature") from None
    return body


class _ParentToolAuthority:
    """Concrete Ledger-only protocol. No tool/queue/process/network adapter exists here."""

    def __init__(self, authority):
        self.a = authority

    def _time(self, value):
        return self.a._time(value)

    def _clock(self):
        now = self.a.now()
        _require(isinstance(now, datetime) and now.utcoffset() is not None)
        return now

    def _window(self, body, at):
        issued, end = self._time(body["issued_at"]), self._time(body["expires_at"])
        _require(issued <= at < end)
        return end

    def _snapshot(self):
        for _ in range(16):
            rows = self.a.ledger.read()
            head = rows[-1].row_hash if rows else GENESIS_HASH
            if self.a.ledger.verify_chain() == head:
                return rows, head
        raise ValueError("parent-tool ledger remained contended")

    def _legacy(self, base_raw, at):
        # Historical checking uses the accepted claim clock and its retained signed
        # base proof. Fresh use separately resolves the live trust/ledger below.
        return AdmissionAuthority(
            self.a.ledger,
            trust=FrozenTrust(self.a.trust.roots, self.a.trust.identities, (base_raw,)),
            domain_tag=self.a.domain_tag,
            now=lambda: at,
        )

    def _lookup_grant(self, grant_id):
        matches = []
        for raw in self.a.trust.grants:
            try:
                value = json.loads(raw)
            except (ValueError, UnicodeError):
                continue
            if (
                type(value) is dict
                and type(value.get("body")) is dict
                and value["body"].get("grant_id") == grant_id
            ):
                matches.append(raw)
        _require(len(matches) == 1)
        return matches[0]

    def _grant(self, grant_raw, base_raw, at):
        g = _wire(
            grant_raw,
            _TOOL_GRANT_FIELDS,
            None,
            self.a.domain_tag,
            self.a.trust.roots,
            version=2,
            limit=16384,
        )
        _require(len(base_raw) <= 16384)
        base = self._legacy(base_raw, at)._grant(g["parent_grant_id"])
        _require(g["parent_grant_digest"] == digest(base))
        _require(g["issuer_id"] == base["issuer_id"] and g["grant_id"] != base["grant_id"])
        _object(g["bindings"], BINDINGS)
        _require(g["bindings"] == {key: base[key] for key in BINDINGS})
        for key, value in g["bindings"].items():
            _text(value, 512)
            if key.endswith("digest"):
                _hash(value)
        self._window(g, at)
        _require(self._time(g["expires_at"]) <= self._time(base["expires_at"]))
        for key in (
            "grant_id",
            "parent_grant_id",
            "admission_ref",
            "policy_id",
            "policy_signer_id",
            "derivative_rule_id",
            "tool_protocol_version",
            "transformation_version",
            "artifact_id",
        ):
            _text(g[key])
        for key in (
            "parent_grant_digest",
            "policy_digest",
            "signed_v2_manifest_sha256",
            "parent_identity_sha256",
            "tool_envelope_sha256",
            "tool_source_sha256",
            "expected_input_sha256",
        ):
            _hash(g[key])
        for key in ("admission_epoch", "policy_revision"):
            _integer(g[key], 1, 2**53 - 1)
        _integer(g["max_operations"], 1, 1)
        _integer(g["max_raw_bytes"], 1, _TOOL_RAW_MAX)
        _integer(g["max_result_bytes"], 1, _TOOL_RESULT_MAX)
        _integer(g["start_window_seconds"], 1, 30)
        _require(
            g["tool_name"] == "read_artifact" and g["transformation"] == "READ_APPROVED_ARTIFACT"
        )
        entries = g["purpose_delegations"]
        _require(type(entries) is list and len(entries) == 3)
        purposes = {}
        for entry in entries:
            _object(
                entry,
                {
                    "purpose",
                    "purpose_version",
                    "signer_identity_id",
                    "public_key_sha256",
                    "expires_at",
                },
            )
            _text(entry["purpose"])
            _require(entry["purpose"] in _TOOL_PURPOSES and entry["purpose"] not in purposes)
            _integer(entry["purpose_version"], 1, 1)
            _text(entry["signer_identity_id"])
            _hash(entry["public_key_sha256"])
            identity = [
                x for x in self.a.trust.identities if x.identity_id == entry["signer_identity_id"]
            ]
            _require(len(identity) == 1)
            _require(
                hashlib.sha256(identity[0].public_key).hexdigest() == entry["public_key_sha256"]
            )
            _require(at < self._time(entry["expires_at"]) <= self._time(g["expires_at"]))
            purposes[entry["purpose"]] = entry
        parent, observed, ack = (purposes[p] for p in _TOOL_PURPOSES)
        _require(parent["signer_identity_id"] == observed["signer_identity_id"])
        _require(parent["public_key_sha256"] == g["parent_identity_sha256"])
        _require(ack["signer_identity_id"] == base["delegate_id"])
        _require(ack["signer_identity_id"] not in {parent["signer_identity_id"], base["issuer_id"]})
        root_key = next(
            x.public_key for x in self.a.trust.roots if x.identity_id == base["issuer_id"]
        )
        _require(parent["public_key_sha256"] != hashlib.sha256(root_key).hexdigest())
        _require(
            ack["public_key_sha256"]
            not in {
                parent["public_key_sha256"],
                hashlib.sha256(root_key).hexdigest(),
            }
        )
        policies = [
            raw
            for raw in self.a._tool_policy_manifests
            if hashlib.sha256(raw).hexdigest() == g["signed_v2_manifest_sha256"]
        ]
        roots = [x for x in self.a.trust.roots if x.identity_id == g["policy_signer_id"]]
        _require(len(policies) == len(roots) == 1)
        policy = verify_founder_derivative_policy(
            policies[0], VerifyKey(roots[0].public_key), roots[0].identity_id, now=at
        )
        _require(policy.policy_id == g["policy_id"] and policy.revision == g["policy_revision"])
        _require(self._time(g["expires_at"]) <= policy.expires_at)
        rules = [x for x in policy.derivative_rules if x.rule_id == g["derivative_rule_id"]]
        _require(len(rules) == 1)
        rule = rules[0]
        _require(rule.input_artifact_sha256s == (g["expected_input_sha256"],))
        _require(rule.tool_envelope_sha256 == g["tool_envelope_sha256"])
        _require("READ_APPROVED_ARTIFACT" in rule.transformation_ids)
        cls = next(x for x in policy.classes if x.class_id == rule.class_id)
        bounds = [
            x.max_bytes
            for x in cls.scope.allowed_artifacts
            if x.sha256 == g["expected_input_sha256"]
        ]
        _require(bool(bounds) and g["max_raw_bytes"] <= min(bounds))
        _require(
            max(g["max_raw_bytes"], g["max_result_bytes"])
            <= min(rule.max_output_bytes, cls.max_bundle_bytes)
        )
        return g, base, purposes

    def _context(self, g, base):
        return dict(
            bindings=g["bindings"],
            base_grant_id=base["grant_id"],
            base_grant_digest=digest(base),
            tool_grant_id=g["grant_id"],
            tool_grant_digest=self._grant_digest(g),
            **{
                key: g[key]
                for key in (
                    "admission_ref",
                    "admission_epoch",
                    "policy_id",
                    "policy_revision",
                    "policy_digest",
                    "signed_v2_manifest_sha256",
                    "derivative_rule_id",
                )
            },
        )

    @staticmethod
    def _grant_digest(g):
        # Digest of canonical unsigned grant BODY, whose signature is checked separately.
        return digest(g)

    def _common(self, body, g, base, purposes, purpose, *, at):
        _object(body["context"], _TOOL_CONTEXT)
        _require(canonical(body["context"]) == canonical(self._context(g, base)))
        _integer(body["ordinal"], 0, 0)
        expected = digest(
            dict(
                root_allocation_id=g["bindings"]["root_allocation_id"],
                operation_kind="PARENT_TOOL_READ",
                ordinal=0,
            )
        )
        _require(body["operation_id"] == expected)
        entry = purposes[purpose]
        _require(body["issuer_id"] == entry["signer_identity_id"])
        self._window(body, at)
        _require(self._time(body["issued_at"]) >= self._time(g["issued_at"]))
        _require(self._time(body["expires_at"]) <= self._time(entry["expires_at"]))

    def _request(self, raw, grant_raw, base_raw, at):
        req = _wire(
            raw,
            _TOOL_CLAIM_FIELDS,
            _TOOL_PURPOSES[0],
            self.a.domain_tag,
            self.a.trust.identities,
            limit=32768,
        )
        g, base, purposes = self._grant(grant_raw, base_raw, at)
        self._common(req, g, base, purposes, _TOOL_PURPOSES[0], at=at)
        for key in (
            "artifact_id",
            "expected_input_sha256",
            "tool_envelope_sha256",
            "tool_source_sha256",
            "tool_protocol_version",
            "transformation",
            "transformation_version",
            "parent_identity_sha256",
            "max_raw_bytes",
            "max_result_bytes",
            "tool_name",
        ):
            _require(type(req[key]) is type(g[key]) and req[key] == g[key])
        _object(req["arguments"], {"artifact_id"})
        _require(req["arguments"] == {"artifact_id": g["artifact_id"]})
        _require(req["arguments_sha256"] == digest(req["arguments"]))
        for key in ("request_id", "parent_boot_id", "parent_process_id"):
            _text(req[key])
        if type(req["mcp_id"]) is str:
            _text(req["mcp_id"])
        else:
            _integer(req["mcp_id"], 0, 2**53 - 1)
        return req, g, base, purposes

    def _live(self, req, g, base, rows, at, *, historical=False):
        # Resolve CURRENT and revocation from this same CAS snapshot. No caller verdict.
        authority = self._legacy(canonical(base), at) if historical else self.a
        if not historical:
            current_grant = _wire(
                self._lookup_grant(g["grant_id"]),
                _TOOL_GRANT_FIELDS,
                None,
                self.a.domain_tag,
                self.a.trust.roots,
                version=2,
                limit=16384,
            )
            _require(canonical(current_grant) == canonical(g))
        current_base = authority._grant(base["grant_id"])
        _require(digest(current_base) == digest(base))
        _require(at < self._time(g["expires_at"]) and at < self._time(req["expires_at"]))
        for entry in g["purpose_delegations"]:
            _require(at < self._time(entry["expires_at"]))
        for row in rows:
            if row.domain_tag == self.a.domain_tag and row.event.kind == "AUTHORITY_GRANT_REVOKED":
                _require(row.event.payload.get("grant_id") not in {base["grant_id"], g["grant_id"]})
        selected = []
        for kind, field, ident, revoked in (
            ("ADMISSION_CURRENT", "admission_ref", g["admission_ref"], "ADMISSION_REVOKED"),
            ("DISCLOSURE_POLICY_CURRENT", "policy_id", g["policy_id"], "DISCLOSURE_POLICY_REVOKED"),
        ):
            relevant = [
                x
                for x in rows
                if x.domain_tag == self.a.domain_tag
                and x.event.kind in {kind, revoked}
                and x.event.payload.get(field) == ident
            ]
            _require(bool(relevant) and relevant[-1].event.kind == kind)
            value = relevant[-1].event.payload
            authority._validate(value, kind)
            _require(value["grant_id"] == base["grant_id"])
            _require(all(value.get(k) == g["bindings"][k] for k in BINDINGS))
            selected.append(value)
        admission, policy = selected
        _require(admission["epoch"] == g["admission_epoch"])
        _require(
            policy["revision"] == g["policy_revision"] and policy["digest"] == g["policy_digest"]
        )
        _require(
            admission["policy_id"] == policy["policy_id"]
            and admission["policy_revision"] == policy["revision"]
            and admission["policy_digest"] == policy["digest"]
        )
        _require(authority.validate_current(rows, admission, policy))
        return min(
            self._time(v["expires_at"])
            for v in (req, g, base, admission, policy, *g["purpose_delegations"])
        )

    def _append(self, kind, payload, head):
        _require(len(canonical(payload)) <= _TOOL_EVENT_MAX)
        return self.a.ledger.append_if_head(
            Event(1, kind, payload), expected_head_hash=head, domain_tag=self.a.domain_tag
        )

    def claim(self, raw):
        # Parse shape before selecting any trusted grant; no untrusted key lookup.
        envelope = _object(_strict(raw, 32768), {"body", "signature"})
        body = _object(envelope["body"], _TOOL_CLAIM_FIELDS)
        context = _object(body["context"], _TOOL_CONTEXT)
        grant_raw = self._lookup_grant(context["tool_grant_id"])
        base = self.a._grant(context["base_grant_id"])
        base_raw = canonical(base)
        for _ in range(16):
            now = self._clock()
            req, g, base, _ = self._request(raw, grant_raw, base_raw, now)
            rows, head = self._snapshot()
            live_end = self._live(req, g, base, rows, now)
            _require(
                not any(
                    x.domain_tag == self.a.domain_tag
                    and x.event.kind == _TOOL_CLAIMED
                    and x.event.payload.get("operation_id") == req["operation_id"]
                    for x in rows
                )
            )
            deadline = min(now + timedelta(seconds=g["start_window_seconds"]), live_end)
            payload = dict(
                schema=1,
                domain_tag=self.a.domain_tag,
                operation_id=req["operation_id"],
                ordinal=0,
                request_b64=_b64(raw),
                request_sha256=hashlib.sha256(raw).hexdigest(),
                base_grant_b64=_b64(base_raw),
                tool_grant_b64=_b64(grant_raw),
                authority_claimed_at=now.isoformat(),
                start_deadline=deadline.isoformat(),
            )
            try:
                return self._append(_TOOL_CLAIMED, payload, head)
            except ForkRejected:
                continue
        raise ValueError("parent-tool claim remained contended")

    def _load(self, operation_id, *, live=True):
        _hash(operation_id)
        rows, head = self._snapshot()
        claims = [
            x
            for x in rows
            if x.domain_tag == self.a.domain_tag
            and x.event.kind == _TOOL_CLAIMED
            and x.event.payload.get("operation_id") == operation_id
        ]
        _require(len(claims) == 1)
        claim = claims[0]
        p = _object(claim.event.payload, _TOOL_CLAIM_ROW)
        _require(
            claim.event.schema_ver == 1
            and type(p["schema"]) is int
            and p["schema"] == 1
            and p["domain_tag"] == self.a.domain_tag
        )
        _require(len(canonical(p)) <= _TOOL_EVENT_MAX)
        _integer(p["ordinal"], 0, 0)
        raw = _unb64(p["request_b64"], 32768)
        _require(hashlib.sha256(raw).hexdigest() == p["request_sha256"])
        at = self._time(p["authority_claimed_at"])
        req, g, base, purposes = self._request(
            raw, _unb64(p["tool_grant_b64"], 16384), _unb64(p["base_grant_b64"], 16384), at
        )
        _require(req["operation_id"] == operation_id)
        _require(at <= self._clock())
        historical_end = self._live(req, g, base, rows[: claim.seq - 1], at, historical=True)
        deadline = min(at + timedelta(seconds=g["start_window_seconds"]), historical_end)
        _require(self._time(p["start_deadline"]) == deadline)
        live_end = self._live(req, g, base, rows, self._clock()) if live else historical_end
        outcomes = [
            x
            for x in rows
            if x.domain_tag == self.a.domain_tag
            and x.event.kind == _TOOL_RECORDED
            and x.event.payload.get("operation_id") == operation_id
        ]
        _require(len(outcomes) <= 1)
        data = dict(
            live_end=live_end,
            rows=rows,
            head=head,
            claim=claim,
            req=req,
            g=g,
            base=base,
            purposes=purposes,
            raw_request=raw,
            outcome_row=None,
            observation=None,
            observation_raw=None,
            raw=None,
            result=None,
        )
        if outcomes:
            row = outcomes[0]
            value = _object(row.event.payload, _TOOL_OUTCOME_ROW)
            _require(row.seq > claim.seq and row.event.schema_ver == 1)
            _require(
                type(value["schema"]) is int
                and value["schema"] == 1
                and value["domain_tag"] == self.a.domain_tag
            )
            _integer(value["ordinal"], 0, 0)
            _require(
                value["claim_seq"] == claim.seq
                and type(value["claim_seq"]) is int
                and value["claim_row_hash"] == claim.row_hash
            )
            _require(len(canonical(value)) <= _TOOL_EVENT_MAX)
            observation_raw = _unb64(value["observation_b64"], _TOOL_WIRE_MAX)
            _require(hashlib.sha256(observation_raw).hexdigest() == value["observation_sha256"])
            observation, raw_bytes, result = self._observation(observation_raw, data)
            data.update(
                outcome_row=row,
                observation=observation,
                observation_raw=observation_raw,
                raw=raw_bytes,
                result=result,
            )
        return data

    def _observation(self, raw, data):
        obs = _wire(
            raw,
            _TOOL_OBSERVATION_FIELDS,
            _TOOL_PURPOSES[1],
            self.a.domain_tag,
            self.a.trust.identities,
        )
        req, g, base, claim = (data[k] for k in ("req", "g", "base", "claim"))
        issued = self._time(obs["issued_at"])
        _require(issued <= self._clock())
        self._common(obs, g, base, data["purposes"], _TOOL_PURPOSES[1], at=issued)
        for key in ("parent_identity_sha256", "parent_boot_id", "parent_process_id"):
            _require(obs[key] == req[key])
        _require(
            type(obs["claim_seq"]) is int
            and obs["claim_seq"] == claim.seq
            and obs["claim_row_hash"] == claim.row_hash
        )
        _require(obs["request_sha256"] == hashlib.sha256(data["raw_request"]).hexdigest())
        claimed = self._time(claim.event.payload["authority_claimed_at"])
        started, observed = self._time(obs["effect_started_at"]), self._time(obs["observed_at"])
        _require(claimed <= started <= self._time(claim.event.payload["start_deadline"]))
        _require(started <= observed <= issued)
        names = (
            "actual_input_sha256",
            "raw_length",
            "raw_b64",
            "result_sha256",
            "result_length",
            "result_b64",
        )
        _text(obs["outcome"])
        if obs["outcome"] in {"ERROR", "UNKNOWN"}:
            _text(obs["error_code"])
            codes = (
                {"UNKNOWN"}
                if obs["outcome"] == "UNKNOWN"
                else {"READ_FAILED", "INPUT_MISMATCH", "LIMIT_EXCEEDED", "INVALID_UTF8"}
            )
            _require(obs["error_code"] in codes and all(obs[k] is None for k in names))
            return obs, None, None
        _require(obs["outcome"] == "RETURNED" and obs["error_code"] is None)
        raw_bytes = _unb64(obs["raw_b64"], g["max_raw_bytes"])
        result = _unb64(obs["result_b64"], g["max_result_bytes"])
        _integer(obs["raw_length"], 0, g["max_raw_bytes"])
        _integer(obs["result_length"], 0, g["max_result_bytes"])
        _require(obs["raw_length"] == len(raw_bytes) and obs["result_length"] == len(result))
        _require(
            obs["actual_input_sha256"]
            == hashlib.sha256(raw_bytes).hexdigest()
            == req["expected_input_sha256"]
        )
        _require(obs["result_sha256"] == hashlib.sha256(result).hexdigest())
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeError:
            raise ValueError("invalid observed text") from None
        inner = json.dumps(
            dict(artifact_id=req["artifact_id"], text=text, sha256=obs["actual_input_sha256"]),
            sort_keys=True,
        )
        expected = (
            canonical(
                dict(
                    jsonrpc="2.0",
                    id=req["mcp_id"],
                    result={"content": [{"type": "text", "text": inner}]},
                )
            )
            + b"\n"
        )
        _require(result == expected)
        return obs, raw_bytes, result

    def record(self, raw):
        envelope = _object(_strict(raw, _TOOL_WIRE_MAX), {"body", "signature"})
        obs = _object(envelope["body"], _TOOL_OBSERVATION_FIELDS)
        for _ in range(16):
            data = self._load(obs["operation_id"], live=False)
            _require(data["outcome_row"] is None)
            self._observation(raw, data)
            p = dict(
                schema=1,
                domain_tag=self.a.domain_tag,
                operation_id=obs["operation_id"],
                ordinal=0,
                claim_seq=data["claim"].seq,
                claim_row_hash=data["claim"].row_hash,
                observation_b64=_b64(raw),
                observation_sha256=hashlib.sha256(raw).hexdigest(),
            )
            try:
                return self._append(_TOOL_RECORDED, p, data["head"])
            except ForkRejected:
                continue
        raise ValueError("parent-tool outcome remained contended")

    def _readback(self, data):
        row = data["outcome_row"] or data["claim"]
        return ParentToolReadback(
            data["req"]["operation_id"],
            data["observation"]["outcome"] if data["observation"] else "UNRESOLVED",
            data["claim"].seq,
            data["claim"].row_hash,
            row.seq,
            row.row_hash,
            data["raw_request"],
            data["observation_raw"],
            data["raw"],
            data["result"],
        )

    def read(self, operation_id):
        return self._readback(self._load(operation_id))

    def _ack_body(self, data, phase, issuer_id, issued, expires):
        _text(phase)
        _require(phase in {"CLAIM", "OUTCOME"})
        _require(issued < expires <= data["live_end"])
        req = data["req"]
        if phase == "CLAIM":
            _require(data["outcome_row"] is None)
            _require(expires <= self._time(data["claim"].event.payload["start_deadline"]))
            row = data["claim"]
        else:
            _require(
                data["observation"] is not None and data["observation"]["outcome"] == "RETURNED"
            )
            row = data["outcome_row"]
        return dict(
            schema=1,
            purpose=_TOOL_PURPOSES[2],
            purpose_version=1,
            domain_tag=self.a.domain_tag,
            issuer_id=issuer_id,
            issued_at=issued.isoformat(),
            expires_at=expires.isoformat(),
            context=req["context"],
            operation_id=req["operation_id"],
            ordinal=0,
            phase=phase,
            request_sha256=hashlib.sha256(data["raw_request"]).hexdigest(),
            observation_sha256=hashlib.sha256(data["observation_raw"]).hexdigest()
            if phase == "OUTCOME"
            else None,
            **{
                key: req[key]
                for key in ("parent_identity_sha256", "parent_boot_id", "parent_process_id")
            },
            claim_seq=data["claim"].seq,
            claim_row_hash=data["claim"].row_hash,
            accepted_kind=row.event.kind,
            accepted_seq=row.seq,
            accepted_row_hash=row.row_hash,
            accepted_prev_hash=row.prev_hash,
            commit_head_hash=row.row_hash,
            verified_head_hash=data["head"],
            raw_sha256=hashlib.sha256(data["raw"]).hexdigest() if phase == "OUTCOME" else None,
            raw_length=len(data["raw"]) if phase == "OUTCOME" else None,
            result_sha256=hashlib.sha256(data["result"]).hexdigest()
            if phase == "OUTCOME"
            else None,
            result_length=len(data["result"]) if phase == "OUTCOME" else None,
            status="COMMITTED",
        )

    def ack(self, operation_id, phase, issuer_id, signer):
        data = self._load(operation_id)
        purpose = data["purposes"][_TOOL_PURPOSES[2]]
        _require(issuer_id == purpose["signer_identity_id"] and callable(signer))
        now = self._clock()
        end = data["live_end"]
        if phase == "CLAIM":
            end = min(end, self._time(data["claim"].event.payload["start_deadline"]))
        body = self._ack_body(data, phase, issuer_id, now, end)
        signature = signer(b"PAEOS_PARENT_TOOL_COMMIT_ACK/v1\0" + canonical(body))
        _require(type(signature) is bytes and len(signature) == 64)
        raw = canonical(dict(body=body, signature=signature.hex()))
        self.verify_ack(
            raw, data["raw_request"], data["observation_raw"] if phase == "OUTCOME" else None
        )
        return raw

    def verify_ack(self, raw, expected_request, expected_observation):
        body = _wire(
            raw, _TOOL_ACK_FIELDS, _TOOL_PURPOSES[2], self.a.domain_tag, self.a.trust.identities
        )
        data = self._load(body["operation_id"])
        _require(type(expected_request) is bytes and expected_request == data["raw_request"])
        _require(
            expected_observation
            == (data["observation_raw"] if body["phase"] == "OUTCOME" else None)
        )
        self._common(
            body, data["g"], data["base"], data["purposes"], _TOOL_PURPOSES[2], at=self._clock()
        )
        for key in ("claim_seq", "accepted_seq"):
            _integer(body[key], 1, 2**53 - 1)
        for key in ("raw_length", "result_length"):
            if body[key] is not None:
                _integer(body[key], 0, _TOOL_RESULT_MAX)
        expected = self._ack_body(
            data,
            body["phase"],
            body["issuer_id"],
            self._time(body["issued_at"]),
            self._time(body["expires_at"]),
        )
        # A verified accepted head can have valid descendants since ACK issuance.
        anchors = [r for r in data["rows"] if r.row_hash == body["verified_head_hash"]]
        _require(len(anchors) == 1 and anchors[0].seq >= expected["accepted_seq"])
        expected["verified_head_hash"] = body["verified_head_hash"]
        _require(canonical(body) == canonical(expected))
        return self._readback(data)
