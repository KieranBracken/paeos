"""Dormant disclosure-policy contracts and pure signature verification.

This module neither loads nor provisions authority. The caller must obtain the public
key independently from trusted configuration. A returned manifest is NOT an egress
permit: policy currentness/revocation, enrollment, bundle composition, admission and
atomic attempt reservation require separate trusted enforcement. No production
transport calls this module yet. V1 supports exact artifacts, not transformations.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

if TYPE_CHECKING:
    from paeos.model_router.types import ModelCatalogEntry

_DOMAIN = b"PAEOS-DISCLOSURE-POLICY-V1\0"
_MAX_DOCUMENT_BYTES = 1024 * 1024
_MAX_INTEGER = 2**53 - 1
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")
_CANONICAL_ID = re.compile(r"[a-z][a-z0-9_-]{0,127}\Z")
_MODEL = re.compile(r"[a-z0-9][a-z0-9_./:-]{0,255}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_UTC_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_SIGNATURE = re.compile(r"[A-Za-z0-9_-]{86}\Z")
_EXCLUSIONS = frozenset(
    {"credentials", "sentium", "legacy_orca_credentials", "unrelated_private_data"}
)
_CLASSES = {"PUBLIC_ARTIFACT": "PUBLIC", "REDACTED_INTERNAL_ENGINEERING_SOURCE": "INTERNAL"}
_DYNAMIC_IDS = frozenset({"auto", "free", "latest", "default", "unknown", "any"})


class DisclosurePolicyError(ValueError):
    """Malformed, unsupported or unverifiable disclosure policy (content-free)."""


class FounderTrustRootError(DisclosurePolicyError):
    """The independently supplied public verification identity did not verify."""


def _object(value: object, fields: set[str]) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise DisclosurePolicyError("policy object fields are not exact")
    return value


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise DisclosurePolicyError("policy identifier is invalid")
    return value


def _positive(value: object) -> int:
    if type(value) is not int or not 0 < value <= _MAX_INTEGER:
        raise DisclosurePolicyError("policy bound must be a positive safe integer")
    return value


def _sequence(value: object) -> list:
    if type(value) is not list or not value:
        raise DisclosurePolicyError("policy collection must be nonempty")
    return value


def _unique(values: tuple) -> tuple:
    if len(set(values)) != len(values):
        raise DisclosurePolicyError("policy collection contains duplicates")
    return values


def _identifiers(value: object) -> tuple[str, ...]:
    return _unique(tuple(_identifier(item) for item in _sequence(value)))


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not _UTC_TIME.fullmatch(value):
        raise DisclosurePolicyError("policy timestamp must be whole-second RFC3339 UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise DisclosurePolicyError("policy timestamp is invalid") from exc


def _json_value(value: object, depth: int = 0) -> None:
    if depth > 32:
        raise DisclosurePolicyError("policy nesting exceeds bound")
    if value is None or type(value) in (str, bool):
        return
    if type(value) is int and -_MAX_INTEGER <= value <= _MAX_INTEGER:
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise DisclosurePolicyError("policy keys must be strings")
            _json_value(item, depth + 1)
        return
    if type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
        return
    raise DisclosurePolicyError("policy contains unsupported JSON values")


def canonical_policy_bytes(value: Mapping[str, object]) -> bytes:
    """Encode the v1 deterministic JSON representation, without a trailing newline."""
    if not isinstance(value, Mapping):
        raise DisclosurePolicyError("policy must be a JSON object")
    _json_value(value)
    try:
        raw = json.dumps(
            dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise DisclosurePolicyError("policy cannot be canonically encoded") from exc
    if len(raw) > _MAX_DOCUMENT_BYTES:
        raise DisclosurePolicyError("policy exceeds document size bound")
    return raw


@dataclass(frozen=True, slots=True)
class ExactRouteIdentity:
    provider_id: str
    model_id: str
    model_family: str
    entitlement_class: str
    transport_profile_id: str
    external_operator_id: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ExactRouteIdentity:
        obj = _object(
            value,
            {
                "provider_id",
                "model_id",
                "model_family",
                "entitlement_class",
                "transport_profile_id",
                "external_operator_id",
            },
        )
        provider, family, model = obj["provider_id"], obj["model_family"], obj["model_id"]
        if any(
            not isinstance(v, str) or not _CANONICAL_ID.fullmatch(v) or v in _DYNAMIC_IDS
            for v in (provider, family)
        ):
            raise DisclosurePolicyError("route provider or family is not a canonical identifier")
        if (
            not isinstance(model, str)
            or not _MODEL.fullmatch(model)
            or model in {"free", "openrouter/free"}
            or any(part in _DYNAMIC_IDS - {"free"} for part in re.split(r"[/:.-]", model))
        ):
            raise DisclosurePolicyError("route model is dynamic or malformed")
        if obj["entitlement_class"] != "FREE":
            raise DisclosurePolicyError("v1 disclosure permits only FREE entitlement")
        return cls(
            provider,
            model,
            family,
            "FREE",
            _identifier(obj["transport_profile_id"]),
            _identifier(obj["external_operator_id"]),
        )

    def matches_catalog(
        self, entry: ModelCatalogEntry, transport_profile_id: str, external_operator_id: str
    ) -> bool:
        """Compare identities only; this is NOT catalog admission or privacy validation."""
        return (
            self.provider_id,
            self.model_id,
            self.model_family,
            self.entitlement_class,
            self.transport_profile_id,
            self.external_operator_id,
        ) == (
            entry.provider_id,
            entry.model_id,
            entry.family,
            entry.cost_tier,
            transport_profile_id,
            external_operator_id,
        )


@dataclass(frozen=True, slots=True)
class ArtifactPolicy:
    relative_path: str
    sha256: str
    max_bytes: int

    @classmethod
    def from_mapping(cls, value: object) -> ArtifactPolicy:
        obj = _object(value, {"relative_path", "sha256", "max_bytes"})
        path, digest = obj["relative_path"], obj["sha256"]
        if (
            not isinstance(path, str)
            or len(path) > 4096
            or any(c in path for c in "\\*?[]<>:\x00")
            or any(ord(c) < 32 or ord(c) == 127 for c in path)
            or any(p in {"", ".", ".."} for p in path.split("/"))
        ):
            raise DisclosurePolicyError("artifact path must be exact and repository-relative")
        if not isinstance(digest, str) or not _HASH.fullmatch(digest):
            raise DisclosurePolicyError("artifact digest must be lowercase SHA256")
        return cls(path, digest, _positive(obj["max_bytes"]))


@dataclass(frozen=True, slots=True)
class ArtifactScope:
    repository_ids: tuple[str, ...]
    allowed_artifacts: tuple[ArtifactPolicy, ...]
    scope_mode: str

    @classmethod
    def from_mapping(cls, value: object) -> ArtifactScope:
        obj = _object(value, {"repository_ids", "allowed_artifacts", "scope_mode"})
        if obj["scope_mode"] != "EXACT_ARTIFACTS":
            raise DisclosurePolicyError("v1 scope must contain exact artifacts")
        artifacts = tuple(
            ArtifactPolicy.from_mapping(item) for item in _sequence(obj["allowed_artifacts"])
        )
        _unique(tuple(item.relative_path for item in artifacts))
        return cls(_identifiers(obj["repository_ids"]), artifacts, "EXACT_ARTIFACTS")


@dataclass(frozen=True, slots=True)
class DisclosureClassPolicy:
    class_id: str
    data_class: str
    purpose_ids: tuple[str, ...]
    scope: ArtifactScope
    allowed_routes: tuple[ExactRouteIdentity, ...]
    max_bundle_bytes: int
    max_artifacts: int
    required_exclusions: tuple[str, ...]
    require_builder_auditor_family_distinct: bool
    require_a08: bool
    max_attempts: int
    capability_ttl_seconds: int

    @classmethod
    def from_mapping(cls, value: object) -> DisclosureClassPolicy:
        obj = _object(
            value,
            {
                "class_id",
                "data_class",
                "purpose_ids",
                "scope",
                "allowed_routes",
                "max_bundle_bytes",
                "max_artifacts",
                "required_exclusions",
                "require_builder_auditor_family_distinct",
                "require_a08",
                "max_attempts",
                "capability_ttl_seconds",
            },
        )
        class_id = _identifier(obj["class_id"])
        if class_id not in _CLASSES or obj["data_class"] != _CLASSES[class_id]:
            raise DisclosurePolicyError("disclosure class is unsupported or mismatched")
        exclusions = _identifiers(obj["required_exclusions"])
        if set(exclusions) != _EXCLUSIONS:
            raise DisclosurePolicyError("v1 exclusions must be exact")
        if (
            obj["require_builder_auditor_family_distinct"] is not True
            or obj["require_a08"] is not True
        ):
            raise DisclosurePolicyError("v1 independence safeguards are mandatory")
        routes = _unique(
            tuple(
                ExactRouteIdentity.from_mapping(item) for item in _sequence(obj["allowed_routes"])
            )
        )
        return cls(
            class_id,
            obj["data_class"],
            _identifiers(obj["purpose_ids"]),
            ArtifactScope.from_mapping(obj["scope"]),
            routes,
            _positive(obj["max_bundle_bytes"]),
            _positive(obj["max_artifacts"]),
            exclusions,
            True,
            True,
            _positive(obj["max_attempts"]),
            _positive(obj["capability_ttl_seconds"]),
        )


@dataclass(frozen=True, slots=True)
class DisclosurePolicyManifest:
    policy_id: str
    revision: int
    status: str
    founder_key_id: str
    issued_at: datetime
    expires_at: datetime
    classes: tuple[DisclosureClassPolicy, ...]
    canonical_envelope: bytes


def policy_digest(manifest: DisclosurePolicyManifest) -> str:
    """Identity of the signed canonical envelope, not an authorization decision."""
    return hashlib.sha256(manifest.canonical_envelope).hexdigest()


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for name, value in pairs:
        if name in result:
            raise DisclosurePolicyError("policy contains a duplicate JSON key")
        result[name] = value
    return result


def verify_founder_policy(
    manifest_bytes: bytes,
    verify_key: VerifyKey,
    expected_key_id: str,
    *,
    now: datetime | None = None,
) -> DisclosurePolicyManifest:
    """Verify an active-shaped v1 envelope against independently supplied public input.

    This checks signature, syntax and the supplied clock; it cannot prove that the key
    is enrolled, the revision is current, or that a later revocation does not exist.
    Never pass worker-selected public verification material to an authority consumer.
    No file access, signing, credential loading, policy installation or network occurs.
    """
    if (
        not isinstance(verify_key, VerifyKey)
        or not isinstance(expected_key_id, str)
        or not _ID.fullmatch(expected_key_id)
    ):
        raise FounderTrustRootError("independent Founder verification material is missing")
    if type(manifest_bytes) is not bytes or not 0 < len(manifest_bytes) <= _MAX_DOCUMENT_BYTES:
        raise DisclosurePolicyError("policy must be bounded UTF8 bytes")
    try:
        raw = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise DisclosurePolicyError("policy JSON is invalid") from exc
    obj = _object(
        raw,
        {
            "schema",
            "policy_id",
            "revision",
            "status",
            "founder_authority",
            "issued_at",
            "expires_at",
            "revocation_mode",
            "classes",
        },
    )
    encoded = canonical_policy_bytes(obj)
    if (
        obj["schema"] != "paeos.disclosure-policy/1"
        or obj["status"] != "ACTIVE"
        or obj["revocation_mode"] != "IMMEDIATE"
    ):
        raise DisclosurePolicyError("policy schema, status or revocation mode is unsupported")
    authority = _object(
        obj["founder_authority"], {"key_id", "algorithm", "signature_encoding", "signature"}
    )
    if (
        authority["key_id"] != expected_key_id
        or authority["algorithm"] != "Ed25519"
        or authority["signature_encoding"] != "base64url-no-pad"
    ):
        raise FounderTrustRootError("Founder verification identity is not exact")
    signature_text = authority["signature"]
    if not isinstance(signature_text, str) or not _SIGNATURE.fullmatch(signature_text):
        raise FounderTrustRootError("Founder signature encoding is invalid")
    try:
        signature = base64.b64decode(signature_text + "==", altchars=b"-_", validate=True)
        if (
            len(signature) != 64
            or base64.urlsafe_b64encode(signature).rstrip(b"=").decode() != signature_text
        ):
            raise FounderTrustRootError("Founder signature encoding is noncanonical")
        unsigned = dict(obj)
        unsigned["founder_authority"] = {
            key: value for key, value in authority.items() if key != "signature"
        }
        verify_key.verify(_DOMAIN + canonical_policy_bytes(unsigned), signature)
    except (BadSignatureError, binascii.Error, ValueError) as exc:
        raise FounderTrustRootError("Founder policy signature did not verify") from exc
    issued_at, expires_at = _timestamp(obj["issued_at"]), _timestamp(obj["expires_at"])
    clock = datetime.now(UTC) if now is None else now
    if (
        not isinstance(clock, datetime)
        or clock.tzinfo is None
        or clock.utcoffset() is None
        or not issued_at <= clock < expires_at
    ):
        raise DisclosurePolicyError("policy is not valid at the supplied clock")
    classes = tuple(DisclosureClassPolicy.from_mapping(item) for item in _sequence(obj["classes"]))
    _unique(tuple(item.class_id for item in classes))
    return DisclosurePolicyManifest(
        _identifier(obj["policy_id"]),
        _positive(obj["revision"]),
        "ACTIVE",
        expected_key_id,
        issued_at,
        expires_at,
        classes,
        encoded,
    )
