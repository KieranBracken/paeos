"""Deterministic canonical JSON, hashing, and ``concept://`` identities."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import cast

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_NAMESPACE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,62}")
_KIND_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_TOKEN_RE = re.compile(r"[0-7][0-9A-HJKMNP-TV-Z]{25}")
_HASH_RE = re.compile(r"[0-9a-f]{64}")
_CAMEL_WORD_BOUNDARY_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
_LOWER_OR_DIGIT_BOUNDARY_RE = re.compile(r"([a-z0-9])([A-Z])")
_WORD_SEPARATOR_RE = re.compile(r"[_\s]+")


class IdentityCollisionError(Exception):
    """A truncated URI token names two distinct canonical identities."""


@dataclass(frozen=True, slots=True)
class ConceptURI:
    """Validated components of a deterministic Concept OS URI."""

    uri: str
    namespace: str
    kind: str
    token: str


def _json_bytes(value: JsonValue) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _normalize_json(value: object, *, path: str = "$") -> JsonValue:
    if value is None or isinstance(value, bool | int | str):
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    if isinstance(value, float):
        if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0):
            raise ValueError(f"noncanonical float at {path}")
        return value

    if isinstance(value, datetime | date | time):
        raise TypeError(f"datetime values at {path} must be explicit normalized UTC strings")

    if isinstance(value, list):
        return [_normalize_json(item, path=f"{path}[{index}]") for index, item in enumerate(value)]

    if isinstance(value, set | frozenset):
        normalized = [_normalize_json(item, path=f"{path}{{set}}") for item in value]
        return sorted(normalized, key=_json_bytes)

    if isinstance(value, dict):
        normalized_object: dict[str, JsonValue] = {}
        source = cast(dict[object, object], value)
        for key, item in source.items():
            if not isinstance(key, str):
                raise TypeError(f"JSON object keys at {path} must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized_object:
                raise ValueError(f"distinct object keys at {path} normalize to the same NFC key")
            normalized_object[normalized_key] = _normalize_json(
                item, path=f"{path}.{normalized_key}"
            )
        return normalized_object

    raise TypeError(f"unsupported non-JSON value {type(value).__name__} at {path}")


def canonical_json(value: JsonValue) -> bytes:
    """Return compact, key-sorted, Unicode-NFC canonical UTF-8 JSON bytes.

    Sets are accepted as an input convenience and become arrays sorted by each
    element's canonical encoding. Datetime-like values require explicit strings.
    Finite binary64 floats are accepted, except negative zero; computed scores
    remain schema-level fixed-scale decimal strings.
    """

    return _json_bytes(_normalize_json(value))


def content_hash(canonical_bytes: bytes) -> str:
    """Return the lowercase SHA-256 hexadecimal digest of canonical bytes."""

    if not isinstance(canonical_bytes, bytes):
        raise TypeError("content_hash requires bytes")
    return hashlib.sha256(canonical_bytes).hexdigest()


def _encode_crockford_128(value: int) -> str:
    """Encode an unsigned 128-bit integer as fixed-width Crockford Base32."""

    if type(value) is not int or not 0 <= value < (1 << 128):
        raise ValueError("Crockford input must be an unsigned 128-bit integer")

    characters = ["0"] * 26
    remainder_value = value
    for index in range(25, -1, -1):
        remainder_value, digit = divmod(remainder_value, 32)
        characters[index] = _CROCKFORD_ALPHABET[digit]
    return "".join(characters)


def _token_from_digest(digest: bytes) -> str:
    if not isinstance(digest, bytes) or len(digest) != 32:
        raise ValueError("token derivation requires one 32-byte SHA-256 digest")
    return _encode_crockford_128(int.from_bytes(digest[:16], byteorder="big", signed=False))


def _token_for(canonical_bytes: bytes) -> str:
    return _token_from_digest(hashlib.sha256(canonical_bytes).digest())


def _validate_namespace(namespace: str) -> None:
    if not isinstance(namespace, str) or _NAMESPACE_RE.fullmatch(namespace) is None:
        raise ValueError("namespace must match ^[a-z0-9][a-z0-9_-]{0,62}$")


def _node_kind(node_type: str) -> str:
    if not isinstance(node_type, str):
        raise ValueError("node kind source must be a string")
    kind = _CAMEL_WORD_BOUNDARY_RE.sub(r"\1-\2", node_type)
    kind = _LOWER_OR_DIGIT_BOUNDARY_RE.sub(r"\1-\2", kind)
    kind = _WORD_SEPARATOR_RE.sub("-", kind).lower()
    if _KIND_RE.fullmatch(kind) is None:
        raise ValueError("node kind must normalize to ^[a-z0-9][a-z0-9-]{0,62}$")
    return kind


def _validate_preimage_namespace(namespace: str, preimage: JsonObject) -> None:
    if not isinstance(preimage, dict):
        raise TypeError("identity preimage must be a JSON object")
    if preimage.get("namespace") != namespace:
        raise ValueError("preimage namespace must match the URI namespace")


def node_uri(namespace: str, node_type: str, preimage: JsonObject) -> str:
    """Construct a deterministic URI for a canonical node preimage."""

    _validate_namespace(namespace)
    kind = _node_kind(node_type)
    _validate_preimage_namespace(namespace, preimage)
    if "node_type" in preimage or "type" not in preimage:
        raise ValueError('node preimage must use field "type", not "node_type"')
    if preimage["type"] != node_type:
        raise ValueError("node_type argument must match the preimage type field")
    return f"concept://{namespace}/{kind}/{_token_for(canonical_json(preimage))}"


def edge_uri(namespace: str, preimage: JsonObject) -> str:
    """Construct a deterministic URI for a canonical edge preimage."""

    _validate_namespace(namespace)
    _validate_preimage_namespace(namespace, preimage)
    return f"concept://{namespace}/edge/{_token_for(canonical_json(preimage))}"


def outbox_uri(namespace: str, event_preimage: JsonObject) -> str:
    """Construct a deterministic URI for a candidate outbox event preimage."""

    _validate_namespace(namespace)
    _validate_preimage_namespace(namespace, event_preimage)
    return f"concept://{namespace}/outbox/{_token_for(canonical_json(event_preimage))}"


def validate_concept_uri(uri: str) -> ConceptURI:
    """Validate a strict ``concept://`` URI and return its typed components."""

    if not isinstance(uri, str) or not uri.startswith("concept://"):
        raise ValueError('Concept URI scheme must be exactly "concept://"')

    segments = uri[len("concept://") :].split("/")
    if len(segments) != 3:
        raise ValueError("Concept URI must contain namespace, kind, and token segments")
    namespace, kind, token = segments
    _validate_namespace(namespace)
    if _KIND_RE.fullmatch(kind) is None:
        raise ValueError("Concept URI kind must match ^[a-z0-9][a-z0-9-]{0,62}$")
    if len(token) != 26:
        raise ValueError("Concept URI token must be exactly 26-character Crockford Base32")
    if any(character.islower() for character in token):
        raise ValueError("Concept URI token must use uppercase Crockford Base32")
    if any(character in "ILOU" for character in token):
        raise ValueError("Concept URI token contains a forbidden Crockford character")
    if _TOKEN_RE.fullmatch(token) is None:
        raise ValueError("Concept URI token is not canonical 128-bit Crockford Base32")
    return ConceptURI(uri=uri, namespace=namespace, kind=kind, token=token)


def _ensure_identity_collision_free(
    *,
    uri: str,
    canonical_bytes: bytes,
    full_hash: str,
    existing_canonical_bytes: bytes,
    existing_full_hash: str,
) -> None:
    """Fail closed unless an existing URI is a byte-and-full-hash idempotent match."""

    if _HASH_RE.fullmatch(full_hash) is None or _HASH_RE.fullmatch(existing_full_hash) is None:
        raise ValueError("identity content hashes must be lowercase 64-character SHA-256 hex")
    if canonical_bytes != existing_canonical_bytes or full_hash != existing_full_hash:
        raise IdentityCollisionError(
            f"identity collision for {uri}: canonical bytes or full SHA-256 differ"
        )
